"""ReviewRun, SourceArtifact, and AuditEvent models."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class ReviewStatus(str, enum.Enum):
    """
    All possible states for a ReviewRun.
    See Implementation Plan [M1].
    """
    pending = "pending"
    running = "running"
    partial = "partial"
    completed = "completed"
    failed = "failed"
    budget_paused = "budget_paused"
    deleted = "deleted"


class AuditAction(str, enum.Enum):
    """
    Audit event action identifiers per [A2].
    Append-only. Source code and secrets are NEVER stored here.
    """
    LOGIN = "LOGIN"
    GRANT_CONSENT = "GRANT_CONSENT"
    REVOKE_CONSENT = "REVOKE_CONSENT"
    CREATE_REVIEW = "CREATE_REVIEW"
    COMPLETE_REVIEW = "COMPLETE_REVIEW"
    DELETE_REVIEW = "DELETE_REVIEW"
    SUBMIT_FEEDBACK = "SUBMIT_FEEDBACK"
    RATE_LIMIT_TRIGGERED = "RATE_LIMIT_TRIGGERED"
    TENANT_MISMATCH_REJECTED = "TENANT_MISMATCH_REJECTED"


class SourceArtifact(Base):
    """Stores uploaded/pasted source code separately from metadata."""
    __tablename__ = "source_artifacts"

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False, index=True
    )
    # Encrypted content in production; plaintext in prototype
    content: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 hex
    language: Mapped[str] = mapped_column(String(32), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    retention_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Legal hold prevents deletion even after retention expiry
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    review_runs: Mapped[list["ReviewRun"]] = relationship(back_populates="source_artifact")


class ReviewRun(Base):
    """Immutable execution record for one review run."""
    __tablename__ = "review_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False, index=True
    )
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("source_artifacts.artifact_id"), nullable=False
    )
    status: Mapped[ReviewStatus] = mapped_column(
        SAEnum(ReviewStatus, name="review_status"), default=ReviewStatus.pending
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Config and prompt version for auditability
    config_version: Mapped[str] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=True)
    # Legal hold prevents deletion
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Reason for parking (budget exhaustion, deadline, etc.)
    parked_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    source_artifact: Mapped["SourceArtifact"] = relationship(back_populates="review_runs")
    findings: Mapped[list["Finding"]] = relationship(  # type: ignore[name-defined]
        back_populates="review_run",
        foreign_keys="[Finding.run_id]",
    )


class AuditEvent(Base):
    """
    Append-only audit trail.
    MUST NEVER contain source code content or credential values.
    """
    __tablename__ = "audit_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, name="audit_action"), nullable=False
    )
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # Sanitized metadata JSON — no source code, no secrets
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
