import sys
import uuid
from pathlib import Path

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.models.finding import Finding, FindingOrigin, Severity
from app.models.review import ReviewRun, ReviewStatus
from app.reports.base import build_report_data
from app.reports.html_report import HTMLReportRenderer


def test_html_report_escapes_script_injection():
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
        fingerprint="fp_xss_test",
        origin=FindingOrigin.rule,
        rule_id="VIGIL-SEC-001",
        category="security",
        severity=Severity.critical,
        confidence=0.99,
        title="<script>alert(1)</script>",
        rationale="Payload: <img src=x onerror=alert(2)>",
        remediation="Ensure <b>strict</b> escaping",
    )

    data = build_report_data(run, [finding])
    renderer = HTMLReportRenderer(template_name="report.html")
    rendered_html = renderer.render(data).decode("utf-8")

    # The raw unescaped script tag must NEVER appear in output
    assert "<script>alert(1)</script>" not in rendered_html
    assert "<img src=x onerror=alert(2)>" not in rendered_html

    # The escaped versions must appear
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in rendered_html
    assert "&lt;img src=x onerror=alert(2)&gt;" in rendered_html
