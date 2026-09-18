"""
Meta-test: Patch Application Gate Enforcement (B2).
Verifies that POST /v1/patches/{id}/apply strictly enforces all Phase 4 governance gates:
1. Status must not be draft (409 Conflict, 0 GitHub writes).
2. Status approved but no validation run (409 Conflict, 0 GitHub writes).
3. Status approved + validation run failed (422 Unprocessable, 0 GitHub writes).
4. Status approved + validation run passed (201 Created, exactly 5 allowlisted writes).
5. Withdraw approval after approval before apply (409 Conflict, 0 GitHub writes).
6. Idempotency replay with same key (201 Created, only 1 set of writes occurs).
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.database import Base
from app.integrations.github.client import GitHubClient
from app.main import app
from app.models.finding import Finding, FindingOrigin, FindingStatus, PatchCandidate, PatchStatus, Severity
from app.models.repository import Repository, RepositoryReview
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import Tenant, User
from app.models.validation import ValidationRun, ValidationVerdictEnum
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


@pytest.fixture
async def setup_db_and_client():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    tenant_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    user_id = uuid.UUID("22222222-2222-2222-2222-222222222222")
    repo_id = uuid.uuid4()
    run_id = uuid.uuid4()
    finding_id = uuid.uuid4()
    base_sha = "0000000000000000000000000000000000000000"

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="Security Meta-Test Tenant"))
        s.add(User(
            user_id=user_id,
            tenant_id=tenant_id,
            email="maintainer@security.test",
            hashed_password="hashed_pwd_stub",
            role="maintainer",
        ))
        await s.commit()

    async with session_maker() as s:
        artifact = SourceArtifact(
            tenant_id=tenant_id,
            content="def vuln(): pass\n",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=len("def vuln(): pass\n"),
            language="python",
            retention_until=datetime.now(timezone.utc) + timedelta(days=30),
        )
        s.add(artifact)
        await s.commit()
        artifact_id = artifact.artifact_id

    async with session_maker() as s:
        s.add(ReviewRun(
            run_id=run_id,
            tenant_id=tenant_id,
            artifact_id=artifact_id,
            requested_by=user_id,
            status=ReviewStatus.completed,
        ))
        s.add(Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            provider="github",
            external_id=999999,
            full_name="org/secure-repo",
            default_branch="main",
            is_connected=True,
        ))
        s.add(RepositoryReview(
            tenant_id=tenant_id,
            repository_id=repo_id,
            review_run_id=run_id,
            ref_type="commit",
            ref_value=base_sha,
            scope_mode="full_repo",
        ))
        s.add(Finding(
            finding_id=finding_id,
            tenant_id=tenant_id,
            run_id=run_id,
            origin=FindingOrigin.rule,
            rule_id="VIGIL-SEC-GATE",
            category="security",
            severity=Severity.high,
            confidence=0.95,
            status=FindingStatus.open,
            title="Gate Test Vulnerability",
            rationale="Test vulnerability for gate assertions",
            remediation="Apply remediation patch",
            fingerprint="fp_security_gate_meta_test_123",
        ))
        await s.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="maintainer")
    transport = httpx.ASGITransport(app=app)

    yield {
        "session_maker": session_maker,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "finding_id": finding_id,
        "base_sha": base_sha,
        "token": token,
        "transport": transport,
    }

    app.dependency_overrides.pop(get_db, None)


def _mock_write_response(method, endpoint, json_data=None):
    """Side effect returning valid responses for the 5 GitHub write calls."""
    if "git/blobs" in endpoint:
        return httpx.Response(201, json={"sha": "blob-sha-001"})
    elif "git/trees" in endpoint:
        return httpx.Response(201, json={"sha": "tree-sha-002"})
    elif "git/commits" in endpoint:
        return httpx.Response(201, json={"sha": "commit-sha-003"})
    elif "git/refs" in endpoint:
        return httpx.Response(201, json={"ref": json_data.get("ref", "refs/heads/patch")})
    elif "pulls" in endpoint:
        return httpx.Response(201, json={"number": 42, "html_url": "https://github.com/org/repo/pull/42"})
    return httpx.Response(200, json={})


@pytest.mark.asyncio
async def test_1_draft_patch_application_fails_409_no_writes(setup_db_and_client, mock_redis_pool):
    """Test 1: PatchCandidate with status='draft' -> POST /apply returns 409 and 0 GitHub writes."""
    ctx = setup_db_and_client
    patch_id = uuid.uuid4()

    async with ctx["session_maker"]() as s:
        s.add(PatchCandidate(
            patch_id=patch_id,
            finding_id=ctx["finding_id"],
            unified_diff="--- a/vuln.py\n+++ b/vuln.py\n@@ -1 +1 @@\n-vuln()\n+safe()\n",
            rationale="Fix vulnerability",
            assumptions=json.dumps([]),
            tests_to_run=["pytest"],
            status=PatchStatus.draft,
        ))
        await s.commit()

    with patch.object(GitHubClient, "_post_allowed_write", new_callable=AsyncMock) as mock_write, \
         patch.object(GitHubClient, "get_ref", new_callable=AsyncMock, return_value={"object": {"sha": ctx["base_sha"]}}):
        async with httpx.AsyncClient(transport=ctx["transport"], base_url="http://test") as client:
            resp = await client.post(
                f"/v1/patches/{patch_id}/apply",
                headers={"Authorization": f"Bearer {ctx['token']}", "X-Idempotency-Key": str(uuid.uuid4())},
            )
            assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
            assert mock_write.call_count == 0


@pytest.mark.asyncio
async def test_2_approved_without_validation_fails_409_no_writes(setup_db_and_client, mock_redis_pool):
    """Test 2: PatchCandidate with status='approved' but no ValidationRun with verdict='passed' -> 409 and 0 GitHub writes."""
    ctx = setup_db_and_client
    patch_id = uuid.uuid4()

    async with ctx["session_maker"]() as s:
        s.add(PatchCandidate(
            patch_id=patch_id,
            finding_id=ctx["finding_id"],
            unified_diff="--- a/vuln.py\n+++ b/vuln.py\n@@ -1 +1 @@\n-vuln()\n+safe()\n",
            rationale="Fix vulnerability",
            assumptions=json.dumps([]),
            tests_to_run=["pytest"],
            status=PatchStatus.approved,
            approved_by=ctx["user_id"],
            approved_at=datetime.now(timezone.utc),
        ))
        await s.commit()

    with patch.object(GitHubClient, "_post_allowed_write", new_callable=AsyncMock) as mock_write, \
         patch.object(GitHubClient, "get_ref", new_callable=AsyncMock, return_value={"object": {"sha": ctx["base_sha"]}}):
        async with httpx.AsyncClient(transport=ctx["transport"], base_url="http://test") as client:
            resp = await client.post(
                f"/v1/patches/{patch_id}/apply",
                headers={"Authorization": f"Bearer {ctx['token']}", "X-Idempotency-Key": str(uuid.uuid4())},
            )
            assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"
            assert "VALIDATION_REQUIRED" in resp.text
            assert mock_write.call_count == 0


@pytest.mark.asyncio
async def test_3_approved_with_failed_validation_fails_422_no_writes(setup_db_and_client, mock_redis_pool):
    """Test 3: PatchCandidate with status='approved' + ValidationRun verdict='failed' -> 422 and 0 GitHub writes."""
    ctx = setup_db_and_client
    patch_id = uuid.uuid4()

    async with ctx["session_maker"]() as s:
        s.add(PatchCandidate(
            patch_id=patch_id,
            finding_id=ctx["finding_id"],
            unified_diff="--- a/vuln.py\n+++ b/vuln.py\n@@ -1 +1 @@\n-vuln()\n+safe()\n",
            rationale="Fix vulnerability",
            assumptions=json.dumps([]),
            tests_to_run=["pytest"],
            status=PatchStatus.approved,
            approved_by=ctx["user_id"],
            approved_at=datetime.now(timezone.utc),
        ))
        s.add(ValidationRun(
            validation_id=uuid.uuid4(),
            patch_candidate_id=patch_id,
            tenant_id=ctx["tenant_id"],
            verdict=ValidationVerdictEnum.failed,
            checks=[{"command": "pytest", "exit_code": 1, "status": "failed"}],
            sandbox_metadata={"network_mode": "none"},
            stdout_log="assertion error in test",
            stderr_log="",
        ))
        await s.commit()

    with patch.object(GitHubClient, "_post_allowed_write", new_callable=AsyncMock) as mock_write, \
         patch.object(GitHubClient, "get_ref", new_callable=AsyncMock, return_value={"object": {"sha": ctx["base_sha"]}}):
        async with httpx.AsyncClient(transport=ctx["transport"], base_url="http://test") as client:
            resp = await client.post(
                f"/v1/patches/{patch_id}/apply",
                headers={"Authorization": f"Bearer {ctx['token']}", "X-Idempotency-Key": str(uuid.uuid4())},
            )
            assert resp.status_code == 422, f"Expected 422, got {resp.status_code}: {resp.text}"
            assert "VALIDATION_FAILED" in resp.text
            assert mock_write.call_count == 0


@pytest.mark.asyncio
async def test_4_approved_with_passed_validation_succeeds_201_five_writes(setup_db_and_client, mock_redis_pool):
    """Test 4: PatchCandidate with status='approved' + ValidationRun verdict='passed' -> 201 and exactly 5 writes."""
    ctx = setup_db_and_client
    patch_id = uuid.uuid4()

    async with ctx["session_maker"]() as s:
        s.add(PatchCandidate(
            patch_id=patch_id,
            finding_id=ctx["finding_id"],
            unified_diff="--- a/vuln.py\n+++ b/vuln.py\n@@ -1 +1 @@\n-vuln()\n+safe()\n",
            rationale="Fix vulnerability",
            assumptions=json.dumps([]),
            tests_to_run=["pytest"],
            status=PatchStatus.approved,
            approved_by=ctx["user_id"],
            approved_at=datetime.now(timezone.utc),
        ))
        s.add(ValidationRun(
            validation_id=uuid.uuid4(),
            patch_candidate_id=patch_id,
            tenant_id=ctx["tenant_id"],
            verdict=ValidationVerdictEnum.passed,
            checks=[{"command": "pytest", "exit_code": 0, "status": "passed"}],
            sandbox_metadata={"network_mode": "none"},
            stdout_log="all checks passed",
            stderr_log="",
        ))
        await s.commit()

    with patch.object(GitHubClient, "_post_allowed_write", new_callable=AsyncMock, side_effect=_mock_write_response) as mock_write, \
         patch.object(GitHubClient, "get_ref", new_callable=AsyncMock, return_value={"object": {"sha": ctx["base_sha"]}}):
        async with httpx.AsyncClient(transport=ctx["transport"], base_url="http://test") as client:
            resp = await client.post(
                f"/v1/patches/{patch_id}/apply",
                headers={"Authorization": f"Bearer {ctx['token']}", "X-Idempotency-Key": str(uuid.uuid4())},
            )
            assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["status"] == "applied"
            assert data["pr_number"] == 42
            assert "vigil/patch-" in data["branch"]
            # Exactly 5 allowlisted writes: blob, tree, commit, ref, pull
            assert mock_write.call_count == 5


@pytest.mark.asyncio
async def test_5_withdraw_approval_before_apply_fails_409(setup_db_and_client, mock_redis_pool):
    """Test 5: Withdraw approval after approval but before apply -> POST /apply returns 409 and 0 writes."""
    ctx = setup_db_and_client
    patch_id = uuid.uuid4()

    async with ctx["session_maker"]() as s:
        s.add(PatchCandidate(
            patch_id=patch_id,
            finding_id=ctx["finding_id"],
            unified_diff="--- a/vuln.py\n+++ b/vuln.py\n@@ -1 +1 @@\n-vuln()\n+safe()\n",
            rationale="Fix vulnerability",
            assumptions=json.dumps([]),
            tests_to_run=["pytest"],
            status=PatchStatus.approved,
            approved_by=ctx["user_id"],
            approved_at=datetime.now(timezone.utc),
        ))
        s.add(ValidationRun(
            validation_id=uuid.uuid4(),
            patch_candidate_id=patch_id,
            tenant_id=ctx["tenant_id"],
            verdict=ValidationVerdictEnum.passed,
            checks=[{"command": "pytest", "exit_code": 0, "status": "passed"}],
            sandbox_metadata={"network_mode": "none"},
            stdout_log="passed",
            stderr_log="",
        ))
        await s.commit()

    with patch.object(GitHubClient, "_post_allowed_write", new_callable=AsyncMock, side_effect=_mock_write_response) as mock_write, \
         patch.object(GitHubClient, "get_ref", new_callable=AsyncMock, return_value={"object": {"sha": ctx["base_sha"]}}):
        async with httpx.AsyncClient(transport=ctx["transport"], base_url="http://test") as client:
            # First withdraw the patch
            withdraw_resp = await client.post(
                f"/v1/patches/{patch_id}/withdraw",
                headers={"Authorization": f"Bearer {ctx['token']}", "X-Idempotency-Key": str(uuid.uuid4())},
            )
            assert withdraw_resp.status_code == 200
            assert withdraw_resp.json()["status"] == "withdrawn"

            # Now attempt apply
            apply_resp = await client.post(
                f"/v1/patches/{patch_id}/apply",
                headers={"Authorization": f"Bearer {ctx['token']}", "X-Idempotency-Key": str(uuid.uuid4())},
            )
            assert apply_resp.status_code == 409, f"Expected 409, got {apply_resp.status_code}: {apply_resp.text}"
            assert mock_write.call_count == 0


@pytest.mark.asyncio
async def test_6_replay_apply_same_idempotency_key_only_one_set_of_writes(setup_db_and_client, mock_redis_pool):
    """Test 6: Replay POST /apply with the same Idempotency-Key -> only one set of writes occurs (5 total)."""
    ctx = setup_db_and_client
    patch_id = uuid.uuid4()
    shared_key = str(uuid.uuid4())

    async with ctx["session_maker"]() as s:
        s.add(PatchCandidate(
            patch_id=patch_id,
            finding_id=ctx["finding_id"],
            unified_diff="--- a/vuln.py\n+++ b/vuln.py\n@@ -1 +1 @@\n-vuln()\n+safe()\n",
            rationale="Fix vulnerability",
            assumptions=json.dumps([]),
            tests_to_run=["pytest"],
            status=PatchStatus.approved,
            approved_by=ctx["user_id"],
            approved_at=datetime.now(timezone.utc),
        ))
        s.add(ValidationRun(
            validation_id=uuid.uuid4(),
            patch_candidate_id=patch_id,
            tenant_id=ctx["tenant_id"],
            verdict=ValidationVerdictEnum.passed,
            checks=[{"command": "pytest", "exit_code": 0, "status": "passed"}],
            sandbox_metadata={"network_mode": "none"},
            stdout_log="all checks passed",
            stderr_log="",
        ))
        await s.commit()

    with patch.object(GitHubClient, "_post_allowed_write", new_callable=AsyncMock, side_effect=_mock_write_response) as mock_write, \
         patch.object(GitHubClient, "get_ref", new_callable=AsyncMock, return_value={"object": {"sha": ctx["base_sha"]}}):
        async with httpx.AsyncClient(transport=ctx["transport"], base_url="http://test") as client:
            # Call 1: fresh apply
            resp1 = await client.post(
                f"/v1/patches/{patch_id}/apply",
                headers={"Authorization": f"Bearer {ctx['token']}", "X-Idempotency-Key": shared_key},
            )
            assert resp1.status_code == 201
            assert mock_write.call_count == 5

            # Call 2: idempotent replay with identical key
            resp2 = await client.post(
                f"/v1/patches/{patch_id}/apply",
                headers={"Authorization": f"Bearer {ctx['token']}", "X-Idempotency-Key": shared_key},
            )
            assert resp2.status_code == 201
            assert resp2.headers.get("X-Vigil-Idempotent") == "true"
            # Crucial: write count MUST still be 5, no duplicate writes!
            assert mock_write.call_count == 5
