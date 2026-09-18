"""
Security tests: GitHub Webhook Replay Protection and Delivery Deduplication (FR-103, B4).
Verifies that replayed deliveries are ignored, signatures cannot be forged,
and unique deliveries are processed independently.
"""
import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.config import get_settings
from app.database import Base
from app.integrations.github.webhook import (
    _IN_MEMORY_DELIVERIES,
    check_and_record_delivery,
    verify_webhook_signature,
)
from app.main import app
from app.models.tenant import Tenant


@pytest.mark.asyncio
async def test_webhook_delivery_replay_rejected_as_duplicate():
    """Verify that re-delivering a webhook with an identical delivery ID is ignored."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    tenant_id = uuid.uuid4()
    async with session_maker() as session:
        session.add(Tenant(tenant_id=tenant_id, name="Replay Tenant"))
        await session.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    secret = "secret-for-replay-test-12345"
    settings = get_settings()
    settings.github_app_webhook_secret = secret

    # Attach mock arq_pool to app.state
    mock_pool = AsyncMock()
    app.state.arq_pool = mock_pool

    delivery_id = f"replay-test-{uuid.uuid4()}"
    payload = {"action": "ping", "zen": "Keep it logically awesome."}
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {
                "X-Hub-Signature-256": sig,
                "X-GitHub-Delivery": delivery_id,
                "X-GitHub-Event": "ping",
                "Content-Type": "application/json",
            }

            # First delivery — must be accepted (202)
            resp1 = await client.post("/v1/webhooks/github", content=payload_bytes, headers=headers)
            assert resp1.status_code == 202
            assert resp1.json()["status"] == "accepted"

            # Replay of identical delivery — must be ignored (200 with duplicate_delivery)
            resp2 = await client.post("/v1/webhooks/github", content=payload_bytes, headers=headers)
            assert resp2.status_code == 200
            assert resp2.json()["status"] == "ignored"
            assert resp2.json()["reason"] == "duplicate_delivery"
    finally:
        app.dependency_overrides.clear()


def test_tampered_payload_signature_rejected():
    """Verify that tampering with body bytes rejects the webhook."""
    secret = "my-secret-key-123456"
    valid_payload = b'{"action":"opened"}'
    tampered_payload = b'{"action":"opened","malicious":"injection"}'

    valid_sig = "sha256=" + hmac.new(secret.encode(), valid_payload, hashlib.sha256).hexdigest()

    # Tampered payload fails verification with valid signature for original payload
    assert verify_webhook_signature(
        payload_bytes=tampered_payload,
        signature_header=valid_sig,
        secret_primary=secret,
    ) is False


def test_invalid_secret_signature_rejected():
    """Verify that signatures calculated with wrong secrets are rejected."""
    correct_secret = "correct-secret-123"
    attacker_secret = "attacker-secret-456"
    payload = b'{"action":"opened"}'

    attacker_sig = "sha256=" + hmac.new(attacker_secret.encode(), payload, hashlib.sha256).hexdigest()

    assert verify_webhook_signature(
        payload_bytes=payload,
        signature_header=attacker_sig,
        secret_primary=correct_secret,
    ) is False


@pytest.mark.asyncio
async def test_distinct_deliveries_processed_independently():
    """Verify distinct delivery IDs are both treated as new."""
    id1 = f"distinct-{uuid.uuid4()}"
    id2 = f"distinct-{uuid.uuid4()}"

    res1 = await check_and_record_delivery(id1)
    assert res1 is True

    res2 = await check_and_record_delivery(id2)
    assert res2 is True

    # Replay of id1 fails
    assert await check_and_record_delivery(id1) is False
