"""
Integration tests for Phase 4 Rate Limiting & Fail-Closed Behavior (H4).
Verifies:
1. Independent rate limit enforcement across all 5 Phase 4 endpoints.
2. HTTP 429 Too Many Requests with Retry-After header when threshold exceeded.
3. Fail-closed HTTP 503 Service Unavailable when Redis is unreachable or raises an error.
"""
import uuid
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.database import Base
from app.main import app
from app.models.tenant import Tenant, User
from app.services.auth_service import create_access_token


@pytest.fixture
async def test_env():
    """Setup in-memory SQLite database and test tenant/user credentials."""
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
    user_id = uuid.uuid4()

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="Rate Limit Tenant"))
        s.add(User(
            user_id=user_id,
            tenant_id=tenant_id,
            email="maintainer@example.com",
            hashed_password="hashed_pwd_stub",
            role="maintainer",
        ))
        await s.commit()

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="maintainer")

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    yield {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "token": token,
        "session_maker": session_maker,
    }

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_rate_limit_exceeded_returns_429_on_phase4_endpoints(test_env):
    """
    Test that exceeding the sliding window limit returns HTTP 429 Too Many Requests
    with a Retry-After header across all five Phase 4 endpoints independently.
    """
    token = test_env["token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Idempotency-Key": str(uuid.uuid4()),
    }

    # Simulate Redis pipeline returning a count that exceeds the threshold (e.g., 999)
    class RateLimitedRedis:
        def pipeline(self, transaction=True):
            class FakePipe:
                def zremrangebyscore(self, *args): pass
                def zadd(self, *args): pass
                def zcard(self, *args): pass
                def expire(self, *args): pass
                async def execute(self):
                    # Index 2 is zcard result: simulate 999 calls in window
                    return [None, None, 999, None]
            return FakePipe()

        async def get(self, key):
            return None

    endpoints_to_test = [
        # 1. Patch Generation
        ("POST", f"/v1/findings/{uuid.uuid4()}/patches", {"force": False}),
        # 2. Patch Validation
        ("POST", f"/v1/patches/{uuid.uuid4()}/validate", {}),
        # 3. Patch Application
        ("POST", f"/v1/patches/{uuid.uuid4()}/apply", None),
        # 4. PR Review Generation
        ("POST", f"/v1/repositories/{uuid.uuid4()}/reviews/{uuid.uuid4()}/generate-draft-review", None),
        # 5. PR Review Publication
        ("POST", f"/v1/repositories/{uuid.uuid4()}/reviews/{uuid.uuid4()}/publish-review", None),
    ]

    with patch("app.api.phase4_guards.get_redis", return_value=RateLimitedRedis()):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for method, path, body in endpoints_to_test:
                # Issue request with unique idempotency key
                req_headers = {**headers, "X-Idempotency-Key": str(uuid.uuid4())}
                if method == "POST":
                    resp = await client.post(path, headers=req_headers, json=body)
                else:
                    resp = await client.get(path, headers=req_headers)

                # Assert HTTP 429 Too Many Requests
                assert resp.status_code == 429, f"Endpoint {path} did not return 429: {resp.status_code} {resp.text}"
                assert "Retry-After" in resp.headers, f"Endpoint {path} missing Retry-After header"
                assert resp.headers["Retry-After"] == "3600"
                data = resp.json()
                assert data["detail"]["code"] == "rate_limit_exceeded"


@pytest.mark.asyncio
async def test_rate_limit_fail_closed_503_when_redis_unreachable(test_env):
    """
    Test that when Redis is unreachable or raises a connection error,
    all Phase 4 endpoints fail CLOSED with HTTP 503 Service Unavailable,
    preventing unmetered execution.
    """
    token = test_env["token"]

    class BrokenRedis:
        def pipeline(self, transaction=True):
            raise ConnectionError("Redis connection refused on 127.0.0.1:6379")

        async def get(self, key):
            raise ConnectionError("Redis connection refused on 127.0.0.1:6379")

    endpoints_to_test = [
        ("POST", f"/v1/findings/{uuid.uuid4()}/patches", {"force": False}),
        ("POST", f"/v1/patches/{uuid.uuid4()}/validate", {}),
        ("POST", f"/v1/patches/{uuid.uuid4()}/apply", None),
        ("POST", f"/v1/repositories/{uuid.uuid4()}/reviews/{uuid.uuid4()}/generate-draft-review", None),
        ("POST", f"/v1/repositories/{uuid.uuid4()}/reviews/{uuid.uuid4()}/publish-review", None),
    ]

    with patch("app.api.phase4_guards.get_redis", return_value=BrokenRedis()):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for method, path, body in endpoints_to_test:
                req_headers = {
                    "Authorization": f"Bearer {token}",
                    "X-Idempotency-Key": str(uuid.uuid4()),
                }
                resp = await client.post(path, headers=req_headers, json=body)

                # Assert HTTP 503 Service Unavailable (Fail-closed invariant)
                assert resp.status_code == 503, f"Endpoint {path} did not fail closed with 503: {resp.status_code} {resp.text}"
                data = resp.json()
                assert data["detail"]["code"] == "service_unavailable"
                assert "Rate limiter unavailable" in data["detail"]["message"]
