"""
Unit tests for the canonical sanitization module (FR-109, B2).
Validates imports from app.learning.sanitization and multi-stage sanitization barrier.
"""
import pytest

from app.learning.sanitization import sanitize_disposition_comment


def test_sanitize_disposition_comment_strips_code_def_eval():
    """Case 1: 'def foo(): eval(x)' -> no 'def' or 'eval'."""
    comment = "def foo(): eval(x)"
    sanitized = sanitize_disposition_comment(comment)
    assert "def" not in sanitized
    assert "eval" not in sanitized
    assert "[comment redacted: contained code-like content]" in sanitized


def test_sanitize_disposition_comment_strips_paths_and_lines():
    """Case 2: 'See line 42 of handler.py for the bug' -> no 'line 42' or 'handler.py'."""
    comment = "See line 42 of handler.py for the bug"
    sanitized = sanitize_disposition_comment(comment)
    assert "line 42" not in sanitized
    assert "handler.py" not in sanitized
    assert "[REDACTED_REF]" in sanitized


def test_sanitize_disposition_comment_redacts_github_tokens():
    """Case 3: 'The token was ghp_1234...' -> token redacted."""
    token = "ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    comment = f"The token was {token}"
    sanitized = sanitize_disposition_comment(comment)
    assert token not in sanitized
    assert "[REDACTED]" in sanitized


def test_sanitize_disposition_comment_strips_class_syntax():
    """Case 4: 'class MyClass: pass' -> no 'class'."""
    comment = "class MyClass: pass"
    sanitized = sanitize_disposition_comment(comment)
    assert "class" not in sanitized
    assert "[comment redacted: contained code-like content]" in sanitized


def test_sanitize_disposition_comment_enforces_500_char_ceiling():
    """Case 5: 'x' * 800 -> truncated to 500 chars."""
    comment = "x" * 800
    sanitized = sanitize_disposition_comment(comment)
    assert len(sanitized) <= 500
    assert len(sanitized) == 500


def test_sanitize_disposition_comment_handles_empty_and_none():
    """Empty or None input returns empty string."""
    assert sanitize_disposition_comment(None) == ""
    assert sanitize_disposition_comment("") == ""
    assert sanitize_disposition_comment("   ") == ""
