"""
AuthContextMiddleware: extracts tenant_id and user_id from verified JWT
and stores them in request.state before downstream rate-limit and idempotency
middlewares execute.
"""
from __future__ import annotations

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from jose import JWTError

from app.services.auth_service import decode_access_token


class AuthContextMiddleware(BaseHTTPMiddleware):
    """
    Decode the Bearer JWT and populate request.state.tenant_id and
    request.state.user_id BEFORE rate-limit and idempotency
    middleware run. Does NOT enforce authorization — that remains
    the job of the get_auth_context FastAPI dependency.
    On missing/invalid token, leaves state unset and passes through
    so public endpoints (health, auth/token) still work.
    """

    async def dispatch(self, request: Request, call_next):
        auth_header = request.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:]
            try:
                payload = decode_access_token(token)
                request.state.tenant_id = uuid.UUID(payload["tenant_id"])
                request.state.user_id = uuid.UUID(payload["sub"])
            except (JWTError, KeyError, ValueError):
                pass
        return await call_next(request)
