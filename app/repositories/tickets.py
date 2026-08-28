from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import InvalidCipherValue, decrypt_field, encrypt_field
from app.models.tag import Tag, TicketTag
from app.models.ticket import Ticket, TicketMessage
from app.repositories.base import TenantScopedRepository


@dataclass
class TicketView:
    """Espejo de un Ticket con campos sensibles descifrados (sin tocar el ORM)."""

    id: int
    tenant_id: str
    customer_id: int | None
    subject: str
    description: str
    category: str | None
    priority: str | None
    status: str
    assignee_id: int | None
    created_at: datetime
    updated_at: datetime


@dataclass
class TicketSummaryView:
    """Espejo resumido para listados: NO accede a `description` (columna diferida)."""

    id: int
    tenant_id: str
    customer_id: int | None
    subject: str
    category: str | None
    priority: str | None
    status: str
    assignee_id: int | None
    created_at: datetime
    updated_at: datetime


@dataclass
class MessageView:
    """Espejo de un TicketMessage con el cuerpo descifrado (sin tocar el ORM)."""

    id: int
    ticket_id: int
    author_id: int | None
    body: str
    created_at: datetime


class TicketRepository(TenantScopedRepository[Ticket]):
    """Repositorio de tickets con cifrado en reposo y filtro por tenant (ADR-001).

    Soporta alcance de un único tenant (`tenant_id`) o de varios (`tenant_ids`),
    para el caso en que el usuario no seleccionó tenant y ve tickets de todos sus
    tenants.
    """

    _SENSITIVE = ("subject", "description")

    def __init__(
        self,
        db: Session,
        tenant_id: str | None = None,
        tenant_ids: list[str] | None = None,
    ) -> None:
        self.tenant_ids = list(dict.fromkeys(tenant_ids or ([tenant_id] if tenant_id else [])))
        self.tenant_id = self.tenant_ids[0] if self.tenant_ids else ""
        super().__init__(db, Ticket, self.tenant_id)

    def _assert_tenant(self, obj: Ticket) -> None:
        if getattr(obj, self.tenant_id_attr) not in self.tenant_ids:
            raise PermissionError("Recurso de otro tenant")

    @staticmethod
    def _encrypt(value: str) -> str:
        return encrypt_field(value, settings.encryption_key)

    @staticmethod
    def _decrypt(value: str) -> str:
        try:
            return decrypt_field(value, settings.encryption_key)
        except InvalidCipherValue:
            return value

    def _summary_view(self, ticket: Ticket) -> TicketSummaryView:
        # No accede a `description` (columna diferida) para no disparar lazy load en listados.
        return TicketSummaryView(
            id=ticket.id,
            tenant_id=ticket.tenant_id,
            customer_id=ticket.customer_id,
            subject=self._decrypt(ticket.subject),
            category=ticket.category,
            priority=ticket.priority,
            status=ticket.status,
            assignee_id=ticket.assignee_id,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
        )

    def _view(self, ticket: Ticket) -> TicketView:
        return TicketView(
            id=ticket.id,
            tenant_id=ticket.tenant_id,
            customer_id=ticket.customer_id,
            subject=self._decrypt(ticket.subject),
            description=self._decrypt(ticket.description),
            category=ticket.category,
            priority=ticket.priority,
            status=ticket.status,
            assignee_id=ticket.assignee_id,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
        )

    def create(
        self,
        *,
        subject: str,
        description: str,
        category: str | None = None,
        priority: str | None = None,
        assignee_id: int | None = None,
        customer_id: int | None = None,
    ) -> TicketView:
        ticket = Ticket(
            tenant_id=self.tenant_id,
            customer_id=customer_id,
            subject=self._encrypt(subject),
            description=self._encrypt(description),
            category=category,
            priority=priority,
            status="open",
            assignee_id=assignee_id,
        )
        self.db.add(ticket)
        self.db.commit()
        self.db.refresh(ticket)
        return self._view(ticket)

    def get_or_none(self, pk) -> TicketView | None:
        ticket = super().get_or_none(pk)
        if ticket is None:
            return None
        return self._view(ticket)

    def list(
        self,
        *,
        status: str | None = None,
        category: str | None = None,
        priority: str | None = None,
        assignee_id: int | None = None,
        customer_id: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[TicketSummaryView], int]:
        filters = [Ticket.tenant_id.in_(self.tenant_ids)]
        if status:
            filters.append(Ticket.status == status)
        if category:
            filters.append(Ticket.category == category)
        if priority:
            filters.append(Ticket.priority == priority)
        if assignee_id is not None:
            filters.append(Ticket.assignee_id == assignee_id)
        if customer_id is not None:
            filters.append(Ticket.customer_id == customer_id)
        if date_from:
            filters.append(Ticket.created_at >= date_from)
        if date_to:
            filters.append(Ticket.created_at <= date_to)
        if q:
            pattern = f"%{q}%"
            has_tag = exists(
                select(TicketTag.id).join(Tag, Tag.id == TicketTag.tag_id).where(
                    TicketTag.ticket_id == Ticket.id,
                    Tag.name.ilike(pattern),
                )
            )
            filters.append(or_(Ticket.category.ilike(pattern), has_tag))

        stmt = (
            select(Ticket, func.count().over().label("_total"))
            .where(*filters)
            .order_by(Ticket.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.db.execute(stmt).all()
        if rows:
            total = rows[0]._total
        else:
            total = self.db.scalar(select(func.count()).select_from(Ticket).where(*filters)) or 0
        return [self._summary_view(t) for t, _ in rows], total

    def update(self, pk, changes: dict[str, Any]) -> TicketView | None:
        ticket = super().get_or_none(pk)
        if ticket is None:
            return None
        for field, value in changes.items():
            if field in self._SENSITIVE:
                setattr(ticket, field, self._encrypt(value))
            else:
                setattr(ticket, field, value)
        self.db.commit()
        self.db.refresh(ticket)
        return self._view(ticket)

    def _view_message(self, message: TicketMessage) -> MessageView:
        return MessageView(
            id=message.id,
            ticket_id=message.ticket_id,
            author_id=message.author_id,
            body=self._decrypt(message.body),
            created_at=message.created_at,
        )

    def add_message(self, ticket_id: int, author_id: int | None, body: str) -> MessageView:
        message = TicketMessage(
            ticket_id=ticket_id,
            author_id=author_id,
            body=self._encrypt(body),
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return self._view_message(message)

    def list_messages(self, ticket_id: int) -> list[MessageView]:
        stmt = (
            select(TicketMessage)
            .join(Ticket, TicketMessage.ticket_id == Ticket.id)
            .where(Ticket.tenant_id.in_(self.tenant_ids), TicketMessage.ticket_id == ticket_id)
            .order_by(TicketMessage.created_at.asc())
        )
        messages = list(self.db.scalars(stmt).all())
        return [self._view_message(m) for m in messages]
