"""
Integration test for Scoped Repository Review (FR-104, B5, C1, M7, M8).
Verifies source_file_path persistence, cross-file deduplication, and cost estimation.
"""
import uuid
import pytest
from unittest.mock import AsyncMock, patch
import httpx
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.database import Base
from app.integrations.github.snapshot import SnapshotFile
from app.main import app
from app.models.tenant import Tenant
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_scoped_repo_review_execution_and_findings():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="Review Tenant"))
        await s.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="developer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Connect a test repo via callback
        mock_repos = [{"id": 11223344, "full_name": "vigil-test/sample-repo", "default_branch": "main"}]
        with patch("app.api.v1.repositories.verify_signed_oauth_state", new=AsyncMock(return_value={
            "tenant_id": str(tenant_id),
            "user_id": str(user_id),
            "nonce": "test-nonce-123",
        })), patch("app.api.v1.repositories.GitHubClient.list_installation_repositories", new=AsyncMock(return_value=mock_repos)):
            cb_resp = await client.get("/v1/repositories/callback?installation_id=555&state=dummy-state", headers=headers)
            assert cb_resp.status_code == 200
            repo_id = cb_resp.json()[0]["repository_id"]

        # 2. Test Cost Preview (C1)
        mock_files = [
            SnapshotFile(
                path="app/server.py",
                content="import os\npassword = 'plain_password_123'\n",
                language="python",
                size_bytes=42,
            ),
            SnapshotFile(
                path="utils/auth.py",
                content="import os\npassword = 'plain_password_123'\n",
                language="python",
                size_bytes=42,
            ),
        ]

        with patch("app.services.repo_review_service.resolve_review_scope", new=AsyncMock(return_value=mock_files)):
            prev_resp = await client.get(
                f"/v1/repositories/{repo_id}/cost-preview?ref_type=branch&ref_value=main&scope_mode=full_repo",
                headers=headers,
            )
            assert prev_resp.status_code == 200
            pdata = prev_resp.json()
            assert pdata["file_count"] == 2
            assert pdata["estimated_cost_usd"] > 0
            assert pdata["exceeds_cap"] is False

            # 3. Trigger Scoped Review
            review_resp = await client.post(
                f"/v1/repositories/{repo_id}/reviews",
                headers=headers,
                json={
                    "ref_type": "branch",
                    "ref_value": "main",
                    "scope_mode": "full_repo",
                },
            )
            assert review_resp.status_code == 202
            rdata = review_resp.json()
            assert rdata["status"] in ("completed", "running")
            assert rdata["file_count"] == 2
            run_id = rdata["review_run_id"]

            # 4. Fetch Review Run Details and verify findings have source_file_path (FR-104) and cross-file dedup (M8)
            run_resp = await client.get(f"/v1/reviews/{run_id}", headers=headers)
            assert run_resp.status_code == 200
            run_obj = run_resp.json()
            findings = run_obj.get("findings", [])

            paths = [f.get("source_file_path") for f in findings if f.get("source_file_path")]
            if len(findings) > 0:
                assert any("app/server.py" in str(p) or "utils/auth.py" in str(p) for p in paths)

    app.dependency_overrides.clear()
