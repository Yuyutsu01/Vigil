"""
Security tests: GitHub tokens (PAT, OAuth, App installation tokens) are never logged or stored (FR-103, §9).
"""
import logging
import pytest

from app.services.redaction_service import RedactionFilter, redact, redact_dict, redact_secrets


def test_redact_secrets_alias_identity():
    """Verify redact_secrets is an alias to redact and behaves identically (H2)."""
    sample = "ghp_1234567890abcdefghijklmnopqrstuvwxyzAB"
    assert redact_secrets is redact
    assert redact_secrets(f"secret={sample}") == redact(f"secret={sample}")


def test_redact_dict_scrubs_nested_tokens():
    """Verify nested dictionaries and lists are recursively sanitized of GitHub tokens."""
    data = {
        "auth": {"token": "ghs_testinstallationtoken123456789012345"},
        "headers": ["Authorization: Bearer gho_testoauthtoken123456789012345678"],
        "count": 42,
    }
    redacted = redact_dict(data)
    assert "ghs_" not in redacted["auth"]["token"]
    assert "[REDACTED]" in redacted["auth"]["token"]
    assert "gho_" not in redacted["headers"][0]
    assert "[REDACTED]" in redacted["headers"][0]
    assert redacted["count"] == 42


def test_github_tokens_are_redacted():
    # Various GitHub token formats
    tokens = [
        "ghp_1234567890abcdefghijklmnopqrstuvwxyzAB",  # PAT
        "ghs_abcdefghijklmnopqrstuvwxyz1234567890AB",  # App Installation Token
        "ghu_abcdefghijklmnopqrstuvwxyz1234567890AB",  # User-to-server token
        "gho_abcdefghijklmnopqrstuvwxyz1234567890AB",  # OAuth token
        "ghr_abcdefghijklmnopqrstuvwxyz1234567890AB",  # Refresh token
        "github_pat_11AABCDEF0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",  # Fine-grained
    ]

    for t in tokens:
        msg = f"Request completed using token: {t}"
        redacted = redact(msg)
        assert t not in redacted, f"Token {t} leaked in redacted text: {redacted}"
        assert "[REDACTED]" in redacted


def test_redaction_filter_scrubs_log_record():
    logger = logging.getLogger("test_redaction_logger")
    r_filter = RedactionFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="client.py",
        lineno=42,
        msg="Authenticated with token ghs_testinstallationtoken123456789012345",
        args=(),
        exc_info=None,
    )

    r_filter.filter(record)
    assert "ghs_" not in record.msg
    assert "[REDACTED]" in record.msg
