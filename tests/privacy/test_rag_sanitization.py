"""
Privacy test for Multi-Stage RAG Comment Sanitization Barrier (FR-109 / B2).

Concept:
Developer feedback commentary must never leak tenant secrets, source code, internal file paths,
or line number references into the learning index.
This test verifies the 5-stage sanitization barrier:
1. Secret token redaction.
2. Code construct and syntax keyword scrubbing.
3. Internal file path redaction.
4. Line reference redaction.
5. 500-character truncation ceiling.
"""
from __future__ import annotations

import pytest

from app.services.learning_service import sanitize_user_comment


def test_sanitize_comment_redacts_credentials():
    """Verify secrets (e.g. AWS access keys, Bearer tokens) are redacted."""
    raw = "False positive: token AKIAIOSFODNN7EXAMPLE is an expired test key."
    sanitized, was_truncated, redaction_count = sanitize_user_comment(raw)

    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized
    assert "[REDACTED_SECRET" in sanitized or "[REDACTED" in sanitized
    assert was_truncated is False
    assert redaction_count >= 1


def test_sanitize_comment_strips_file_paths_and_line_numbers():
    """Verify file paths (*.py, *.ts, etc.) and line references (line 42, L10) are scrubbed."""
    raw = "Reviewed backend/services/auth_handler.py at line 142 and L88; verified safe."
    sanitized, was_truncated, redaction_count = sanitize_user_comment(raw)

    assert "backend/services/auth_handler.py" not in sanitized
    assert "line 142" not in sanitized
    assert "L88" not in sanitized
    assert "[REDACTED_REF]" in sanitized


def test_sanitize_comment_detects_and_replaces_code_syntax():
    """Verify code patterns (def, return, eval, import, =>) are rejected."""
    raw = "def custom_sanitizer(val): return eval(val)"
    sanitized, was_truncated, redaction_count = sanitize_user_comment(raw)

    assert "def " not in sanitized
    assert "return " not in sanitized
    assert "eval(" not in sanitized
    assert sanitized == "[comment redacted: contained code-like content]"


def test_sanitize_comment_enforces_500_char_ceiling():
    """Verify commentary is strictly capped at 500 characters and sets was_truncated=True."""
    long_comment = "Safe architectural pattern explained in detail: " + ("a" * 600)
    sanitized, was_truncated, redaction_count = sanitize_user_comment(long_comment)

    assert len(sanitized) <= 500
    assert was_truncated is True


def test_sanitize_comment_handles_empty_and_clean_text():
    """Verify clean commentary passes through unchanged and None returns (None, False, 0)."""
    clean = "Verified as intentional architecture pattern for testing environment."
    sanitized, was_truncated, redaction_count = sanitize_user_comment(clean)

    assert sanitized == clean
    assert was_truncated is False
    assert redaction_count == 0

    none_res, none_trunc, none_redacts = sanitize_user_comment(None)
    assert none_res is None
    assert none_trunc is False
    assert none_redacts == 0
