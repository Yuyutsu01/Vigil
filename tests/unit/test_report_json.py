import json
import sys
import uuid
from pathlib import Path

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.models.finding import EvidenceKind, Finding, FindingOrigin, Severity
from app.models.review import ReviewRun, ReviewStatus
from app.reports.base import build_report_data
from app.reports.json_report import JSONReportRenderer


def test_json_report_structure():
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    run = ReviewRun(
        run_id=run_id,
        tenant_id=tenant_id,
        status=ReviewStatus.completed,
    )

    finding = Finding(
        finding_id=uuid.uuid4(),
        run_id=run_id,
        tenant_id=tenant_id,
        fingerprint="fp1234567890",
        origin=FindingOrigin.rule,
        rule_id="VIGIL-SEC-002",
        category="security",
        severity=Severity.critical,
        confidence=0.95,
        title="Unsafe eval execution",
        rationale="eval() executes arbitrary code",
        remediation="Use literal_eval instead",
    )

    data = build_report_data(run, [finding])
    renderer = JSONReportRenderer()
    raw_bytes = renderer.render(data)

    parsed = json.loads(raw_bytes.decode("utf-8"))
    assert parsed["run_id"] == str(run_id)
    assert parsed["tenant_id"] == str(tenant_id)
    assert parsed["total_findings"] == 1
    assert parsed["severity_counts"]["Critical"] == 1
    assert len(parsed["top_risks"]) == 1
    assert parsed["top_risks"][0]["rule_id"] == "VIGIL-SEC-002"
    assert "remediation_by_category" in parsed
    assert "appendix" in parsed
    assert "tool_versions" in parsed["appendix"]
