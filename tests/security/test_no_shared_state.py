"""
Security tests for agent state isolation and immutability (FR-108, B3).
Asserts that concurrent agent executions operate on disjoint state and that
ReviewContextSnapshot is frozen against mutation.
"""
from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError
import uuid
import pytest

from app.agents.orchestrator import ReviewContextSnapshot
from app.agents.risk_scoring_agent import RiskScoringAgent, RiskScoringInput, SanitizedPrecedent
from app.agents.dataflow_agent import DataflowAgent, DataflowInput
from app.agents.llm_provider import MockProvider


@pytest.mark.asyncio
async def test_concurrent_agents_do_not_share_mutable_state():
    """
    Run two concurrent invocations of an agent with different inputs.
    Assert outputs are independent — mutating one result does not affect the other.
    """
    agent1 = DataflowAgent()
    agent2 = DataflowAgent()

    input1 = DataflowInput(
        source_code="def f1(req):\n    v1 = req.args.get('a')\n    eval(v1)\n",
        language="python",
        candidate_sinks=[{"sink_symbol": "eval", "line_number": 3, "expression": "eval(v1)"}],
    )
    input2 = DataflowInput(
        source_code="def f2(req):\n    v2 = int(req.args.get('b'))\n    eval(v2)\n",
        language="python",
        candidate_sinks=[{"sink_symbol": "eval", "line_number": 3, "expression": "eval(v2)"}],
    )

    out1, out2 = await asyncio.gather(
        agent1.analyze_dataflow(input1),
        agent2.analyze_dataflow(input2),
    )

    assert len(out1.confirmed_traces) == 1
    assert len(out2.confirmed_traces) == 1

    # Verify distinct results
    assert out1.confirmed_traces[0].sanitizer_detected is False
    assert out2.confirmed_traces[0].sanitizer_detected is True

    # Mutate one result object in place
    out1.validated_findings.append({"finding_id": "mutated_finding"})

    # Assert out2 is completely unaffected
    assert len(out1.validated_findings) != len(out2.validated_findings)
    assert not any(f.get("finding_id") == "mutated_finding" for f in out2.validated_findings)


@pytest.mark.asyncio
async def test_immutable_snapshot_cannot_be_mutated():
    """
    Attempt to mutate ReviewContextSnapshot fields. Assert
    FrozenInstanceError or TypeError is raised.
    """
    snapshot = ReviewContextSnapshot(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="import os\nos.system('test')",
        language="python",
    )

    with pytest.raises((FrozenInstanceError, TypeError, AttributeError)):
        snapshot.source_code = "modified_source_code"

    with pytest.raises((FrozenInstanceError, TypeError, AttributeError)):
        snapshot.language = "ruby"

    with pytest.raises((FrozenInstanceError, TypeError, AttributeError)):
        snapshot.target_file_path = "hacked.py"
