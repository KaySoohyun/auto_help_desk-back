import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_effective_tenant_ids
from app.core.permissions import EDIT_RESPONSE, READ_TICKETS, require_permissions
from app.database import get_db
from app.models.tag import Tag
from app.models.user import User
from app.schemas.tag import TagCreate, TagOut
from app.services.audit import AuditService, get_audit_service

router = APIRouter(prefix="/v1/tags", tags=["tags"])


def _get_trace_id() -> str:
    return str(uuid.uuid4())


@router.get("", response_model=list[TagOut])
def list_tags(
    search: str | None = Query(default=None, max_length=50),
    current_user: User = Depends(require_permissions(READ_TICKETS)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
) -> list[TagOut]:
    """Lista/busca tags del tenant por subcadena (§ error 7)."""
    query = db.query(Tag).filter(Tag.tenant_id.in_(tenant_ids))
    if search:
        pattern = f"%{search}%"
        query = query.filter(Tag.name.ilike(pattern))
    tags = query.order_by(Tag.name.asc()).limit(20).all()
    return [TagOut.model_validate(tag) for tag in tags]


@router.post("", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(
    payload: TagCreate,
    current_user: User = Depends(require_permissions(EDIT_RESPONSE)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    trace_id: str = Depends(_get_trace_id),
) -> TagOut:
    """Crea una tag para el tenant actual (§ error 7)."""
    name = payload.name.strip()
    if not name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El nombre de la tag es requerido",
        )

    # El usuario tiene un tenant efectivo único (membresía por tenant)
    tenant_id = tenant_ids[0] if tenant_ids else current_user.tenant_id
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario sin tenant",
        )

    # Evitar duplicados por tenant
    existing = (
        db.query(Tag)
        .filter(Tag.tenant_id == tenant_id, Tag.name.ilike(name))
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una tag con ese nombre",
        )

    tag = Tag(tenant_id=tenant_id, name=name)
    db.add(tag)
    db.commit()
    db.refresh(tag)

    audit.log(
        "tag.created",
        user_id=current_user.id,
        tenant_id=tenant_id,
        service="tags",
        model="Tag",
        trace_id=trace_id,
        detail={"tag_id": tag.id, "tag_name": tag.name},
    )

    return TagOut.model_validate(tag)
