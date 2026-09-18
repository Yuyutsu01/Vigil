"""
Integration test for GitHub repository review running full pipeline (B1).
Verifies that repo review executes run_review_graph, finds eval (VIGIL-SEC-002)
and pickle (VIGIL-SEC-004), sets source_file_path, and ignores tests/**.
"""
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.database import Base
from app.integrations.github.snapshot import SnapshotFile
from app.main import app
from app.models.finding import FindingOrigin
from app.models.tenant import Tenant
from app.services.auth_service import create_access_token


@pytest.mark.asyncio
async def test_repo_review_runs_full_pipeline_and_records_findings():
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
        s.add(Tenant(tenant_id=tenant_id, name="Pipeline Review Tenant"))
        await s.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="developer")
    headers = {"Authorization": f"Bearer {token}"}

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Connect a test repo via callback
            mock_repos = [{"id": 99887766, "full_name": "vigil-org/pipeline-repo", "default_branch": "main"}]
            with patch("app.api.v1.repositories.verify_signed_oauth_state", new=AsyncMock(return_value={
                "tenant_id": str(tenant_id),
                "user_id": str(user_id),
                "nonce": "test-nonce-pipeline",
            })), patch("app.api.v1.repositories.GitHubClient.list_installation_repositories", new=AsyncMock(return_value=mock_repos)):
                cb_resp = await client.get("/v1/repositories/callback?installation_id=777&state=test-state", headers=headers)
                assert cb_resp.status_code == 200
                repo_id = cb_resp.json()[0]["repository_id"]

            # 2. Mock GitHub file fetch to return one eval file and one pickle file
            mock_files = [
                SnapshotFile(
                    path="src/eval_runner.py",
                    content="def execute(user_input):\n    eval(user_input)\n",
                    language="python",
                    size_bytes=48,
                ),
                SnapshotFile(
                    path="src/deserializer.py",
                    content="import pickle\ndef load(data):\n    return pickle.loads(data)\n",
                    language="python",
                    size_bytes=62,
                ),
            ]

            with patch("app.services.repo_review_service.resolve_review_scope", new=AsyncMock(return_value=mock_files)):
                # 3. Trigger review via POST /v1/repositories/{id}/reviews
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
                run_id = rdata["review_run_id"]

                # 4. Fetch Review Run Details
                run_resp = await client.get(f"/v1/reviews/{run_id}", headers=headers)
                assert run_resp.status_code == 200
                run_obj = run_resp.json()
                findings = run_obj.get("findings", [])

                # Assert rule-origin finding for eval (VIGIL-SEC-002)
                eval_findings = [f for f in findings if f.get("rule_id") == "VIGIL-SEC-002" and f.get("origin") == FindingOrigin.rule.value]
                assert len(eval_findings) >= 1, "Expected VIGIL-SEC-002 (eval) finding from rule engine"

                # Assert rule-origin finding for pickle (VIGIL-SEC-004)
                pickle_findings = [f for f in findings if f.get("rule_id") == "VIGIL-SEC-004" and f.get("origin") == FindingOrigin.rule.value]
                assert len(pickle_findings) >= 1, "Expected VIGIL-SEC-004 (pickle) finding from rule engine"

                # Assert each finding has source_file_path set
                for f in findings:
                    path = f.get("source_file_path")
                    assert path is not None and len(path) > 0, f"Finding {f.get('title')} is missing source_file_path"
                    # Assert no finding has source_file_path matching tests/**
                    assert not path.startswith("tests/"), f"Finding on ignored path: {path}"

    finally:
        app.dependency_overrides.clear()
