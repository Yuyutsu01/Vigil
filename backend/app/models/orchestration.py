"""
Phase 5 (M5) Orchestration & Learning Models.
Tracks multi-agent execution trees (FR-108) and tenant-isolated RAG disposition indices (FR-109).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

_UUID = UUID(as_uuid=True).with_variant(sa.Uuid(as_uuid=True), "sqlite")
_JSON = JSONB().with_variant(sa.JSON(), "sqlite")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class LearningDispositionIndex(Base):
    """
    Metadata for tenant-isolated RAG index over historical dispositions (FR-109).
    Stores pointers to vector/BM25 retrieval indexes with instant revocation purge support.
    """
    __tablename__ = "learning_disposition_indices"

    index_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    vector_index_name: Mapped[str] = mapped_column(String(128), nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_purged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class AgentCoordinationRun(Base):
    """
    Tracks the lifecycle, aggregate token spend, and completion status of a multi-agent tree run (FR-108).
    """
    __tablename__ = "agent_coordination_runs"

    coordination_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    review_run_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("review_runs.run_id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False, index=True
    )
    # running | completed | partial | failed | budget_paused
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    total_tokens_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_wall_clock_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_agents: Mapped[Any] = mapped_column(_JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    tasks: Mapped[List["AgentTaskExecution"]] = relationship(
        "AgentTaskExecution", back_populates="coordination_run", cascade="all, delete-orphan"
    )


class AgentTaskExecution(Base):
    """
    Records execution metrics, status, duration, and partial outputs for an individual specialist agent.
    """
    __tablename__ = "agent_task_executions"

    task_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, primary_key=True, default=_uuid
    )
    coordination_id: Mapped[uuid.UUID] = mapped_column(
        _UUID, ForeignKey("agent_coordination_runs.coordination_id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False)
    # running | completed | failed | timeout | skipped
    status: Mapped[str] = mapped_column(String(32), default="running", nullable=False)
    tokens_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    partial_output: Mapped[Optional[Any]] = mapped_column(_JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)

    coordination_run: Mapped["AgentCoordinationRun"] = relationship(back_populates="tasks")
