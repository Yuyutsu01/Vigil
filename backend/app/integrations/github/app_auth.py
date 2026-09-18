"""
GitHub App Authentication, RS256 JWT Generation, Token Exchange, and State Signing (FR-103, B1, B2, B7).
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import get_settings
from app.integrations.github.vault import get_vault_resolver
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# In-memory fallback sets/caches if Redis is unavailable in local dev/tests
_IN_MEMORY_NONCES: set[str] = set()
_IN_MEMORY_TOKENS: dict[int, dict[str, Any]] = {}


def generate_ephemeral_rsa_keypair() -> tuple[str, str]:
    """Generate an ephemeral RSA key pair (PEM format) for testing/fallback."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    priv_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")

    pub_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    return priv_pem, pub_pem


def create_app_jwt(app_id: int, private_key_pem: str, ttl_seconds: int = 600) -> str:
    """
    Generate an RS256-signed JWT for GitHub App authentication.
    iat: now - 60s (clock skew tolerance)
    exp: now + ttl_seconds (max 10 minutes per GitHub spec)
    iss: app_id as string
    """
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + ttl_seconds,
        "iss": str(app_id),
    }
    return jwt.encode(payload, private_key_pem, algorithm="RS256")


def extract_public_key_pem(private_key_pem: str) -> str:
    """Derive public key PEM string from an RSA private key PEM string."""
    priv_key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"),
        password=None,
    )
    return priv_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")


async def create_signed_oauth_state(
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    private_key_pem: str,
    ttl_seconds: int = 300,
) -> str:
    """
    Generate an RS256-signed state parameter with nonce (B2).
    Stored in Redis with SETNX to prevent CSRF and replay attacks.
    """
    nonce = str(uuid.uuid4())
    now = int(time.time())
    payload = {
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "nonce": nonce,
        "iat": now,
        "exp": now + ttl_seconds,
    }

    # Store nonce in Redis
    redis_key = f"oauth_state:{nonce}"
    stored = False
    try:
        client = get_redis()
        res = await client.set(redis_key, "1", ex=ttl_seconds, nx=True)
        if res:
            stored = True
    except Exception as e:
        logger.warning("Redis unavailable for state nonce storage, using in-memory fallback: %s", e)
        _IN_MEMORY_NONCES.add(nonce)
        stored = True

    if not stored:
        raise RuntimeError("Failed to store OAuth state nonce in Redis")

    return jwt.encode(payload, private_key_pem, algorithm="RS256")


async def verify_signed_oauth_state(
    state_token: str,
    public_key_pem: str,
) -> dict[str, Any]:
    """
    Verify RS256-signed state parameter and validate single-use nonce (B2).
    Returns payload dict containing tenant_id, user_id, nonce.
    Raises ValueError on invalid signature, expiration, or consumed nonce.
    """
    try:
        payload = jwt.decode(
            state_token,
            public_key_pem,
            algorithms=["RS256"],
            options={"require": ["tenant_id", "user_id", "nonce", "exp"]},
        )
    except jwt.PyJWTError as e:
        raise ValueError(f"Invalid state token signature or expired: {e}") from e

    nonce = payload.get("nonce")
    if not nonce:
        raise ValueError("Missing nonce in state token")

    redis_key = f"oauth_state:{nonce}"
    consumed = False
    try:
        client = get_redis()
        # Atomic delete: returns 1 if key was present and deleted, 0 if already consumed
        res = await client.delete(redis_key)
        if res > 0:
            consumed = True
    except Exception as e:
        logger.warning("Redis error during nonce consumption, using in-memory fallback: %s", e)
        if nonce in _IN_MEMORY_NONCES:
            _IN_MEMORY_NONCES.remove(nonce)
            consumed = True

    if not consumed:
        raise ValueError("State token nonce has already been consumed or expired (replay prevented)")

    return payload


async def invalidate_installation_token(installation_id: int) -> None:
    """Invalidate cached installation token in Redis and memory (B7)."""
    redis_key = f"github:inst_token:{installation_id}"
    try:
        client = get_redis()
        await client.delete(redis_key)
    except Exception:
        pass
    _IN_MEMORY_TOKENS.pop(installation_id, None)


async def get_installation_access_token(
    installation_id: int,
    private_key_ref: str,
    app_id: Optional[int] = None,
    force_refresh: bool = False,
) -> str:
    """
    Retrieve an installation access token (B7).
    Checks cache first; refreshes proactively if remaining lifetime < 5 minutes (300s).
    """
    settings = get_settings()
    target_app_id = app_id or settings.github_app_id or 1000

    redis_key = f"github:inst_token:{installation_id}"
    now = int(time.time())

    # 1. Check Redis cache if not force refresh
    if not force_refresh:
        try:
            client = get_redis()
            raw = await client.get(redis_key)
            if raw:
                cached = json.loads(raw)
                exp = cached.get("exp", 0)
                # Refresh if less than 5 minutes remaining (B7)
                if exp - now > 300:
                    return cached["token"]
        except Exception as e:
            logger.debug("Redis error checking cached installation token: %s", e)
            cached = _IN_MEMORY_TOKENS.get(installation_id)
            if cached and cached.get("exp", 0) - now > 300:
                return cached["token"]

    # 2. Resolve private key from vault
    vault = get_vault_resolver()
    private_key_pem = await vault.resolve_private_key(private_key_ref)

    # 3. Create App RS256 JWT
    app_jwt = create_app_jwt(app_id=target_app_id, private_key_pem=private_key_pem)

    # 4. Exchange JWT for installation access token via GitHubClient (H3)
    from app.integrations.github.client import GitHubClient, validate_github_url

    base_url = (getattr(settings, "github_api_base", None) or settings.github_api_base_url).rstrip("/")
    url = f"{base_url}/app/installations/{installation_id}/access_tokens"
    validate_github_url(url)

    app_client = GitHubClient(
        installation_id=installation_id,
        private_key_ref=private_key_ref,
        base_url=base_url,
        app_jwt=app_jwt,
    )
    resp = await app_client._post_app_jwt(
        f"/app/installations/{installation_id}/access_tokens",
        body={},
    )

    if resp.status_code != 201:
        logger.error(
            "Failed to exchange installation token for installation %d: status %d body %s",
            installation_id,
            resp.status_code,
            resp.text,
        )
        raise RuntimeError(f"GitHub App token exchange failed with status {resp.status_code}")

    data = resp.json()
    token = data["token"]
    expires_at_str = data.get("expires_at")
    # GitHub returns ISO 8601 timestamp e.g. "2026-09-18T22:00:00Z"
    if expires_at_str:
        dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        exp_timestamp = int(dt.timestamp())
    else:
        exp_timestamp = now + 3600

    ttl = max(60, exp_timestamp - now)
    cache_payload = {"token": token, "exp": exp_timestamp}

    try:
        client = get_redis()
        await client.set(redis_key, json.dumps(cache_payload), ex=ttl)
    except Exception as e:
        logger.debug("Redis error caching installation token: %s", e)
        _IN_MEMORY_TOKENS[installation_id] = cache_payload

    return token
