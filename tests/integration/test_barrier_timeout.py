"""
Integration test for Multi-Agent Orchestration Barrier Timeout (FR-108).

Concept:
In multi-agent orchestration, Subtree 1 parallel execution runs independent specialist agents concurrently.
If an individual agent stalls or exceeds the synchronization barrier deadline, the barrier expires:
1. Incomplete tasks are cancelled gracefully via asyncio cancellation.
2. The partial outputs from completed agents are preserved.
3. The coordination status degrades to 'partial'.
4. An AuditEvent is recorded with action=AGENT_EXECUTION_FAILED and reason='barrier_timeout'.
5. AgentTaskExecution records the timeout state.
"""
from __future__ import annotations

import asyncio
import time
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
async def test_subtree1_barrier_timeout_cancellation(monkeypatch):
    """
    Simulate a hanging Subtree 1 agent with a short 0.5s barrier timeout.
    Verify that:
    1. The orchestration does not block for the slow agent's sleep duration.
    2. The slow agent is cancelled and recorded with status='timeout'.
    3. The completed agents are preserved.
    4. OrchestrationResult degrades to status='partial'.
    5. AuditEvent logs AGENT_EXECUTION_FAILED with reason='barrier_timeout'.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id = uuid.uuid4()
        run_id = uuid.uuid4()
        artifact_id = uuid.uuid4()

        # Seed tenant, source artifact, and review run
        tenant = Tenant(tenant_id=tenant_id, name="Barrier Timeout Tenant")
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content="import os\nos.system('ls')",
            checksum="chk_barrier_test",
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
            source_code="import os\nos.system('ls')",
            language="python",
            manifest_files={"requirements.txt": "requests==2.25.0"},
            target_file_path="main.py",
        )

        policy = RepositoryPolicy(
            enable_specialist_risk_scoring=False,
            enable_dependency_risk=True,
            enable_dataflow_investigation=True,
            enable_test_generation_agent=False,
            enable_executive_summary=False,
        )

        # Mock dataflow agent to simulate a slow / hanging execution (3.0s)
        async def _slow_dataflow(*args, **kwargs):
            await asyncio.sleep(3.0)
            from app.agents.dataflow_agent import DataflowOutput
            return DataflowOutput(taint_paths=[], complex_sinks=[], sanitizer_coverage=0.0)

        import app.agents.orchestrator as orch_module
        monkeypatch.setattr(orch_module, "run_dataflow_agent", _slow_dataflow)

        provider = MockProvider()
        # Barrier timeout set to 0.4s (well below the 3.0s mock delay)
        orchestrator = MultiAgentOrchestrator(
            provider=provider,
            db=session,
            barrier_timeout=0.4,
        )

        start_time = time.perf_counter()
        result = await orchestrator.run(
            snapshot=snapshot,
            policy=policy,
            enable_patch=False,
        )
        duration = time.perf_counter() - start_time
        await session.commit()

        # Orchestration must exit near the barrier timeout, far faster than 3.0s
        assert duration < 2.0, f"Orchestrator did not enforce barrier timeout; elapsed {duration:.2f}s"

        # Coordination result status must be degraded to 'partial'
        assert result.status == "partial"
        assert "dataflow" in result.failed_agents

        # Fast agent (dependency_risk) should have succeeded
        assert result.dependency_output is not None

        # Verify database record for AgentCoordinationRun
        stmt = select(AgentCoordinationRun).where(AgentCoordinationRun.review_run_id == run_id)
        coord_res = await session.execute(stmt)
        coord = coord_res.scalar_one()
        assert coord.status == "partial"

        # Verify database records for AgentTaskExecution
        task_stmt = select(AgentTaskExecution).where(
            AgentTaskExecution.coordination_id == coord.coordination_id
        )
        tasks_res = await session.execute(task_stmt)
        tasks = {t.agent_name: t for t in tasks_res.scalars().all()}

        assert "dataflow" in tasks
        dataflow_task = tasks["dataflow"]
        assert dataflow_task.status == "timeout"
        assert dataflow_task.error_message == "barrier_timeout"

        assert "dependency_risk" in tasks
        assert tasks["dependency_risk"].status == "completed"

        # Verify AuditEvent logging for barrier timeout failure
        import json
        audit_stmt = select(AuditEvent).where(
            AuditEvent.action == AuditAction.AGENT_EXECUTION_FAILED
        )
        audit_res = await session.execute(audit_stmt)
        failed_audits = audit_res.scalars().all()
        assert any(
            json.loads(a.metadata_json or "{}").get("reason") == "barrier_timeout"
            and json.loads(a.metadata_json or "{}").get("agent") == "dataflow"
            for a in failed_audits
        )
