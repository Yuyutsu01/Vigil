"""
Integration test for GitHub App connection flow (FR-103, B1, B2, H6).
Tests connect URL, callback verification, repo listing, policy patch, and disconnect.
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
async def test_github_connect_and_callback_flow():
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
        s.add(Tenant(tenant_id=tenant_id, name="Test Tenant"))
        await s.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role="developer",
    )
    auth_headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Connect endpoint returns install_url with signed state
        resp = await client.post("/v1/repositories/connect", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "install_url" in data
        assert "state" in data
        state = data["state"]

        # 2. Callback endpoint with mock GitHub API client
        mock_repos = [
            {
                "id": 987654321,
                "full_name": "vigil-org/secure-core",
                "default_branch": "main",
            }
        ]

        with patch("app.api.v1.repositories.GitHubClient.list_installation_repositories", new=AsyncMock(return_value=mock_repos)):
            cb_resp = await client.get(
                f"/v1/repositories/callback?installation_id=12345&state={state}",
                headers=auth_headers,
            )
            assert cb_resp.status_code == 200
            cb_data = cb_resp.json()
            assert len(cb_data) >= 1
            repo_id = cb_data[0]["repository_id"]
            assert cb_data[0]["full_name"] == "vigil-org/secure-core"
            assert cb_data[0]["is_connected"] is True

        # 3. List connected repositories
        list_resp = await client.get("/v1/repositories", headers=auth_headers)
        assert list_resp.status_code == 200
        repos = list_resp.json()
        assert any(r["repository_id"] == repo_id for r in repos)

        # 4. Update repository policy
        patch_resp = await client.patch(
            f"/v1/repositories/{repo_id}/policy",
            headers=auth_headers,
            json={
                "enabled_languages": ["python", "typescript"],
                "max_files_per_review": 250,
                "auto_review_on_pr": False,
            },
        )
        assert patch_resp.status_code == 200
        pol = patch_resp.json()
        assert pol["max_files_per_review"] == 250
        assert pol["auto_review_on_pr"] is False

        # 5. Disconnect repository locally (H6)
        disc_resp = await client.post(
            f"/v1/repositories/{repo_id}/disconnect",
            headers=auth_headers,
        )
        assert disc_resp.status_code == 200
        assert disc_resp.json()["status"] == "disconnected"

    app.dependency_overrides.clear()
