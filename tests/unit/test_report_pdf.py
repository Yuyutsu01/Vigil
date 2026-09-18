import io
import sys
import uuid
from pathlib import Path
import pypdf
import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.models.finding import Finding, FindingOrigin, Severity
from app.models.review import ReviewRun, ReviewStatus
from app.reports.base import build_report_data
from app.reports.pdf_report import PDFReportRenderer, _generate_fallback_pdf, safe_url_fetcher


def test_pdf_report_rendering():
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
        fingerprint="fp789",
        origin=FindingOrigin.rule,
        rule_id="VIGIL-SEC-001",
        category="security",
        severity=Severity.critical,
        confidence=0.98,
        title="Hardcoded AWS Access Key",
        rationale="Exposed secret in source",
        remediation="Rotate key immediately",
    )

    data = build_report_data(run, [finding])
    renderer = PDFReportRenderer(template_name="report.html")
    pdf_bytes = renderer.render(data)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 0
    # Must be valid PDF format starting with %PDF-
    assert pdf_bytes.startswith(b"%PDF-")


def test_pdf_report_executive_rendering():
    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    run = ReviewRun(
        run_id=run_id,
        tenant_id=tenant_id,
        status=ReviewStatus.completed,
    )

    data = build_report_data(run, [])
    renderer = PDFReportRenderer(template_name="executive.html")
    pdf_bytes = renderer.render(data)

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")


def test_safe_url_fetcher_refuses_remote_resources():
    """Verify that safe_url_fetcher unconditionally blocks remote resource fetching."""
    with pytest.raises(PermissionError) as exc_info:
        safe_url_fetcher("http://169.254.169.254/latest/meta-data/")
    assert "SSRF Refusal" in str(exc_info.value)

    with pytest.raises(PermissionError):
        safe_url_fetcher("https://evil.com/font.woff")

    with pytest.raises(PermissionError):
        safe_url_fetcher("ftp://internal.corp/secret.txt")


def test_fallback_pdf_xref_valid():
    """Verify fallback PDF xref table has valid computed byte offsets and parses cleanly (M2)."""
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
        fingerprint="fp123",
        origin=FindingOrigin.rule,
        rule_id="VIGIL-SEC-002",
        category="security",
        severity=Severity.high,
        confidence=0.95,
        title="SQL Injection",
        rationale="Raw query formatting",
        remediation="Use parameterized queries",
    )
    data = build_report_data(run, [finding])

    # Render fallback PDF directly
    pdf_bytes = _generate_fallback_pdf(data, "report.html")
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-1.4\n")

    # Parse with pypdf - assert no exceptions on cross-reference parsing
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    # Assert page count is 1
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "Vigil Security Review Report" in text
    assert "SQL Injection" in text

