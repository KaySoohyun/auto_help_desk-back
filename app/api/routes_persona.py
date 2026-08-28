import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_effective_tenant_ids
from app.core.permissions import PERSONA_TICKETS, require_permissions
from app.database import get_db
from app.models.customer import Customer
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.tickets import TicketRepository, TicketView
from app.schemas.persona import PersonaProfile
from app.schemas.ticket import (
    TicketCreate,
    TicketListOut,
    TicketMessageIn,
    TicketMessageOut,
    TicketOut,
)
from app.services.audit import AuditService, get_audit_service

router = APIRouter(prefix="/v1/me", tags=["persona"])


def _get_my_customer(db: Session, user: User) -> Customer:
    customer = db.query(Customer).filter(Customer.user_id == user.id).first()
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Perfil de cliente no encontrado",
        )
    return customer


@router.get("", response_model=PersonaProfile)
def get_my_profile(
    current_user: User = Depends(require_permissions(PERSONA_TICKETS)),
    db: Session = Depends(get_db),
) -> PersonaProfile:
    """Perfil del cliente (persona) para el portal: nombre, empresa y tenant."""
    customer = _get_my_customer(db, current_user)
    tenant = db.get(Tenant, customer.tenant_id)
    return PersonaProfile(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        company=customer.company,
        tenant_id=customer.tenant_id,
        tenant_name=tenant.name if tenant else customer.tenant_id,
    )


def _repo(db: Session, tenant_ids: list[str]) -> TicketRepository:
    return TicketRepository(db, tenant_ids=tenant_ids)


def _get_my_ticket_or_404(repo: TicketRepository, customer: Customer, ticket_id: int) -> TicketView:
    try:
        ticket = repo.get_or_none(ticket_id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado") from exc
    if ticket is None or ticket.customer_id != customer.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
    return ticket


def _audit(
    audit: AuditService,
    user: User,
    tenant_id: str | None,
    action: str,
    ticket_id: int,
    detail: dict | None = None,
) -> None:
    detail = dict(detail or {})
    detail["ticket_id"] = ticket_id
    audit.log(
        action,
        user_id=user.id,
        tenant_id=tenant_id,
        service="persona",
        model="Ticket",
        trace_id=str(uuid.uuid4()),
        detail=detail,
    )


@router.get("/tickets", response_model=TicketListOut)
def list_my_tickets(
    current_user: User = Depends(require_permissions(PERSONA_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    status_filter: str | None = Query(default=None, alias="status", pattern="^(open|in_progress|on_hold|closed)$"),
    category: str | None = Query(default=None, max_length=100),
    priority: str | None = Query(default=None, pattern="^(low|medium|high|urgent)$"),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TicketListOut:
    """Lista los tickets del cliente (solo los suyos, aislado por customer y tenant)."""
    customer = _get_my_customer(db, current_user)
    items, total = _repo(db, tenant_ids).list(
        customer_id=customer.id,
        status=status_filter,
        category=category,
        priority=priority,
        q=q,
        limit=limit,
        offset=offset,
    )
    return TicketListOut(items=items, total=total, limit=limit, offset=offset)


@router.post("/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_my_ticket(
    payload: TicketCreate,
    current_user: User = Depends(require_permissions(PERSONA_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
) -> TicketView:
    """Crea un ticket como cliente (se asocia al customer del usuario)."""
    customer = _get_my_customer(db, current_user)
    ticket = _repo(db, tenant_ids).create(
        subject=payload.subject,
        description=payload.description,
        category=payload.category,
        priority=payload.priority,
        customer_id=customer.id,
    )
    _audit(audit, current_user, tenant_ids[0] if tenant_ids else None, "persona.ticket_created", ticket.id)
    return ticket


@router.get("/tickets/{ticket_id}", response_model=TicketOut)
def get_my_ticket(
    ticket_id: int,
    current_user: User = Depends(require_permissions(PERSONA_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
) -> TicketView:
    """Detalle de un ticket del cliente (aislado por customer)."""
    customer = _get_my_customer(db, current_user)
    return _get_my_ticket_or_404(_repo(db, tenant_ids), customer, ticket_id)


@router.get("/tickets/{ticket_id}/messages", response_model=list[TicketMessageOut])
def list_my_messages(
    ticket_id: int,
    current_user: User = Depends(require_permissions(PERSONA_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
) -> list[TicketMessageOut]:
    """Lista los mensajes de un ticket propio del cliente."""
    customer = _get_my_customer(db, current_user)
    repo = _repo(db, tenant_ids)
    _get_my_ticket_or_404(repo, customer, ticket_id)
    return [TicketMessageOut.model_validate(m) for m in repo.list_messages(ticket_id)]


@router.post("/tickets/{ticket_id}/messages", response_model=TicketMessageOut, status_code=status.HTTP_201_CREATED)
def send_my_message(
    ticket_id: int,
    payload: TicketMessageIn,
    current_user: User = Depends(require_permissions(PERSONA_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
) -> TicketMessageOut:
    """Envía un mensaje del cliente en su ticket (sin LLM)."""
    customer = _get_my_customer(db, current_user)
    repo = _repo(db, tenant_ids)
    ticket = _get_my_ticket_or_404(repo, customer, ticket_id)
    if ticket.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pueden enviar mensajes a un ticket cerrado.",
        )
    message = repo.add_message(ticket_id, current_user.id, payload.body)
    _audit(audit, current_user, tenant_ids[0] if tenant_ids else None, "persona.ticket_message", ticket_id)
    return TicketMessageOut.model_validate(message)
