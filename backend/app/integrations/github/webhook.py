"""
GitHub Webhook Validation: Dual-secret HMAC-SHA256, Delivery Deduplication, and Policy Filters (FR-103, H2, H3, H4).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional, Tuple

from app.config import get_settings
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# Fallback set for non-Redis environments
_IN_MEMORY_DELIVERIES: set[str] = set()


def verify_webhook_signature(
    payload_bytes: bytes,
    signature_header: Optional[str],
    secret_primary: Optional[str],
    secret_previous: Optional[str] = None,
) -> bool:
    """
    Validate X-Hub-Signature-256 with dual-secret support for zero-downtime rotation (H4).
    Uses hmac.compare_digest for constant-time comparison against timing attacks.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False

    received_hash = signature_header[len("sha256="):]

    secrets_to_try = [s for s in (secret_primary, secret_previous) if s]
    if not secrets_to_try:
        logger.warning("No webhook secret configured; rejecting signature.")
        return False

    for secret in secrets_to_try:
        mac = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256)
        expected_hash = mac.hexdigest()
        if hmac.compare_digest(expected_hash, received_hash):
            return True

    return False


async def check_and_record_delivery(delivery_id: str, ttl_seconds: int = 86400) -> bool:
    """
    Check if delivery_id is new using Redis SETNX.
    Returns True if delivery is new, False if already seen (duplicate).
    """
    redis_key = f"webhook:delivery:{delivery_id}"
    try:
        client = get_redis()
        res = await client.set(redis_key, "1", ex=ttl_seconds, nx=True)
        return bool(res)
    except Exception as e:
        logger.warning("Redis error checking webhook delivery, using in-memory fallback: %s", e)
        if delivery_id in _IN_MEMORY_DELIVERIES:
            return False
        _IN_MEMORY_DELIVERIES.add(delivery_id)
        return True


def should_review_pr(
    pr_data: Dict[str, Any],
    review_fork_prs: bool,
    review_draft_prs: bool,
) -> Tuple[bool, Optional[str]]:
    """
    Evaluate whether a pull request event is eligible for review under repository policy (H2, H3).
    Returns (should_review: bool, reason: Optional[str]).
    """
    # 1. Draft PR check (H3)
    is_draft = pr_data.get("draft", False)
    if is_draft and not review_draft_prs:
        return False, "draft_pr_skipped"

    # 2. Fork PR check (H2)
    head_repo = pr_data.get("head", {}).get("repo", {}) or {}
    base_repo = pr_data.get("base", {}).get("repo", {}) or {}

    head_full_name = head_repo.get("full_name")
    base_full_name = base_repo.get("full_name")

    is_fork = bool(head_repo.get("fork")) or (head_full_name is not None and base_full_name is not None and head_full_name != base_full_name)
    if is_fork and not review_fork_prs:
        return False, "fork_pr_skipped"

    return True, None
