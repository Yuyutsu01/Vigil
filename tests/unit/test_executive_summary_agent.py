"""
Unit tests for A14: Executive Summary Agent (FR-108, M4).
Validates narrative synthesis, composite risk score computation, and partial-failure prefixing.
"""
from __future__ import annotations

import pytest

from app.agents.executive_summary_agent import (
    ExecutiveSummaryAgent,
    ExecutiveSummaryInput,
    ExecutiveSummaryOutput,
    run_executive_summary_agent,
)
from app.agents.llm_provider import MockProvider
from app.schemas.finding import RawFinding


@pytest.mark.asyncio
async def test_executive_summary_completed_review():
    """Validates summary generation for a completed multi-agent review."""
    findings = [
        RawFinding(
            tool_name="security_agent",
            rule_id="SEC-001",
            severity_raw="Critical",
            message="SQL injection in login query",
            file_path="app/auth.py",
            start_line=45,
        ),
        RawFinding(
            tool_name="quality_agent",
            rule_id="QUAL-002",
            severity_raw="Medium",
            message="Complex cyclomatic complexity in router",
            file_path="app/router.py",
            start_line=10,
        ),
    ]

    inp = ExecutiveSummaryInput(
        final_findings=findings,
        review_metadata={"repo": "acme/web-service"},
        agent_execution_summary={
            "dependency_risk": "completed",
            "security": "completed",
            "quality": "completed",
            "dataflow": "completed",
        },
    )

    provider = MockProvider()
    agent = ExecutiveSummaryAgent(provider=provider)
    output = await agent.generate_summary(inp)

    assert isinstance(output, ExecutiveSummaryOutput)
    assert output.composite_risk_score > 0.0
    assert len(output.primary_risk_areas) >= 1
    assert len(output.remediation_roadmap) >= 1
    assert "Partial review:" not in output.executive_summary


@pytest.mark.asyncio
async def test_executive_summary_partial_failure_prefix():
    """
    [M4] Partial-Failure Behavior: When one or more agents fail or time out,
    executive summary explicitly prefixes output with 'Partial review: N of M agents completed.'.
    """
    findings = [
        RawFinding(
            tool_name="security_agent",
            rule_id="SEC-001",
            severity_raw="High",
            message="Hardcoded API key",
            file_path="config.py",
            start_line=5,
        )
    ]

    inp = ExecutiveSummaryInput(
        final_findings=findings,
        review_metadata={},
        agent_execution_summary={
            "dependency_risk": "completed",
            "security": "completed",
            "quality": "completed",
            "dataflow": "failed",  # A12 failed
        },
    )

    output = await run_executive_summary_agent(inp)
    assert isinstance(output, ExecutiveSummaryOutput)
    # 3 of 4 completed
    assert output.executive_summary.startswith("Partial review: 3 of 4 agents completed.")


@pytest.mark.asyncio
async def test_executive_summary_skips_llm_on_empty_findings():
    """
    IC6: When final_findings is empty, ExecutiveSummaryAgent skips LLM call
    and returns a deterministic empty summary.
    """
    from unittest.mock import AsyncMock
    mock_provider = MockProvider()
    mock_provider.complete = AsyncMock()

    agent = ExecutiveSummaryAgent(provider=mock_provider)
    output = await agent.generate(ExecutiveSummaryInput(
        final_findings=[],
        review_metadata={},
        agent_execution_summary={},
    ))
    assert mock_provider.complete.call_count == 0
    assert "No findings" in output.executive_summary
