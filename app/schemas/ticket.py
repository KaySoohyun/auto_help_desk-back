from datetime import datetime

from pydantic import BaseModel, Field


class AgentRefOut(BaseModel):
    """Usuario asignado a un ticket (nombre + email para display)."""

    id: int
    name: str | None
    email: str
    role: str

    model_config = {"from_attributes": True}


class TicketCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1)
    category: str | None = Field(default=None, max_length=100)
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")


class TicketUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|in_progress|on_hold|closed)$")
    priority: str | None = Field(default=None, pattern="^(low|medium|high|urgent)$")
    category: str | None = Field(default=None, max_length=100)
    assignee_id: int | None = None


class TicketMessageIn(BaseModel):
    body: str = Field(min_length=1)


class TicketMessageOut(BaseModel):
    id: int
    ticket_id: int
    author_id: int | None
    body: str
    created_at: datetime
    author_name: str | None = None

    model_config = {"from_attributes": True}


class TicketOut(BaseModel):
    id: int
    tenant_id: str
    customer_id: int | None = None
    subject: str
    description: str
    category: str | None
    priority: str | None
    status: str
    assignee_id: int | None
    assignee: AgentRefOut | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketSummaryOut(BaseModel):
    id: int
    tenant_id: str
    customer_id: int | None = None
    subject: str
    category: str | None
    priority: str | None
    status: str
    assignee_id: int | None
    assignee: AgentRefOut | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TicketListOut(BaseModel):
    items: list[TicketSummaryOut]
    total: int
    limit: int
    offset: int