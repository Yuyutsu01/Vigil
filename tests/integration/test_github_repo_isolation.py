"""
Integration test for tenant isolation across repository endpoints (FR-103, §9).
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.database import Base
from app.main import app
from app.models.tenant import Tenant
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_cross_tenant_repository_access_is_blocked():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    tenant_a = uuid.UUID("11111111-1111-1111-1111-111111111111")
    user_a = uuid.UUID("11111111-1111-1111-1111-111111111112")
    token_a = create_access_token(user_id=user_a, tenant_id=tenant_a, role="developer")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    tenant_b = uuid.UUID("22222222-2222-2222-2222-222222222222")
    user_b = uuid.UUID("22222222-2222-2222-2222-222222222223")
    token_b = create_access_token(user_id=user_b, tenant_id=tenant_b, role="developer")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_a, name="Tenant A"))
        s.add(Tenant(tenant_id=tenant_b, name="Tenant B"))
        await s.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Tenant A connects repo
        mock_repos = [{"id": 88877766, "full_name": "tenant-a/private-code", "default_branch": "main"}]
        with patch("app.api.v1.repositories.verify_signed_oauth_state", new=AsyncMock(return_value={
            "tenant_id": str(tenant_a),
            "user_id": str(user_a),
            "nonce": "nonce-tenant-a",
        })), patch("app.api.v1.repositories.GitHubClient.list_installation_repositories", new=AsyncMock(return_value=mock_repos)):
            cb_resp = await client.get("/v1/repositories/callback?installation_id=999&state=dummy", headers=headers_a)
            assert cb_resp.status_code == 200
            repo_id = cb_resp.json()[0]["repository_id"]

        # Tenant B attempts to read repo details -> 404
        b_get = await client.get(f"/v1/repositories/{repo_id}", headers=headers_b)
        assert b_get.status_code == 404

        # Tenant B attempts to update repo policy -> 404
        b_patch = await client.patch(
            f"/v1/repositories/{repo_id}/policy",
            headers=headers_b,
            json={"max_files_per_review": 10},
        )
        assert b_patch.status_code == 404

        # Tenant B attempts to trigger review -> 404
        b_review = await client.post(
            f"/v1/repositories/{repo_id}/reviews",
            headers=headers_b,
            json={"ref_type": "branch", "ref_value": "main", "scope_mode": "full_repo"},
        )
        assert b_review.status_code == 404

    app.dependency_overrides.clear()
