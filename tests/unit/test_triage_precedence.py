"""
Unit tests for triage precedence: rule > tool > agent (B4).
Verifies:
- rule + tool + llm with same fingerprint -> rule wins
- tool + llm with same fingerprint -> tool wins
- llm only -> llm wins
- all three distinct fingerprints -> all three survive
- final order is severity-then-confidence
"""
import sys
import uuid
from pathlib import Path
import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.agents.capabilities import capability_triage
from app.agents.state import ReviewGraphState
from app.models.finding import EvidenceKind, FindingOrigin
from app.rules.engine import DetectedFinding
from app.schemas.finding import RawLLMFinding, Severity


def _make_finding(
    rule_id: str = "SEC-001",
    ast_path: str = "Call[func=eval]",
    matched_text: str = "eval(x)",
    origin: FindingOrigin = FindingOrigin.rule,
    severity: str = "High",
    confidence: float = 0.9,
    tool_name: str | None = None,
) -> DetectedFinding:
    return DetectedFinding(
        rule_id=rule_id,
        category="security",
        severity=severity,
        confidence=confidence,
        title=f"Finding from {origin.value}",
        rationale="Security issue",
        remediation="Fix it",
        evidence_kind=EvidenceKind.ast_node,
        ast_path=ast_path,
        matched_text=matched_text,
        origin=origin,
        tool_name=tool_name,
    )


def _make_llm_finding(
    rule_id: str = "SEC-001",
    ast_path: str = "Call[func=eval]",
    matched_text: str = "eval(x)",
    evidence_kind: EvidenceKind = EvidenceKind.ast_node,
    severity: Severity = Severity.high,
    confidence: float = 0.75,
) -> RawLLMFinding:
    return RawLLMFinding(
        rule_id=rule_id,
        category="security",
        severity=severity,
        confidence=confidence,
        title="LLM finding",
        rationale="LLM detected issue",
        remediation="Fix LLM issue",
        evidence_kind=evidence_kind,
        ast_path=ast_path,
        matched_text=matched_text,
    )


@pytest.mark.asyncio
async def test_rule_wins_over_tool_and_llm():
    """When rule, tool, and LLM report same issue, rule finding wins."""
    rule_f = _make_finding(origin=FindingOrigin.rule, confidence=0.99)
    tool_f = _make_finding(origin=FindingOrigin.tool, tool_name="bandit", confidence=0.85)
    llm_f = _make_llm_finding(confidence=0.70)

    state = ReviewGraphState(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="eval(x)",
        language="python",
        rule_findings=[rule_f],
        tool_findings=[tool_f],
        llm_security_findings=[llm_f],
    )

    result = await capability_triage(state)
    assert len(result.final_findings) == 1
    winner = result.final_findings[0]
    assert winner.origin == FindingOrigin.rule
    assert winner.confidence == 0.99


@pytest.mark.asyncio
async def test_tool_wins_over_llm():
    """When tool and LLM report same issue without rule finding, tool finding wins."""
    tool_f = _make_finding(origin=FindingOrigin.tool, tool_name="bandit", confidence=0.85)
    llm_f = _make_llm_finding(confidence=0.70)

    state = ReviewGraphState(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="eval(x)",
        language="python",
        rule_findings=[],
        tool_findings=[tool_f],
        llm_security_findings=[llm_f],
    )

    result = await capability_triage(state)
    assert len(result.final_findings) == 1
    winner = result.final_findings[0]
    assert winner.origin == FindingOrigin.tool
    assert winner.tool_name == "bandit"
    assert winner.confidence == 0.85


@pytest.mark.asyncio
async def test_llm_only_wins():
    """When only LLM reports an issue, LLM finding survives."""
    llm_f = _make_llm_finding(confidence=0.70)

    state = ReviewGraphState(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="eval(x)",
        language="python",
        rule_findings=[],
        tool_findings=[],
        llm_security_findings=[llm_f],
    )

    result = await capability_triage(state)
    assert len(result.final_findings) == 1
    winner = result.final_findings[0]
    assert winner.origin == FindingOrigin.agent
    assert winner.confidence == 0.70


@pytest.mark.asyncio
async def test_all_three_distinct_survive_and_sorted():
    """Distinct findings all survive and are sorted by severity then confidence."""
    # 1. Critical rule finding
    rule_f = _make_finding(
        rule_id="RULE-1",
        ast_path="path/1",
        matched_text="match1",
        origin=FindingOrigin.rule,
        severity="Critical",
        confidence=0.80,
    )
    # 2. Medium tool finding
    tool_f = _make_finding(
        rule_id="TOOL-1",
        ast_path="path/2",
        matched_text="match2",
        origin=FindingOrigin.tool,
        tool_name="ruff",
        severity="Medium",
        confidence=0.95,
    )
    # 3. High LLM finding
    llm_f = _make_llm_finding(
        rule_id="LLM-1",
        ast_path="path/3",
        matched_text="match3",
        severity=Severity.high,
        confidence=0.88,
    )

    state = ReviewGraphState(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="...",
        language="python",
        rule_findings=[rule_f],
        tool_findings=[tool_f],
        llm_security_findings=[llm_f],
    )

    result = await capability_triage(state)
    assert len(result.final_findings) == 3

    # Order must be: Critical -> High -> Medium
    assert result.final_findings[0].severity == "Critical"
    assert result.final_findings[0].origin == FindingOrigin.rule

    assert result.final_findings[1].severity == "High"
    assert result.final_findings[1].origin == FindingOrigin.agent

    assert result.final_findings[2].severity == "Medium"
    assert result.final_findings[2].origin == FindingOrigin.tool
