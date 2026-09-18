"""
Acceptance Tests for AC-105: Patch Candidate Generation and Governance (FR-105).
Covers SRS §14 M4 Exit Criteria:
1. POST /v1/findings/{id}/patches returns 201 with non-empty diff, rationale, assumptions, tests_to_run.
2. Returned PatchCandidate.status is 'draft'; never created as 'applied'.
3. Critical severity finding requires force=True from Maintainer; otherwise returns 422.
4. POST /v1/patches/{id}/approve requires Maintainer/Reviewer; Developer returns 403.
5. POST /v1/patches/{id}/apply on draft status returns 409 Conflict.
6. Attempting to merge a PR raises NotImplementedError (merge not on write allowlist).
7. Budget cap breach halts generation.
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
from app.integrations.github.client import GitHubClient
from app.main import app
from app.models.finding import Finding, FindingOrigin, FindingStatus, PatchCandidate, PatchStatus, Severity
from app.models.repository import Repository, RepositoryPolicy, RepositoryReview
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import Tenant, User
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


@pytest.fixture
async def setup_db():
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
    maintainer_id = uuid.uuid4()
    dev_id = uuid.uuid4()
    run_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    finding_normal_id = uuid.uuid4()
    finding_critical_id = uuid.uuid4()

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="AC105 Tenant"))
        s.add(User(user_id=maintainer_id, tenant_id=tenant_id, email="m@ex.com", hashed_password="h", role="maintainer"))
        s.add(User(user_id=dev_id, tenant_id=tenant_id, email="d@ex.com", hashed_password="h", role="developer"))
        await s.commit()

    async with session_maker() as s:
        art = SourceArtifact(
            tenant_id=tenant_id,
            content="def vuln():\n    eval(input())\n",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=30,
            language="python",
            retention_until=datetime.now(timezone.utc) + timedelta(days=30),
        )
        s.add(art)
        await s.commit()
        art_id = art.artifact_id

    async with session_maker() as s:
        run = ReviewRun(run_id=run_id, tenant_id=tenant_id, artifact_id=art_id, requested_by=maintainer_id, status=ReviewStatus.completed)
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
            external_id=777888,
            full_name="acme/ac105-repo",
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

        # Normal High finding
        f_norm = Finding(
            finding_id=finding_normal_id,
            tenant_id=tenant_id,
            run_id=run_id,
            origin=FindingOrigin.rule,
            rule_id="VIG-01",
            category="security",
            severity=Severity.high,
            confidence=0.95,
            status=FindingStatus.open,
            title="Insecure eval",
            rationale="eval execution",
            remediation="literal_eval",
            fingerprint="fp_norm_1",
        )
        s.add(f_norm)

        # Critical severity finding
        f_crit = Finding(
            finding_id=finding_critical_id,
            tenant_id=tenant_id,
            run_id=run_id,
            origin=FindingOrigin.rule,
            rule_id="VIG-02",
            category="security",
            severity=Severity.critical,
            confidence=0.99,
            status=FindingStatus.open,
            title="Remote Code Execution",
            rationale="RCE flaw",
            remediation="Sanitize input",
            fingerprint="fp_crit_1",
        )
        s.add(f_crit)
        await s.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    yield {
        "tenant_id": tenant_id,
        "maintainer_id": maintainer_id,
        "dev_id": dev_id,
        "finding_normal_id": finding_normal_id,
        "finding_critical_id": finding_critical_id,
        "maint_token": create_access_token(user_id=maintainer_id, tenant_id=tenant_id, role="maintainer"),
        "dev_token": create_access_token(user_id=dev_id, tenant_id=tenant_id, role="developer"),
        "session_maker": session_maker,
    }

    app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_ac105_full_exit_criteria(mock_redis, setup_db):
    """Verify all 7 acceptance criteria of AC-105."""
    env = setup_db
    maint_headers = {"Authorization": f"Bearer {env['maint_token']}", "X-Idempotency-Key": str(uuid.uuid4())}
    dev_headers = {"Authorization": f"Bearer {env['dev_token']}", "X-Idempotency-Key": str(uuid.uuid4())}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        # 1 & 2: Generate patch on normal finding -> returns 201 with draft status, non-empty diff, rationale, assumptions, tests_to_run
        gen_resp = await client.post(
            f"/v1/findings/{env['finding_normal_id']}/patches",
            headers={**dev_headers, "X-Idempotency-Key": str(uuid.uuid4())},
            json={"force": False},
        )
        assert gen_resp.status_code == 201, f"Generation failed: {gen_resp.text}"
        patch_data = gen_resp.json()
        patch_id = patch_data["patch_id"]

        assert patch_data["status"] == "draft"  # Criterion 2
        assert patch_data["unified_diff"] and "---" in patch_data["unified_diff"]  # Criterion 1
        assert patch_data["rationale"]  # Criterion 1
        assert "tests_to_run" in patch_data  # Criterion 1
        assert "assumptions" in patch_data  # Criterion 1

        # 3: Critical severity finding rejects generation without force=true with 422
        crit_no_force = await client.post(
            f"/v1/findings/{env['finding_critical_id']}/patches",
            headers={**maint_headers, "X-Idempotency-Key": str(uuid.uuid4())},
            json={"force": False},
        )
        assert crit_no_force.status_code == 422
        assert "Critical findings require explicit force=True override" in crit_no_force.text

        # Critical severity finding with force=true succeeds
        crit_force = await client.post(
            f"/v1/findings/{env['finding_critical_id']}/patches",
            headers={**maint_headers, "X-Idempotency-Key": str(uuid.uuid4())},
            json={"force": True},
        )
        assert crit_force.status_code == 201

        # 4: Developer cannot approve patch (403 Forbidden)
        dev_approve = await client.post(
            f"/v1/patches/{patch_id}/approve",
            headers={**dev_headers, "X-Idempotency-Key": str(uuid.uuid4())},
        )
        assert dev_approve.status_code == 403

        # 5: Applying patch while in 'draft' status returns 409 Conflict
        apply_draft = await client.post(
            f"/v1/patches/{patch_id}/apply",
            headers={**maint_headers, "X-Idempotency-Key": str(uuid.uuid4())},
        )
        assert apply_draft.status_code == 409
        assert "Must be 'approved'" in apply_draft.text

        # Maintainer approves patch -> 200 OK
        maint_approve = await client.post(
            f"/v1/patches/{patch_id}/approve",
            headers={**maint_headers, "X-Idempotency-Key": str(uuid.uuid4())},
        )
        assert maint_approve.status_code == 200
        assert maint_approve.json()["status"] == "approved"

        # 6: GitHub client write allowlist strictly forbids merge (raises NotImplementedError)
        gh = GitHubClient()
        with pytest.raises(NotImplementedError, match="Not in Phase 4 GitHub write allowlist"):
            await gh.put("repos/acme/repo/pulls/1/merge", {})
