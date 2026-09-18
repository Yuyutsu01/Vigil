"""Tenant, User, and ConsentRecord models."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

_UUID = UUID(as_uuid=True).with_variant(sa.Uuid(as_uuid=True), "sqlite")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Tenant(Base):
    __tablename__ = "tenants"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Days to retain source artifacts
    source_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    # Days to retain findings
    findings_retention_days: Mapped[int] = mapped_column(Integer, default=90)
    # LLM provider policy: "mock" | "openai" | etc.
    model_policy: Mapped[str] = mapped_column(String(64), default="mock")
    # Daily cost ceiling in dollars (FR-108, B5)
    daily_cost_limit_dollars: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    consents: Mapped[list["ConsentRecord"]] = relationship(back_populates="tenant")


class User(Base):
    """
    # PROTOTYPE_ONLY
    Local user store for Phase 1 prototype.
    TODO: Replace with Auth0/Keycloak OIDC before any external pilot.
    See IMPLEMENTATION_NOTES.md and plan [M6] / [F2].
    """
    __tablename__ = "users"

    user_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    # Argon2id hash — PROTOTYPE_ONLY
    hashed_password: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(64), default="developer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    consents: Mapped[list["ConsentRecord"]] = relationship(back_populates="user")


class ConsentRecord(Base):
    """Records user consent to data processing per FR-009."""
    __tablename__ = "consent_records"

    consent_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("users.user_id"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id"), nullable=False
    )
    # Purpose identifier, e.g. "code_review_processing"
    purpose: Mapped[str] = mapped_column(String(128), nullable=False)
    # Policy version at time of consent
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    # Whether the user granted (True) or revoked (False) consent
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now
    )

    user: Mapped["User"] = relationship(back_populates="consents")
    tenant: Mapped["Tenant"] = relationship(back_populates="consents")
