"""Schemas para agentes asignables (feature 018)."""

from pydantic import BaseModel, EmailStr


class AgentOut(BaseModel):
    """Agente activo de un tenant, para el selector de asignación.

    Incluye `is_active` para que el frontend tenga el dato completo
    (id, nombre/email, rol y estado) y no ofrezca agentes inactivos.
    """

    id: int
    name: str | None
    email: EmailStr
    role: str
    is_active: bool = True

    model_config = {"from_attributes": True}