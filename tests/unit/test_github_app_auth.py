"""
Unit tests for GitHub App authentication, RS256 JWT creation, token caching, and signed state verification (FR-103, B1, B2, B7).
"""
import time
import uuid
import pytest
import jwt

from app.integrations.github.app_auth import (
    create_app_jwt,
    create_signed_oauth_state,
    extract_public_key_pem,
    generate_ephemeral_rsa_keypair,
    verify_signed_oauth_state,
)


@pytest.mark.asyncio
async def test_app_jwt_generation_and_claims():
    priv_pem, pub_pem = generate_ephemeral_rsa_keypair()
    app_id = 123456

    token = create_app_jwt(app_id=app_id, private_key_pem=priv_pem, ttl_seconds=600)
    decoded = jwt.decode(token, pub_pem, algorithms=["RS256"])

    assert decoded["iss"] == "123456"
    assert decoded["exp"] - decoded["iat"] == 660  # 600s + 60s skew tolerance


@pytest.mark.asyncio
async def test_signed_oauth_state_nonce_and_replay_protection():
    priv_pem, pub_pem = generate_ephemeral_rsa_keypair()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    # 1. Create signed state with nonce
    state_token = await create_signed_oauth_state(
        tenant_id=tenant_id,
        user_id=user_id,
        private_key_pem=priv_pem,
        ttl_seconds=300,
    )

    # 2. First verification succeeds
    payload = await verify_signed_oauth_state(state_token, pub_pem)
    assert payload["tenant_id"] == str(tenant_id)
    assert payload["user_id"] == str(user_id)
    assert "nonce" in payload

    # 3. Second verification (replay) fails (B2)
    with pytest.raises(ValueError, match="already been consumed or expired"):
        await verify_signed_oauth_state(state_token, pub_pem)


@pytest.mark.asyncio
async def test_signed_oauth_state_tampered_signature_rejected():
    priv_pem, _ = generate_ephemeral_rsa_keypair()
    _, different_pub_pem = generate_ephemeral_rsa_keypair()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()

    state_token = await create_signed_oauth_state(
        tenant_id=tenant_id,
        user_id=user_id,
        private_key_pem=priv_pem,
        ttl_seconds=300,
    )

    # Verifying with different public key fails signature check
    with pytest.raises(ValueError, match="Invalid state token signature"):
        await verify_signed_oauth_state(state_token, different_pub_pem)
