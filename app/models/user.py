from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

UserRole = Literal["platform_admin", "tenant_admin", "supervisor", "agent", "customer"]


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Nombre de display
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50))
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # Legacy, se migrará a user_tenants
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    # Relación multi-tenant
    tenant_memberships: Mapped[list["UserTenant"]] = relationship("UserTenant", back_populates="user", cascade="all, delete-orphan")
