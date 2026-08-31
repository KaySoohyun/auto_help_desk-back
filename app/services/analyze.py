"""Servicio de análisis unificado de tickets (Feature 012).

Ejecuta classify, summary y suggested-reply en paralelo usando asyncio.gather,
además de detectar PII y buscar artículos KB recomendados por categoría.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.kb import KbArticle
from app.schemas.analyze import KbRecommendation, PiiDetection
from app.services.classifier import ClassificationError, ClassificationResult, TicketClassifier
from app.services.llm import LLMRateLimitExceeded, LLMUnavailableError
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.pii import PiiRedactor
from app.services.reply_suggester import ReplyError, ReplyResult, TicketReplySuggester
from app.services.summarizer import SummaryError, SummaryResult, TicketSummarizer
from app.services.audit import AuditService
from app.services.guardrails import Guardrails, OutputBlockedError
from app.services.policy import PolicyResolver
from app.repositories.tickets import TicketRepository


@dataclass
class AnalyzeResult:
    classification: dict
    summary: dict
    suggested_reply: dict
    kb_recommendations: list[KbRecommendation] = field(default_factory=list)
    pii_detected: list[PiiDetection] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


class AnalyzeService:
    """Servicio de análisis unificado que ejecuta classify, summary y suggested-reply en paralelo."""

    def __init__(
        self,
        db: Session,
        *,
        user_id: int | None,
        tenant_id: str | None = None,
        tenant_ids: list[str] | None = None,
        orchestrator: LLMOrchestrator | None = None,
        audit: AuditService | None = None,
        policy: dict[str, Any] | None = None,
    ) -> None:
        self._db = db
        self._user_id = user_id
        self._tenant_ids = list(dict.fromkeys(tenant_ids or ([tenant_id] if tenant_id else [])))
        self._tenant_id = self._tenant_ids[0] if self._tenant_ids else None
        self._policy = policy or {}
        self._orchestrator = orchestrator
        self._audit = audit
        self._redactor = PiiRedactor()
        self._repo = TicketRepository(db, tenant_ids=self._tenant_ids) if self._tenant_ids else None

    def _get_orchestrator(self) -> LLMOrchestrator:
        if self._orchestrator:
            return self._orchestrator
        return LLMOrchestrator(
            audit=self._audit,
            guardrails=Guardrails(enabled=self._policy.get("guardrails_enabled", True)),
            model=self._policy.get("llm_model"),
            rate_max_calls=self._policy.get("llm_rate_max_calls"),
        )

    def _detect_pii(self, ticket: Any) -> list[PiiDetection]:
        """Detecta PII en el contenido del ticket."""
        messages = self._repo.list_messages(ticket.id)

        # Combinar todo el contenido
        content_parts = [ticket.subject, ticket.description]
        content_parts.extend(m.body for m in messages)
        full_content = "\n".join(content_parts)
        
        # Detectar PII usando el redactor en modo detect
        redactor = PiiRedactor()
        result = redactor.redact(full_content, mode="detect")
        
        # Si no hay PII, retornar vacío
        if result.report.total == 0:
            return []
        
        # Buscar las posiciones de cada tipo de PII
        detections = []
        import re
        
        patterns = {
            "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
            "phone": r"(?:\+\d[\d\s().-]{6,16}|\b\d{2,4}(?:[\s.-]\d{2,4}){2}\b|\b\d{9}\b)",
            "card": r"\b(?:\d[ -]?){12,18}\d\b",
            "id_number": r"\b[XYZ]?\d{7,8}[A-Z]\b",
            "passport": r"\b[A-Z]{2}\d{6,7}\b",
            "birth_date": r"\b\d{1,2}/\d{1,2}/(?:19|20)\d{2}\b",
            "ip_address": r"(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\b",
            "internal_url": r"(?:https?://)?(?:[A-Za-z0-9-]+\.)*(?:localhost|\.local|\.internal)(?:[:/][^\s]*)?",
        }
        
        for pii_type in result.report.types.keys():
            if pii_type in patterns:
                pattern = re.compile(patterns[pii_type], re.IGNORECASE)
                for match in pattern.finditer(full_content):
                    detections.append(PiiDetection(
                        type=pii_type,
                        value=match.group(),
                        position=match.start()
                    ))
        
        return detections

    def _get_kb_recommendations(self, ticket: Any, limit: int = 5) -> list[KbRecommendation]:
        """Busca artículos KB publicados recomendados por categoría del ticket."""
        if not ticket.category:
            return []

        # Buscar artículos publicados de la misma categoría
        stmt = (
            select(KbArticle)
            .where(
                KbArticle.tenant_id == ticket.tenant_id,
                KbArticle.category == ticket.category,
                KbArticle.status == "published"
            )
            .order_by(KbArticle.updated_at.desc())
            .limit(limit)
        )
        articles = list(self._db.scalars(stmt).all())
        
        # Calcular score basado en qué tan reciente es
        recommendations = []
        for i, article in enumerate(articles):
            score = 1.0 - (i * 0.1)  # Score decreciente
            recommendations.append(KbRecommendation(
                article_id=article.id,
                title=article.title,
                score=round(score, 2)
            ))
        
        return recommendations

    def analyze(self, ticket_id: int, *, trace_id: str | None = None) -> AnalyzeResult:
        """Ejecuta classify, summary y suggested-reply, más PII y KB recommendations.
        
        Nota: Las tareas se ejecutan en secuencia para evitar problemas de concurrencia
        con la base de datos y el servicio de auditoría.
        """
        if self._repo is None:
            raise PermissionError("Tenant no definido")

        ticket = self._repo.get_or_none(ticket_id)
        if ticket is None:
            raise PermissionError("Ticket no encontrado")
        # El tenant efectivo es el del ticket (correcto con alcance de varios tenants).
        tenant_id = ticket.tenant_id
        
        orchestrator = self._get_orchestrator()
        confidence_threshold = self._policy.get("ai_confidence_threshold")
        
        # Ejecutar las 3 tareas en secuencia
        classification_result = None
        classification_suggestion = None
        classification_error = None
        
        summary_result = None
        summary_suggestion = None
        summary_error = None
        
        reply_result = None
        reply_suggestion = None
        reply_error = None
        
        # Clasificar
        try:
            classifier = TicketClassifier(
                self._db,
                user_id=self._user_id,
                tenant_id=tenant_id,
                orchestrator=orchestrator,
                audit=self._audit,
                confidence_threshold=confidence_threshold,
            )
            classification_result, classification_suggestion = classifier.classify(ticket_id, trace_id=trace_id)
        except Exception as e:
            classification_error = str(e)
        
        # Resumir
        try:
            summarizer = TicketSummarizer(
                self._db,
                user_id=self._user_id,
                tenant_id=tenant_id,
                orchestrator=orchestrator,
                audit=self._audit,
                confidence_threshold=confidence_threshold,
            )
            summary_result, summary_suggestion = summarizer.summarize(ticket_id, trace_id=trace_id)
        except Exception as e:
            summary_error = str(e)
        
        # Sugerir respuesta
        try:
            suggester = TicketReplySuggester(
                self._db,
                user_id=self._user_id,
                tenant_id=tenant_id,
                orchestrator=orchestrator,
                audit=self._audit,
                confidence_threshold=confidence_threshold,
            )
            reply_result, reply_suggestion = suggester.suggest_reply(ticket_id, trace_id=trace_id)
        except Exception as e:
            reply_error = str(e)
        
        # Construir resultados
        classification_dict = {}
        if classification_result:
            classification_dict = {
                "category": classification_result.category,
                "suggested_priority": classification_result.suggested_priority,
                "confidence": classification_result.confidence,
                "warnings": classification_result.warnings,
                "suggestion_id": classification_suggestion.id if classification_suggestion else None,
                "trace_id": trace_id,
            }
        elif classification_error:
            classification_dict = {"error": classification_error}
        
        summary_dict = {}
        if summary_result:
            summary_dict = {
                "summary": summary_result.summary,
                "missing_information": summary_result.missing_information,
                "confidence": summary_result.confidence,
                "warnings": summary_result.warnings,
                "suggestion_id": summary_suggestion.id if summary_suggestion else None,
                "trace_id": trace_id,
            }
        elif summary_error:
            summary_dict = {"error": summary_error}
        
        reply_dict = {}
        if reply_result:
            reply_dict = {
                "suggested_reply": reply_result.suggested_reply,
                "confidence": reply_result.confidence,
                "sources": reply_result.sources,
                "policy_flags": reply_result.policy_flags,
                "warnings": reply_result.warnings,
                "suggestion_id": reply_suggestion.id if reply_suggestion else None,
                "trace_id": trace_id,
            }
        elif reply_error:
            reply_dict = {"error": reply_error}
        
        # Detectar PII
        pii_detected = self._detect_pii(ticket)
        
        # Obtener recomendaciones KB
        kb_recommendations = self._get_kb_recommendations(ticket)
        
        # Construir riesgos
        risks = []
        if pii_detected:
            risks.append(f"PII detectada: {len(pii_detected)} elementos")
        if classification_dict.get("confidence", 1.0) < 0.7:
            risks.append("Confianza baja en clasificación")
        if summary_dict.get("confidence", 1.0) < 0.7:
            risks.append("Confianza baja en resumen")
        if reply_dict.get("confidence", 1.0) < 0.7:
            risks.append("Confianza baja en respuesta sugerida")
        
        return AnalyzeResult(
            classification=classification_dict,
            summary=summary_dict,
            suggested_reply=reply_dict,
            kb_recommendations=kb_recommendations,
            pii_detected=pii_detected,
            risks=risks,
        )
