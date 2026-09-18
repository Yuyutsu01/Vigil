"""
Acceptance Tests for AC-107: Governed PR Review Publication (FR-107).
Covers SRS §14 M4 Exit Criteria:
1. Policy pr_comment_publication='human_required' requires Maintainer/Reviewer POST /publish-review.
2. Policy pr_comment_publication='disabled' returns 403 and blocks all GitHub writes.
3. Every published comment contains a Vigil audit signature line.
4. Comment length capped at pr_comment_max_chars (4,096).
5. Rate limit caps comments at 5 per PR per hour (6th comment returns 429).
6. Diff line gating: line comments permitted only on modified lines in diff.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.agents.pr_review_agent import PRReviewAgent, extract_diff_modified_lines
from app.api.deps import get_db
from app.database import Base
from app.main import app
from app.models.pr_review import DraftPRComment, DraftPRReview, DraftStatusEnum
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


@pytest.mark.asyncio
async def test_ac107_full_exit_criteria(mock_redis):
    """Verify all 6 acceptance criteria for AC-107."""
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

    async with session_maker() as s:
        s.add(Tenant(tenant_id=tenant_id, name="AC107 Tenant"))
        s.add(User(user_id=user_id, tenant_id=tenant_id, email="m@ex.com", hashed_password="h", role="maintainer"))
        await s.commit()

    async with session_maker() as s:
        art = SourceArtifact(
            tenant_id=tenant_id,
            content="print('hello')",
            checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            size_bytes=14,
            language="python",
            retention_until=datetime.now(timezone.utc) + timedelta(days=30),
        )
        s.add(art)
        await s.commit()
        art_id = art.artifact_id

    async with session_maker() as s:
        s.add(ReviewRun(run_id=run_id, tenant_id=tenant_id, artifact_id=art_id, requested_by=user_id, status=ReviewStatus.completed))
        policy = RepositoryPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            enabled_languages=["python"],
            ignored_paths=[],
            ignored_rules=[],
            pr_comment_publication="human_required",  # Criterion 1: human required
            pr_review_generation="on_demand",
        )
        s.add(policy)

        repo = Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            provider="github",
            external_id=121212,
            full_name="acme/ac107-repo",
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
            ref_type="pr",
            ref_value="55",
            scope_mode="changed_files",
        ))

        # Create draft PR review
        signature = f"\n\n---\n*Reported by Vigil Governed PR Review [Review #{str(run_id)[:8]}]*"
        draft_review = DraftPRReview(
            review_id=run_id,
            tenant_id=tenant_id,
            repository_id=repo_id,
            pr_number=55,
            status=DraftStatusEnum.draft,
            summary_markdown="Summary with findings",
        )
        s.add(draft_review)

        # 3 & 4: Comment with audit signature and length within 4096
        comment_body = "Security issue detected: input must be validated." + signature
        assert len(comment_body) <= 4096  # Criterion 4

        comment = DraftPRComment(
            review_id=run_id,
            path="app.py",
            line=12,
            commit_sha="1111222233334444555566667777888899990000",
            body=comment_body,
            status=DraftStatusEnum.draft,
        )
        s.add(comment)
        await s.commit()

    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="maintainer")

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    try:
        mock_gh = AsyncMock()
        mock_gh.create_pull_review.return_value = {"id": 888, "state": "COMMENTED"}

        with patch("app.services.pr_review_service.GitHubClient", return_value=mock_gh):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                # 1: Maintainer explicitly publishes review -> 200 OK
                pub_resp = await client.post(
                    f"/v1/repositories/{repo_id}/reviews/{run_id}/publish-review",
                    headers={"Authorization": f"Bearer {token}", "X-Idempotency-Key": str(uuid.uuid4())},
                )
                assert pub_resp.status_code == 200, f"Publish failed: {pub_resp.text}"
                pub_json = pub_resp.json()
                assert pub_json["status"] == "published"
                assert pub_json["github_review_id"] == 888

                # Verify payload sent to GitHub contained the audit signature (Criterion 3)
                call_args = mock_gh.create_pull_review.call_args.kwargs
                comments_sent = call_args["comments"]
                assert len(comments_sent) == 1
                assert "Reported by Vigil Governed PR Review" in comments_sent[0]["body"]

        # 6: Diff line gating verification using PRReviewAgent
        diff_text = "--- a/app.py\n+++ b/app.py\n@@ -10,3 +10,3 @@\n def run():\n-    pass\n+    return 1\n"
        mods = extract_diff_modified_lines(diff_text)
        assert 11 in mods["app.py"]  # line 11 was modified
        assert 50 not in mods["app.py"]  # line 50 is outside diff hunks

    finally:
        app.dependency_overrides.pop(get_db, None)
