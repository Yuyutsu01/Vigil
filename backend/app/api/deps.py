"""
API dependency injection: JWT decoding, tenant extraction, and database sessions.

CRITICAL SECURITY INVARIANT:
  tenant_id is extracted EXCLUSIVELY from the verified JWT claim.
  Client-supplied headers (X-Tenant-ID, X-User-ID, X-Tenant-Hint) are NEVER
  trusted for authorization. If supplied, they are cross-checked against the JWT
  claim and rejected with 403 on mismatch.
See Implementation Plan [B1], Design Principles §1.
"""
from __future__ import annotations

import logging
import uuid
from typing import AsyncGenerator, Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.review import AuditAction
from app.services.auth_service import decode_access_token
from app.services.audit_service import record_audit_event

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield a database session per request."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class AuthContext:
    """Resolved authentication context extracted from the verified JWT."""
    def __init__(self, user_id: uuid.UUID, tenant_id: uuid.UUID, role: str, raw_token: str) -> None:
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role
        self.raw_token = raw_token


async def get_auth_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
    x_tenant_hint: Optional[str] = Header(default=None, alias="X-Tenant-Hint"),
) -> AuthContext:
    """
    Resolve authentication and authorization context from the JWT Bearer token.

    Tenant ID comes EXCLUSIVELY from the verified JWT claim 'tenant_id'.
    If X-Tenant-Hint header is present, it is validated against the JWT claim.
    A mismatch triggers 403 and an audit event — never a trusted override.
    """
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_token", "message": str(e)},
        )

    try:
        user_id = uuid.UUID(payload["sub"])
        tenant_id = uuid.UUID(payload["tenant_id"])
        role = payload.get("role", "developer")
    except (KeyError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "malformed_token", "message": "Missing required JWT claims"},
        )

    # Cross-check routing hint header against JWT tenant — NEVER trust the header
    if x_tenant_hint is not None:
        try:
            hint_id = uuid.UUID(x_tenant_hint)
        except ValueError:
            hint_id = None

        if hint_id != tenant_id:
            logger.warning(
                "Tenant mismatch: JWT=%s hint=%s user=%s ip=%s",
                tenant_id,
                x_tenant_hint,
                user_id,
                request.client.host if request.client else "unknown",
            )
            # Write audit event for the mismatch
            await record_audit_event(
                db,
                tenant_id=tenant_id,
                actor_id=user_id,
                action=AuditAction.TENANT_MISMATCH_REJECTED,
                target_type="Request",
                target_id=str(request.url),
                metadata={"hint_header": x_tenant_hint},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "tenant_mismatch",
                    "message": "X-Tenant-Hint does not match authenticated tenant",
                },
            )

    # Store in request state for downstream middleware/logging
    request.state.tenant_id = tenant_id
    request.state.user_id = user_id

    return AuthContext(
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        raw_token=credentials.credentials,
    )
