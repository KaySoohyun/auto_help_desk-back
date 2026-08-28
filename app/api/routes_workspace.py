import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_effective_tenant_ids
from app.core.permissions import EDIT_RESPONSE, READ_TICKETS, require_permissions
from app.database import get_db
from app.models.ai_suggestion import AISuggestion
from app.models.user import User
from app.repositories.tickets import TicketRepository
from app.schemas.ai import FeedbackIn, FeedbackOut, SuggestionOut
from app.schemas.ticket import TicketListOut
from app.services.audit import AuditService, get_audit_service
from app.services.feedback import FeedbackService

router = APIRouter(prefix="/v1", tags=["workspace"])


def _trace() -> str:
    return str(uuid.uuid4())


def _repo(db: Session, tenant_ids: list[str]) -> TicketRepository:
    return TicketRepository(db, tenant_ids=tenant_ids)


def _get_ticket_or_404(repo: TicketRepository, ticket_id: int) -> None:
    """404 si el ticket no existe o es de otro tenant."""
    try:
        ticket = repo.get_or_none(ticket_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado") from exc
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")


@router.post("/ai/tickets/{ticket_id}/feedback", response_model=FeedbackOut)
def record_feedback(
    ticket_id: int,
    payload: FeedbackIn,
    current_user: User = Depends(require_permissions(EDIT_RESPONSE)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_trace),
) -> FeedbackOut:
    """Registra la decisión del agente sobre una sugerencia de IA (spec §15.4)."""
    _get_ticket_or_404(_repo(db, tenant_ids), ticket_id)
    service = FeedbackService(db, tenant_ids=tenant_ids, audit=audit)
    try:
        feedback, _suggestion = service.record(
            payload.suggestion_id,
            action=payload.action,
            reason=payload.reason,
            edited_content_hash=payload.edited_content_hash,
            user_id=current_user.id,
            trace_id=trace_id,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sugerencia no encontrada") from exc
    return FeedbackOut(
        suggestion_id=feedback.suggestion_id,
        action=feedback.action,
        reason=feedback.reason,
        edited_content_hash=feedback.edited_content_hash,
        created_at=feedback.created_at,
    )


@router.get("/ai/tickets/{ticket_id}/suggestions", response_model=list[SuggestionOut])
def list_suggestions(
    ticket_id: int,
    current_user: User = Depends(require_permissions(READ_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
) -> list[SuggestionOut]:
    """Lista las sugerencias de IA de un ticket del tenant (spec §13.2)."""
    _get_ticket_or_404(_repo(db, tenant_ids), ticket_id)
    stmt = (
        select(AISuggestion)
        .where(
            AISuggestion.tenant_id.in_(tenant_ids),
            AISuggestion.ticket_id == ticket_id,
        )
        .order_by(AISuggestion.created_at.desc())
    )
    suggestions = list(db.scalars(stmt).all())
    return [SuggestionOut.model_validate(s) for s in suggestions]


@router.get("/workspace/my-tickets", response_model=TicketListOut)
def my_tickets(
    current_user: User = Depends(require_permissions(READ_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(open|in_progress|on_hold|closed)$"),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TicketListOut:
    """Bandeja de trabajo del agente: tickets asignados a él (épica 5.2)."""
    repo = _repo(db, tenant_ids)
    items, total = repo.list(
        assignee_id=current_user.id,
        status=status_filter,
        q=q,
        limit=limit,
        offset=offset,
    )
    return TicketListOut(items=items, total=total, limit=limit, offset=offset)
