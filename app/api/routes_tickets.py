import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.categories import TICKET_CATEGORIES
from app.core.deps import get_effective_tenant_ids
from app.core.permissions import EDIT_RESPONSE, READ_TICKETS, SEND_RESPONSE, require_permissions
from app.core.metrics import metrics
from app.database import get_db
from app.models.user import User
from app.models.user_tenant import UserTenant
from app.repositories.tickets import MessageView, TicketRepository, TicketSummaryView, TicketView
from app.schemas.ticket import (
    TicketCreate,
    TicketListOut,
    TicketMessageIn,
    TicketMessageOut,
    TicketOut,
    TicketUpdate,
)
from app.services.audit import AuditService, get_audit_service

router = APIRouter(prefix="/v1/tickets", tags=["tickets"])


def _get_trace_id() -> str:
    import uuid as _uuid

    return str(_uuid.uuid4())


@router.get("/categories")
def list_categories() -> list[dict[str, str]]:
    """Lista las categorías disponibles para tickets."""
    return TICKET_CATEGORIES


def _repo(db: Session, tenant_ids: list[str]) -> TicketRepository:
    return TicketRepository(db, tenant_ids=tenant_ids)


def _get_or_404(repo: TicketRepository, ticket_id: int):
    """Devuelve el ticket del tenant, o 404 si no existe o es de otro tenant."""
    try:
        ticket = repo.get_or_none(ticket_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado") from exc
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    return ticket


def _is_assignable_agent(db: Session, user_id: int, tenant_id: str) -> bool:
    """True si `user_id` es un agente activo del tenant (membresía o legacy)."""
    if user_id is None:
        return False
    target = db.get(User, user_id)
    if target is None or not target.is_active or target.role != "agent":
        return False
    if target.tenant_id == tenant_id:
        return True
    membership = db.scalar(
        select(UserTenant.id).where(
            UserTenant.user_id == user_id,
            UserTenant.tenant_id == tenant_id,
        )
    )
    return membership is not None


def _audit(
    audit: AuditService,
    user: User,
    action: str,
    model_id: int,
    trace_id: str,
    detail: dict | None = None,
) -> None:
    detail = dict(detail or {})
    detail["ticket_id"] = model_id
    audit.log(
        action,
        user_id=user.id,
        tenant_id=user.tenant_id,
        service="tickets",
        model="Ticket",
        trace_id=trace_id,
        detail=detail,
    )


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: TicketCreate,
    current_user: User = Depends(require_permissions(READ_TICKETS, EDIT_RESPONSE)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_get_trace_id),
) -> TicketView:
    repo = _repo(db, tenant_ids)
    ticket = repo.create(
        subject=payload.subject,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
    )
    metrics.inc("tickets_created_total", labels={"tenant_id": current_user.tenant_id or ""})
    _audit(audit, current_user, "ticket.created", ticket.id, trace_id)
    return ticket


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(
    ticket_id: int,
    current_user: User = Depends(require_permissions(READ_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
) -> TicketView:
    repo = _repo(db, tenant_ids)
    return _get_or_404(repo, ticket_id)


@router.get("", response_model=TicketListOut)
def list_tickets(
    current_user: User = Depends(require_permissions(READ_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(open|in_progress|on_hold|closed)$"),
    category: str | None = Query(default=None, max_length=100),
    priority: str | None = Query(default=None, pattern="^(low|medium|high|urgent)$"),
    assignee_id: int | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TicketListOut:
    repo = _repo(db, tenant_ids)
    items, total = repo.list(
        status=status_filter,
        category=category,
        priority=priority,
        assignee_id=assignee_id,
        date_from=date_from,
        date_to=date_to,
        q=q,
        limit=limit,
        offset=offset,
    )
    return TicketListOut(items=items, total=total, limit=limit, offset=offset)


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(
    ticket_id: int,
    payload: TicketUpdate,
    current_user: User = Depends(require_permissions(EDIT_RESPONSE, SEND_RESPONSE)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_get_trace_id),
) -> TicketView:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Sin cambios")

    repo = _repo(db, tenant_ids)
    ticket = _get_or_404(repo, ticket_id)

    # Reglas de asignación (feature 018):
    # - agent: solo asignarse a sí mismo o desasignar (null).
    # - otros roles: cualquier agente activo del tenant del ticket.
    audit_detail: dict = dict(changes)
    if "assignee_id" in changes:
        new_assignee = changes["assignee_id"]
        if current_user.role == "agent":
            if new_assignee not in (None, current_user.id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Solo podés asignarte a vos mismo",
                )
        elif new_assignee is not None:
            if not _is_assignable_agent(db, new_assignee, ticket.tenant_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario no encontrado",
                )
            target = db.get(User, new_assignee)
            audit_detail["assignee_name"] = target.name if target else None

    try:
        ticket = repo.update(ticket_id, changes)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado") from exc
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    _audit(audit, current_user, "ticket.updated", ticket_id, trace_id, detail=audit_detail)
    return ticket


@router.post("/{ticket_id}/messages", response_model=TicketMessageOut, status_code=status.HTTP_201_CREATED)
def add_message(
    ticket_id: int,
    payload: TicketMessageIn,
    current_user: User = Depends(require_permissions(EDIT_RESPONSE)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_get_trace_id),
) -> TicketMessageOut:
    repo = _repo(db, tenant_ids)
    ticket = _get_or_404(repo, ticket_id)
    if ticket.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pueden enviar mensajes a un ticket cerrado.",
        )
    message = repo.add_message(ticket_id, current_user.id, payload.body)
    _audit(audit, current_user, "ticket.message", ticket_id, trace_id)
    return TicketMessageOut.model_validate(message)


@router.get("/{ticket_id}/messages", response_model=list[TicketMessageOut])
def list_messages(
    ticket_id: int,
    current_user: User = Depends(require_permissions(READ_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
) -> list[TicketMessageOut]:
    repo = _repo(db, tenant_ids)
    _get_or_404(repo, ticket_id)
    messages = repo.list_messages(ticket_id)
    return [TicketMessageOut.model_validate(m) for m in messages]


@router.post("/{ticket_id}/close", response_model=TicketOut)
def close_ticket(
    ticket_id: int,
    current_user: User = Depends(require_permissions(SEND_RESPONSE)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_get_trace_id),
) -> TicketView:
    try:
        ticket = _repo(db, tenant_ids).update(ticket_id, {"status": "closed"})
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado") from exc
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    metrics.inc("tickets_closed_total", labels={"tenant_id": current_user.tenant_id or ""})
    _audit(audit, current_user, "ticket.closed", ticket_id, trace_id)
    return ticket


# === Endpoints de tags (Feature 012) ===

from app.models.tag import Tag, TicketTag
from app.schemas.tag import TagOut


@router.get("/{ticket_id}/tags", response_model=list[TagOut])
def list_ticket_tags(
    ticket_id: int,
    current_user: User = Depends(require_permissions(READ_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
) -> list[TagOut]:
    """Lista los tags de un ticket."""
    repo = _repo(db, tenant_ids)
    _get_or_404(repo, ticket_id)
    
    # Obtener tags del ticket
    ticket_tags = db.query(TicketTag).filter(TicketTag.ticket_id == ticket_id).all()
    tag_ids = [tt.tag_id for tt in ticket_tags]
    
    if not tag_ids:
        return []
    
    tags = db.query(Tag).filter(Tag.id.in_(tag_ids)).all()
    return [TagOut.model_validate(tag) for tag in tags]


@router.post("/{ticket_id}/tags", status_code=status.HTTP_201_CREATED)
def add_ticket_tag(
    ticket_id: int,
    payload: dict,
    current_user: User = Depends(require_permissions(EDIT_RESPONSE)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_get_trace_id),
) -> dict:
    """Agrega un tag a un ticket."""
    repo = _repo(db, tenant_ids)
    _get_or_404(repo, ticket_id)
    
    tag_id = payload.get("tag_id")
    if not tag_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="tag_id es requerido",
        )
    
    # Verificar que el tag existe y pertenece a uno de los tenants del usuario
    tag = db.query(Tag).filter(Tag.id == tag_id, Tag.tenant_id.in_(tenant_ids)).first()
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag no encontrado",
        )
    
    # Verificar que el tag no esté ya asociado
    existing = db.query(TicketTag).filter(
        TicketTag.ticket_id == ticket_id,
        TicketTag.tag_id == tag_id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El tag ya está asociado al ticket",
        )
    
    # Crear la asociación
    ticket_tag = TicketTag(ticket_id=ticket_id, tag_id=tag_id)
    db.add(ticket_tag)
    db.commit()
    
    _audit(audit, current_user, "ticket.tag_added", ticket_id, trace_id, detail={"tag_id": tag_id, "tag_name": tag.name})
    
    return {"ticket_id": ticket_id, "tag_id": tag_id, "tag_name": tag.name}


@router.delete("/{ticket_id}/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_ticket_tag(
    ticket_id: int,
    tag_id: int,
    current_user: User = Depends(require_permissions(EDIT_RESPONSE)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_get_trace_id),
) -> None:
    """Quita un tag de un ticket."""
    repo = _repo(db, tenant_ids)
    _get_or_404(repo, ticket_id)
    
    # Buscar la asociación
    ticket_tag = db.query(TicketTag).filter(
        TicketTag.ticket_id == ticket_id,
        TicketTag.tag_id == tag_id
    ).first()
    
    if not ticket_tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag no encontrado en el ticket",
        )
    
    # Obtener info del tag para auditoría
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    tag_name = tag.name if tag else None
    
    db.delete(ticket_tag)
    db.commit()
    
    _audit(audit, current_user, "ticket.tag_removed", ticket_id, trace_id, detail={"tag_id": tag_id, "tag_name": tag_name})
