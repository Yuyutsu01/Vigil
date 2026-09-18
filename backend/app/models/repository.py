"""
Repository, IntegrationCredential, RepositoryPolicy, RepositoryReview, and WebhookEvent models (FR-103, FR-104).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

_JSON = JSONB().with_variant(sa.JSON(), "sqlite")
_UUID = UUID(as_uuid=True).with_variant(sa.Uuid(as_uuid=True), "sqlite")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class IntegrationCredential(Base):
    """
    Credentials for third-party integration installations (e.g. GitHub App).
    Stores installation IDs and vault references for private keys (never plaintext).
    """
    __tablename__ = "integration_credentials"

    credential_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="github", nullable=False)
    installation_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    encrypted_private_key_ref: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[Any] = mapped_column(_JSON, default=list, nullable=False)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    repositories: Mapped[List["Repository"]] = relationship(back_populates="credential")


class RepositoryPolicy(Base):
    """
    Per-repository review policy controlling language support, path exclusion,
    rule exclusion, file caps, and automated webhook triggers.
    """
    __tablename__ = "repository_policies"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    enabled_languages: Mapped[Any] = mapped_column(_JSON, nullable=False)
    ignored_paths: Mapped[Any] = mapped_column(_JSON, nullable=False)
    ignored_rules: Mapped[Any] = mapped_column(_JSON, nullable=False)
    max_files_per_review: Mapped[int] = mapped_column(Integer, default=500, nullable=False)
    auto_review_on_push: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_review_on_pr: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    review_fork_prs: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    review_draft_prs: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allowed_ci_commands: Mapped[Any] = mapped_column(_JSON, default=list, nullable=False)
    pr_comment_publication: Mapped[str] = mapped_column(String(32), default="human_required", nullable=False)
    pr_review_generation: Mapped[str] = mapped_column(String(32), default="on_demand", nullable=False)
    # Phase 5 Specialist Agent Toggles (FR-108, D15)
    enable_specialist_risk_scoring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enable_dependency_risk: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enable_dataflow_investigation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enable_test_generation_agent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enable_executive_summary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enable_feedback_learning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    repositories: Mapped[List["Repository"]] = relationship(back_populates="policy")



class Repository(Base):
    """
    Connected repository entity mapped to a tenant and installation credential.
    Strictly read-only access in Phase 3.
    """
    __tablename__ = "repositories"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_repositories_provider_external_id"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="github", nullable=False)
    external_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    default_branch: Mapped[str] = mapped_column(String(128), default="main", nullable=False)
    installation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        _UUID,
        ForeignKey("integration_credentials.credential_id", ondelete="SET NULL"),
        nullable=True,
    )
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        _UUID,
        ForeignKey("repository_policies.policy_id", ondelete="SET NULL"),
        nullable=True,
    )
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    credential: Mapped[Optional[IntegrationCredential]] = relationship(back_populates="repositories")
    policy: Mapped[Optional[RepositoryPolicy]] = relationship(back_populates="repositories")
    reviews: Mapped[List["RepositoryReview"]] = relationship(back_populates="repository")

    @property
    def owner(self) -> str:
        return self.full_name.split("/")[0] if "/" in self.full_name else ""

    @property
    def name(self) -> str:
        return self.full_name.split("/")[1] if "/" in self.full_name else self.full_name



class RepositoryReview(Base):
    """
    Scoped revision review record linking a general ReviewRun to a specific
    repository and git reference (branch, commit, PR, or directory).
    """
    __tablename__ = "repository_reviews"

    repository_review_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("repositories.repository_id", ondelete="CASCADE"), nullable=False, index=True
    )
    review_run_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("review_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    ref_type: Mapped[str] = mapped_column(String(32), nullable=False)  # branch, commit, pr, directory
    ref_value: Mapped[str] = mapped_column(Text, nullable=False)
    scope_mode: Mapped[str] = mapped_column(String(32), nullable=False)  # full_repo, changed_files, directory, files
    file_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    budget_paused_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    repository: Mapped[Repository] = relationship(back_populates="reviews")

    @property
    def run_id(self) -> uuid.UUID:
        return self.review_run_id

    @property
    def commit_sha(self) -> str:
        return self.ref_value if self.ref_type == "commit" else ""

    @property
    def pr_number(self) -> Optional[int]:
        if self.ref_type == "pr":
            try:
                return int(self.ref_value)
            except Exception:
                return None
        return None


# Alias for backward and forward compatibility
RepositoryReviewRun = RepositoryReview




class WebhookEvent(Base):
    """
    Audit and idempotency log for incoming webhooks.
    Raw body bytes are hashed with SHA-256 for integrity verification.
    """
    __tablename__ = "webhook_events"

    webhook_event_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    delivery_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    tenant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id", ondelete="SET NULL"), nullable=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), default="github", nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)  # pending, processed, ignored, failed
