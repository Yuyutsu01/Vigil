"""
Integration test verifying fail-CLOSED behavior when Redis is unreachable (Bug 1 verification).
When Redis raises ConnectionError, POST /v1/reviews must return 503 Service Unavailable.
"""
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.services.auth_service import create_access_token


def test_rate_limit_fail_closed_when_redis_down():
    from app.main import app
    from app.api.deps import get_db

    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="developer")
    headers = {"Authorization": f"Bearer {token}"}

    async def mock_get_db():
        yield AsyncMock()

    app.dependency_overrides[get_db] = mock_get_db

    def mock_redis_connection_error():
        raise ConnectionError("Redis cluster connection refused")

    try:
        with patch("app.main.create_tables", new=AsyncMock()), \
             patch("app.api.rate_limit.get_redis", side_effect=mock_redis_connection_error):

            with TestClient(app) as client:
                resp = client.post(
                    "/v1/reviews",
                    json={"language": "python", "source_text": "x = 1"},
                    headers=headers,
                )
                assert resp.status_code == 503
                data = resp.json()
                assert data.get("code") == "service_unavailable"
    finally:
        app.dependency_overrides.pop(get_db, None)
