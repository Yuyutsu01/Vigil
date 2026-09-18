"""
Security test for Cross-Agent Cumulative Budget Ceiling (FR-108 / AC-108.3).

Concept:
Specialist agents consume LLM tokens. To prevent runaway costs or token exhaustion attacks,
the MultiAgentOrchestrator tracks cumulative token consumption against a strict ceiling
(200,000 tokens / $1.00 limit).
When cumulative token consumption reaches or exceeds the budget:
1. Pending and subsequent agent tasks are skipped without executing.
2. The task status is recorded as 'skipped' with error 'budget_paused'.
3. The orchestration result degrades to status 'budget_paused'.
4. An AuditEvent with action=AGENT_BUDGET_EXCEEDED is written.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.llm_provider import MockProvider
from app.agents.orchestrator import (
    MultiAgentOrchestrator,
    ReviewContextSnapshot,
)
from app.database import Base
from app.models.orchestration import AgentCoordinationRun, AgentTaskExecution
from app.models.repository import RepositoryPolicy
from app.models.review import AuditAction, AuditEvent, ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import Tenant
import app.models  # ensure models are registered


@pytest.mark.asyncio
async def test_cross_agent_budget_exceeded_halts_orchestration():
    """
    Simulate a run where early agents consume or exceed the configured token budget.
    Assert that subsequent agents are halted, status is 'budget_paused', and audit event is logged.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id = uuid.uuid4()
        run_id = uuid.uuid4()
        artifact_id = uuid.uuid4()

        tenant = Tenant(tenant_id=tenant_id, name="Budget Security Tenant")
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content="def calculate(): pass",
            checksum="chk_budget_test",
            language="python",
            size_bytes=24,
            retention_until=datetime.now(timezone.utc),
        )
        review_run = ReviewRun(
            run_id=run_id,
            tenant_id=tenant_id,
            artifact_id=artifact_id,
            status=ReviewStatus.running,
            requested_by=uuid.uuid4(),
        )
        session.add(tenant)
        session.add(artifact)
        session.add(review_run)
        await session.commit()

        snapshot = ReviewContextSnapshot(
            run_id=run_id,
            tenant_id=tenant_id,
            source_code="def calculate(): pass",
            language="python",
            manifest_files={},
            target_file_path="main.py",
        )

        policy = RepositoryPolicy(
            enable_specialist_risk_scoring=True,
            enable_dependency_risk=True,
            enable_dataflow_investigation=True,
            enable_test_generation_agent=True,
            enable_executive_summary=True,
        )

        provider = MockProvider()
        # Set an artificially small budget of 5,000 tokens (less than Subtree 1 agents consume)
        orchestrator = MultiAgentOrchestrator(
            provider=provider,
            db=session,
            token_budget=5000,
        )

        result = await orchestrator.run(
            snapshot=snapshot,
            policy=policy,
            enable_patch=True,
        )
        await session.commit()

        # Orchestration status must be 'budget_paused'
        assert result.status == "budget_paused"

        # Check that subsequent agents (e.g. executive_summary or test_generation) were skipped
        task_stmt = select(AgentTaskExecution).where(
            AgentTaskExecution.coordination_id == result.coordination_id
        )
        res = await session.execute(task_stmt)
        tasks = res.scalars().all()
        skipped_tasks = [t for t in tasks if t.status == "skipped" and t.error_message == "budget_paused"]
        assert len(skipped_tasks) > 0, "No tasks were skipped despite budget exhaustion!"

        # Check AuditEvent recorded AGENT_BUDGET_EXCEEDED
        audit_stmt = select(AuditEvent).where(
            AuditEvent.action == AuditAction.AGENT_BUDGET_EXCEEDED
        )
        audit_res = await session.execute(audit_stmt)
        budget_audits = audit_res.scalars().all()
        assert len(budget_audits) >= 1
        meta = json.loads(budget_audits[0].metadata_json or "{}")
        assert meta["budget_limit"] == 5000
        assert meta["consumed"] >= 5000
