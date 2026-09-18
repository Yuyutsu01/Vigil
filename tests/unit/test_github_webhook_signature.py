"""
Unit tests for GitHub Webhook HMAC-SHA256 dual-secret verification and delivery deduplication (H4, B4).
"""
import hashlib
import hmac
import pytest

from app.integrations.github.webhook import (
    check_and_record_delivery,
    should_review_pr,
    verify_webhook_signature,
)


def test_dual_secret_signature_verification():
    payload = b'{"action":"opened","pull_request":{"id":1}}'
    secret_primary = "new_secret_2026"
    secret_previous = "old_secret_2025"

    # Signed with primary secret
    sig_primary = "sha256=" + hmac.new(secret_primary.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(payload, sig_primary, secret_primary, secret_previous) is True

    # Signed with previous secret (zero-downtime rotation)
    sig_previous = "sha256=" + hmac.new(secret_previous.encode(), payload, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(payload, sig_previous, secret_primary, secret_previous) is True

    # Signed with unknown/wrong secret
    sig_bad = "sha256=" + hmac.new(b"attacker_secret", payload, hashlib.sha256).hexdigest()
    assert verify_webhook_signature(payload, sig_bad, secret_primary, secret_previous) is False

    # Invalid header format
    assert verify_webhook_signature(payload, "invalid_header", secret_primary, secret_previous) is False


@pytest.mark.asyncio
async def test_delivery_id_deduplication():
    delivery_id = "delivery-unique-uuid-12345"

    # First check succeeds
    first = await check_and_record_delivery(delivery_id, ttl_seconds=60)
    assert first is True

    # Second check fails (duplicate detected)
    second = await check_and_record_delivery(delivery_id, ttl_seconds=60)
    assert second is False


def test_pr_policy_draft_and_fork_filtering():
    # Draft PR check (H3)
    draft_pr = {"draft": True, "head": {"repo": {"full_name": "org/repo"}}, "base": {"repo": {"full_name": "org/repo"}}}
    should_rev, reason = should_review_pr(draft_pr, review_fork_prs=False, review_draft_prs=False)
    assert should_rev is False
    assert reason == "draft_pr_skipped"

    # Fork PR check (H2)
    fork_pr = {"draft": False, "head": {"repo": {"full_name": "contributor/repo"}}, "base": {"repo": {"full_name": "org/repo"}}}
    should_rev, reason = should_review_pr(fork_pr, review_fork_prs=False, review_draft_prs=False)
    assert should_rev is False
    assert reason == "fork_pr_skipped"

    # Normal PR allowed
    normal_pr = {"draft": False, "head": {"repo": {"full_name": "org/repo"}}, "base": {"repo": {"full_name": "org/repo"}}}
    should_rev, reason = should_review_pr(normal_pr, review_fork_prs=False, review_draft_prs=False)
    assert should_rev is True
    assert reason is None
