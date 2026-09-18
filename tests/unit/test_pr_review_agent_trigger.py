"""
Unit tests for PR Review Agent invocation policies (H2, M7).
Verifies behavior under "never", "after_repo_review", and "on_demand" repository policies.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.models.repository import Repository, RepositoryPolicy, RepositoryReviewRun
from app.services.pr_review_service import PRReviewService


@pytest.mark.asyncio
async def test_policy_never_blocks_generation():
    """Verify policy='never' raises ValueError and prevents A9 invocation."""
    mock_session = AsyncMock()

    repo_id = uuid.uuid4()
    review_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    # Mock repository with policy='never'
    repo = Repository(
        repository_id=repo_id,
        tenant_id=tenant_id,
        full_name="org/repo",
        external_id=12345,
    )
    repo.policy = MagicMock(pr_review_generation="never")

    # Configure session executes
    mock_session.execute.return_value = MagicMock(scalar_one_or_none=lambda: repo)


    service = PRReviewService(mock_session)
    with pytest.raises(ValueError, match="PR review generation is disabled by repository policy"):
        await service.generate_draft_review(
            repository_id=repo_id,
            review_id=review_id,
            tenant_id=tenant_id,
            user_role="maintainer",
        )


@pytest.mark.asyncio
async def test_downstream_trigger_policy_after_repo_review():
    """Verify webhook worker enqueues PR review draft job when policy is 'after_repo_review'."""
    from app.integrations.github.webhook_worker import process_repo_review_job

    mock_redis = AsyncMock()
    mock_ctx = {"redis": mock_redis}

    repo_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())

    mock_repo = MagicMock(
        repository_id=uuid.UUID(repo_id),
        tenant_id=uuid.UUID(tenant_id),
        policy=MagicMock(pr_review_generation="after_repo_review"),
    )
    mock_review_run = MagicMock(
        run_id=uuid.uuid4(),
        status=MagicMock(value="completed"),
    )
    mock_repo_review = MagicMock(
        file_count=2,
        pr_number=42,
        ref_name="refs/pull/42/head",
        ref_type="pr",
    )

    with patch("app.integrations.github.webhook_worker.async_session_factory") as mock_session_factory:
        mock_sess = AsyncMock()
        mock_sess.execute.return_value = MagicMock(scalar_one_or_none=lambda: mock_repo)
        mock_session_factory.return_value.__aenter__.return_value = mock_sess

        with patch("app.integrations.github.webhook_worker.RepoReviewService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.execute_repo_review = AsyncMock(return_value=(mock_review_run, mock_repo_review))
            mock_svc_cls.return_value = mock_svc

            await process_repo_review_job(
                ctx=mock_ctx,
                repository_id=repo_id,
                tenant_id=tenant_id,
                ref_value="pr/42",
            )

    # Asserts downstream job enqueued in Redis
    mock_redis.enqueue_job.assert_called_once_with(
        "process_draft_pr_review_job",
        str(mock_repo.repository_id),
        str(mock_review_run.run_id),
    )


@pytest.mark.asyncio
async def test_downstream_trigger_skipped_on_demand_policy():
    """Verify webhook worker does NOT enqueue PR review draft job when policy is 'on_demand'."""
    from app.integrations.github.webhook_worker import process_repo_review_job

    mock_redis = AsyncMock()
    mock_ctx = {"redis": mock_redis}

    repo_id = str(uuid.uuid4())
    tenant_id = str(uuid.uuid4())

    mock_repo = MagicMock(
        repository_id=uuid.UUID(repo_id),
        tenant_id=uuid.UUID(tenant_id),
        policy=MagicMock(pr_review_generation="on_demand"),
    )
    mock_review_run = MagicMock(
        run_id=uuid.uuid4(),
        status=MagicMock(value="completed"),
    )
    mock_repo_review = MagicMock(
        file_count=2,
        pr_number=42,
        ref_name="refs/pull/42/head",
    )

    with patch("app.integrations.github.webhook_worker.async_session_factory") as mock_session_factory:
        mock_sess = AsyncMock()
        mock_sess.execute.return_value = MagicMock(scalar_one_or_none=lambda: mock_repo)
        mock_session_factory.return_value.__aenter__.return_value = mock_sess

        with patch("app.integrations.github.webhook_worker.RepoReviewService") as mock_svc_cls:
            mock_svc = MagicMock()
            mock_svc.execute_repo_review = AsyncMock(return_value=(mock_review_run, mock_repo_review))
            mock_svc_cls.return_value = mock_svc

            await process_repo_review_job(
                ctx=mock_ctx,
                repository_id=repo_id,
                tenant_id=tenant_id,
                ref_value="pr/42",
            )

    # Asserts downstream job NOT called
    mock_redis.enqueue_job.assert_not_called()
