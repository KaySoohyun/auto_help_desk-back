from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.models.user import UserRole
from app.schemas.auth import UserOut


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole
    tenant_id: str | None = None


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def _at_least_one(self) -> "UserUpdate":
        if self.role is None and self.is_active is None and self.name is None:
            raise ValueError("Debe indicar role, is_active o name")
        return self


class UserListOut(BaseModel):
    items: list[UserOut]
    total: int
    limit: int
    offset: int


class CustomerAdminOut(BaseModel):
    """Cliente visible en la consola de administración (sin PII: email enmascarado)."""

    id: int
    tenant_id: str
    name: str
    email_masked: str | None
    company: str | None
    plan: str | None
    created_at: datetime


class CustomerListOut(BaseModel):
    items: list[CustomerAdminOut]
    total: int
    limit: int
    offset: int


class TenantPolicyIn(BaseModel):
    ai_enabled: bool = True
    tone: str | None = Field(default=None, max_length=50)
    language: str | None = Field(default=None, max_length=10)
    allowed_categories: list[str] | None = None
    escalation_rules: dict | None = None


class TenantPolicyOut(TenantPolicyIn):
    tenant_id: str
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class GlobalPolicyIn(BaseModel):
    llm_model: str | None = None
    ai_confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    guardrails_enabled: bool | None = None
    llm_rate_max_calls: int | None = Field(default=None, ge=1)


class GlobalPolicyOut(BaseModel):
    llm_model: str
    ai_confidence_threshold: float
    guardrails_enabled: bool
    llm_rate_max_calls: int
