"""
Webhook Background Worker using ARQ (B4, FR-103, FR-104).
Processes queued GitHub webhooks asynchronously with retry logic.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional
import uuid

from arq.connections import RedisSettings
from sqlalchemy import select, update

from app.config import get_settings
from app.database import async_session_factory
from app.integrations.github.webhook import should_review_pr
from app.models.repository import (
    IntegrationCredential,
    Repository,
    RepositoryPolicy,
    RepositoryReview,
    WebhookEvent,
)
from app.models.review import AuditAction, AuditEvent, ReviewRun
from app.services.audit_service import record_audit_event
from app.services.repo_review_service import RepoReviewService

logger = logging.getLogger(__name__)


async def process_repo_review_job(
    ctx: Dict[str, Any],
    repository_id: str,
    tenant_id: str,
    ref_value: str,
    scope_mode: str = "changed_files",
) -> None:
    """
    ARQ background job to execute automated repository review (B3).
    Opens a fresh database session and delegates execution to RepoReviewService.
    """
    logger.info(
        "Starting background repo review job for repo %s, ref %s (scope=%s)",
        repository_id,
        ref_value,
        scope_mode,
    )
    repo_uuid = uuid.UUID(repository_id)
    tenant_uuid = uuid.UUID(tenant_id)

    async with async_session_factory() as session:
        from sqlalchemy.orm import selectinload
        query = (
            select(Repository)
            .options(
                selectinload(Repository.credential),
                selectinload(Repository.policy),
            )
            .where(
                Repository.repository_id == repo_uuid,
                Repository.tenant_id == tenant_uuid,
            )
        )
        res = await session.execute(query)
        repo = res.scalar_one_or_none()
        if not repo:
            logger.error("Repository %s not found for review job; aborting", repository_id)
            return

        svc = RepoReviewService(session)
        try:
            review_run, repo_review = await svc.execute_repo_review(
                tenant_id=tenant_uuid,
                repo=repo,
                ref_type="commit",
                ref_value=ref_value,
                scope_mode=scope_mode,
                requested_by=None,  # system-triggered
            )
            logger.info(
                "Background review job finished for repo %s: run_id=%s, files=%d, status=%s",
                repository_id,
                review_run.run_id,
                repo_review.file_count,
                review_run.status.value,
            )

            # Downstream PR Review Draft Trigger [H2, M7]
            if repo.policy and repo.policy.pr_review_generation == "after_repo_review":
                if getattr(repo_review, "ref_type", None) != "pr":
                    logger.info("Skipping A9: ref_type=%s", getattr(repo_review, "ref_type", None))
                    return

                redis_pool = ctx.get("redis")
                if redis_pool:
                    await redis_pool.enqueue_job(
                        "process_draft_pr_review_job",
                        str(repo.repository_id),
                        str(review_run.run_id),
                    )
                else:
                    from app.services.pr_review_service import PRReviewService
                    pr_svc = PRReviewService(session)
                    try:
                        await pr_svc.generate_draft_review(
                            repository_id=repo.repository_id,
                            review_id=review_run.run_id,
                            tenant_id=repo.tenant_id,
                            user_role="maintainer",
                        )
                    except Exception as pr_err:
                        logger.error("Downstream PR review draft generation failed: %s", pr_err)

        except Exception as e:
            logger.error(
                "Background review job failed for repo %s (ref %s): %s",
                repository_id,
                ref_value,
                e,
                exc_info=True,
            )
            await record_audit_event(
                db=session,
                tenant_id=tenant_uuid,
                action=AuditAction.CREATE_REVIEW,
                target_type="repository",
                target_id=str(repo.repository_id),
                metadata={"status": "failed", "error": str(e), "ref_value": ref_value},
            )


async def process_webhook_job(ctx: Dict[str, Any], delivery_id: str, event_type: str, action: Optional[str], payload: Dict[str, Any]) -> None:
    """
    ARQ task handler for background processing of GitHub webhooks.
    """
    logger.info("Processing webhook delivery %s (%s.%s)", delivery_id, event_type, action)

    async with async_session_factory() as session:
        # Check event record
        query = select(WebhookEvent).where(WebhookEvent.delivery_id == delivery_id)
        result = await session.execute(query)
        event_record = result.scalar_one_or_none()

        if not event_record:
            logger.warning("WebhookEvent %s not found in DB; skipping", delivery_id)
            return

        if event_record.status == "processed":
            logger.info("Webhook %s already processed; skipping (idempotent)", delivery_id)
            return

        try:
            # 1. Handle installation events
            if event_type == "installation":
                inst = payload.get("installation", {})
                installation_id = inst.get("id")

                if action in ("deleted", "suspend"):
                    # Revoke credentials locally (H6)
                    cred_stmt = (
                        update(IntegrationCredential)
                        .where(IntegrationCredential.installation_id == installation_id)
                        .values(revoked_at=datetime.now(timezone.utc))
                    )
                    await session.execute(cred_stmt)

                    # Mark repos disconnected
                    repo_stmt = (
                        update(Repository)
                        .where(
                            Repository.installation_id.in_(
                                select(IntegrationCredential.credential_id).where(
                                    IntegrationCredential.installation_id == installation_id
                                )
                            )
                        )
                        .values(is_connected=False)
                    )
                    await session.execute(repo_stmt)

                    if event_record.tenant_id:
                        await record_audit_event(
                            db=session,
                            tenant_id=event_record.tenant_id,
                            action=AuditAction.GITHUB_APP_REVOKED,
                            metadata={"installation_id": installation_id, "action": action},
                        )

            # 2. Handle installation_repositories events
            elif event_type == "installation_repositories":
                inst = payload.get("installation", {})
                installation_id = inst.get("id")
                removed_repos = payload.get("repositories_removed", [])

                for r in removed_repos:
                    ext_id = r.get("id")
                    if ext_id:
                        await session.execute(
                            update(Repository)
                            .where(Repository.external_id == ext_id)
                            .values(is_connected=False)
                        )
                        if event_record.tenant_id:
                            await record_audit_event(
                                db=session,
                                tenant_id=event_record.tenant_id,
                                action=AuditAction.GITHUB_REPO_DISCONNECTED,
                                target_type="repository",
                                target_id=str(ext_id),
                                metadata={"external_id": ext_id, "full_name": r.get("full_name")},
                            )

            # 3. Handle pull_request events (B3)
            elif event_type == "pull_request" and action in ("opened", "synchronize"):
                repo_data = payload.get("repository", {})
                ext_id = repo_data.get("id")

                from sqlalchemy.orm import selectinload
                repo_query = (
                    select(Repository)
                    .options(selectinload(Repository.policy), selectinload(Repository.credential))
                    .where(Repository.external_id == ext_id, Repository.is_connected.is_(True))
                )
                repo_res = await session.execute(repo_query)
                repo = repo_res.scalar_one_or_none()

                if repo and repo.policy:
                    policy: RepositoryPolicy = repo.policy
                    if policy.auto_review_on_pr:
                        pr_data = payload.get("pull_request", {})
                        should_rev, reason = should_review_pr(
                            pr_data,
                            review_fork_prs=policy.review_fork_prs,
                            review_draft_prs=policy.review_draft_prs,
                        )
                        if should_rev:
                            head_sha = pr_data.get("head", {}).get("sha")
                            logger.info(
                                "PR #%s for repo %s eligible for automated review (head_sha=%s)",
                                pr_data.get("number"),
                                repo.full_name,
                                head_sha,
                            )
                            if head_sha:
                                redis_pool = ctx.get("redis")
                                if redis_pool:
                                    await redis_pool.enqueue_job(
                                        "process_repo_review_job",
                                        str(repo.repository_id),
                                        str(repo.tenant_id),
                                        head_sha,
                                        "changed_files",
                                    )
                                else:
                                    svc = RepoReviewService(session)
                                    try:
                                        await svc.execute_repo_review(
                                            tenant_id=repo.tenant_id,
                                            repo=repo,
                                            ref_type="commit",
                                            ref_value=head_sha,
                                            scope_mode="changed_files",
                                            requested_by=None,
                                        )
                                    except Exception as err:
                                        logger.error("Auto-review failed for PR #%s: %s", pr_data.get("number"), err, exc_info=True)
                        else:
                            logger.info("PR #%s skipped per policy: %s", pr_data.get("number"), reason)

            # 4. Handle push events (B3)
            elif event_type == "push":
                repo_data = payload.get("repository", {})
                ext_id = repo_data.get("id")

                from sqlalchemy.orm import selectinload
                repo_query = (
                    select(Repository)
                    .options(selectinload(Repository.policy), selectinload(Repository.credential))
                    .where(Repository.external_id == ext_id, Repository.is_connected.is_(True))
                )
                repo_res = await session.execute(repo_query)
                repo = repo_res.scalar_one_or_none()

                if repo and repo.policy and repo.policy.auto_review_on_push:
                    head_sha = payload.get("after")
                    if head_sha and head_sha != "0000000000000000000000000000000000000000":
                        logger.info(
                            "Push event for repo %s eligible for automated review (head_sha=%s)",
                            repo.full_name,
                            head_sha,
                        )
                        redis_pool = ctx.get("redis")
                        if redis_pool:
                            await redis_pool.enqueue_job(
                                "process_repo_review_job",
                                str(repo.repository_id),
                                str(repo.tenant_id),
                                head_sha,
                                "changed_files",
                            )
                        else:
                            svc = RepoReviewService(session)
                            try:
                                await svc.execute_repo_review(
                                    tenant_id=repo.tenant_id,
                                    repo=repo,
                                    ref_type="commit",
                                    ref_value=head_sha,
                                    scope_mode="changed_files",
                                    requested_by=None,
                                )
                            except Exception as err:
                                logger.error("Auto-review failed for push: %s", err, exc_info=True)

            # Mark processed
            event_record.status = "processed"
            event_record.processed_at = datetime.now(timezone.utc)
            await session.commit()

        except Exception as exc:
            logger.error("Error processing webhook %s: %s", delivery_id, exc, exc_info=True)
            event_record.status = "failed"
            await session.commit()
            raise exc


async def process_draft_pr_review_job(
    ctx: Dict[str, Any],
    repository_id: str,
    review_run_id: str,
) -> None:
    """
    ARQ background job to generate a draft PR review downstream of a completed repo review (H2, M7).
    """
    repo_uuid = uuid.UUID(repository_id)
    review_uuid = uuid.UUID(review_run_id)
    async with async_session_factory() as session:
        from app.services.pr_review_service import PRReviewService
        res = await session.execute(select(Repository).where(Repository.repository_id == repo_uuid))
        repo = res.scalar_one_or_none()
        if not repo:
            logger.error("Repository %s not found for draft PR review job", repository_id)
            return

        svc = PRReviewService(session)
        try:
            await svc.generate_draft_review(
                repository_id=repo_uuid,
                review_id=review_uuid,
                tenant_id=repo.tenant_id,
                user_role="maintainer",
            )
            logger.info("Draft PR review generated successfully for review %s", review_run_id)
        except Exception as exc:
            logger.error("Failed to generate draft PR review for run %s: %s", review_run_id, exc, exc_info=True)


async def purge_orphaned_drafts_job(ctx: Dict[str, Any]) -> None:
    """
    ARQ scheduled cron job to purge orphaned PR review drafts older than retention window (M8).
    Runs daily at 03:00 UTC.
    """
    async with async_session_factory() as session:
        from app.services.pr_review_service import PRReviewService
        svc = PRReviewService(session)
        try:
            count = await svc.purge_orphaned_drafts()
            logger.info("Purge orphaned drafts job completed. Purged %d drafts.", count)
        except Exception as exc:
            logger.error("Failed to purge orphaned drafts: %s", exc, exc_info=True)


from arq import cron


class WorkerSettings:
    """ARQ Worker configuration."""
    functions = [
        process_webhook_job,
        process_repo_review_job,
        process_draft_pr_review_job,
        purge_orphaned_drafts_job,
    ]
    cron_jobs = [
        cron(purge_orphaned_drafts_job, hour=3, minute=0),
    ]
    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_tries = 3
    job_timeout = 300

