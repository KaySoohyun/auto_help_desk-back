"""Administración de tenants y auditoría (spec §4.3, §4.4, FR-06).

`AdminService` concentra la lógica de negocio de la consola admin: creación y
actualización de usuarios con restricciones de rol y tenant, políticas IA por
tenant (FR-06) y políticas globales (permiso `MANAGE_AI_POLICIES`). Cada acción
se audita (`admin.*`) sin registrar datos sensibles.
"""

from __future__ import annotations

from typing import Any, Protocol

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.policy import GlobalPolicy, TenantPolicy
from app.models.user import User

PLATFORM_ADMIN = "platform_admin"
TENANT_ADMIN = "tenant_admin"
SUPERVISOR = "supervisor"
AGENT = "agent"

# Roles que un tenant_admin puede asignar (nunca platform_admin).
_TENANT_ADMIN_ASSIGNABLE = {TENANT_ADMIN, SUPERVISOR, AGENT}


class AuditPort(Protocol):
    def log(
        self,
        action: str,
        *,
        user_id: int | None = None,
        tenant_id: str | None = None,
        service: str | None = None,
        model: str | None = None,
        model_version: str | None = None,
        prompt_version: str | None = None,
        trace_id: str | None = None,
        result: str = "success",
        confidence: float | None = None,
        detail: dict[str, Any] | None = None,
    ) -> object: ...


class AdminService:
    """Lógica de negocio de la consola de administración."""

    def __init__(
        self,
        db: Session,
        *,
        current_user: User,
        audit: AuditPort | None = None,
        tenant_ids: list[str] | None = None,
    ) -> None:
        self._db = db
        self._user = current_user
        self._audit = audit
        self._tenant_ids = tenant_ids or []

    # -- helpers -----------------------------------------------------------

    @property
    def _is_platform_admin(self) -> bool:
        return self._user.role == PLATFORM_ADMIN

    def _require_tenant(self) -> str:
        """Tenant único requerido para operaciones tenant-scoped de escritura."""
        if len(self._tenant_ids) == 1:
            return self._tenant_ids[0]
        if len(self._tenant_ids) > 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seleccioná un tenant para esta operación",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Rol sin tenant asignado",
        )

    def _log_audit(self, action_name: str, detail: dict[str, Any] | None, *, user_id: int | None = None) -> None:
        if self._audit is not None:
            self._audit.log(
                action_name,
                user_id=user_id,
                tenant_id=self._tenant_ids[0] if self._tenant_ids else self._user.tenant_id,
                service="admin",
                result="success",
                detail=detail,
            )

    def _resolve_target_tenant(self, tenant_id: str | None) -> str:
        """Tenant destino de la operación según el rol del invocante."""
        if self._is_platform_admin:
            if not tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Se requiere tenant_id para crear un usuario",
                )
            return tenant_id
        # tenant_admin solo opera en su propio tenant
        own_tenant = self._require_tenant()
        if tenant_id is not None and tenant_id != own_tenant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puede crear usuarios en otro tenant",
            )
        return own_tenant

    def _assert_role_assignable(self, role: str) -> None:
        if not self._is_platform_admin and role not in _TENANT_ADMIN_ASSIGNABLE:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rol fuera del alcance del administrador",
            )

    # -- usuarios ----------------------------------------------------------

    def create_user(self, *, email: str, name: str, password: str, role: str, tenant_id: str | None) -> User:
        target_tenant = self._resolve_target_tenant(tenant_id)
        self._assert_role_assignable(role)

        existing = self._db.scalar(select(User).where(User.email == email))
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado")

        user = User(
            email=email,
            name=name,
            password_hash=hash_password(password),
            role=role,
            tenant_id=target_tenant,
            is_active=True,
        )
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        self._log_audit(
            "admin.user_created",
            {"user_id": user.id, "name": name, "role": role, "tenant_id": target_tenant},
            user_id=self._user.id,
        )
        return user

    def update_user(
        self,
        user_id: int,
        *,
        role: str | None,
        is_active: bool | None,
        name: str | None = None,
    ) -> User:
        if self._is_platform_admin:
            target = self._db.get(User, user_id)
        else:
            target = self._db.scalar(
                select(User).where(User.id == user_id, User.tenant_id == self._require_tenant())
            )
        if target is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        if role is not None:
            self._assert_role_assignable(role)
        if is_active is False and user_id == self._user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No puede desactivarse a sí mismo",
            )

        changes: dict[str, Any] = {}
        if role is not None and role != target.role:
            target.role = role
            changes["role"] = role
        if is_active is not None and is_active != target.is_active:
            target.is_active = is_active
            changes["is_active"] = is_active
        if name is not None and name != target.name:
            target.name = name
            changes["name"] = name

        if changes:
            self._db.commit()
            self._db.refresh(target)
            self._log_audit(
                "admin.user_updated",
                {"user_id": target.id, **changes},
                user_id=self._user.id,
            )
        return target

    # -- políticas IA por tenant (FR-06) -----------------------------------

    def get_tenant_policy(self) -> TenantPolicy:
        tenant_id = self._require_tenant()
        policy = self._db.scalar(select(TenantPolicy).where(TenantPolicy.tenant_id == tenant_id))
        if policy is None:
            return TenantPolicy(tenant_id=tenant_id, ai_enabled=True)
        return policy

    def save_tenant_policy(
        self,
        *,
        ai_enabled: bool,
        tone: str | None,
        language: str | None,
        allowed_categories: list[str] | None,
        escalation_rules: dict | None,
    ) -> TenantPolicy:
        tenant_id = self._require_tenant()
        policy = self._db.scalar(select(TenantPolicy).where(TenantPolicy.tenant_id == tenant_id))
        if policy is None:
            policy = TenantPolicy(
                tenant_id=tenant_id,
                ai_enabled=ai_enabled,
                tone=tone,
                language=language,
                allowed_categories=allowed_categories,
                escalation_rules=escalation_rules,
            )
            self._db.add(policy)
        else:
            policy.ai_enabled = ai_enabled
            policy.tone = tone
            policy.language = language
            policy.allowed_categories = allowed_categories
            policy.escalation_rules = escalation_rules
        self._db.commit()
        self._db.refresh(policy)
        self._log_audit(
            "admin.tenant_policy_updated",
            {"tenant_id": tenant_id, "ai_enabled": ai_enabled},
            user_id=self._user.id,
        )
        return policy

    # -- políticas globales (§4.4, MANAGE_AI_POLICIES) ---------------------

    def get_global_policy(self) -> GlobalPolicy:
        policy = self._db.get(GlobalPolicy, 1)
        if policy is None:
            return GlobalPolicy(id=1)
        return policy

    def save_global_policy(
        self,
        *,
        llm_model: str | None,
        ai_confidence_threshold: float | None,
        guardrails_enabled: bool | None,
        llm_rate_max_calls: int | None,
    ) -> GlobalPolicy:
        policy = self._db.get(GlobalPolicy, 1)
        if policy is None:
            policy = GlobalPolicy(id=1)
            self._db.add(policy)
        if llm_model is not None:
            policy.llm_model = llm_model
        if ai_confidence_threshold is not None:
            policy.ai_confidence_threshold = ai_confidence_threshold
        if guardrails_enabled is not None:
            policy.guardrails_enabled = guardrails_enabled
        if llm_rate_max_calls is not None:
            policy.llm_rate_max_calls = llm_rate_max_calls
        self._db.commit()
        self._db.refresh(policy)
        self._log_audit(
            "admin.global_policy_updated",
            {"policy_id": policy.id},
            user_id=self._user.id,
        )
        return policy


def effective_global_policy(policy: GlobalPolicy) -> dict[str, Any]:
    """Valores efectivos: override de `settings` + defaults de `.env`."""
    return {
        "llm_model": policy.llm_model or settings.llm_effective_model,
        "ai_confidence_threshold": (
            policy.ai_confidence_threshold
            if policy.ai_confidence_threshold is not None
            else settings.ai_confidence_threshold
        ),
        "guardrails_enabled": (
            policy.guardrails_enabled if policy.guardrails_enabled is not None else settings.guardrails_enabled
        ),
        "llm_rate_max_calls": (
            policy.llm_rate_max_calls if policy.llm_rate_max_calls is not None else settings.llm_rate_max_calls
        ),
    }
