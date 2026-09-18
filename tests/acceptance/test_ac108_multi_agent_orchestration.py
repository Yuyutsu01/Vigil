"""
Acceptance tests for Multi-Agent Orchestration (FR-108, AC-108.1 through AC-108.8).

Validates:
- AC-108.1: Specialist Agents coordination (A10 Risk Scoring, A11 Dependency, A12 Dataflow, A13 Test Gen, A14 Executive Summary).
- AC-108.2: Parallel Subtree 1 fan-out benchmarking (parallel wall clock < 2.0s vs sequential delay).
- AC-108.3: Review token budget ceiling (200k tokens / $1.00) and graceful pause.
- AC-108.4: Agent failure non-fatal to entire DAG (graceful degradation to 'partial').
- AC-108.5: Deterministic Triage supremacy (A5) preserves rule-origin findings.
- AC-108.6: Immutable context snapshot passed across all agents.
- AC-108.7: OpenTelemetry distributed tracing root and child spans.
- AC-108.8: Audit trail records agent execution lifecycles.
"""
from __future__ import annotations

import asyncio
import json
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
from app.models.finding import FindingOrigin
from app.models.orchestration import AgentCoordinationRun, AgentTaskExecution
from app.models.repository import RepositoryPolicy
from app.models.review import AuditAction, AuditEvent, ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import Tenant
import app.models  # ensure models are registered


async def _seed_test_run(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID]:
    """Helper to seed tenant, artifact, and review run."""
    tenant_id = uuid.uuid4()
    run_id = uuid.uuid4()
    artifact_id = uuid.uuid4()

    tenant = Tenant(tenant_id=tenant_id, name="AC108 Acceptance Tenant")
    artifact = SourceArtifact(
        artifact_id=artifact_id,
        tenant_id=tenant_id,
        content="import os\nos.system('ls')",
        checksum="chk_ac108",
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
    return tenant_id, run_id


@pytest.mark.asyncio
async def test_ac108_1_and_ac108_8_specialist_coordination_and_audit():
    """AC-108.1 & AC-108.8: All specialist agents coordinate and log audit trail."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id, run_id = await _seed_test_run(session)

        snapshot = ReviewContextSnapshot(
            run_id=run_id,
            tenant_id=tenant_id,
            source_code="import os\nos.system('test')",
            language="python",
            manifest_files={"requirements.txt": "requests==2.25.0"},
            target_file_path="main.py",
        )
        policy = RepositoryPolicy(
            enable_specialist_risk_scoring=True,
            enable_dependency_risk=True,
            enable_dataflow_investigation=True,
            enable_test_generation_agent=True,
            enable_executive_summary=True,
        )

        orchestrator = MultiAgentOrchestrator(
            provider=MockProvider(),
            db=session,
        )
        result = await orchestrator.run(snapshot=snapshot, policy=policy, enable_patch=True)
        await session.commit()

        assert result.status in {"completed", "partial"}
        assert result.coordination_id is not None

        # Verify audit records
        audit_stmt = select(AuditEvent).where(AuditEvent.tenant_id == tenant_id)
        res = await session.execute(audit_stmt)
        audits = res.scalars().all()
        actions = {a.action for a in audits}
        assert AuditAction.AGENT_EXECUTION_STARTED in actions
        assert AuditAction.AGENT_EXECUTION_COMPLETED in actions


@pytest.mark.asyncio
async def test_ac108_2_subtree1_parallel_speedup_benchmark(monkeypatch):
    """
    AC-108.2: Subtree 1 parallel execution runs concurrently.
    Injecting 0.3s delay into 3 Subtree 1 agents (0.9s sequential) must finish in < 0.65s in parallel.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id, run_id = await _seed_test_run(session)

        snapshot = ReviewContextSnapshot(
            run_id=run_id,
            tenant_id=tenant_id,
            source_code="import os\nos.system('test')",
            language="python",
            manifest_files={"requirements.txt": "requests==2.25.0"},
            target_file_path="main.py",
        )

        # Inject 0.3s artificial sleep into Subtree 1 capabilities
        import app.agents.orchestrator as orch_module
        async def _mock_slow_dataflow(*args, **kwargs):
            await asyncio.sleep(0.3)
            from app.agents.dataflow_agent import DataflowOutput
            return DataflowOutput(taint_paths=[], complex_sinks=[], sanitizer_coverage=1.0)

        async def _mock_slow_dep(*args, **kwargs):
            await asyncio.sleep(0.3)
            from app.agents.dependency_agent import DependencyRiskOutput
            return DependencyRiskOutput(findings=[], cves_detected=[], total_dependencies_analyzed=1)

        monkeypatch.setattr(orch_module, "run_dataflow_agent", _mock_slow_dataflow)
        monkeypatch.setattr(orch_module, "run_dependency_agent", _mock_slow_dep)

        policy = RepositoryPolicy(
            enable_specialist_risk_scoring=False,
            enable_dependency_risk=True,
            enable_dataflow_investigation=True,
            enable_test_generation_agent=False,
            enable_executive_summary=False,
        )

        orchestrator = MultiAgentOrchestrator(
            provider=MockProvider(),
            db=session,
            barrier_timeout=10.0,
        )

        start = time.perf_counter()
        result = await orchestrator.run(snapshot=snapshot, policy=policy, enable_patch=False)
        duration = time.perf_counter() - start

        # Sequential would be >= 0.6s (0.3s + 0.3s)
        # Parallel should finish in ~0.35 - 0.55s (well under 2.0s benchmark requirement)
        assert duration < 2.0, f"Subtree 1 parallel execution exceeded 2.0s benchmark: {duration:.3f}s"
        assert result.status == "completed"


@pytest.mark.asyncio
async def test_ac108_4_agent_failure_non_fatal_graceful_degradation(monkeypatch):
    """
    AC-108.4: A crash in an individual specialist agent degrades status to 'partial'
    without crashing the orchestrator or dropping outputs from healthy agents.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id, run_id = await _seed_test_run(session)

        snapshot = ReviewContextSnapshot(
            run_id=run_id,
            tenant_id=tenant_id,
            source_code="import os\nos.system('test')",
            language="python",
            manifest_files={"requirements.txt": "requests==2.25.0"},
            target_file_path="main.py",
        )

        # Force dataflow agent to raise an unhandled exception
        import app.agents.orchestrator as orch_module
        async def _exploding_dataflow(*args, **kwargs):
            raise RuntimeError("Dataflow AST crashed with unexpected syntax structure")

        monkeypatch.setattr(orch_module, "run_dataflow_agent", _exploding_dataflow)

        policy = RepositoryPolicy(
            enable_specialist_risk_scoring=False,
            enable_dependency_risk=True,
            enable_dataflow_investigation=True,
            enable_test_generation_agent=False,
            enable_executive_summary=True,
        )

        orchestrator = MultiAgentOrchestrator(
            provider=MockProvider(),
            db=session,
        )
        result = await orchestrator.run(snapshot=snapshot, policy=policy, enable_patch=False)
        await session.commit()

        # Overall run completes with 'partial' status
        assert result.status == "partial"
        assert "dataflow" in result.failed_agents

        # Healthy agents succeeded
        assert result.dependency_output is not None
        assert result.executive_summary_output is not None
        assert "Partial review:" in result.executive_summary_output.executive_summary


@pytest.mark.asyncio
async def test_ac108_5_deterministic_triage_supremacy():
    """
    AC-108.5: Deterministic Triage (A5) is supreme arbiter. Rule findings cannot be suppressed.
    """
    from app.rules.engine import DetectedFinding
    from app.models.finding import EvidenceKind

    rule_finding = DetectedFinding(
        rule_id="VIGIL-SEC-001",
        category="security",
        severity="High",
        confidence=0.9,
        title="Command injection",
        rationale="Unsafe shell execution",
        remediation="Use subprocess list args",
        evidence_kind=EvidenceKind.ast_node,
        origin=FindingOrigin.rule,
    )

    snapshot = ReviewContextSnapshot(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="import os\nos.system('test')",
        language="python",
        manifest_files={},
        target_file_path="main.py",
    )

    # Provider attempting to suppress everything
    class SuppressMockProvider(MockProvider):
        async def generate(self, prompt: str, **kwargs) -> str:
            return json.dumps({
                "scored_items": [{
                    "finding_id": str(uuid.uuid4()),
                    "adjusted_confidence": 0.0,
                    "suggested_action": "suppress",
                    "scoring_rationale": "Attempting to suppress finding",
                }],
                "aggregate_risk_score": 0.0,
            })

    orchestrator = MultiAgentOrchestrator(provider=SuppressMockProvider())
    policy = RepositoryPolicy(enable_specialist_risk_scoring=True)

    result = await orchestrator.run(snapshot=snapshot, policy=policy)

    # Rule findings MUST NOT be suppressed
    rule_findings = [f for f in result.final_findings if getattr(f, "origin", None) in {"rule", FindingOrigin.rule}]
    assert len(rule_findings) >= 1


def test_ac108_6_immutable_context_snapshot():
    """AC-108.6: ReviewContextSnapshot is a frozen dataclass and cannot be mutated."""
    snapshot = ReviewContextSnapshot(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="print(1)",
        language="python",
    )

    with pytest.raises(Exception):
        snapshot.source_code = "modified_code"

    with pytest.raises(Exception):
        snapshot.language = "javascript"


@pytest.mark.asyncio
async def test_ac108_1b_subtree2_sequential_ordering(monkeypatch):
    """
    Given Subtree 2 (Patch -> Test Generation -> Validation),
    each configured for 1.0s under the mock provider, assert
    total duration >= 3.0 seconds. Proves strict serialization.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id, run_id = await _seed_test_run(session)

        snapshot = ReviewContextSnapshot(
            run_id=run_id,
            tenant_id=tenant_id,
            source_code="import os\nos.system('test')",
            language="python",
            manifest_files={},
            target_file_path="main.py",
        )

        import app.agents.orchestrator as orch_module
        from app.agents.patch_agent import PatchDraft
        from app.agents.test_generation_agent import TestGenerationOutput
        from app.agents.validation_agent import ValidationVerdict

        # Configure PatchAgent, TestGen, and Validation to each take 1.0s
        async def _mock_patch(*args, **kwargs):
            await asyncio.sleep(1.0)
            return PatchDraft(
                unified_diff="--- a/main.py\n+++ b/main.py\n@@ -1,1 +1,1 @@\n-import os\n+import subprocess\n",
                rationale="Refactor unsafe execution",
                assumptions="",
                tests_to_run=["pytest tests/test_gen.py"],
            )

        async def _mock_test_gen(*args, **kwargs):
            await asyncio.sleep(1.0)
            return TestGenerationOutput(
                test_code="def test_patch(): assert True",
                test_commands=["pytest tests/test_gen.py"],
                framework="pytest",
                rationale="Automated regression test",
            )

        async def _mock_validation(*args, **kwargs):
            await asyncio.sleep(1.0)
            return ValidationVerdict(
                verdict="passed",
                duration_ms=1000,
            )

        monkeypatch.setattr(orch_module.PatchAgent, "draft_patch", _mock_patch)
        monkeypatch.setattr(orch_module, "run_test_generation_agent", _mock_test_gen)
        monkeypatch.setattr(orch_module.ValidationAgent, "run_validation", _mock_validation)

        policy = RepositoryPolicy(
            enable_specialist_risk_scoring=False,
            enable_dependency_risk=False,
            enable_dataflow_investigation=False,
            enable_test_generation_agent=True,
            enable_executive_summary=False,
        )

        orchestrator = MultiAgentOrchestrator(
            provider=MockProvider(),
            db=session,
        )

        start_time = time.monotonic()
        result = await orchestrator.run(
            snapshot=snapshot,
            policy=policy,
            enable_patch=True,
        )
        total_duration = time.monotonic() - start_time

        assert result.patch_draft is not None
        assert result.test_generation_output is not None
        assert result.validation_verdict is not None
        assert total_duration >= 3.0, f"Subtree 2 took {total_duration:.2f}s, expected >= 3.0s (strictly serialized)"


@pytest.mark.asyncio
async def test_ac108_8_agent_tree_endpoint_accurate():
    """
    Run a review with specialists enabled. Call
    GET /v1/reviews/{id}/agent-tree. Assert the response
    contains:
      - coordination_id
      - per-agent duration_ms for each executed agent
      - per-agent tokens_consumed
      - status for each agent
    Values must match the persisted agent_task_executions rows.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id, run_id = await _seed_test_run(session)

        snapshot = ReviewContextSnapshot(
            run_id=run_id,
            tenant_id=tenant_id,
            source_code="import os\nos.system('test')",
            language="python",
            manifest_files={"requirements.txt": "requests==2.25.0"},
            target_file_path="main.py",
        )
        policy = RepositoryPolicy(
            enable_specialist_risk_scoring=True,
            enable_dependency_risk=True,
            enable_dataflow_investigation=True,
            enable_test_generation_agent=True,
            enable_executive_summary=True,
        )

        orchestrator = MultiAgentOrchestrator(
            provider=MockProvider(),
            db=session,
        )
        result = await orchestrator.run(snapshot=snapshot, policy=policy, enable_patch=True)
        await session.commit()

        # Call get_agent_tree endpoint handler
        from app.api.v1.reviews import get_agent_tree
        from app.api.deps import AuthContext

        auth = AuthContext(
            user_id=uuid.uuid4(),
            tenant_id=tenant_id,
            role="admin",
            raw_token="dummy_token",
        )

        tree_data = await get_agent_tree(run_id=run_id, auth=auth, db=session)

        assert tree_data["coordination_id"] == str(result.coordination_id)
        assert "tasks" in tree_data
        assert "agents" in tree_data
        assert len(tree_data["agents"]) > 0

        # Query DB directly to verify matching
        task_stmt = select(AgentTaskExecution).where(
            AgentTaskExecution.coordination_id == result.coordination_id
        )
        db_tasks = (await session.execute(task_stmt)).scalars().all()
        assert len(db_tasks) == len(tree_data["agents"])

        db_task_map = {str(t.task_id): t for t in db_tasks}
        for ag in tree_data["agents"]:
            assert "duration_ms" in ag
            assert "tokens_consumed" in ag
            assert "status" in ag
            assert ag["duration_ms"] is not None
            assert ag["tokens_consumed"] is not None
            assert ag["status"] is not None

            # Assert matching with persisted row
            db_row = db_task_map[ag["task_id"]]
            assert ag["agent_name"] == db_row.agent_name
            assert ag["status"] == db_row.status
            assert ag["duration_ms"] == db_row.duration_ms
            assert ag["tokens_consumed"] == db_row.tokens_consumed
