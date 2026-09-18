"""
Integration tests for Base SHA Drift Detection (FR-105, FR-106, AC-105).
Verifies that when a repository's base branch has advanced since the review was run,
patch application is refused with HTTP 409 Conflict (BASE_SHA_DRIFT), and zero GitHub
branches, commits, or pull requests are created.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.database import Base
from app.main import app
from app.models.finding import Finding, FindingOrigin, FindingStatus, PatchCandidate, PatchStatus, Severity
from app.models.repository import Repository, RepositoryReview
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import Tenant, User
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
async def test_base_sha_drift_detection_rejects_patch_application(mock_redis_pool):
    """
    Test that when the base branch has advanced since the review run,
    POST /v1/patches/{id}/apply fails with HTTP 409 Conflict (BASE_SHA_DRIFT)
    and no branch/commit/PR is created.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    user_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    tenant_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    finding_id = uuid.uuid4()
    run_id = uuid.uuid4()
    patch_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    # Initial expected base SHA from the review run
    initial_base_sha = "1111222233334444555566667777888899990000"
    # New remote head SHA simulating base branch advancement (drift)
    diverged_head_sha = "aaaabbbbccccddddeeeeffff0000111122223333"

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="Drift Tenant"))
        s.add(User(
            user_id=user_id,
            tenant_id=tenant_id,
            email="maintainer@example.com",
            hashed_password="hashed_pwd_stub",
            role="maintainer",
        ))
        await s.commit()

    async with session_maker() as s:
        artifact = SourceArtifact(
            tenant_id=tenant_id,
            content="def target():\n    pass\n",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=len("def target():\n    pass\n"),
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

        repo = Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            provider="github",
            external_id=123456,
            full_name="acme/security-lib",
            default_branch="main",
            is_connected=True,
        )
        s.add(repo)

        repo_review = RepositoryReview(
            tenant_id=tenant_id,
            repository_id=repo_id,
            review_run_id=run_id,
            ref_type="commit",
            ref_value=initial_base_sha,  # Initial commit SHA recorded at review time
            scope_mode="full_repo",
        )
        s.add(repo_review)

        finding = Finding(
            finding_id=finding_id,
            tenant_id=tenant_id,
            run_id=run_id,
            origin=FindingOrigin.rule,
            rule_id="VIG-001",
            category="security",
            severity=Severity.medium,
            confidence=0.9,
            status=FindingStatus.open,
            title="Insecure Configuration",
            rationale="Test finding for drift detection",
            remediation="Update config",
            fingerprint="drift_fp_12345",
        )
        s.add(finding)

        # Pre-approved patch candidate
        patch_candidate = PatchCandidate(
            patch_id=patch_id,
            finding_id=finding_id,
            unified_diff="--- a/config.py\n+++ b/config.py\n@@ -1,2 +1,2 @@\n-insecure = True\n+insecure = False\n",
            rationale="Fix insecure config",
            assumptions=json.dumps(["Python 3.11"]),
            tests_to_run=["pytest"],
            status=PatchStatus.approved,
            approved_by=user_id,
            approved_at=datetime.now(timezone.utc),
        )
        s.add(patch_candidate)
        from app.models.validation import ValidationRun, ValidationVerdictEnum
        val_run = ValidationRun(
            validation_id=uuid.uuid4(),
            patch_candidate_id=patch_id,
            tenant_id=tenant_id,
            verdict=ValidationVerdictEnum.passed,
            checks=[{"command": "pytest", "exit_code": 0, "status": "passed"}],
            sandbox_metadata={"network_mode": "none"},
            stdout_log="test output",
            stderr_log="",
        )
        s.add(val_run)
        await s.commit()

    # Create Maintainer auth token
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="maintainer")
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Idempotency-Key": str(uuid.uuid4()),
    }

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    try:
        # Mock GitHubClient to simulate base branch having advanced
        mock_gh = AsyncMock()
        # get_ref returns diverged HEAD sha
        mock_gh.get_ref.return_value = {"object": {"sha": diverged_head_sha}}
        # None of the write operations should be called
        mock_gh.create_blob = AsyncMock()
        mock_gh.create_tree = AsyncMock()
        mock_gh.create_commit = AsyncMock()
        mock_gh.create_ref = AsyncMock()
        mock_gh.create_pull = AsyncMock()

        with patch("app.services.patch_service.GitHubClient", return_value=mock_gh):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(f"/v1/patches/{patch_id}/apply", headers=headers)

                # Assert HTTP 409 Conflict returned
                assert resp.status_code == 409, f"Expected 409 Conflict, got {resp.status_code}: {resp.text}"
                data = resp.json()
                detail = data.get("detail", {})
                assert detail.get("code") == "BASE_SHA_DRIFT"
                assert "Base branch has advanced since review" in detail.get("message", "")

                # Verify zero GitHub branch or commit creation calls were initiated
                mock_gh.create_blob.assert_not_called()
                mock_gh.create_tree.assert_not_called()
                mock_gh.create_commit.assert_not_called()
                mock_gh.create_ref.assert_not_called()
                mock_gh.create_pull.assert_not_called()

        # Verify database patch state remains approved (not marked applied)
        async with session_maker() as s:
            p_res = await s.get(PatchCandidate, patch_id)
            assert p_res.status == PatchStatus.approved
            assert p_res.applied_branch is None
            assert p_res.applied_commit_sha is None

    finally:
        app.dependency_overrides.pop(get_db, None)
