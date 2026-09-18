"""
Integration tests for the Specialist Multi-Agent Kill Switch (FR-108, IC10, B3).
Asserts that when vigil:killswitch:multi_agent is set to true in Redis, all
specialist agents (A10-A14) are bypassed and the review completes with Phase 1-4 findings only.
"""
from __future__ import annotations

import uuid
import pytest

from app.agents.orchestrator import MultiAgentOrchestrator, ReviewContextSnapshot
from app.agents.llm_provider import MockProvider
from app.models.repository import RepositoryPolicy


class MockKillswitchRedis:
    def __init__(self, initial_state: dict | None = None):
        self.store = initial_state or {}

    async def get(self, key: str):
        val = self.store.get(key)
        return val

    async def set(self, key: str, value: str):
        self.store[key] = value

    async def delete(self, key: str):
        self.store.pop(key, None)


@pytest.mark.asyncio
async def test_killswitch_bypasses_all_specialist_agents():
    """
    Set vigil:killswitch:multi_agent = true in Redis. Trigger a review.
    Assert no specialist agent (A10-A14) is invoked.
    Assert the review completes with Phase 1-4 findings only.
    """
    mock_redis = MockKillswitchRedis({"vigil:killswitch:multi_agent": "true"})

    orchestrator = MultiAgentOrchestrator(
        provider=MockProvider(),
        redis_client=mock_redis,
    )

    snapshot = ReviewContextSnapshot(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="import os\nos.system('echo dangerous')",
        language="python",
        manifest_files={"requirements.txt": "requests==2.25.0"},
    )

    policy = RepositoryPolicy(
        enable_dependency_risk=True,
        enable_dataflow_investigation=True,
        enable_specialist_risk_scoring=True,
        enable_executive_summary=True,
    )

    result = await orchestrator.run(snapshot=snapshot, policy=policy, enable_patch=False)

    # Invariants under active kill switch:
    assert result.status == "completed"

    # Verify no Phase 5 specialist agent (A10-A14) was executed
    executed_agents = set(result.task_executions.keys())
    specialist_agents = {"dependency_risk", "dataflow", "risk_scoring", "test_generation", "executive_summary"}
    assert executed_agents.isdisjoint(specialist_agents), f"Specialists executed despite killswitch: {executed_agents & specialist_agents}"

    # Verify Phase 1-4 outputs exist
    assert len(result.final_findings) >= 1
    assert result.dependency_output is None
    assert result.dataflow_output is None
    assert result.risk_scoring_output is None
    assert result.test_generation_output is None
    assert result.executive_summary_output is None


@pytest.mark.asyncio
async def test_killswitch_off_runs_specialists():
    """
    Set vigil:killswitch:multi_agent = false. Trigger a review
    with specialist flags enabled. Assert at least one specialist agent ran.
    """
    mock_redis = MockKillswitchRedis({"vigil:killswitch:multi_agent": "false"})

    orchestrator = MultiAgentOrchestrator(
        provider=MockProvider(),
        redis_client=mock_redis,
    )

    snapshot = ReviewContextSnapshot(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="import os\nos.system('echo dangerous')",
        language="python",
        manifest_files={"requirements.txt": "requests==2.25.0"},
    )

    policy = RepositoryPolicy(
        enable_dependency_risk=True,
        enable_dataflow_investigation=True,
        enable_specialist_risk_scoring=True,
        enable_executive_summary=True,
    )

    result = await orchestrator.run(snapshot=snapshot, policy=policy, enable_patch=False)

    # Invariants under inactive kill switch:
    executed_agents = set(result.task_executions.keys())
    assert "dependency_risk" in executed_agents or "security" in executed_agents
    assert any(
        agent in executed_agents
        for agent in ["dependency_risk", "dataflow", "risk_scoring", "executive_summary"]
    )
    assert result.executive_summary_output is not None or result.dependency_output is not None
