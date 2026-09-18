import sys
import uuid
from pathlib import Path

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.models.finding import Finding, FindingOrigin, Severity
from app.models.review import ReviewRun, ReviewStatus
from app.reports.base import build_report_data
from app.reports.html_report import HTMLReportRenderer


def test_html_report_rendering_and_escaping():
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    run = ReviewRun(
        run_id=run_id,
        tenant_id=tenant_id,
        status=ReviewStatus.completed,
    )

    # Injected title containing malicious script
    finding = Finding(
        finding_id=uuid.uuid4(),
        run_id=run_id,
        tenant_id=tenant_id,
        fingerprint="fp123",
        origin=FindingOrigin.rule,
        rule_id="SEC-001",
        category="security",
        severity=Severity.critical,
        confidence=0.9,
        title="Cross-Site Scripting <script>alert(1)</script>",
        rationale="Payload with <b>HTML</b> tags",
        remediation="Ensure proper <i>escaping</i>",
    )

    data = build_report_data(run, [finding])
    renderer = HTMLReportRenderer(template_name="report.html")
    html_output = renderer.render(data).decode("utf-8")

    # Verify autoescape
    assert "<script>alert(1)</script>" not in html_output
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_output

    # Verify WCAG structure
    assert "<!DOCTYPE html>" in html_output
    assert '<meta name="viewport"' in html_output
    assert "<title>" in html_output
    assert "<h1>" in html_output
    assert "<h2>" in html_output
    assert "<th>" in html_output
    assert "<td>" in html_output


def test_executive_html_report_rendering():
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
        fingerprint="fp456",
        origin=FindingOrigin.rule,
        rule_id="SEC-002",
        category="security",
        severity=Severity.high,
        confidence=0.88,
        title="High Severity Risk",
        rationale="Detailed technical rationale",
        remediation="Mitigate immediately",
    )

    data = build_report_data(run, [finding])
    renderer = HTMLReportRenderer(template_name="executive.html")
    html_output = renderer.render(data).decode("utf-8")

    assert "Vigil Executive Security Summary" in html_output
    assert "Top 5 Immediate Risk Priorities" in html_output
    assert "High Severity Risk" in html_output
