"""
DraftPRReview and DraftPRComment database models (FR-107).
Stores drafted PR review summaries and line-level comments prior to publication.
"""
from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional

import sqlalchemy as sa
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

_UUID = UUID(as_uuid=True).with_variant(sa.Uuid(as_uuid=True), "sqlite")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class DraftStatusEnum(str, enum.Enum):
    draft = "draft"
    approved = "approved"
    published = "published"
    orphaned = "orphaned"


class DraftPRReview(Base):
    """
    Draft review container grouping top-level summary markdown and line-level comments.
    """
    __tablename__ = "draft_pr_reviews"

    review_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    repository_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("repositories.repository_id", ondelete="CASCADE"), nullable=False, index=True
    )
    pr_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[DraftStatusEnum] = mapped_column(
        SAEnum(DraftStatusEnum, name="draft_pr_status"), default=DraftStatusEnum.draft, nullable=False
    )
    summary_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    # Relationships
    comments: Mapped[List["DraftPRComment"]] = relationship(
        "DraftPRComment", back_populates="review", cascade="all, delete-orphan"
    )


class DraftPRComment(Base):
    """
    Line-level draft comment proposed by Agent A9.
    Constrained to ≤4,096 characters and lines present in the PR diff hunk.
    """
    __tablename__ = "draft_pr_comments"

    comment_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("draft_pr_reviews.review_id", ondelete="CASCADE"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(String(4096), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    line: Mapped[int] = mapped_column(Integer, nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[DraftStatusEnum] = mapped_column(
        SAEnum(DraftStatusEnum, name="draft_pr_status"), default=DraftStatusEnum.draft, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    # Relationships
    review: Mapped["DraftPRReview"] = relationship("DraftPRReview", back_populates="comments")
