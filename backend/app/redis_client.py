"""
Redis client factory with error handling.
Fail-CLOSED semantics for rate-limiting and idempotency paths.
"""
from __future__ import annotations

import logging

import redis.asyncio as aioredis

from app.config import get_settings

import asyncio

logger = logging.getLogger(__name__)

_redis_client: aioredis.Redis | None = None
_redis_loop: asyncio.AbstractEventLoop | None = None


def get_redis() -> aioredis.Redis:
    """Return the shared Redis client (lazy-initialized per event loop)."""
    global _redis_client, _redis_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    # If the active loop changed (e.g. across async test runs) or is closed, reinitialize
    if _redis_client is None or _redis_loop is not current_loop or (current_loop is not None and current_loop.is_closed()):
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        _redis_loop = current_loop
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
