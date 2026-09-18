"""
ValidationRun database model and verdict enums (FR-106).
Stores ephemeral sandbox validation results, command check logs, and resource metrics.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional, TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.finding import PatchCandidate

_JSON = JSONB().with_variant(sa.JSON(), "sqlite")
_UUID = UUID(as_uuid=True).with_variant(sa.Uuid(as_uuid=True), "sqlite")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class ValidationVerdictEnum(str, enum.Enum):
    passed = "passed"
    failed = "failed"
    error = "error"
    timeout = "timeout"


class ValidationRun(Base):
    """
    Structured record of a patch execution inside an isolated gVisor sandbox.
    Captures individual allowlisted command checks and redacted output.
    """
    __tablename__ = "validation_runs"

    validation_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    patch_candidate_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("patch_candidates.patch_id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    verdict: Mapped[ValidationVerdictEnum] = mapped_column(
        SAEnum(ValidationVerdictEnum, name="validation_verdict"), nullable=False
    )
    # List of {name, command, exit_code, duration_ms, status, stdout_excerpt, stderr_excerpt}
    checks: Mapped[Any] = mapped_column(_JSON, nullable=False, default=list)
    # Resource metrics, runtime (e.g. gvisor), image digest, peak RAM/CPU
    sandbox_metadata: Mapped[Any] = mapped_column(_JSON, nullable=False, default=dict)
    stdout_log: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stderr_log: Mapped[str] = mapped_column(Text, nullable=False, default="")
    log_dir_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    # Relationships
    patch_candidate: Mapped["PatchCandidate"] = relationship("PatchCandidate", back_populates="validations")
