"""Agentes asignables del tenant (feature 018).

`GET /v1/agents` lista los agentes activos de los tenants efectivos del usuario
autenticado, para alimentar el selector de asignación del detalle de ticket.
La regla real de asignación se valida en `PATCH /v1/tickets/{id}`.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_effective_tenant_ids
from app.core.permissions import READ_TICKETS, require_permissions
from app.database import get_db
from app.models.user import User
from app.models.user_tenant import UserTenant
from app.schemas.agents import AgentOut

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
def list_agents(
    current_user: User = Depends(require_permissions(READ_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
) -> list[AgentOut]:
    """Lista agentes activos de los tenants efectivos del usuario."""
    if not tenant_ids:
        return []

    membership_ids = select(UserTenant.user_id).where(UserTenant.tenant_id.in_(tenant_ids))
    stmt = (
        select(User)
        .where(
            User.is_active.is_(True),
            User.role == "agent",
            or_(
                User.id.in_(membership_ids),
                User.tenant_id.in_(tenant_ids),
            ),
        )
        .order_by(User.name.asc().nullslast(), User.email.asc())
        .distinct()
    )
    agents = list(db.scalars(stmt).all())
    return [AgentOut.model_validate(a) for a in agents]