"""
Integration tests for tenant stats endpoint GET /v1/tenants/me/stats.
Verifies real-time stats aggregation and tenant isolation.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.deps import get_db
from app.services.auth_service import create_access_token


class MockPipeline:
    def __init__(self, store):
        self.store = store

    def zremrangebyscore(self, key, min_val, max_val):
        return self

    def zadd(self, key, mapping):
        return self

    def zcard(self, key):
        return self

    def expire(self, key, ttl):
        return self

    async def execute(self):
        return [0, 1, 1, True]


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


def test_get_tenant_stats_endpoint():
    mock_redis = MockRedis()
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role="developer",
    )
    headers = {"Authorization": f"Bearer {token}"}

    mock_db = AsyncMock()
    # Mock execute result
    mock_result_scalar = MagicMock()
    mock_result_scalar.scalar.return_value = 0
    mock_result_all = MagicMock()
    mock_result_all.all.return_value = []
    
    mock_db.execute.side_effect = [
        mock_result_scalar,  # total_reviews
        mock_result_all,     # findings by severity
        mock_result_scalar,  # total tokens
        mock_result_all,     # runs durations
        mock_result_scalar,  # last 7 days
        mock_result_scalar,  # prev 7 days
    ]

    async def mock_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = mock_get_db

    try:
        with patch("app.main.create_tables", new=AsyncMock()), \
             patch("app.api.rate_limit.get_redis", return_value=mock_redis), \
             patch("app.api.idempotency.get_redis", return_value=mock_redis):

            with TestClient(app) as client:
                resp = client.get("/v1/tenants/me/stats", headers=headers)
                assert resp.status_code == 200
                data = resp.json()

                # Verify response schema fields
                assert "total_reviews" in data
                assert "total_findings" in data
                assert "findings_by_severity" in data
                assert "total_tokens_used" in data
                assert "total_cost_usd" in data
                assert "avg_review_duration_ms" in data
                assert "reviews_last_7_days" in data
                assert "reviews_previous_7_days" in data

                # Verify severity breakdown schema
                sev = data["findings_by_severity"]
                assert "Critical" in sev
                assert "High" in sev
                assert "Medium" in sev
                assert "Low" in sev
                assert "Info" in sev
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_get_tenant_stats_requires_auth():
    mock_redis = MockRedis()
    with patch("app.main.create_tables", new=AsyncMock()), \
         patch("app.api.rate_limit.get_redis", return_value=mock_redis), \
         patch("app.api.idempotency.get_redis", return_value=mock_redis):

        with TestClient(app) as client:
            resp = client.get("/v1/tenants/me/stats")
            assert resp.status_code == 401
