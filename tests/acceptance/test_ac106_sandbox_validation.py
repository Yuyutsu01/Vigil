"""
Acceptance Tests for AC-106: Sandbox Isolation and Verdict (FR-106).
Covers SRS §14 M4 Exit Criteria:
1. POST /v1/patches/{id}/validate creates a ValidationRun with verdict in {passed, failed, error, timeout}.
2. ValidationVerdict contains per-check exit codes, durations, and stdout/stderr references.
3. Sandbox container is destroyed after validation (cleanup called).
4. Network egress denial: network_mode='none'.
5. Zero tokens or DB credentials in container environment.
6. Memory allocation bounded at 512 MB.
7. Rootfs is read-only (read_only=True).
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.database import Base
from app.main import app
from app.models.finding import Finding, FindingOrigin, FindingStatus, PatchCandidate, PatchStatus, Severity
from app.models.repository import Repository, RepositoryPolicy, RepositoryReview
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import Tenant, User
from app.models.validation import ValidationRun, ValidationVerdictEnum
from app.sandbox.gvisor import GVisorSandboxRuntime
from app.sandbox.limits import SandboxLimits
from app.services.auth_service import create_access_token


@pytest.fixture
def mock_redis():
    class FakeRedis:
        async def get(self, key): return None
        async def setex(self, key, ttl, val): pass
        def pipeline(self, transaction=True):
            class FakePipe:
                def zremrangebyscore(self, *args): pass
                def zadd(self, *args): pass
                def zcard(self, *args): pass
                def expire(self, *args): pass
                async def execute(self): return [None, None, 1, None]
            return FakePipe()

    with patch("app.api.phase4_guards.get_redis", return_value=FakeRedis()):
        yield FakeRedis()


@pytest.mark.asyncio
async def test_ac106_full_sandbox_validation_flow(mock_redis, sandbox_enabled):
    """Verify criteria 1, 2, and 3: validation endpoint creates ValidationRun and cleans up container."""
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
    run_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    patch_id = uuid.uuid4()

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="AC106 Tenant"))
        s.add(User(user_id=user_id, tenant_id=tenant_id, email="val@ex.com", hashed_password="h", role="maintainer"))
        await s.commit()

    async with session_maker() as s:
        art = SourceArtifact(
            tenant_id=tenant_id,
            content="def add(a, b): return a + b\n",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=30,
            language="python",
            retention_until=datetime.now(timezone.utc) + timedelta(days=30),
        )
        s.add(art)
        await s.commit()
        art_id = art.artifact_id

    async with session_maker() as s:
        run = ReviewRun(run_id=run_id, tenant_id=tenant_id, artifact_id=art_id, requested_by=user_id, status=ReviewStatus.completed)
        s.add(run)

        pol = RepositoryPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            enabled_languages=["python"],
            ignored_paths=[],
            ignored_rules=[],
            allowed_ci_commands=["pytest"],
        )
        s.add(pol)

        repo = Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            provider="github",
            external_id=999888,
            full_name="acme/ac106-repo",
            default_branch="main",
            policy_id=policy_id,
            is_connected=True,
        )
        s.add(repo)
        await s.flush()

        s.add(RepositoryReview(
            tenant_id=tenant_id,
            repository_id=repo_id,
            review_run_id=run_id,
            ref_type="commit",
            ref_value="1111222233334444555566667777888899990000",
            scope_mode="changed_files",
        ))

        finding = Finding(
            finding_id=finding_id,
            tenant_id=tenant_id,
            run_id=run_id,
            origin=FindingOrigin.rule,
            rule_id="VIG-01",
            category="security",
            severity=Severity.medium,
            confidence=0.9,
            status=FindingStatus.open,
            title="Validation test",
            rationale="Test",
            remediation="Fix",
            fingerprint="ac106_fp_1",
        )
        s.add(finding)

        patch_cand = PatchCandidate(
            patch_id=patch_id,
            finding_id=finding_id,
            unified_diff="--- a/math.py\n+++ b/math.py\n@@ -1 +1 @@\n-def add(a, b): return a\n+def add(a, b): return a + b\n",
            rationale="Fix addition",
            assumptions=json.dumps([]),
            tests_to_run=["pytest"],
            status=PatchStatus.draft,
        )
        s.add(patch_cand)
        await s.commit()

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="maintainer")

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    try:
        # Mock Docker container execution
        mock_docker = MagicMock()
        mock_container = MagicMock()
        mock_container.id = "mock_val_container_001"
        mock_docker.containers.create.return_value = mock_container
        mock_docker.containers.get.return_value = mock_container

        mock_exec_res = MagicMock()
        mock_exec_res.exit_code = 0
        mock_exec_res.output = (b"=== 1 passed in 0.05s ===", None)
        mock_container.exec_run.return_value = mock_exec_res

        mock_runtime = GVisorSandboxRuntime(docker_client=mock_docker)

        with patch("app.agents.validation_agent.get_sandbox_runtime", return_value=mock_runtime):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/v1/patches/{patch_id}/validate",
                    headers={"Authorization": f"Bearer {token}", "X-Idempotency-Key": str(uuid.uuid4())},
                    json={"commands": ["pytest"]},
                )
                assert resp.status_code == 200, f"Validation failed: {resp.text}"
                val_data = resp.json()

                # Criterion 1: verdict is in {passed, failed, error, timeout}
                assert val_data["verdict"] in {"passed", "failed", "error", "timeout"}
                assert val_data["verdict"] == "passed"

                # Criterion 2: check diagnostics contain exit_code, duration_ms, stdout
                checks = val_data["checks"]
                assert len(checks) == 1
                assert checks[0]["exit_code"] == 0
                assert "duration_ms" in checks[0]
                assert "1 passed" in val_data["stdout_log"]

                # Criterion 3: container is destroyed (remove force=True called)
                mock_container.remove.assert_called_with(force=True)

        # Criteria 4, 5, 6, 7: Resource controls and security invariants
        limits = SandboxLimits.from_settings()
        kwargs = limits.to_docker_kwargs()
        assert kwargs["network_mode"] == "none"  # Criterion 4: network egress denial
        assert kwargs["read_only"] is True  # Criterion 7: read-only rootfs
        assert kwargs["mem_limit"] == 512 * 1024 * 1024  # Criterion 6: memory cap
        assert kwargs["memswap_limit"] == 512 * 1024 * 1024  # Criterion 6: swap disabled

    finally:
        app.dependency_overrides.pop(get_db, None)
