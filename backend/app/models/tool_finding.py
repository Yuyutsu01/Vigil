"""ToolFinding model: raw findings produced by static analyzer tool adapters."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    JSON,
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


class ToolFinding(Base):
    """
    Stores raw tool findings from static analyzer adapters (Bandit, Semgrep, ESLint, Ruff, etc.).
    Preserves verbatim tool evidence and raw tool outputs for auditability and normalized triage.
    """
    __tablename__ = "tool_findings"

    tool_finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_runs.run_id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tool_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    severity_raw: Mapped[str | None] = mapped_column(String(32), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_col: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    review_run: Mapped["ReviewRun"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[run_id],
    )
