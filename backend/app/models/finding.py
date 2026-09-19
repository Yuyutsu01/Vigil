"""Finding, Evidence, PatchCandidate (nullable stub), and FindingFeedback models."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from typing import Any, List, Optional, TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.validation import ValidationRun

_JSON = JSONB().with_variant(sa.JSON(), "sqlite")
_UUID = UUID(as_uuid=True).with_variant(sa.Uuid(as_uuid=True), "sqlite")



def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Severity(str, enum.Enum):
    critical = "Critical"
    high = "High"
    medium = "Medium"
    low = "Low"
    info = "Info"


class FindingOrigin(str, enum.Enum):
    rule = "rule"
    tool = "tool"
    agent = "agent"


class EvidenceKind(str, enum.Enum):
    ast_node = "ast_node"
    token_regex = "token_regex"
    llm_reasoning = "llm_reasoning"


class FindingStatus(str, enum.Enum):
    open = "open"
    accepted = "accepted"
    rejected = "rejected"
    false_positive = "false_positive"


class Finding(Base):
    """
    Normalized, deduplicated review finding.

    finding_id: UUID v7 primary key (database identity).
    fingerprint: Deterministic SHA-256 per the plan:
        sha256(rule_id || ast_path || matched_text_hash || evidence_kind)
        This is what deduplication and SARIF partialFingerprints use.
        It is line-shift-invariant: inserting blank lines does not change it.
    See Implementation Plan [C3] and [H3].
    """
    __tablename__ = "findings"

    finding_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("review_runs.run_id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, nullable=False, index=True
    )
    # Deterministic SHA-256 fingerprint for deduplication and SARIF
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    origin: Mapped[FindingOrigin] = mapped_column(
        SAEnum(FindingOrigin, name="finding_origin"), nullable=False
    )
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_evidence_ref: Mapped[uuid.UUID | None] = mapped_column(
        _UUID,
        ForeignKey("tool_findings.tool_finding_id", ondelete="SET NULL"),
        nullable=True,
    )
    # Repository-relative source file path (FR-104; NULL for single-file submissions)
    source_file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    # Versioned rule ID (e.g. VIGIL-SEC-001 or LLM-SEC-001)
    rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity, name="finding_severity", values_callable=lambda obj: [e.value for e in obj]), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    remediation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FindingStatus] = mapped_column(
        SAEnum(FindingStatus, name="finding_status"), default=FindingStatus.open
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    review_run: Mapped["ReviewRun"] = relationship(  # type: ignore[name-defined]
        back_populates="findings",
        foreign_keys=[run_id],
    )
    evidence: Mapped[list["Evidence"]] = relationship(back_populates="finding")
    feedback: Mapped[list["FindingFeedback"]] = relationship(back_populates="finding")
    # Nullable stub — no patch generation in Phase 1 (FR-105 is Phase 3)
    patch_candidate: Mapped["PatchCandidate | None"] = relationship(
        back_populates="finding", uselist=False
    )


class Evidence(Base):
    """Source location and tool evidence backing a finding."""
    __tablename__ = "evidence"

    evidence_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("findings.finding_id"), nullable=False, index=True
    )
    # SARIF-compatible source range
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # AST path for fingerprinting; line-shift-invariant
    ast_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Tool or rule that produced this evidence
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Short excerpt of the matched code
    code_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_kind: Mapped[EvidenceKind] = mapped_column(
        SAEnum(EvidenceKind, name="evidence_kind"), nullable=False
    )

    finding: Mapped["Finding"] = relationship(back_populates="evidence")


class PatchStatus(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    withdrawn = "withdrawn"
    validating = "validating"
    applied = "applied"
    rejected = "rejected"


class PatchCandidate(Base):
    """
    Remediation patch candidate generated by Agent A6 (FR-105).
    Contains unified diff, rationale, assumptions, tests to run, and approval state.
    """
    __tablename__ = "patch_candidates"

    patch_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("findings.finding_id", ondelete="CASCADE"), nullable=True
    )
    base_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    unified_diff: Mapped[str | None] = mapped_column(Text, nullable=True)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Phase 4 extensions
    status: Mapped[PatchStatus] = mapped_column(
        SAEnum(PatchStatus, name="patch_status"), default=PatchStatus.draft, nullable=False
    )
    assumptions: Mapped[str] = mapped_column(Text, default="", nullable=False)
    tests_to_run: Mapped[Any] = mapped_column(_JSON, default=list, nullable=False)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        _UUID, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_branch: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    applied_pr_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    applied_commit_sha: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    finding: Mapped["Finding"] = relationship(back_populates="patch_candidate")
    validations: Mapped[List["ValidationRun"]] = relationship(
        "ValidationRun", back_populates="patch_candidate", cascade="all, delete-orphan"
    )



class FindingFeedback(Base):
    """User disposition on a finding (FR-009, §8.1 Step 7)."""
    __tablename__ = "finding_feedback"

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    finding_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("findings.finding_id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(_UUID, nullable=False)
    useful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    disposition: Mapped[str | None] = mapped_column(String(32), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Phase 5 Governed Learning Fields (FR-109, B2, B4)
    reason_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    indexed_for_learning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    learning_precedent_id: Mapped[uuid.UUID | None] = mapped_column(
        _UUID,
        ForeignKey("learning_disposition_indices.index_id", ondelete="SET NULL", name="fk_feedback_learning_precedent"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    finding: Mapped["Finding"] = relationship(back_populates="feedback")
