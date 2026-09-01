from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import get_effective_tenant_ids, get_effective_tenant_ids_optional
from app.core.permissions import CONFIGURE_TENANT, MANAGE_AI_POLICIES, require_permissions
from app.database import get_db
from app.models.customer import Customer
from app.models.policy import TenantPolicy
from app.models.user import User, UserRole
from app.repositories.user_tenant import UserTenantRepository
from app.schemas.admin import (
    CustomerAdminOut,
    CustomerListOut,
    GlobalPolicyIn,
    GlobalPolicyOut,
    TenantPolicyIn,
    TenantPolicyOut,
    UserCreate,
    UserListOut,
    UserUpdate,
)
from app.schemas.auth import UserOut
from app.services.admin import AdminService, effective_global_policy
from app.services.audit import AuditService, get_audit_service
from app.services.pii import mask_email

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin_service(db: Session, current_user: User, audit: AuditService, tenant_ids: list[str]) -> AdminService:
    return AdminService(db, current_user=current_user, audit=audit, tenant_ids=tenant_ids)


@router.get("/users", response_model=UserListOut)
def list_tenant_users(
    current_user: User = Depends(require_permissions(CONFIGURE_TENANT)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    q: str | None = Query(default=None, max_length=255),
    role: UserRole | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> UserListOut:
    filters = [User.tenant_id.in_(tenant_ids), User.role != "customer"]
    if q:
        pattern = f"%{q}%"
        filters.append(or_(User.name.ilike(pattern), User.email.ilike(pattern)))
    if role:
        filters.append(User.role == role)
    total = db.scalar(select(func.count()).select_from(User).where(*filters)) or 0
    stmt = select(User).where(*filters).order_by(User.id).limit(limit).offset(offset)
    items = list(db.scalars(stmt).all())
    return UserListOut(items=items, total=total, limit=limit, offset=offset)


@router.get("/customers", response_model=CustomerListOut)
def list_admin_customers(
    current_user: User = Depends(require_permissions(CONFIGURE_TENANT)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids),
    db: Session = Depends(get_db),
    tenant_id: str | None = Query(default=None, max_length=64),
    q: str | None = Query(default=None, max_length=255),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> CustomerListOut:
    """Lista los clientes del/los tenant(s) con PII enmascarada (sin emails crudos).

    `tenant_id` opcional filtra a un tenant puntual; se valida que el usuario
    pertenezca a ese tenant (membresía `user_tenants` o `users.tenant_id` legacy).
    """
    scope = tenant_ids
    if tenant_id:
        repo = UserTenantRepository(db)
        is_member = repo.user_has_tenant(current_user.id, tenant_id) or current_user.tenant_id == tenant_id
        if not is_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permiso insuficiente",
            )
        scope = [tenant_id]
    filters = [Customer.tenant_id.in_(scope)]
    if q:
        pattern = f"%{q}%"
        filters.append(or_(Customer.name.ilike(pattern), Customer.company.ilike(pattern)))
    total = db.scalar(select(func.count()).select_from(Customer).where(*filters)) or 0
    customers = (
        db.query(Customer)
        .filter(*filters)
        .order_by(Customer.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    items = [
        CustomerAdminOut(
            id=c.id,
            tenant_id=c.tenant_id,
            name=c.name,
            email_masked=mask_email(c.email),
            company=c.company,
            plan=c.plan,
            created_at=c.created_at,
        )
        for c in customers
    ]
    return CustomerListOut(items=items, total=total, limit=limit, offset=offset)


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    current_user: User = Depends(require_permissions(CONFIGURE_TENANT)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids_optional),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
) -> User:
    service = _admin_service(db, current_user, audit, tenant_ids)
    return service.create_user(
        email=payload.email,
        name=payload.name,
        password=payload.password,
        role=payload.role,
        tenant_id=payload.tenant_id,
    )


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: User = Depends(require_permissions(CONFIGURE_TENANT)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids_optional),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
) -> User:
    service = _admin_service(db, current_user, audit, tenant_ids)
    return service.update_user(
        user_id, role=payload.role, is_active=payload.is_active, name=payload.name
    )


@router.get("/ai-policy", response_model=TenantPolicyOut)
def get_tenant_policy(
    current_user: User = Depends(require_permissions(CONFIGURE_TENANT)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids_optional),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
) -> TenantPolicy:
    service = _admin_service(db, current_user, audit, tenant_ids)
    return service.get_tenant_policy()


@router.put("/ai-policy", response_model=TenantPolicyOut)
def save_tenant_policy(
    payload: TenantPolicyIn,
    current_user: User = Depends(require_permissions(CONFIGURE_TENANT)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids_optional),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
) -> TenantPolicy:
    service = _admin_service(db, current_user, audit, tenant_ids)
    return service.save_tenant_policy(
        ai_enabled=payload.ai_enabled,
        tone=payload.tone,
        language=payload.language,
        allowed_categories=payload.allowed_categories,
        escalation_rules=payload.escalation_rules,
    )


@router.get("/ai-policies/global", response_model=GlobalPolicyOut)
def get_global_policy(
    current_user: User = Depends(require_permissions(MANAGE_AI_POLICIES)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids_optional),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
) -> GlobalPolicyOut:
    service = _admin_service(db, current_user, audit, tenant_ids)
    policy = service.get_global_policy()
    return GlobalPolicyOut(**effective_global_policy(policy))


@router.put("/ai-policies/global", response_model=GlobalPolicyOut)
def save_global_policy(
    payload: GlobalPolicyIn,
    current_user: User = Depends(require_permissions(MANAGE_AI_POLICIES)),
    tenant_ids: list[str] = Depends(get_effective_tenant_ids_optional),
    db: Session = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
) -> GlobalPolicyOut:
    service = _admin_service(db, current_user, audit, tenant_ids)
    policy = service.save_global_policy(
        llm_model=payload.llm_model,
        ai_confidence_threshold=payload.ai_confidence_threshold,
        guardrails_enabled=payload.guardrails_enabled,
        llm_rate_max_calls=payload.llm_rate_max_calls,
    )
    return GlobalPolicyOut(**effective_global_policy(policy))
