"""ReportArtifact model: tracks exported reports (JSON, HTML, PDF, Executive PDF)."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
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


class ReportFormat(str, enum.Enum):
    json = "json"
    html = "html"
    pdf = "pdf"
    executive_pdf = "executive_pdf"


class ReportArtifact(Base):
    """
    Stores metadata for generated reports. Subject to tenant isolation,
    consent, legal_hold, and retention rules.
    """
    __tablename__ = "report_artifacts"

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_runs.run_id"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.tenant_id"), nullable=False, index=True
    )
    format: Mapped[ReportFormat] = mapped_column(
        SAEnum(ReportFormat, name="report_format"), nullable=False
    )
    storage_ref: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    review_run: Mapped["ReviewRun"] = relationship(  # type: ignore[name-defined]
        foreign_keys=[run_id],
    )
