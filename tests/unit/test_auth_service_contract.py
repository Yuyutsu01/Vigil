"""
Contract characterization tests for JWT authentication service and dependencies.
Locks in token encoding/decoding behaviors, claim validation, and middleware handling.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services.auth_service import create_access_token, decode_access_token


def test_1_round_trip() -> None:
    """create_access_token -> decode_access_token preserves all core claims."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    role = "security_lead"

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role=role, expires_minutes=15)
    payload = decode_access_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["role"] == role
    assert "exp" in payload
    assert "iat" in payload


def test_2_expired_token_rejected() -> None:
    """An expired token is rejected with an exception upon decode."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="developer", expires_minutes=-5)
    with pytest.raises(Exception):
        decode_access_token(token)


def test_3_wrong_signature_rejected() -> None:
    """A token decoded with a mismatched secret key is rejected."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="developer")
    settings = get_settings()

    with patch.object(settings, "jwt_secret_key", "different-secret-key-32-bytes-min-len"):
        with pytest.raises(Exception):
            decode_access_token(token)


def test_4_missing_claim_rejected() -> None:
    """A token missing required claims (e.g. sub or tenant_id) fails validation downstream."""
    import jwt as pyjwt
    settings = get_settings()
    # Encode token directly missing 'tenant_id'
    payload = {"sub": str(uuid.uuid4()), "role": "developer"}
    bad_token = pyjwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    decoded = decode_access_token(bad_token)
    assert "tenant_id" not in decoded

    # Downstream deps parsing raises HTTPException(401)
    with pytest.raises(KeyError):
        _ = uuid.UUID(decoded["tenant_id"])


def test_5_deps_get_auth_context_expired_401() -> None:
    """Sending an expired token to an authenticated endpoint yields 401, not 500."""
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    expired_token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="developer", expires_minutes=-10)

    client = TestClient(app)
    resp = client.get(
        "/v1/tenants/me/stats",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "invalid_token"


def test_6_middleware_passes_through_invalid_token() -> None:
    """Public endpoints (/health) succeed even when invalid or malformed tokens are sent in headers."""
    client = TestClient(app)
    # 1. No token
    resp1 = client.get("/health")
    assert resp1.status_code == 200

    # 2. Garbage/malformed token
    resp2 = client.get("/health", headers={"Authorization": "Bearer invalid.garbage.token"})
    assert resp2.status_code == 200
