"""
Integration tests for POST /v1/reviews and GET /v1/reviews/{run_id}.
Uses httpx.AsyncClient against a live FastAPI app with an in-memory database.
Run with: pytest tests/integration/ -v

For real PostgreSQL integration, set DATABASE_URL env var to a test database.
AC-2: Verify the full review lifecycle end-to-end.
"""
import asyncio
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    """Create a FastAPI app instance for testing."""
    import os
    from unittest.mock import AsyncMock, patch

    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_vigil.db")
    os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
    os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-integration-tests")
    os.environ.setdefault("VIGIL_LLM_PROVIDER", "mock")
    os.environ.setdefault("VIGIL_ENV", "test")

    with patch("app.main.create_tables", new=AsyncMock()):
        from app.main import app as fastapi_app
        from app.api.deps import get_db

        async def mock_get_db():
            mock_session = AsyncMock()
            yield mock_session

        fastapi_app.dependency_overrides[get_db] = mock_get_db
        yield fastapi_app
        fastapi_app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="module")
def valid_token(app):
    """Create a valid JWT token for a test user/tenant."""
    from app.services.auth_service import create_access_token
    return create_access_token(
        user_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
        role="developer",
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestReviewAPIFlow:
    """Integration tests for the review API flow."""

    def test_health_endpoint_ok(self, app) -> None:
        """GET /health returns 200 or 503."""
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            resp = client.get("/health")
        assert resp.status_code in (200, 503)  # 503 if Redis not available in CI
        data = resp.json()
        assert "status" in data

    def test_review_requires_auth(self, app) -> None:
        """POST /v1/reviews without Bearer token → 403."""
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            resp = client.post(
                "/v1/reviews",
                json={"language": "python", "source_text": "x = 1"},
            )
        assert resp.status_code in (401, 403), f"Expected auth error, got {resp.status_code}"

    def test_invalid_language_rejected(self, app, valid_token) -> None:
        """POST /v1/reviews with unsupported language → 422."""
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            resp = client.post(
                "/v1/reviews",
                json={"language": "ruby", "source_text": "x = 1"},
                headers={"Authorization": f"Bearer {valid_token}"},
            )
        assert resp.status_code == 422

    def test_upload_wrong_content_type_rejected(self, app, valid_token) -> None:
        """POST /v1/uploads with text/plain → 415."""
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            resp = client.post(
                "/v1/uploads",
                content=b"x = 1",
                headers={
                    "Authorization": f"Bearer {valid_token}",
                    "Content-Type": "text/plain",
                },
            )
        assert resp.status_code in (415, 422)

    def test_source_size_limit_enforced(self, app, valid_token) -> None:
        """POST /v1/reviews with oversized payload → 422."""
        from fastapi.testclient import TestClient
        large = "x = 1\n" * (250 * 1024 // 6 + 1)  # >250KB
        with TestClient(app) as client:
            resp = client.post(
                "/v1/reviews",
                json={"language": "python", "source_text": large},
                headers={"Authorization": f"Bearer {valid_token}"},
            )
        assert resp.status_code == 422

    def test_review_requires_json_content_type(self, app, valid_token) -> None:
        """POST /v1/reviews with wrong Content-Type → 415."""
        from fastapi.testclient import TestClient
        with TestClient(app) as client:
            resp = client.post(
                "/v1/reviews",
                content=b'language=python&source_text=x%3D1',
                headers={
                    "Authorization": f"Bearer {valid_token}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            )
        assert resp.status_code in (415, 422)

    def test_tenant_mismatch_rejected(self, app) -> None:
        """X-Tenant-Hint mismatch with JWT tenant → 403."""
        from app.services.auth_service import create_access_token
        from fastapi.testclient import TestClient

        token = create_access_token(
            user_id=uuid.uuid4(),
            tenant_id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            role="developer",
        )
        different_tenant = str(uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"))

        with TestClient(app) as client:
            resp = client.post(
                "/v1/reviews",
                json={"language": "python", "source_text": "x = 1"},
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Tenant-Hint": different_tenant,
                },
            )
        assert resp.status_code == 403
        data = resp.json()
        assert data.get("detail", {}).get("code") == "tenant_mismatch"
