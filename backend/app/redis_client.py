"""
Redis client factory with error handling.
Fail-CLOSED semantics for rate-limiting and idempotency paths.
"""
from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.config import get_settings

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return the shared Redis client (lazy-initialized)."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis_client


async def check_redis_health() -> bool:
    """Return True if Redis is reachable, False otherwise."""
    try:
        client = get_redis()
        await client.ping()
        return True
    except Exception:
        logger.warning("Redis health check failed")
        return False
