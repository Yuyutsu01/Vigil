"""
Integration test for idempotency enforcement (Bug 1 verification).
Verifies:
  - Sending the same POST /v1/reviews body twice with the same JWT returns the same run_id
  - The second response carries the header 'X-Vigil-Idempotent: true'
  - Only one review run is created for that request body
  - Sending a different body produces a new, distinct run_id
"""
import json
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
                results.append(0)
            elif op[0] == "zadd":
                results.append(1)
            elif op[0] == "zcard":
                results.append(1)
            elif op[0] == "expire":
                results.append(True)
        return results


class MockRedis:
    def __init__(self):
        self.kv = {}
        self.store = {}

    def pipeline(self, transaction=True):
        return MockPipeline(self.store)

    async def get(self, key):
        return self.kv.get(key)

    async def setex(self, key, ttl, value):
        self.kv[key] = value
        return True


def test_idempotency_enforced_for_reviews():
    from app.main import app
    from app.api.deps import get_db

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="developer")
    headers = {"Authorization": f"Bearer {token}"}

    mock_redis = MockRedis()
    created_runs = []

    async def mock_create_run(db, tenant_id, user_id, source_text, language, provider=None):
        run = ReviewRun(
            run_id=uuid.uuid4(),
            tenant_id=tenant_id,
            status=ReviewStatus.running,
        )
        created_runs.append(run)
        return run

    async def mock_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = mock_get_db

    try:
        with patch("app.main.create_tables", new=AsyncMock()), \
             patch("app.api.idempotency.get_redis", return_value=mock_redis), \
             patch("app.api.rate_limit.get_redis", return_value=mock_redis), \
             patch("app.api.v1.reviews.create_and_run_review", side_effect=mock_create_run):

            with TestClient(app) as client:
                body_1 = {"language": "python", "source_text": "x = 42"}

                # First submission -> creates run 1
                resp1 = client.post("/v1/reviews", json=body_1, headers=headers)
                assert resp1.status_code == 202
                run_id_1 = resp1.json()["run_id"]
                assert len(created_runs) == 1

                # Second submission with identical body -> intercepted by idempotency middleware
                resp2 = client.post("/v1/reviews", json=body_1, headers=headers)
                assert resp2.status_code == 200
                assert resp2.headers.get("X-Vigil-Idempotent") == "true"
                run_id_2 = resp2.json()["run_id"]

                # Assert second response returns SAME run_id
                assert run_id_1 == run_id_2

                # Assert only ONE ReviewRun was created in DB for this body
                assert len(created_runs) == 1

                # Third submission with DIFFERENT body -> creates new run
                body_2 = {"language": "python", "source_text": "y = 100"}
                resp3 = client.post("/v1/reviews", json=body_2, headers=headers)
                assert resp3.status_code == 202
                run_id_3 = resp3.json()["run_id"]
                assert run_id_3 != run_id_1
                assert len(created_runs) == 2

    finally:
        app.dependency_overrides.pop(get_db, None)
