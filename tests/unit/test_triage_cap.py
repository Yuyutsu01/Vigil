"""
Unit tests for triage severity capping on LLM findings (Bug 2 fix verification).
Quality findings with Critical/High severity must be capped to Medium.
Security findings must retain their original severity.
Deduplication on identical fields must preserve the security finding.
"""
import sys
from pathlib import Path
import uuid
import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.agents.capabilities import capability_triage
from app.agents.state import ReviewGraphState
from app.models.finding import EvidenceKind, Severity
from app.schemas.finding import RawLLMFinding


@pytest.mark.asyncio
async def test_quality_severity_capping():
    """Verify that quality findings are capped to Medium, while security findings are uncapped."""
    sec_crit = RawLLMFinding(
        rule_id="SEC-001",
        category="security",
        severity=Severity.critical,
        confidence=0.95,
        title="Critical Remote Code Execution",
        rationale="Arbitrary eval called",
        remediation="Do not use eval",
        evidence_kind=EvidenceKind.llm_reasoning,
        ast_path="line_10/eval",
    )

    qual_crit = RawLLMFinding(
        rule_id="QUAL-001",
        category="maintainability",
        severity=Severity.critical,
        confidence=0.85,
        title="Function Too Complex",
        rationale="Cyclomatic complexity is 50",
        remediation="Refactor into smaller functions",
        evidence_kind=EvidenceKind.llm_reasoning,
        ast_path="line_20/func",
    )

    qual_high = RawLLMFinding(
        rule_id="QUAL-002",
        category="maintainability",
        severity=Severity.high,
        confidence=0.80,
        title="Excessive Parameters",
        rationale="Function takes 12 arguments",
        remediation="Use a config object",
        evidence_kind=EvidenceKind.llm_reasoning,
        ast_path="line_30/params",
    )

    qual_low = RawLLMFinding(
        rule_id="QUAL-003",
        category="maintainability",
        severity=Severity.low,
        confidence=0.70,
        title="Naming Convention",
        rationale="Variable name is too short",
        remediation="Rename variable",
        evidence_kind=EvidenceKind.llm_reasoning,
        ast_path="line_40/var",
    )

    state = ReviewGraphState(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="def f(): pass",
        language="python",
        parse_successful=True,
    )
    state.llm_security_findings = [sec_crit]
    state.llm_quality_findings = [qual_crit, qual_high, qual_low]

    result_state = await capability_triage(state)
    findings_by_rule = {f.rule_id: f for f in result_state.final_findings}

    # Assert: security Critical stays Critical
    assert findings_by_rule["SEC-001"].severity == "Critical"

    # Assert: quality Critical becomes Medium
    assert findings_by_rule["QUAL-001"].severity == "Medium"

    # Assert: quality High becomes Medium
    assert findings_by_rule["QUAL-002"].severity == "Medium"

    # Assert: quality Low stays Low
    assert findings_by_rule["QUAL-003"].severity == "Low"


@pytest.mark.asyncio
async def test_identical_security_and_quality_findings_edge_case():
    """
    Edge case: security Critical and quality Critical with IDENTICAL field values.
    Security finding must remain Critical, and deduplication preserves the Critical finding.
    """
    sec_crit = RawLLMFinding(
        rule_id="SHARED-001",
        category="security",
        severity=Severity.critical,
        confidence=0.90,
        title="Shared Vulnerability Title",
        rationale="Shared Rationale",
        remediation="Shared Remediation",
        evidence_kind=EvidenceKind.llm_reasoning,
        ast_path="line_5/shared",
        matched_text="shared_code()",
    )

    qual_crit = RawLLMFinding(
        rule_id="SHARED-001",
        category="security",
        severity=Severity.critical,
        confidence=0.90,
        title="Shared Vulnerability Title",
        rationale="Shared Rationale",
        remediation="Shared Remediation",
        evidence_kind=EvidenceKind.llm_reasoning,
        ast_path="line_5/shared",
        matched_text="shared_code()",
    )

    state = ReviewGraphState(
        run_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        source_code="shared_code()",
        language="python",
        parse_successful=True,
    )
    state.llm_security_findings = [sec_crit]
    state.llm_quality_findings = [qual_crit]

    result_state = await capability_triage(state)

    # Identical fingerprint -> deduplicated to single finding, keeping the Critical security finding
    shared_findings = [f for f in result_state.final_findings if f.rule_id == "SHARED-001"]
    assert len(shared_findings) == 1
    assert shared_findings[0].severity == "Critical"
