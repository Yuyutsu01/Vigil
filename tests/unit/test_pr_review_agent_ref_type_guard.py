"""
Unit tests for A9 (PR Review Agent) ref_type guard (IC3, H2).
Ensures PRReviewService.generate_draft_review rejects branch/commit ref_types and only runs for 'pr'.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.models.repository import Repository, RepositoryPolicy, RepositoryReviewRun
from app.services.pr_review_service import PRReviewService


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_ref_type", ["branch", "commit"])
async def test_pr_review_agent_ref_type_guard_rejects_non_pr(invalid_ref_type):
    """Verify that ref_type='branch' and ref_type='commit' raise ValueError."""
    repo_id = uuid.uuid4()
    review_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    mock_session = AsyncMock()

    # Mock repository
    mock_repo = Repository(
        repository_id=repo_id,
        tenant_id=tenant_id,
        full_name="org/repo",
        default_branch="main",
        is_connected=True,
    )
    mock_repo.policy = RepositoryPolicy(
        policy_id=uuid.uuid4(),
        tenant_id=tenant_id,
        pr_review_generation="on_demand",
    )

    # Mock repository review run with invalid ref_type
    mock_repo_run = RepositoryReviewRun(
        tenant_id=tenant_id,
        repository_id=repo_id,
        review_run_id=review_id,
        ref_type=invalid_ref_type,
        ref_value="refs/heads/main",
        scope_mode="diff",
    )

    # Mock execute results
    repo_result = MagicMock()
    repo_result.scalar_one_or_none.return_value = mock_repo

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = mock_repo_run

    mock_session.execute.side_effect = [repo_result, run_result]

    service = PRReviewService(mock_session)

    with pytest.raises(ValueError, match=r"A9 \(PR Review Agent\) only runs when ref_type='pr'"):
        await service.generate_draft_review(
            repository_id=repo_id,
            review_id=review_id,
            tenant_id=tenant_id,
            user_role="maintainer",
        )


@pytest.mark.asyncio
async def test_pr_review_agent_ref_type_guard_allows_pr():
    """Verify that ref_type='pr' passes the guard and generates a draft review."""
    repo_id = uuid.uuid4()
    review_id = uuid.uuid4()
    tenant_id = uuid.uuid4()

    mock_session = AsyncMock()

    mock_repo = Repository(
        repository_id=repo_id,
        tenant_id=tenant_id,
        full_name="org/repo",
        default_branch="main",
        is_connected=True,
    )
    mock_repo.policy = RepositoryPolicy(
        policy_id=uuid.uuid4(),
        tenant_id=tenant_id,
        pr_review_generation="on_demand",
    )

    mock_repo_run = RepositoryReviewRun(
        tenant_id=tenant_id,
        repository_id=repo_id,
        review_run_id=review_id,
        ref_type="pr",
        ref_value="42",
        scope_mode="diff",
    )

    repo_result = MagicMock()
    repo_result.scalar_one_or_none.return_value = mock_repo

    run_result = MagicMock()
    run_result.scalar_one_or_none.return_value = mock_repo_run

    findings_result = MagicMock()
    findings_result.scalars.return_value.all.return_value = []

    mock_session.execute.side_effect = [repo_result, run_result, findings_result]

    mock_client = AsyncMock()
    mock_client.get_pull_diff.return_value = "diff --git a/test.py b/test.py"

    from app.agents.pr_review_agent import PRReviewDraftOutput
    mock_agent = MagicMock()
    mock_agent.generate_draft = AsyncMock(return_value=PRReviewDraftOutput(
        summary_markdown="PR review summary",
        comments=[],
    ))

    service = PRReviewService(mock_session)

    with patch("app.services.pr_review_service.PRReviewAgent", return_value=mock_agent):
        draft = await service.generate_draft_review(
            repository_id=repo_id,
            review_id=review_id,
            tenant_id=tenant_id,
            user_role="maintainer",
            client=mock_client,
        )

    assert draft.pr_number == 42
    assert draft.summary_markdown == "PR review summary"
    assert mock_session.add.called
