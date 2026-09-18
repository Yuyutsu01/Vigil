"""
Integration tests for Multi-Agent Coordination (FR-108).
Validates end-to-end execution of all 5 specialist agents with database persistence.
"""
from __future__ import annotations

import uuid
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
from app.models.review import ReviewRun, ReviewStatus
from app.models.tenant import Tenant
import app.models  # ensure models are registered


@pytest.mark.asyncio
async def test_end_to_end_specialist_agents_coordination():
    """
    Executes all 5 specialist agents (A10, A11, A12, A13, A14) through MultiAgentOrchestrator
    and verifies database records (AgentCoordinationRun, AgentTaskExecution).
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id = uuid.uuid4()
        run_id = uuid.uuid4()

        # Seed tenant, source artifact, and review run
        from datetime import datetime, timezone
        from app.models.review import SourceArtifact
        tenant = Tenant(tenant_id=tenant_id, name="Coordination Test Tenant")
        artifact_id = uuid.uuid4()
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content="print(1)",
            checksum="chk123",
            language="python",
            size_bytes=8,
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

        # Input code with vulnerable call and dependency manifest
        code = (
            "import os\n"
            "def handle_query(req):\n"
            "    target = req.args.get('target')\n"
            "    os.system(target)\n"
        )
        manifest = "requests==2.25.0\n"

        snapshot = ReviewContextSnapshot(
            run_id=run_id,
            tenant_id=tenant_id,
            source_code=code,
            language="python",
            manifest_files={"requirements.txt": manifest},
            patch_diff="--- a/main.py\n+++ b/main.py\n@@ -1,2 +1,2 @@\n-os.system(target)\n+subprocess.run([target])\n",
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
        orchestrator = MultiAgentOrchestrator(
            provider=provider,
            db=session,
            barrier_timeout=15.0,
        )

        # Run multi-agent orchestrator
        result = await orchestrator.run(
            snapshot=snapshot,
            policy=policy,
            enable_patch=True,
        )

        await session.commit()

        assert result.status in {"completed", "partial"}

        # Query database coordination run
        stmt = select(AgentCoordinationRun).where(AgentCoordinationRun.review_run_id == run_id)
        res = await session.execute(stmt)
        coord = res.scalar_one_or_none()
        assert coord is not None
        assert coord.status == result.status
        assert coord.total_wall_clock_ms >= 0

        # Query database task executions
        task_stmt = select(AgentTaskExecution).where(
            AgentTaskExecution.coordination_id == coord.coordination_id
        )
        task_res = await session.execute(task_stmt)
        tasks = task_res.scalars().all()
        agent_names = {t.agent_name for t in tasks}

        assert "dependency_risk" in agent_names
        assert "security" in agent_names
        assert "quality" in agent_names
        assert "dataflow" in agent_names
        assert "risk_scoring" in agent_names
        assert "executive_summary" in agent_names
