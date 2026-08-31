"""Feedback del agente sobre sugerencias IA (spec §15.4, CU-04, FR-09).

Registra la decisión del agente (accepted | edited | rejected | flagged) sobre
una `AISuggestion`, actualiza su estado y queda auditado y con métrica. Solo
maneja datos de la sugerencia ya persistida (sin PII por diseño de 011-013).
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.metrics import metrics
from app.models.ai_suggestion import AISuggestion
from app.models.feedback import Feedback

STATE_BY_ACTION = {
    "accepted": "accepted",
    "edited": "edited",
    "rejected": "rejected",
    "flagged": "flagged",
}


class AuditPort(Protocol):
    def log(
        self,
        action: str,
        *,
        user_id: int | None = None,
        tenant_id: str | None = None,
        service: str | None = None,
        model: str | None = None,
        model_version: str | None = None,
        prompt_version: str | None = None,
        trace_id: str | None = None,
        result: str = "success",
        confidence: float | None = None,
        detail: dict[str, Any] | None = None,
    ) -> object: ...


class FeedbackService:
    """Registra feedback del agente y actualiza el estado de la sugerencia."""

    def __init__(
        self,
        db: Session,
        *,
        tenant_id: str | None = None,
        tenant_ids: list[str] | None = None,
        audit: AuditPort | None = None,
    ) -> None:
        self._db = db
        self._tenant_ids = list(dict.fromkeys(tenant_ids or ([tenant_id] if tenant_id else [])))
        self._tenant_id = self._tenant_ids[0] if self._tenant_ids else None
        self._audit = audit

    def record(
        self,
        suggestion_id: int,
        *,
        action: str,
        reason: str | None = None,
        edited_content_hash: str | None = None,
        edited_output: dict | None = None,
        user_id: int | None = None,
        trace_id: str | None = None,
    ) -> tuple[Feedback, AISuggestion]:
        """Registra el feedback y actualiza el estado de la sugerencia.

        Si viene `edited_output` (contenido editado por el agente, p. ej. resumen
        corregido), se persiste sobre el `output` de la sugerencia para que quede
        disponible al re-entrar al ticket. Sin PII cruda (016).

        Sugerencia fuera del alcance del usuario o inexistente → `PermissionError`.
        """
        if not self._tenant_ids:
            raise PermissionError("Tenant no definido")

        suggestion = self._db.scalar(
            select(AISuggestion).where(
                AISuggestion.id == suggestion_id,
                AISuggestion.tenant_id.in_(self._tenant_ids),
            )
        )
        if suggestion is None:
            raise PermissionError("Sugerencia no encontrada")

        tenant_id = suggestion.tenant_id
        feedback = self._db.scalar(
            select(Feedback).where(Feedback.suggestion_id == suggestion_id)
        )
        if feedback is None:
            feedback = Feedback(
                suggestion_id=suggestion_id,
                tenant_id=tenant_id,
                action=action,
                reason=reason,
                edited_content_hash=edited_content_hash,
            )
            self._db.add(feedback)
        else:
            feedback.action = action
            feedback.reason = reason
            feedback.edited_content_hash = edited_content_hash

        suggestion.state = STATE_BY_ACTION[action]
        if edited_output is not None:
            suggestion.output = edited_output
        self._db.commit()
        self._db.refresh(feedback)
        self._db.refresh(suggestion)

        metrics.inc("ai_feedback_total", labels={"action": action})
        if self._audit is not None:
            self._audit.log(
                "ai.feedback",
                user_id=user_id,
                tenant_id=tenant_id,
                service="ai",
                model="AISuggestion",
                trace_id=trace_id,
                result="success",
                detail={
                    "ticket_id": suggestion.ticket_id,
                    "suggestion_id": suggestion.id,
                    "action": action,
                },
            )
        return feedback, suggestion
