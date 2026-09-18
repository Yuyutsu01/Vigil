"""
Integration test for dev sandbox availability flag (IC10, H5).
Verifies that when verify_runsc_available raises RuntimeError during development startup,
app.state.sandbox_available is set to False and POST /v1/patches/{id}/validate returns 503.
"""
import uuid
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.config import get_settings
from app.main import app, lifespan
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_sandbox_unavailable_returns_503():
    """Verify that if runsc is missing in development, validate endpoint returns 503."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    patch_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="maintainer")

    settings = get_settings()

    class FakeRedis:
        async def get(self, key):
            return None

        async def setex(self, key, ttl, value):
            pass

        def pipeline(self, transaction=True):
            class FakePipe:
                def zremrangebyscore(self, *args): pass
                def zadd(self, *args): pass
                def zcard(self, *args): pass
                def expire(self, *args): pass
                async def execute(self):
                    return [None, None, 1, None]
            return FakePipe()

    def raise_runsc_missing(*args, **kwargs):
        raise RuntimeError("runsc binary missing or outdated")

    try:
        with patch("app.main.get_settings") as mock_get_settings, \
             patch("app.sandbox.gvisor.verify_runsc_available", side_effect=raise_runsc_missing), \
             patch("app.main.create_tables", new_callable=AsyncMock), \
             patch("app.api.phase4_guards.get_redis", return_value=FakeRedis()):

            # Configure environment as development
            dev_settings = settings.model_copy(update={"environment": "development"})
            mock_get_settings.return_value = dev_settings

            async with lifespan(app):
                assert app.state.sandbox_available is False

                transport = httpx.ASGITransport(app=app)
                async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.post(
                        f"/v1/patches/{patch_id}/validate",
                        headers={
                            "Authorization": f"Bearer {token}",
                            "X-Idempotency-Key": str(uuid.uuid4()),
                        },
                        json={"commands": ["pytest"]},
                    )

                    assert resp.status_code == 503
                    data = resp.json()
                    detail = data.get("detail", {})
                    assert detail.get("code") == "sandbox_unavailable"
                    assert "Sandbox runtime is not available" in detail.get("message", "")
    finally:
        app.state.sandbox_available = True
