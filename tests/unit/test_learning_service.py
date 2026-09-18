"""
Unit tests for Governed Learning Service (FR-109, B2, AC-109.1, AC-109.8).
Validates multi-stage sanitization pipeline, consent checks, and zero code persistence.
"""
from __future__ import annotations

import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.services.consent_service import grant_consent
from app.services.learning_service import (
    sanitize_user_comment,
    verify_learning_consent,
)


def test_sanitize_user_comment_clean():
    """Validates that normal user feedback passes through cleanly."""
    comment = "This is a false positive because the test uses a mock."
    sanitized, truncated, red_count = sanitize_user_comment(comment)
    assert sanitized == comment
    assert truncated is False
    assert red_count == 0


def test_sanitize_user_comment_truncation():
    """Validates that comments exceeding 500 characters are capped (B2)."""
    long_comment = "A" * 600
    sanitized, truncated, red_count = sanitize_user_comment(long_comment)
    assert len(sanitized) == 500
    assert truncated is True


def test_sanitize_user_comment_secret_redaction():
    """Validates that API keys and GitHub tokens are scrubbed from feedback."""
    comment = "Found issue with token ghp_1234567890abcdef1234 and key AKIAIOSFODNN7EXAMPLE"
    sanitized, truncated, red_count = sanitize_user_comment(comment)
    assert "ghp_" not in sanitized
    assert "AKIA" not in sanitized
    assert "[REDACTED]" in sanitized
    assert red_count >= 2


def test_sanitize_user_comment_file_paths_and_lines():
    """[B2] Validates that references to file paths and line numbers are replaced with [REDACTED_REF]."""
    comment = "False positive in backend/app/auth.py at line 42, see also utils.ts at lines 10-15."
    sanitized, truncated, red_count = sanitize_user_comment(comment)
    assert "backend/app/auth.py" not in sanitized
    assert "utils.ts" not in sanitized
    assert "line 42" not in sanitized
    assert "[REDACTED_REF]" in sanitized
    assert red_count >= 3


def test_sanitize_user_comment_code_pattern_scrubbing():
    """[B2, AC-109.3] Validates that substantive code snippets are replaced with safe indicator."""
    code_comment = "def foo(x):\n    return eval(x)"
    sanitized, truncated, red_count = sanitize_user_comment(code_comment)
    assert "def " not in sanitized
    assert "eval(" not in sanitized
    assert sanitized == "[comment redacted: contained code-like content]"


@pytest.mark.asyncio
async def test_verify_learning_consent_lifecycle():
    """
    [AC-109.1, AC-109.8] Validates consent verification, rejection on revocation,
    and stale policy version detection.
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from app.database import Base
    import app.models  # ensure models are registered

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        user_id = uuid.uuid4()
        tenant_id = uuid.uuid4()
        settings = get_settings()
        current_version = getattr(settings, "learning_policy_version", "1.0")

        # 1. No consent record -> consent_required
        allowed, reason = await verify_learning_consent(session, user_id, tenant_id)
        assert allowed is False
        assert reason == "consent_required"

        # 2. Grant consent with current version -> ok
        await grant_consent(
            db=session,
            user_id=user_id,
            tenant_id=tenant_id,
            purpose="feedback_learning",
            version=current_version,
            granted=True,
        )
        allowed, reason = await verify_learning_consent(session, user_id, tenant_id)
        assert allowed is True
        assert reason == "ok"

        # 3. Revoke consent -> consent_required
        await grant_consent(
            db=session,
            user_id=user_id,
            tenant_id=tenant_id,
            purpose="feedback_learning",
            version=current_version,
            granted=False,
        )
        allowed, reason = await verify_learning_consent(session, user_id, tenant_id)
        assert allowed is False
        assert reason == "consent_required"

        # 4. [AC-109.8] Stale consent version -> consent_version_stale
        await grant_consent(
            db=session,
            user_id=user_id,
            tenant_id=tenant_id,
            purpose="feedback_learning",
            version="0.9",  # older version
            granted=True,
        )
        allowed, reason = await verify_learning_consent(session, user_id, tenant_id)
        assert allowed is False
        assert reason == "consent_version_stale"
