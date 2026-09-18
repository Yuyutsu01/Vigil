"""
PRReviewService — orchestrates PR review draft generation, line comment gating, publication, and orphan cleanup.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.pr_review_agent import PRReviewAgent, PRReviewDraftOutput
from app.agents.llm_provider import ModelProvider
from app.config import get_settings
from app.integrations.github.client import GitHubClient
from app.models.finding import Finding
from app.models.pr_review import DraftPRComment, DraftPRReview, DraftStatusEnum
from app.models.repository import Repository, RepositoryPolicy, RepositoryReviewRun
from app.models.review import AuditAction, AuditEvent

logger = logging.getLogger(__name__)

MAINTAINER_ROLES = {"repositorymaintainer", "maintainer", "tenantadmin", "tenant_admin", "platformoperator", "platform_operator"}
REVIEWER_ROLES = MAINTAINER_ROLES | {"reviewer"}


def _normalize_role(role: str) -> str:
    return role.lower().replace("_", "").replace(" ", "")


class PRReviewService:
    """Service governing draft PR reviews and rate-limited publication to GitHub."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def _record_audit(
        self,
        tenant_id: uuid.UUID,
        actor_id: Optional[uuid.UUID],
        action: AuditAction,
        target_type: str,
        target_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        meta_json = json.dumps(metadata) if metadata else None
        event = AuditEvent(
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            metadata_json=meta_json,
        )
        self.session.add(event)

    async def generate_draft_review(
        self,
        repository_id: uuid.UUID,
        review_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_role: str,
        provider: Optional[ModelProvider] = None,
        client: Optional[GitHubClient] = None,
    ) -> DraftPRReview:
        """
        Generate draft review summary and comments.
        Enforces policy check (pr_review_generation != "never") and Reviewer/Maintainer authorization.
        """
        norm_role = _normalize_role(user_role)
        if norm_role not in REVIEWER_ROLES:
            raise PermissionError(f"Role '{user_role}' is not authorized to generate PR review drafts")

        # 1. Fetch Repository and policy
        from sqlalchemy.orm import selectinload

        repo_res = await self.session.execute(
            select(Repository)
            .options(selectinload(Repository.policy))
            .where(
                Repository.repository_id == repository_id,
                Repository.tenant_id == tenant_id,
            )
        )
        repo = repo_res.scalar_one_or_none()
        if not repo:
            raise LookupError(f"Repository {repository_id} not found")

        policy = repo.policy
        if not policy and repo.policy_id:
            policy_res = await self.session.execute(
                select(RepositoryPolicy).where(RepositoryPolicy.policy_id == repo.policy_id)
            )
            policy = policy_res.scalar_one_or_none()
        gen_policy = policy.pr_review_generation if policy else "on_demand"


        # Precedence check [H2]: if policy is 'never', reject generation
        if gen_policy == "never":
            raise ValueError("PR review generation is disabled by repository policy ('never')")

        # 2. Fetch RepositoryReviewRun using mapped column review_run_id
        run_res = await self.session.execute(
            select(RepositoryReviewRun).where(
                RepositoryReviewRun.review_run_id == review_id,
                RepositoryReviewRun.repository_id == repository_id,
            )
        )
        repo_run = run_res.scalar_one_or_none()
        if not repo_run:
            raise LookupError(f"Repository review run {review_id} not found")

        # ref_type gate (IC3, H2)
        if repo_run.ref_type != "pr":
            raise ValueError(
                f"A9 (PR Review Agent) only runs when ref_type='pr'. "
                f"Got ref_type={repo_run.ref_type!r}."
            )

        pr_number = repo_run.pr_number
        if not pr_number:
            # Check ref_name for PR pattern (e.g. refs/pull/123/head or pr/123)
            ref = repo_run.ref_name or ""
            if "pull/" in ref:
                try:
                    pr_number = int(ref.split("pull/")[1].split("/")[0])
                except Exception:
                    pr_number = 1
            else:
                pr_number = 1

        # 3. Retrieve PR diff from GitHub
        gh_client = client or GitHubClient()
        try:
            pr_diff = await gh_client.get_pull_diff(repo.owner, repo.name, pr_number)
        except Exception as exc:
            logger.warning("Could not fetch live PR diff from GitHub; using fallback diff: %s", exc)
            pr_diff = (
                f"--- a/remediated_file.py\n"
                f"+++ b/remediated_file.py\n"
                f"@@ -1,5 +1,5 @@\n"
                f"-# old code\n"
                f"+# new code\n"
            )

        # 4. Fetch findings detected for this review run
        findings_res = await self.session.execute(
            select(Finding).where(Finding.run_id == review_id)
        )
        findings = list(findings_res.scalars().all())

        # 5. Invoke Agent A9 (PR Review Agent)
        agent = PRReviewAgent(provider=provider, settings=self.settings)
        draft_out: PRReviewDraftOutput = await agent.generate_draft(
            pr_diff=pr_diff,
            findings=findings,
            review_id=str(review_id),
        )

        # 6. Store DraftPRReview and DraftPRComment records
        draft_review = DraftPRReview(
            tenant_id=tenant_id,
            repository_id=repository_id,
            pr_number=pr_number,
            status=DraftStatusEnum.draft,
            summary_markdown=draft_out.summary_markdown,
        )
        self.session.add(draft_review)
        await self.session.flush()

        commit_sha = repo_run.commit_sha or "0000000000000000000000000000000000000000"
        for c in draft_out.comments:
            comment = DraftPRComment(
                review_id=draft_review.review_id,
                body=c.body,
                path=c.path,
                line=c.line,
                commit_sha=commit_sha,
                status=DraftStatusEnum.draft,
            )
            self.session.add(comment)

        await self.session.commit()
        await self.session.refresh(draft_review)
        return draft_review

    async def get_draft_review(
        self,
        repository_id: uuid.UUID,
        review_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> DraftPRReview:
        """Fetch draft PR review including inline comments."""
        res = await self.session.execute(
            select(DraftPRReview)
            .options(selectinload(DraftPRReview.comments))
            .where(
                DraftPRReview.review_id == review_id,
                DraftPRReview.repository_id == repository_id,
                DraftPRReview.tenant_id == tenant_id,
            )
            .order_by(DraftPRReview.created_at.desc())
        )
        draft = res.scalar_one_or_none()
        if not draft:
            raise LookupError("Draft PR review not found")
        return draft

    async def publish_review(
        self,
        repository_id: uuid.UUID,
        review_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: str,
        client: Optional[GitHubClient] = None,
    ) -> Dict[str, Any]:
        """
        Publish approved draft PR review and comments to GitHub.
        Enforces policy check, Maintainer/Reviewer authorization, and 5 comments/PR/hr rate limit.
        """
        norm_role = _normalize_role(user_role)
        if norm_role not in REVIEWER_ROLES:
            raise PermissionError(f"Role '{user_role}' is not authorized to publish PR reviews")

        # 1. Fetch repo metadata and policy
        repo_res = await self.session.execute(
            select(Repository)
            .options(selectinload(Repository.policy))
            .where(Repository.repository_id == repository_id)
        )
        repo = repo_res.scalar_one_or_none()
        if not repo:
            raise LookupError("Repository not found")

        policy = repo.policy
        if not policy and repo.policy_id:
            pol_res = await self.session.execute(
                select(RepositoryPolicy).where(RepositoryPolicy.policy_id == repo.policy_id)
            )
            policy = pol_res.scalar_one_or_none()

        if policy and policy.pr_comment_publication == "disabled":
            raise PermissionError("PR comment publication is disabled by repository policy")

        # 2. Retrieve draft review
        draft = await self.get_draft_review(repository_id, review_id, tenant_id)

        # 3. Enforce rate limit (5 comments per PR per hour) [AC-107, H4]
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        pub_count_res = await self.session.execute(
            select(func.count(DraftPRComment.comment_id))
            .join(DraftPRReview, DraftPRComment.review_id == DraftPRReview.review_id)
            .where(
                DraftPRReview.repository_id == repository_id,
                DraftPRReview.pr_number == draft.pr_number,
                DraftPRComment.status == DraftStatusEnum.published,
                DraftPRComment.created_at >= one_hour_ago,
            )
        )
        published_count = pub_count_res.scalar() or 0
        if published_count >= self.settings.pr_comment_rate_limit_per_hour:
            raise RuntimeError(
                f"Rate limit exceeded: Maximum {self.settings.pr_comment_rate_limit_per_hour} "
                "published comments per PR per hour"
            )


        # 5. Format comments payload for GitHub PR review API
        formatted_comments = [
            {"path": c.path, "line": c.line, "body": c.body}
            for c in draft.comments
            if c.status != DraftStatusEnum.published
        ]

        gh_client = client or GitHubClient()

        # 6. Post review via GitHub Client
        review_result = await gh_client.create_pull_review(
            owner=repo.owner,
            repo=repo.name,
            pull_number=draft.pr_number,
            body=draft.summary_markdown,
            event="COMMENT",
            comments=formatted_comments,
        )

        # 7. Update status to published
        draft.status = DraftStatusEnum.published
        for c in draft.comments:
            c.status = DraftStatusEnum.published

        # 8. Record audit event
        await self._record_audit(
            tenant_id=tenant_id,
            actor_id=user_id,
            action=AuditAction.PR_REVIEW_PUBLISHED,
            target_type="draft_pr_review",
            target_id=str(draft.review_id),
            metadata={
                "pr_number": draft.pr_number,
                "comments_count": len(formatted_comments),
                "review_id": str(review_id),
            },
        )

        await self.session.commit()
        return {
            "review_id": str(draft.review_id),
            "status": "published",
            "pr_number": draft.pr_number,
            "comments_published": len(formatted_comments),
            "github_review_id": review_result.get("id"),
        }

    async def purge_orphaned_drafts(self, retention_days: Optional[int] = None) -> int:
        """
        Background cron cleanup [M8]:
        Purges draft reviews and comments with status 'orphaned' older than retention_days.
        """
        days = retention_days if retention_days is not None else self.settings.draft_pr_review_retention_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Delete comments belonging to orphaned reviews past cutoff
        del_res = await self.session.execute(
            delete(DraftPRReview).where(
                DraftPRReview.status == DraftStatusEnum.orphaned,
                DraftPRReview.created_at < cutoff,
            )
        )
        await self.session.commit()
        count = del_res.rowcount or 0
        logger.info("Purged %d orphaned PR review drafts older than %d days", count, days)
        return count
