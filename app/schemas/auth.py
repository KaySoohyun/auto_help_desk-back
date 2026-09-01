from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class RegisterRequest(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    tenant_id: str | None = None  # Legacy: único tenant (compatibilidad con tests)
    tenant_ids: list[str] = Field(default_factory=list)  # Uno o varios tenants del registro


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_id: str | None = None  # Opcional: si el usuario pertenece a múltiples tenants


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class SwitchTenantRequest(BaseModel):
    tenant_id: str


class TenantInfo(BaseModel):
    """Información básica de un tenant para el usuario."""
    id: str
    name: str
    slug: str
    role: str  # Rol del usuario en este tenant


class UserOut(BaseModel):
    id: int
    email: EmailStr
    name: str | None  # Nombre de display
    role: str  # Rol principal (legacy, para compatibilidad)
    tenant_id: str | None  # Tenant principal (legacy, para compatibilidad)
    is_active: bool
    created_at: datetime
    tenants: list[TenantInfo] = []  # Lista de tenants a los que pertenece

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
