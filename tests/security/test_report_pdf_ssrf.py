import sys
from pathlib import Path
import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.reports.pdf_report import safe_url_fetcher


def test_pdf_rendering_refuses_remote_ssrf():
    # Cloud metadata endpoints
    with pytest.raises(PermissionError) as exc_info:
        safe_url_fetcher("http://169.254.169.254/latest/meta-data/iam/security-credentials/")
    assert "SSRF Refusal" in str(exc_info.value)

    # Local loopback services
    with pytest.raises(PermissionError):
        safe_url_fetcher("http://127.0.0.1:8000/internal/secret")

    # External web assets
    with pytest.raises(PermissionError):
        safe_url_fetcher("https://attacker.com/malicious.css")

    with pytest.raises(PermissionError):
        safe_url_fetcher("file:///etc/passwd")
