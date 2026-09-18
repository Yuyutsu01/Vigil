"""
Unit tests for A12: Dataflow Investigation Agent (FR-108).
Validates AST taint tracking from user-controlled sources to dangerous sinks,
sanitizer detection, and multi-hop traversal.
"""
from __future__ import annotations

import pytest

from app.agents.dataflow_agent import (
    DataflowInput,
    DataflowInvestigationAgent,
    DataflowOutput,
    run_dataflow_agent,
)


@pytest.mark.asyncio
async def test_dataflow_unsanitized_eval_sink():
    """Tests detection of unsanitized taint flow from request parameter into eval()."""
    code = (
        "def process_input(request):\n"
        "    raw = request.args.get('code')\n"
        "    payload = raw\n"
        "    result = eval(payload)\n"
        "    return result\n"
    )

    sinks = [{"sink_symbol": "eval", "line_number": 4, "expression": "eval(payload)"}]
    inp = DataflowInput(source_code=code, candidate_sinks=sinks)

    output = await run_dataflow_agent(inp)

    assert isinstance(output, DataflowOutput)
    assert len(output.confirmed_traces) == 1
    trace = output.confirmed_traces[0]
    assert trace.sink_symbol == "eval"
    assert trace.source_symbol == "payload" or "raw" in [h.symbol for h in trace.hops]
    assert trace.sanitizer_detected is False
    assert len(output.validated_findings) == 1
    assert "EVAL" in output.validated_findings[0]["rule_id"]


@pytest.mark.asyncio
async def test_dataflow_sanitized_flow():
    """Tests that detecting a recognized sanitizer (int()) neutralizes taint and prevents finding."""
    code = (
        "def calculate_tax(request):\n"
        "    user_val = request.args.get('amount')\n"
        "    safe_val = int(user_val)\n"
        "    res = eval(safe_val)\n"
        "    return res\n"
    )

    sinks = [{"sink_symbol": "eval", "line_number": 4, "expression": "eval(safe_val)"}]
    inp = DataflowInput(source_code=code, candidate_sinks=sinks)

    agent = DataflowInvestigationAgent()
    output = await agent.investigate_dataflow(inp)

    assert isinstance(output, DataflowOutput)
    if output.confirmed_traces:
        trace = output.confirmed_traces[0]
        assert trace.sanitizer_detected is True
    # Sanitized trace must not produce an unmitigated security finding
    assert len(output.validated_findings) == 0


@pytest.mark.asyncio
async def test_dataflow_no_hops_to_safe_sink():
    """Tests that constant arguments to sinks produce zero taint traces."""
    code = (
        "def run_constant():\n"
        "    eval('1 + 1')\n"
    )

    sinks = [{"sink_symbol": "eval", "line_number": 2, "expression": "eval('1 + 1')"}]
    inp = DataflowInput(source_code=code, candidate_sinks=sinks)

    output = await run_dataflow_agent(inp)
    assert len(output.confirmed_traces) == 0
    assert len(output.validated_findings) == 0
