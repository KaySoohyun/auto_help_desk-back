from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Any

from app.core.config import settings
from app.core.deps import get_effective_tenant_ids, get_trace_id
from app.core.metrics import metrics
from app.core.permissions import REQUEST_AI_SUGGESTION, VIEW_AUDIT, require_permissions
from app.database import get_db
from app.models.policy import TenantPolicy
from app.models.user import User
from app.schemas.ai import ClassificationOut, SuggestedReplyOut, SuggestedReplyRequest, SummaryOut
from app.schemas.analyze import AnalyzeOut
from app.schemas.llm import LLMPingInfo
from app.services.analyze import AnalyzeService
from app.services.audit import AuditService, get_audit_service
from app.services.classifier import ClassificationError, TicketClassifier
from app.services.guardrails import Guardrails, OutputBlockedError
from app.services.llm import LLMRateLimitExceeded, LLMUnavailableError
from app.services.llm_orchestrator import LLMOrchestrator
from app.services.policy import PolicyResolver
from app.services.reply_suggester import ReplyError, TicketReplySuggester
from app.services.summarizer import SummaryError, TicketSummarizer

router = APIRouter(prefix="/v1/ai", tags=["ai"])


def _orchestrator(audit: AuditService, policy: dict[str, Any]) -> LLMOrchestrator:
    """Orquestador con los overrides efectivos de `GlobalPolicy` (018)."""
    return LLMOrchestrator(
        audit=audit,
        guardrails=Guardrails(enabled=policy["guardrails_enabled"]),
        model=policy["llm_model"],
        rate_max_calls=policy["llm_rate_max_calls"],
    )


def _trace() -> str:
    return get_trace_id()


def _ai_features_enabled(
    current_user: User = Depends(require_permissions(REQUEST_AI_SUGGESTION)),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_trace),
) -> None:
    """Kill-switch de despliegue (018): si la IA está deshabilitada, 503 auditado."""
    if settings.ai_features_enabled:
        return
    audit.log(
        "ai.disabled",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        service="ai",
        trace_id=trace_id,
        result="disabled",
    )
    metrics.inc("ai_disabled_total")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="IA deshabilitada",
    )


def _tenant_ai_enabled(
    current_user: User = Depends(require_permissions(REQUEST_AI_SUGGESTION)),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_trace),
) -> None:
    """Rollout por tenant (018): respeta `TenantPolicy.ai_enabled` (default True)."""
    policy = db.scalars(
        select(TenantPolicy).where(TenantPolicy.tenant_id == current_user.tenant_id)
    ).first()
    if policy is None or policy.ai_enabled:
        return
    audit.log(
        "ai.tenant_disabled",
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        service="ai",
        trace_id=trace_id,
        result="disabled",
    )
    metrics.inc("ai_tenant_disabled_total")
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="IA deshabilitada para este tenant",
    )


@router.post("/ping", response_model=LLMPingInfo)
def ai_ping(
    _: None = Depends(_ai_features_enabled),
    _tenant: None = Depends(_tenant_ai_enabled),
    current_user: User = Depends(require_permissions(REQUEST_AI_SUGGESTION)),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_trace),
) -> LLMPingInfo:
    """Prueba de conectividad del orquestador LLM (sin PII, sin red en dev)."""
    policy = PolicyResolver(db).effective_global()
    orchestrator = _orchestrator(audit, policy)
    try:
        result = orchestrator.complete(
            task="ping",
            system="Responde solo: pong.",
            user="ping",
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            trace_id=trace_id,
        )
    except LLMRateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM no disponible"
        ) from exc
    except OutputBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Contenido bloqueado por política de seguridad",
        ) from exc
    return LLMPingInfo(ok=True, model=result["model"], trace_id=trace_id)


@router.get("/info")
def ai_info(
    current_user: User = Depends(require_permissions(VIEW_AUDIT)),
) -> dict[str, object]:
    """Config del orquestador sin secretos (spec §14.4)."""
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_effective_model,
        "rate_max_calls": settings.llm_rate_max_calls,
        "rate_window_seconds": settings.llm_rate_window_seconds,
        "max_retries": settings.llm_max_retries,
    }


@router.post("/tickets/{ticket_id}/classify", response_model=ClassificationOut)
def classify_ticket(
    ticket_id: int,
    _: None = Depends(_ai_features_enabled),
    _tenant: None = Depends(_tenant_ai_enabled),
    current_user: User = Depends(require_permissions(REQUEST_AI_SUGGESTION)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_trace),
) -> ClassificationOut:
    """Clasifica un ticket con IA (spec §15.1). El contexto va redactado de PII."""
    policy = PolicyResolver(db).effective_global()
    classifier = TicketClassifier(
        db,
        user_id=current_user.id,
        tenant_ids=tenant_ids,
        orchestrator=_orchestrator(audit, policy),
        audit=audit,
        confidence_threshold=policy["ai_confidence_threshold"],
    )
    try:
        result, suggestion = classifier.classify(ticket_id, trace_id=trace_id)
    except LLMRateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM no disponible"
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado") from exc
    except ClassificationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except OutputBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Contenido bloqueado por política de seguridad",
        ) from exc
    return ClassificationOut(
        category=result.category,
        suggested_priority=result.suggested_priority,
        confidence=result.confidence,
        warnings=result.warnings,
        suggestion_id=suggestion.id,
        trace_id=trace_id,
    )


@router.post("/tickets/{ticket_id}/summary", response_model=SummaryOut)
def summarize_ticket(
    ticket_id: int,
    _: None = Depends(_ai_features_enabled),
    _tenant: None = Depends(_tenant_ai_enabled),
    current_user: User = Depends(require_permissions(REQUEST_AI_SUGGESTION)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_trace),
) -> SummaryOut:
    """Resume un ticket con IA (spec §15.2). El contexto va redactado de PII."""
    policy = PolicyResolver(db).effective_global()
    summarizer = TicketSummarizer(
        db,
        user_id=current_user.id,
        tenant_ids=tenant_ids,
        orchestrator=_orchestrator(audit, policy),
        audit=audit,
        confidence_threshold=policy["ai_confidence_threshold"],
    )
    try:
        result, suggestion = summarizer.summarize(ticket_id, trace_id=trace_id)
    except LLMRateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM no disponible"
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado") from exc
    except SummaryError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except OutputBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Contenido bloqueado por política de seguridad",
        ) from exc
    return SummaryOut(
        summary=result.summary,
        missing_information=result.missing_information,
        confidence=result.confidence,
        warnings=result.warnings,
        suggestion_id=suggestion.id,
        trace_id=trace_id,
    )


@router.post("/tickets/{ticket_id}/suggested-reply", response_model=SuggestedReplyOut)
def suggest_reply(
    ticket_id: int,
    _: None = Depends(_ai_features_enabled),
    _tenant: None = Depends(_tenant_ai_enabled),
    body: SuggestedReplyRequest | None = None,
    current_user: User = Depends(require_permissions(REQUEST_AI_SUGGESTION)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_trace),
) -> SuggestedReplyOut:
    """Sugiere una respuesta editable para un ticket con IA (spec §15.3). El contexto va redactado de PII."""
    policy = PolicyResolver(db).effective_global()
    suggester = TicketReplySuggester(
        db,
        user_id=current_user.id,
        tenant_ids=tenant_ids,
        orchestrator=_orchestrator(audit, policy),
        audit=audit,
        confidence_threshold=policy["ai_confidence_threshold"],
    )
    try:
        result, suggestion = suggester.suggest_reply(
            ticket_id,
            tone=body.tone if body else None,
            language=body.language if body else None,
            trace_id=trace_id,
        )
    except LLMRateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM no disponible"
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado") from exc
    except ReplyError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except OutputBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Contenido bloqueado por política de seguridad",
        ) from exc
    return SuggestedReplyOut(
        suggested_reply=result.suggested_reply,
        confidence=result.confidence,
        sources=result.sources,
        policy_flags=result.policy_flags,
        warnings=result.warnings,
        suggestion_id=suggestion.id,
        trace_id=trace_id,
    )


@router.post("/tickets/{ticket_id}/analyze", response_model=AnalyzeOut)
def analyze_ticket(
    ticket_id: int,
    _: None = Depends(_ai_features_enabled),
    _tenant: None = Depends(_tenant_ai_enabled),
    current_user: User = Depends(require_permissions(REQUEST_AI_SUGGESTION)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_trace),
) -> AnalyzeOut:
    """Analiza un ticket con IA: ejecuta classify, summary y suggested-reply en paralelo, más PII y KB recommendations."""
    policy = PolicyResolver(db).effective_global()
    analyzer = AnalyzeService(
        db,
        user_id=current_user.id,
        tenant_ids=tenant_ids,
        orchestrator=_orchestrator(audit, policy),
        audit=audit,
        policy=policy,
    )
    try:
        result = analyzer.analyze(ticket_id, trace_id=trace_id)
    except LLMRateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(exc)) from exc
    except LLMUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM no disponible"
        ) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado") from exc
    except OutputBlockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Contenido bloqueado por política de seguridad",
        ) from exc
    
    return AnalyzeOut(
        classification=result.classification,
        summary=result.summary,
        suggested_reply=result.suggested_reply,
        kb_recommendations=result.kb_recommendations,
        pii_detected=result.pii_detected,
        risks=result.risks,
    )