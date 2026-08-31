"""Clasificación automática de tickets (spec §15.1, FR-01, épica 4.2).

Arma el contexto del ticket (asunto, descripción, historial) redactado de PII,
lo envía al orquestador LLM con la tarea `classify`, valida la salida JSON
estructurada, la persiste como `AISuggestion` (state=draft) y audita sin PII.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.metrics import metrics
from app.models.ai_suggestion import AISuggestion
from app.prompts.classification import CLASSIFY_PROMPT_VERSION, build_classify_system, build_classify_user_prompt
from app.repositories.tickets import TicketRepository
from app.services.llm import LLMRateLimitExceeded, LLMUnavailableError
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.pii import PiiRedactor

VALID_PRIORITIES = ("low", "medium", "high", "urgent")


class ClassificationError(ValueError):
    """La salida del LLM no es un JSON de clasificación válido (fallback seguro)."""


@dataclass
class ClassificationResult:
    category: str
    suggested_priority: str
    confidence: float
    warnings: list[str] = field(default_factory=list)


class AuditPort(Protocol):
    def log(
        self,
        action: str,
        *,
        user_id: int | None = None,
        tenant_id: str | None = None,
        service: str | None = None,
        trace_id: str | None = None,
        result: str = "success",
        confidence: float | None = None,
        detail: dict[str, Any] | None = None,
    ) -> object: ...


class TicketClassifier:
    """Clasifica un ticket del tenant usando el orquestador LLM."""

    def __init__(
        self,
        db: Session,
        *,
        user_id: int | None,
        tenant_id: str | None = None,
        tenant_ids: list[str] | None = None,
        orchestrator: LLMOrchestrator | None = None,
        audit: AuditPort | None = None,
        confidence_threshold: float | None = None,
    ) -> None:
        self._db = db
        self._user_id = user_id
        self._tenant_ids = list(dict.fromkeys(tenant_ids or ([tenant_id] if tenant_id else [])))
        self._tenant_id = self._tenant_ids[0] if self._tenant_ids else None
        self._orchestrator = orchestrator or LLMOrchestrator()
        self._audit = audit
        self._redactor = PiiRedactor()
        self._repo = TicketRepository(db, tenant_ids=self._tenant_ids) if self._tenant_ids else None
        # Override de GlobalPolicy (018): None = usar settings.
        self._confidence_threshold = (
            confidence_threshold if confidence_threshold is not None else settings.ai_confidence_threshold
        )

    def classify(
        self,
        ticket_id: int,
        *,
        trace_id: str | None = None,
    ) -> tuple[ClassificationResult, AISuggestion]:
        """Clasifica el ticket y persiste la sugerencia. Fuera del alcance → PermissionError."""
        if self._repo is None:
            raise PermissionError("Tenant no definido")
        ticket = self._repo.get_or_none(ticket_id)
        if ticket is None:
            raise PermissionError("Ticket no encontrado")
        # El tenant efectivo es el del ticket (correcto con alcance de varios tenants).
        tenant_id = ticket.tenant_id
        messages = self._repo.list_messages(ticket_id)

        history = "\n".join(f"- {m.body}" for m in messages[-5:])
        subject = self._redactor.redact(ticket.subject).text
        description = self._redactor.redact(ticket.description).text
        history = self._redactor.redact(history).text

        system = build_classify_system(
            categories=settings.ai_classify_categories,
        )
        user_prompt = build_classify_user_prompt(
            subject=subject,
            description=description,
            history=history,
            locale="es",
        )

        result_payload = self._orchestrator.complete(
            task="classify",
            system=system,
            user=user_prompt,
            tenant_id=tenant_id,
            user_id=self._user_id,
            trace_id=trace_id,
        )
        parsed = self._parse_output(result_payload["content"], result_payload["model"])

        suggestion = AISuggestion(
            tenant_id=tenant_id,
            ticket_id=ticket_id,
            type="classification",
            output={
                "category": parsed.category,
                "suggested_priority": parsed.suggested_priority,
            },
            confidence=parsed.confidence,
            model=result_payload["model"],
            prompt_version=CLASSIFY_PROMPT_VERSION,
            state="draft",
        )
        self._db.add(suggestion)
        self._db.commit()
        self._db.refresh(suggestion)

        metrics.inc("ai_classifications_total", labels={"status": "ok"})
        if self._audit is not None:
            self._audit.log(
                "ai.classified",
                user_id=self._user_id,
                tenant_id=tenant_id,
                service="ai",
                trace_id=trace_id,
                result="success",
                confidence=parsed.confidence,
                detail={
                    "ticket_id": ticket_id,
                    "category": parsed.category,
                    "suggested_priority": parsed.suggested_priority,
                    "model": result_payload["model"],
                    "prompt_version": CLASSIFY_PROMPT_VERSION,
                },
            )
        return parsed, suggestion

    def _parse_output(self, content: str, model: str) -> ClassificationResult:
        """Valida y normaliza la salida JSON del LLM (fallback seguro si es inválida)."""
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise ClassificationError("Salida de clasificación inválida") from exc
        if not isinstance(data, dict):
            raise ClassificationError("Salida de clasificación inválida")

        category = str(data.get("category") or "").strip()
        priority = str(data.get("suggestedPriority") or "").strip().lower()
        if not category or priority not in VALID_PRIORITIES:
            raise ClassificationError("Campos de clasificación inválidos")

        confidence = float(data.get("confidence", 0.0))
        confidence = max(0.0, min(1.0, confidence))
        warnings = [str(w) for w in data.get("warnings", []) if isinstance(w, (str, int, float))]
        if confidence < self._confidence_threshold:
            warnings.append("revisión humana recomendada: confianza baja")

        return ClassificationResult(
            category=category,
            suggested_priority=priority,
            confidence=confidence,
            warnings=warnings,
        )