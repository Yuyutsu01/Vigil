"""
Integration test for GitHub Webhook ingestion endpoint (FR-103, B4, H4).
"""
import hashlib
import hmac
import json
import uuid
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.config import get_settings
from app.database import Base
from app.main import app


@pytest.mark.asyncio
async def test_webhook_ingestion_and_signature_handling():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    settings = get_settings()
    secret = "test_webhook_secret_key"

    with patch("app.main.create_tables", new=AsyncMock()), patch.object(settings, "github_app_webhook_secret", secret):
        payload_dict = {
            "action": "opened",
            "number": 42,
            "pull_request": {
                "id": 101,
                "draft": False,
                "head": {"repo": {"full_name": "vigil-org/secure-core"}},
                "base": {"repo": {"full_name": "vigil-org/secure-core"}},
            },
        }
        body = json.dumps(payload_dict).encode("utf-8")
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Invalid signature -> 401
            resp_bad = await client.post(
                "/v1/webhooks/github",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": "sha256=invalid_signature_hash",
                    "X-GitHub-Delivery": "delivery-001",
                    "X-GitHub-Event": "pull_request",
                },
            )
            assert resp_bad.status_code == 401

            # 2. Valid signature -> 202 Accepted
            delivery_id = f"delivery-{uuid.uuid4()}"
            resp_ok = await client.post(
                "/v1/webhooks/github",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Delivery": delivery_id,
                    "X-GitHub-Event": "pull_request",
                },
            )
            assert resp_ok.status_code == 202
            data = resp_ok.json()
            assert data["status"] == "accepted"
            assert data["delivery_id"] == delivery_id

            # 3. Replay of same delivery -> 200 duplicate ignored
            resp_dup = await client.post(
                "/v1/webhooks/github",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Delivery": delivery_id,
                    "X-GitHub-Event": "pull_request",
                },
            )
            assert resp_dup.status_code == 200
            assert resp_dup.json()["reason"] == "duplicate_delivery"

    app.dependency_overrides.clear()
