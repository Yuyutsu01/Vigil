"""
Redis-backed rate limiting middleware.
Fail-CLOSED: if Redis is unavailable, all requests are BLOCKED (return 503).
Limits are per-tenant (sliding window) and per-user (sliding window).
See Implementation Plan [B1], [H5].
"""
from __future__ import annotations

import logging
import time

import redis.asyncio as aioredis
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import get_settings
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = {"/health", "/v1/auth/token", "/v1/auth/login", "/v1/auth/register", "/docs", "/openapi.json"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Sliding-window rate limiter using Redis sorted sets.
    Fail-CLOSED: Redis unreachable → 503 Service Unavailable.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Exempt auth and health endpoints
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        settings = get_settings()

        # Attempt to get tenant/user IDs from request state (set by AuthContextMiddleware)
        tenant_id = getattr(getattr(request, "state", None), "tenant_id", None)
        user_id = getattr(getattr(request, "state", None), "user_id", None)

        if tenant_id is None:
            # No auth context yet (will be handled by auth dependency)
            return await call_next(request)

        now = int(time.time() * 1000)  # milliseconds
        window_ms = 60_000  # 1 minute

        try:
            client = get_redis()
            # Tenant-level rate limit (requests per minute)
            tenant_key = f"rl:tenant:{tenant_id}"
            is_ok = await _sliding_window_check(
                client,
                tenant_key,
                now,
                window_ms,
                settings.rate_limit_tenant_per_minute,
            )
            if not is_ok:
                return Response(
                    content='{"code":"rate_limited","message":"Tenant rate limit exceeded"}',
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    media_type="application/json",
                    headers={"Retry-After": "60"},
                )

            # User-level rate limit
            if user_id:
                user_key = f"rl:user:{user_id}"
                is_ok = await _sliding_window_check(
                    client,
                    user_key,
                    now,
                    window_ms,
                    settings.rate_limit_user_per_minute,
                )
                if not is_ok:
                    return Response(
                        content='{"code":"rate_limited","message":"User rate limit exceeded"}',
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        media_type="application/json",
                        headers={"Retry-After": "60"},
                    )

        except Exception as e:
            # Fail-CLOSED: Redis unavailable → block request
            logger.error("Rate limiter Redis unavailable: %s — BLOCKING request (fail-closed)", e)
            return Response(
                content='{"code":"service_unavailable","message":"Rate limiter unavailable"}',
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json",
            )

        return await call_next(request)


async def _sliding_window_check(
    client: aioredis.Redis,
    key: str,
    now_ms: int,
    window_ms: int,
    limit: int,
) -> bool:
    """
    Atomic sliding window rate limit check using Redis sorted set.
    Returns True if request is allowed, False if limit exceeded.
    Raises on Redis error (caller decides to fail-closed or not).
    """
    pipe = client.pipeline(transaction=True)
    cutoff = now_ms - window_ms

    pipe.zremrangebyscore(key, "-inf", cutoff)
    pipe.zadd(key, {str(now_ms): now_ms})
    pipe.zcard(key)
    pipe.expire(key, 120)  # 2-minute TTL

    results = await pipe.execute()
    count = results[2]
    return count <= limit
