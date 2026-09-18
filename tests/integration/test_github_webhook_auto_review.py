"""
Integration test for GitHub webhook automated review triggering (B3).
Verifies that PR webhooks check policy, enqueue process_repo_review_job,
execute the review job, and filter out fork PRs when review_fork_prs=False.
"""
import hashlib
import hmac
import json
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.config import get_settings
from app.database import Base
from app.integrations.github.snapshot import SnapshotFile
from app.integrations.github.webhook_worker import (
    process_repo_review_job,
    process_webhook_job,
)
from app.main import app
from app.models.repository import (
    IntegrationCredential,
    Repository,
    RepositoryPolicy,
    RepositoryReview,
    WebhookEvent,
)
from app.models.review import ReviewRun, ReviewStatus
from app.models.tenant import Tenant


@pytest.mark.asyncio
async def test_webhook_auto_review_pr_flow_and_fork_filtering():
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
    cred_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    ext_repo_id = 987654321

    secret = "test-webhook-secret-primary"
    settings = get_settings()
    settings.github_app_webhook_secret = secret

    # Seed Database
    async with session_maker() as session:
        session.add(Tenant(tenant_id=tenant_id, name="Webhook Tenant"))
        await session.commit()

        cred = IntegrationCredential(
            credential_id=cred_id,
            tenant_id=tenant_id,
            provider="github",
            installation_id=1234,
            encrypted_private_key_ref="vault://key",
        )
        session.add(cred)

        policy = RepositoryPolicy(
            policy_id=policy_id,
            tenant_id=tenant_id,
            enabled_languages=["python"],
            ignored_paths=[],
            ignored_rules=[],
            max_files_per_review=100,
            auto_review_on_pr=True,
            review_fork_prs=False,  # Block fork PRs
            review_draft_prs=False,
        )
        session.add(policy)

        repo = Repository(
            repository_id=repo_id,
            tenant_id=tenant_id,
            installation_id=cred_id,
            policy_id=policy_id,
            external_id=ext_repo_id,
            full_name="vigil-test/auto-review-repo",
            default_branch="main",
            is_connected=True,
        )
        session.add(repo)
        await session.commit()

    async def override_get_db():
        async with session_maker() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db

    # Setup mock ARQ pool on app.state
    mock_arq_pool = AsyncMock()
    app.state.arq_pool = mock_arq_pool

    # 1. Send signed PR webhook via POST /v1/webhooks/github
    payload = {
        "action": "opened",
        "repository": {
            "id": ext_repo_id,
            "full_name": "vigil-test/auto-review-repo",
        },
        "pull_request": {
            "number": 42,
            "draft": False,
            "head": {
                "sha": "abcdef1234567890abcdef1234567890abcdef12",
                "repo": {"fork": False},
            },
        },
    }
    payload_bytes = json.dumps(payload).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()

    delivery_id = f"delivery-pr-{uuid.uuid4()}"
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/v1/webhooks/github",
                content=payload_bytes,
                headers={
                    "X-Hub-Signature-256": sig,
                    "X-GitHub-Delivery": delivery_id,
                    "X-GitHub-Event": "pull_request",
                    "Content-Type": "application/json",
                },
            )
            assert resp.status_code == 202
            # Verify Webhook was accepted and enqueued to app.state.arq_pool
            mock_arq_pool.enqueue_job.assert_called_once()

        # 2. Test worker execution of process_webhook_job
        mock_redis = AsyncMock()
        ctx = {"redis": mock_redis}

        with patch("app.integrations.github.webhook_worker.async_session_factory", session_maker):
            await process_webhook_job(
                ctx=ctx,
                delivery_id=delivery_id,
                event_type="pull_request",
                action="opened",
                payload=payload,
            )

        # Assert process_repo_review_job was enqueued with PR head sha
        mock_redis.enqueue_job.assert_called_once_with(
            "process_repo_review_job",
            str(repo_id),
            str(tenant_id),
            "abcdef1234567890abcdef1234567890abcdef12",
            "changed_files",
        )

        # 3. Call process_repo_review_job directly and assert RepositoryReview row created
        mock_files = [
            SnapshotFile(
                path="src/main.py",
                content="eval(user_input)\n",
                language="python",
                size_bytes=18,
            )
        ]

        with patch("app.integrations.github.webhook_worker.async_session_factory", session_maker), \
             patch("app.services.repo_review_service.resolve_review_scope", new=AsyncMock(return_value=mock_files)):
            await process_repo_review_job(
                ctx=ctx,
                repository_id=str(repo_id),
                tenant_id=str(tenant_id),
                ref_value="abcdef1234567890abcdef1234567890abcdef12",
                scope_mode="changed_files",
            )

        # Verify DB rows
        async with session_maker() as session:
            q_rr = select(RepositoryReview).where(RepositoryReview.repository_id == repo_id)
            repo_review = (await session.execute(q_rr)).scalar_one_or_none()
            assert repo_review is not None
            assert repo_review.ref_value == "abcdef1234567890abcdef1234567890abcdef12"

            q_run = select(ReviewRun).where(ReviewRun.run_id == repo_review.review_run_id)
            review_run = (await session.execute(q_run)).scalar_one()
            assert review_run.status in (ReviewStatus.completed, ReviewStatus.budget_paused)

        # 4. Test Fork PR (review_fork_prs=False): assert no job is enqueued
        mock_redis.reset_mock()
        fork_delivery_id = "delivery-pr-fork-review-2"

        # Record webhook event for fork PR
        async with session_maker() as session:
            session.add(WebhookEvent(
                delivery_id=fork_delivery_id,
                provider="github",
                event_type="pull_request",
                action="opened",
                payload_hash="hash-fork-pr",
                status="pending",
            ))
            await session.commit()

        fork_payload = {
            "action": "opened",
            "repository": {
                "id": ext_repo_id,
                "full_name": "vigil-test/auto-review-repo",
            },
            "pull_request": {
                "number": 43,
                "draft": False,
                "head": {
                    "sha": "forksha1234567890abcdef1234567890abcdef12",
                    "repo": {"fork": True},  # Forked repo
                },
            },
        }

        with patch("app.integrations.github.webhook_worker.async_session_factory", session_maker):
            await process_webhook_job(
                ctx=ctx,
                delivery_id=fork_delivery_id,
                event_type="pull_request",
                action="opened",
                payload=fork_payload,
            )

        # Fork PR must NOT trigger any review job
        mock_redis.enqueue_job.assert_not_called()

    finally:
        app.dependency_overrides.clear()
