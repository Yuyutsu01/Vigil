"""
Integration test for rate limiting enforcement (Bug 1 verification).
Verifies:
  - Real JWT token causes AuthContextMiddleware to populate request.state.tenant_id
  - RateLimitMiddleware limits requests per tenant to rate_limit_tenant_per_minute (3)
  - Requests 1-3 return 202, Request 4 returns 429 with Retry-After header
  - Request 5 with a different tenant returns 202 (tenant isolation)
"""
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.models.review import ReviewRun, ReviewStatus
from app.services.auth_service import create_access_token


class MockPipeline:
    def __init__(self, store):
        self.store = store
        self.ops = []

    def zremrangebyscore(self, key, min_val, max_val):
        self.ops.append(("zrem", key, max_val))
        return self

    def zadd(self, key, mapping):
        self.ops.append(("zadd", key, mapping))
        return self

    def zcard(self, key):
        self.ops.append(("zcard", key))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key, ttl))
        return self

    async def execute(self):
        results = []
        for op in self.ops:
            if op[0] == "zrem":
                key, max_val = op[1], op[2]
                zset = self.store.setdefault(key, {})
                to_del = [m for m, s in zset.items() if s <= max_val]
                for m in to_del:
                    del zset[m]
                results.append(len(to_del))
            elif op[0] == "zadd":
                key, mapping = op[1], op[2]
                zset = self.store.setdefault(key, {})
                zset.update(mapping)
                results.append(len(mapping))
            elif op[0] == "zcard":
                key = op[1]
                results.append(len(self.store.get(key, {})))
            elif op[0] == "expire":
                results.append(True)
        return results


class MockRedis:
    def __init__(self):
        self.store = {}
        self.kv = {}

    def pipeline(self, transaction=True):
        return MockPipeline(self.store)

    async def get(self, key):
        return self.kv.get(key)

    async def setex(self, key, ttl, value):
        self.kv[key] = value
        return True


@pytest.fixture
def mock_redis_instance():
    return MockRedis()


def test_rate_limit_enforced_per_tenant(mock_redis_instance):
    from app.main import app
    from app.api.deps import get_db
    from app.config import get_settings

    settings = get_settings()
    original_limit = settings.rate_limit_tenant_per_minute
    settings.rate_limit_tenant_per_minute = 3

    tenant_a = uuid.uuid4()
    user_a = uuid.uuid4()
    jwt_a = create_access_token(user_id=user_a, tenant_id=tenant_a, role="developer")

    tenant_b = uuid.uuid4()
    user_b = uuid.uuid4()
    jwt_b = create_access_token(user_id=user_b, tenant_id=tenant_b, role="developer")

    # Dependency override for DB
    async def mock_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = mock_get_db

    mock_run = ReviewRun(run_id=uuid.uuid4(), status=ReviewStatus.running)

    try:
        with patch("app.main.create_tables", new=AsyncMock()), \
             patch("app.api.rate_limit.get_redis", return_value=mock_redis_instance), \
             patch("app.api.idempotency.get_redis", return_value=mock_redis_instance), \
             patch("app.api.v1.reviews.create_and_run_review", new=AsyncMock(return_value=mock_run)):

            with TestClient(app) as client:
                headers_a = {"Authorization": f"Bearer {jwt_a}"}

                # Requests 1-3 should succeed (202 Accepted)
                for i in range(1, 4):
                    resp = client.post(
                        "/v1/reviews",
                        json={"language": "python", "source_text": f"x = {i}"},
                        headers=headers_a,
                    )
                    assert resp.status_code == 202, f"Request {i} failed: {resp.text}"

                # Request 4 should be rate limited (429 Too Many Requests)
                resp4 = client.post(
                    "/v1/reviews",
                    json={"language": "python", "source_text": "x = 4"},
                    headers=headers_a,
                )
                assert resp4.status_code == 429
                assert "Retry-After" in resp4.headers
                data4 = resp4.json()
                assert data4.get("code") == "rate_limited"

                # Request 5 with Tenant B's JWT must succeed (202) -> Tenant isolation
                headers_b = {"Authorization": f"Bearer {jwt_b}"}
                resp5 = client.post(
                    "/v1/reviews",
                    json={"language": "python", "source_text": "x = 5"},
                    headers=headers_b,
                )
                assert resp5.status_code == 202, f"Tenant B request failed: {resp5.text}"

    finally:
        settings.rate_limit_tenant_per_minute = original_limit
        app.dependency_overrides.pop(get_db, None)
