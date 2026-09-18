"""
Integration tests for the Patch Approval and Application Flow (FR-105, FR-106, AC-105).
Verifies patch generation, role-gated approval, idempotency replay, validation, and GitHub PR application.
"""
import json
import uuid
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.database import Base
from app.main import app
from app.models.finding import Finding, FindingOrigin, FindingStatus, Severity
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import Tenant
from app.services.auth_service import create_access_token


@pytest.fixture
def mock_redis_pool():
    store = {}

    class FakeRedis:
        async def get(self, key):
            return store.get(key)

        async def setex(self, key, ttl, value):
            store[key] = value

        def pipeline(self, transaction=True):
            class FakePipe:
                def zremrangebyscore(self, *args): pass
                def zadd(self, *args): pass
                def zcard(self, *args): pass
                def expire(self, *args): pass
                async def execute(self):
                    return [None, None, 1, None]
            return FakePipe()

    with patch("app.api.phase4_guards.get_redis", return_value=FakeRedis()):
        yield FakeRedis()


@pytest.mark.asyncio
async def test_full_patch_approval_validation_and_apply_flow(mock_redis_pool, sandbox_enabled):
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

    finding_id = uuid.uuid4()
    run_id = uuid.uuid4()

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="Patch Tenant"))
        from app.models.tenant import User
        s.add(User(
            user_id=user_id,
            tenant_id=tenant_id,
            email="tester@example.com",
            hashed_password="hashed_pwd_stub",
            role="maintainer",
        ))
        await s.commit()

    async with session_maker() as s:
        from datetime import datetime, timedelta, timezone
        artifact = SourceArtifact(
            tenant_id=tenant_id,
            content="def vuln():\n    eval(input())\n",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=len("def vuln():\n    eval(input())\n"),
            language="python",
            retention_until=datetime.now(timezone.utc) + timedelta(days=30),
        )
        s.add(artifact)
        await s.commit()
        artifact_id = artifact.artifact_id

    async with session_maker() as s:
        run = ReviewRun(
            run_id=run_id,
            tenant_id=tenant_id,
            artifact_id=artifact_id,
            requested_by=user_id,
            status=ReviewStatus.completed,
        )
        s.add(run)
        await s.commit()


    async with session_maker() as s:
        finding = Finding(
            finding_id=finding_id,
            run_id=run_id,
            tenant_id=tenant_id,
            origin=FindingOrigin.rule,
            category="security",
            rule_id="VIGIL-SEC-001",
            severity=Severity.high,
            confidence=0.9,
            title="Insecure eval usage",
            rationale="eval executes arbitrary input",
            remediation="Use literal_eval",
            status=FindingStatus.open,
            fingerprint="abc1234567890abcdef",
        )
        s.add(finding)
        await s.commit()



    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    dev_token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="developer")
    maintainer_token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="maintainer")

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Generate patch as Developer
        idem_key_gen = str(uuid.uuid4())
        gen_resp = await client.post(
            f"/v1/findings/{finding_id}/patches",
            headers={"Authorization": f"Bearer {dev_token}", "X-Idempotency-Key": idem_key_gen},
            json={"force": False},
        )
        assert gen_resp.status_code == 201


        patch_data = gen_resp.json()
        assert patch_data["status"] == "draft"
        patch_id = patch_data["patch_id"]

        # 2. Idempotency replay check
        gen_replay = await client.post(
            f"/v1/findings/{finding_id}/patches",
            headers={"Authorization": f"Bearer {dev_token}", "X-Idempotency-Key": idem_key_gen},
            json={"force": False},
        )
        assert gen_replay.status_code == 201
        assert gen_replay.headers.get("X-Vigil-Idempotent") == "true"
        assert gen_replay.json()["patch_id"] == patch_id

        # 3. Approve attempt by Developer must be rejected (403)
        idem_key_app = str(uuid.uuid4())
        dev_app_resp = await client.post(
            f"/v1/patches/{patch_id}/approve",
            headers={"Authorization": f"Bearer {dev_token}", "X-Idempotency-Key": idem_key_app},
        )
        assert dev_app_resp.status_code == 403

        # 4. Approve by Maintainer must succeed (200)
        maint_app_resp = await client.post(
            f"/v1/patches/{patch_id}/approve",
            headers={"Authorization": f"Bearer {maintainer_token}", "X-Idempotency-Key": idem_key_app},
        )
        assert maint_app_resp.status_code == 200
        assert maint_app_resp.json()["status"] == "approved"

        # 5. Validate patch
        app.state.sandbox_available = True
        idem_key_val = str(uuid.uuid4())
        from app.sandbox.runtime import SandboxRuntime
        class MockRuntime(SandboxRuntime):
            async def create_or_reuse(self, image, run_id, files=None): return "mock-cid"
            async def start(self, sid): pass
            async def execute(self, sid, commands, timeout_seconds=120):
                return {
                    "verdict": "passed",
                    "checks": [{"command": "pytest", "exit_code": 0, "status": "passed", "duration_ms": 10, "stdout": "ok", "stderr": ""}],
                    "stdout_log": "ok",
                    "stderr_log": "",
                    "duration_ms": 20,
                }
            async def cleanup(self, sid): pass

        with patch("app.services.validation_service.ValidationAgent") as mock_val_agent:
            agent_inst = mock_val_agent.return_value
            from app.agents.validation_agent import ValidationVerdict, CheckResult
            agent_inst.run_validation = AsyncMock(return_value=ValidationVerdict(
                verdict="passed",
                checks=[CheckResult(command="pytest", exit_code=0, status="passed", duration_ms=10, stdout="ok", stderr="")],
                stdout_log="ok",
                duration_ms=10,
            ))
            val_resp = await client.post(
                f"/v1/patches/{patch_id}/validate",
                headers={"Authorization": f"Bearer {maintainer_token}", "X-Idempotency-Key": idem_key_val},
                json={"commands": ["pytest"]},
            )
            assert val_resp.status_code == 200
            assert val_resp.json()["verdict"] == "passed"

        # 6. Apply patch to GitHub mock
        idem_key_apply = str(uuid.uuid4())
        mock_gh = AsyncMock()
        mock_gh.get_ref.return_value = {"object": {"sha": "0000000000000000000000000000000000000000"}}
        mock_gh.create_blob.return_value = "blob-sha-111"
        mock_gh.create_tree.return_value = "tree-sha-222"
        mock_gh.create_commit.return_value = "commit-sha-333"
        mock_gh.create_ref.return_value = {"ref": "refs/heads/vigil/patch-abc12345-2026"}
        mock_gh.create_pull.return_value = {"number": 101, "html_url": "https://github.com/org/repo/pull/101"}

        with patch("app.services.patch_service.GitHubClient", return_value=mock_gh):
            apply_resp = await client.post(
                f"/v1/patches/{patch_id}/apply",
                headers={"Authorization": f"Bearer {maintainer_token}", "X-Idempotency-Key": idem_key_apply},
            )
            assert apply_resp.status_code == 201
            data = apply_resp.json()
            assert data["status"] == "applied"
            assert data["pr_number"] == 101
            assert "vigil/patch-" in data["branch"]

    app.dependency_overrides.clear()
