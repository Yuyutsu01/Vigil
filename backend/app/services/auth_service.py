"""
# PROTOTYPE_ONLY
Auth service — local user store for Phase 1 prototype.
TODO: Replace with Auth0/Keycloak OIDC integration before any external pilot.
See IMPLEMENTATION_NOTES.md and plan [M6], [F2].

Uses Argon2id for password hashing per [A3].
"""
# PROTOTYPE_ONLY — see module docstring
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.tenant import User

logger = logging.getLogger(__name__)


# ── Argon2id password hashing ─────────────────────────────────────────────────

def _get_hasher():
    """Return Argon2id PasswordHasher (lazy import to avoid hard dependency)."""
    try:
        from argon2 import PasswordHasher
        return PasswordHasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )
    except ImportError:
        # Fallback to bcrypt if argon2-cffi not installed
        logger.warning("argon2-cffi not available; falling back to passlib bcrypt")
        from passlib.context import CryptContext  # type: ignore
        return CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hash a password using Argon2id."""
    hasher = _get_hasher()
    try:
        return hasher.hash(plain)
    except AttributeError:
        # passlib fallback
        return hasher.hash(plain)  # type: ignore


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against an Argon2id hash."""
    hasher = _get_hasher()
    try:
        hasher.verify(hashed, plain)
        return True
    except Exception:
        # passlib fallback
        try:
            return hasher.verify(plain, hashed)  # type: ignore
        except Exception:
            return False


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    role: str,
    expires_minutes: Optional[int] = None,
) -> str:
    """Create a signed JWT access token with tenant_id claim."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.jwt_access_token_expire_minutes
    )
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token. Raises JWTError on invalid token."""
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


# ── User lookup ───────────────────────────────────────────────────────────────

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> Optional[User]:
    """Verify credentials and return User or None."""
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user
