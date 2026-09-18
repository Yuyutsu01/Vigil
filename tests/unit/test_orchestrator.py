"""
Unit tests for Multi-Agent Orchestrator (FR-108).
Validates DAG sequencing, context snapshot immutability, and specialist agent dispatch.
"""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import uuid
import pytest

from app.agents.llm_provider import MockProvider
from app.agents.orchestrator import (
    MultiAgentOrchestrator,
    OrchestrationResult,
    ReviewContextSnapshot,
)


def test_review_context_snapshot_immutability():
    """
    [FR-108 Core Invariant] Asserts that ReviewContextSnapshot is strictly immutable.
    Attempts to mutate attributes raise FrozenInstanceError.
    """
    snapshot = ReviewContextSnapshot(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="print('hello')",
        language="python",
    )

    with pytest.raises(FrozenInstanceError):
        snapshot.source_code = "print('tampered')"

    with pytest.raises(FrozenInstanceError):
        snapshot.language = "javascript"


@pytest.mark.asyncio
async def test_orchestrator_subtree1_execution():
    """
    Validates end-to-end execution of Subtree 1 (A11 Dependency Risk, A3 Security Reasoning,
    A4 Quality Review, A12 Dataflow Investigation) and subsequent A10 Risk Scoring and A14 Executive Summary.
    """
    code = (
        "import os\n"
        "def handler(request):\n"
        "    cmd = request.args.get('cmd')\n"
        "    os.system(cmd)\n"
    )
    manifest = "requests==2.25.0\n"

    snapshot = ReviewContextSnapshot(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code=code,
        language="python",
        manifest_files={"requirements.txt": manifest},
    )

    provider = MockProvider()
    orchestrator = MultiAgentOrchestrator(
        provider=provider,
        barrier_timeout=10.0,
    )

    result = await orchestrator.run(snapshot)

    assert isinstance(result, OrchestrationResult)
    assert result.status in {"completed", "partial"}
    assert result.total_wall_clock_ms >= 0

    # Specialist agent tasks must be recorded
    task_names = set(result.task_executions.keys())
    assert "dependency_risk" in task_names
    assert "security" in task_names
    assert "quality" in task_names
    assert "dataflow" in task_names
    assert "executive_summary" in task_names

    # Output artifacts must be populated
    assert result.dependency_output is not None
    assert result.dataflow_output is not None
    assert result.executive_summary_output is not None
    assert len(result.final_findings) >= 1
