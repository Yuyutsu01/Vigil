"""
Unit tests for GitHub token redaction (H2).
Verifies that all GitHub token formats are scrubbed by redact() and redact_secrets().
"""
import pytest

from app.services.redaction_service import redact, redact_secrets


@pytest.mark.parametrize(
    "prefix,sample_token",
    [
        ("ghs_", "ghs_1234567890abcdefghijklmnopqrstuvwxyzAB"),
        ("ghu_", "ghu_1234567890abcdefghijklmnopqrstuvwxyzAB"),
        ("ghp_", "ghp_1234567890abcdefghijklmnopqrstuvwxyzAB"),
        ("ghr_", "ghr_1234567890abcdefghijklmnopqrstuvwxyzAB"),
        ("gho_", "gho_1234567890abcdefghijklmnopqrstuvwxyzAB"),
        ("github_pat_", "github_pat_11AABCDEF0123456789abcdefghijklmnopqrstuvwxyz0123456789"),
    ],
)
def test_all_github_token_prefixes_are_redacted(prefix: str, sample_token: str) -> None:
    # Ensure sample starts with expected prefix
    assert sample_token.startswith(prefix)

    input_text = f"token={sample_token}"
    
    # Test with redact()
    redacted_1 = redact(input_text)
    assert sample_token not in redacted_1
    assert "[REDACTED]" in redacted_1

    # Test with redact_secrets alias (H2)
    redacted_2 = redact_secrets(input_text)
    assert sample_token not in redacted_2
    assert "[REDACTED]" in redacted_2
