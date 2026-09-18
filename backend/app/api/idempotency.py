"""Redis-backed idempotency middleware for POST /v1/reviews.
Fail-CLOSED: Redis unavailable → 503 block.
TTL: 24 hours. Key: sha256(tenant_id:source_checksum:language).
See Implementation Plan [H5], [A1].
"""
from __future__ import annotations

import hashlib
import json
import logging

from fastapi import Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

_IDEMPOTENCY_TTL = 86_400  # 24 hours in seconds
_IDEMPOTENCY_PATHS = {"/v1/reviews"}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    Redis-backed idempotency for POST /v1/reviews.
    If a matching run_id exists in Redis for the same (tenant, source_checksum, language),
    returns the cached run_id rather than creating a new run.
    Fail-CLOSED: Redis unreachable → block the request (503).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Only intercept POST to /v1/reviews
        if request.method != "POST" or request.url.path not in _IDEMPOTENCY_PATHS:
            return await call_next(request)

        tenant_id = getattr(getattr(request, "state", None), "tenant_id", None)
        if tenant_id is None:
            return await call_next(request)

        try:
            client = get_redis()
            # Peek at the body without consuming it
            body_bytes = await request.body()

            try:
                body_json = json.loads(body_bytes)
                source_checksum = hashlib.sha256(
                    body_json.get("source_text", "").encode("utf-8")
                ).hexdigest()
                language = body_json.get("language", "")
            except (json.JSONDecodeError, AttributeError):
                return await call_next(request)

            idem_key = f"idem:{tenant_id}:{source_checksum}:{language}"
            cached = await client.get(idem_key)

            if cached:
                # Return cached run_id
                data = json.loads(cached)
                return Response(
                    content=json.dumps(data),
                    status_code=status.HTTP_200_OK,
                    media_type="application/json",
                    headers={"X-Vigil-Idempotent": "true"},
                )

            # Store the key after processing by storing it in request state
            request.state.idempotency_key = idem_key
            request.state.idempotency_client = client

        except Exception as e:
            # Fail-CLOSED
            logger.error("Idempotency Redis error — BLOCKING (fail-closed): %s", e)
            return Response(
                content='{"code":"service_unavailable","message":"Idempotency store unavailable"}',
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json",
            )

        return await call_next(request)
