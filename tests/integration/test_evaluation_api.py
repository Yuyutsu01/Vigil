"""
Integration tests for internal evaluation API role-gated access control.
"""
import uuid
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.evaluation import EvaluationRun
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


def test_evaluation_api_role_gate():
    mock_redis = MockRedis()
    # 1. Developer role -> 403 Forbidden
    dev_token = create_access_token(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        role="developer",
    )
    with patch("app.main.create_tables", new=AsyncMock()), \
         patch("app.api.rate_limit.get_redis", return_value=mock_redis), \
         patch("app.api.idempotency.get_redis", return_value=mock_redis):
        with TestClient(app) as client:
            resp = client.get(
                "/v1/internal/evaluation/run?suite=python",
                headers={"Authorization": f"Bearer {dev_token}"},
            )
            assert resp.status_code == 403
            assert resp.json().get("detail", {}).get("code") == "forbidden"

    # 2. PlatformOperator role -> 200 OK
    admin_token = create_access_token(
        user_id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        role="PlatformOperator",
    )
    mock_run = EvaluationRun(
        evaluation_run_id=uuid.uuid4(),
        suite="python",
        precision=1.0,
        recall=1.0,
        f1=1.0,
        per_rule_breakdown={},
    )

    with patch("app.main.create_tables", new=AsyncMock()), \
         patch("app.api.rate_limit.get_redis", return_value=mock_redis), \
         patch("app.api.idempotency.get_redis", return_value=mock_redis), \
         patch("app.api.v1.evaluation.EvaluationRunner.run_suite", new=AsyncMock(return_value=(mock_run, AsyncMock(evidence_completeness=1.0)))):
        with TestClient(app) as client:
            resp = client.get(
                "/v1/internal/evaluation/run?suite=python",
                headers={"Authorization": f"Bearer {admin_token}"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["suite"] == "python"
            assert data["precision"] == 1.0
