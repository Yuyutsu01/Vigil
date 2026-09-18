"""
Phase 4 API guards: idempotency key verification, replay caching, and fail-closed sliding window rate limiting.
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, Optional

from fastapi import Header, HTTPException, status

from app.redis_client import get_redis

logger = logging.getLogger(__name__)


def require_idempotency_key(
    x_idempotency_key: Optional[str] = Header(None, alias="X-Idempotency-Key"),
) -> str:
    """Validate that X-Idempotency-Key is supplied and formatted as a valid UUID."""
    if not x_idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "missing_idempotency_key", "message": "X-Idempotency-Key header is required"},
        )
    try:
        parsed = uuid.UUID(x_idempotency_key)
        return str(parsed)
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_idempotency_key", "message": "X-Idempotency-Key must be a valid UUIDv4"},
        )


async def check_phase4_rate_limit(
    tenant_id: uuid.UUID,
    action_name: str,
    limit_per_hour: int,
) -> None:
    """
    Check per-tenant sliding window rate limit (1 hour window).
    Fail-CLOSED: raises HTTP 503 if Redis is unreachable.
    """
    now_ms = int(time.time() * 1000)
    window_ms = 3_600_000  # 1 hour
    key = f"rl:p4:{action_name}:{tenant_id}"

    try:
        client = get_redis()
        pipe = client.pipeline(transaction=True)
        cutoff = now_ms - window_ms

        pipe.zremrangebyscore(key, "-inf", cutoff)
        pipe.zadd(key, {str(now_ms): now_ms})
        pipe.zcard(key)
        pipe.expire(key, 7200)  # 2 hours TTL

        results = await pipe.execute()
        count = results[2]
        if count > limit_per_hour:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "code": "rate_limit_exceeded",
                    "message": f"Hourly rate limit ({limit_per_hour}/hr) exceeded for action '{action_name}'",
                },
                headers={"Retry-After": "3600"},
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Rate limit check failed for %s: %s (fail-closed)", action_name, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "service_unavailable", "message": "Rate limiter unavailable"},
        )


async def get_cached_idempotent_response(
    tenant_id: uuid.UUID,
    action_name: str,
    idempotency_key: str,
) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached idempotent response if previously processed.
    Fail-CLOSED: raises HTTP 503 if Redis is unreachable.
    """
    key = f"idem:p4:{action_name}:{tenant_id}:{idempotency_key}"
    try:
        client = get_redis()
        cached = await client.get(key)
        if cached:
            if isinstance(cached, bytes):
                cached = cached.decode("utf-8")
            return json.loads(cached)
        return None
    except Exception as exc:
        logger.error("Idempotency lookup failed: %s (fail-closed)", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "service_unavailable", "message": "Idempotency layer unavailable"},
        )


async def cache_idempotent_response(
    tenant_id: uuid.UUID,
    action_name: str,
    idempotency_key: str,
    response_data: Dict[str, Any],
    ttl_seconds: int = 86400,
) -> None:
    """Store idempotent response with 24-hour TTL."""
    key = f"idem:p4:{action_name}:{tenant_id}:{idempotency_key}"
    try:
        client = get_redis()
        await client.setex(key, ttl_seconds, json.dumps(response_data, default=str))
    except Exception as exc:
        logger.warning("Failed to cache idempotent response: %s", exc)
