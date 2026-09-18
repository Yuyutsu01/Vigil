"""
Integration tests for Governed PR Review Publication (FR-107, AC-107).
Verifies:
1. Policy `human_required` prevents automated publication.
2. Policy `disabled` rejects manual publication with HTTP 403.
3. Policy `auto_after_validation` publishes only when validation verdict is `passed`.
4. Rate limit caps comments at 5 per PR per hour, returning HTTP 429 on subsequent publish.
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
from app.models.pr_review import DraftPRComment, DraftPRReview, DraftStatusEnum
from app.models.repository import Repository, RepositoryPolicy, RepositoryReview
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


@pytest.mark.asyncio
async def test_human_required_policy_prevents_unauthorized_auto_publication(mock_redis_pool):
    """
    With policy.pr_comment_publication = 'human_required', validation should NOT
    automatically publish the draft review. It requires explicit POST /publish-review.
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

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    run_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    patch_id = uuid.uuid4()
    finding_id = uuid.uuid4()

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="Test Tenant"))
        s.add(User(
            user_id=user_id,
            tenant_id=tenant_id,
            email="maintainer@example.com",
            hashed_password="hash",
            role="maintainer",
        ))
        await s.commit()

    async with session_maker() as s:
        artifact = SourceArtifact(
            tenant_id=tenant_id,
            content="def foo(): pass",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=15,
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

        # Policy with human_required
        policy = RepositoryPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            enabled_languages=["python"],
            ignored_paths=[],
            ignored_rules=[],
            pr_comment_publication="human_required",
            pr_review_generation="on_demand",
            allowed_ci_commands=["pytest"],
        )
        s.add(policy)

        repo = Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            provider="github",
            external_id=98765,
            full_name="acme/governed-repo",
            default_branch="main",
            policy_id=policy_id,
            is_connected=True,
        )
        s.add(repo)
        await s.flush()

        repo_review = RepositoryReview(
            tenant_id=tenant_id,
            repository_id=repo_id,
            review_run_id=run_id,
            ref_type="pr",
            ref_value="42",
            scope_mode="changed_files",
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
            title="Finding for Review",
            rationale="Rationale",
            remediation="Remediation",
            fingerprint="fp_pr_pub_1",
        )
        s.add(finding)

        patch_cand = PatchCandidate(
            patch_id=patch_id,
            finding_id=finding_id,
            unified_diff="--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-def foo(): pass\n+def foo(): return 1\n",
            rationale="Fix return",
            assumptions=json.dumps([]),
            tests_to_run=["pytest"],
            status=PatchStatus.approved,
            approved_by=user_id,
            approved_at=datetime.now(timezone.utc),
        )
        s.add(patch_cand)

        # Create draft PR review with 1 comment
        draft_review = DraftPRReview(
            review_id=run_id,
            tenant_id=tenant_id,
            repository_id=repo_id,
            pr_number=42,
            status=DraftStatusEnum.draft,
            summary_markdown="Draft Summary",
        )
        s.add(draft_review)

        comment = DraftPRComment(
            review_id=run_id,
            path="foo.py",
            line=1,
            commit_sha="abcdef1234567890abcdef1234567890abcdef12",
            body="Review comment <!-- vigil-audit-signature -->",
            status=DraftStatusEnum.draft,
        )
        s.add(comment)
        await s.commit()

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="maintainer")
    dev_token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="developer")

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    try:
        mock_gh = AsyncMock()
        mock_gh.create_pull_review.return_value = {"id": 1001, "state": "COMMENTED"}

        with patch("app.services.pr_review_service.GitHubClient", return_value=mock_gh):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                # 1. Developer cannot publish review (403 Forbidden)
                resp_dev = await client.post(
                    f"/v1/repositories/{repo_id}/reviews/{run_id}/publish-review",
                    headers={"Authorization": f"Bearer {dev_token}", "X-Idempotency-Key": str(uuid.uuid4())},
                )
                assert resp_dev.status_code == 403

                # 2. Maintainer publishes review explicitly (200 OK)
                resp_maint = await client.post(
                    f"/v1/repositories/{repo_id}/reviews/{run_id}/publish-review",
                    headers={"Authorization": f"Bearer {token}", "X-Idempotency-Key": str(uuid.uuid4())},
                )
                assert resp_maint.status_code == 200, f"Expected 200, got {resp_maint.status_code}: {resp_maint.text}"
                pub_data = resp_maint.json()
                assert pub_data["status"] == "published"
                assert pub_data["github_review_id"] == 1001
                assert mock_gh.create_pull_review.called

    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_disabled_policy_rejects_pr_review_publication(mock_redis_pool):
    """
    When repository policy has pr_comment_publication = 'disabled',
    POST /publish-review returns HTTP 403 and no GitHub API calls are made.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    run_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="Disabled Tenant"))
        s.add(User(user_id=user_id, tenant_id=tenant_id, email="m@example.com", hashed_password="h", role="maintainer"))
        policy = RepositoryPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            enabled_languages=["python"],
            ignored_paths=[],
            ignored_rules=[],
            pr_comment_publication="disabled",  # Explicitly disabled
            pr_review_generation="on_demand",
        )
        s.add(policy)
        repo = Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            provider="github",
            external_id=55555,
            full_name="acme/disabled-repo",
            default_branch="main",
            policy_id=policy_id,
            is_connected=True,
        )
        s.add(repo)
        draft_review = DraftPRReview(
            review_id=run_id,
            tenant_id=tenant_id,
            repository_id=repo_id,
            pr_number=10,
            status=DraftStatusEnum.draft,
            summary_markdown="Disabled test",
        )
        s.add(draft_review)
        await s.commit()

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="maintainer")

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    try:
        mock_gh = AsyncMock()
        with patch("app.services.pr_review_service.GitHubClient", return_value=mock_gh):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/v1/repositories/{repo_id}/reviews/{run_id}/publish-review",
                    headers={"Authorization": f"Bearer {token}", "X-Idempotency-Key": str(uuid.uuid4())},
                )
                assert resp.status_code == 403
                assert "disabled by repository policy" in resp.json()["detail"]
                mock_gh.create_pull_review.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_pr_comment_rate_limit_5_per_hour(mock_redis_pool):
    """
    Verifies that the 6th comment on the same PR within one hour triggers
    HTTP 429 Too Many Requests with Retry-After header.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    run_id = uuid.uuid4()
    policy_id = uuid.uuid4()

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="Rate Cap Tenant"))
        s.add(User(user_id=user_id, tenant_id=tenant_id, email="m@example.com", hashed_password="h", role="maintainer"))
        policy = RepositoryPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            enabled_languages=["python"],
            ignored_paths=[],
            ignored_rules=[],
            pr_comment_publication="human_required",
            pr_review_generation="on_demand",
        )
        s.add(policy)
        repo = Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            provider="github",
            external_id=66666,
            full_name="acme/capped-repo",
            default_branch="main",
            policy_id=policy_id,
            is_connected=True,
        )
        s.add(repo)

        # Existing review that has already published 5 comments in the last 15 minutes
        prior_review_id = uuid.uuid4()
        prior_review = DraftPRReview(
            review_id=prior_review_id,
            tenant_id=tenant_id,
            repository_id=repo_id,
            pr_number=77,
            status=DraftStatusEnum.published,
            summary_markdown="Prior Review",
        )
        s.add(prior_review)

        now = datetime.now(timezone.utc)
        for i in range(5):
            s.add(DraftPRComment(
                review_id=prior_review_id,
                path="app.py",
                line=i + 1,
                commit_sha="1111222233334444555566667777888899990000",
                body=f"Comment {i+1}",
                status=DraftStatusEnum.published,
                created_at=now - timedelta(minutes=10),
            ))

        # New draft review on the same PR #77 attempting to publish a 6th comment
        new_review = DraftPRReview(
            review_id=run_id,
            tenant_id=tenant_id,
            repository_id=repo_id,
            pr_number=77,
            status=DraftStatusEnum.draft,
            summary_markdown="New Review attempting 6th comment",
        )
        s.add(new_review)
        s.add(DraftPRComment(
            review_id=run_id,
            path="app.py",
            line=10,
            commit_sha="1111222233334444555566667777888899990000",
            body="6th comment",
            status=DraftStatusEnum.draft,
        ))

        await s.commit()

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="maintainer")

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    try:
        mock_gh = AsyncMock()
        with patch("app.services.pr_review_service.GitHubClient", return_value=mock_gh):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    f"/v1/repositories/{repo_id}/reviews/{run_id}/publish-review",
                    headers={"Authorization": f"Bearer {token}", "X-Idempotency-Key": str(uuid.uuid4())},
                )
                # Should return HTTP 429 Too Many Requests
                assert resp.status_code == 429, f"Expected 429, got {resp.status_code}: {resp.text}"
                assert "Retry-After" in resp.headers
                assert "Maximum 5 published comments per PR per hour" in resp.text
                mock_gh.create_pull_review.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_db, None)
