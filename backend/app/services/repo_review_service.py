"""
Scoped Repository Review Service (FR-103, FR-104, B5, C1, M7, M8).
Orchestrates multi-file review with aggregate budget tracking, hard cost cap ($5.00),
zero-source-persistence, and cross-file finding deduplication.
"""
from __future__ import annotations

import hashlib
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.github.client import GitHubClient
from app.integrations.github.policy import is_file_eligible
from app.integrations.github.scope import resolve_review_scope
from app.integrations.github.snapshot import SnapshotFile
from app.agents.graph import run_review_graph
from app.agents.llm_provider import get_provider
from app.agents.state import ReviewGraphState
from app.models.finding import (
    Evidence,
    EvidenceKind,
    Finding,
    FindingOrigin,
    FindingStatus,
    Severity,
)
from app.models.repository import (
    IntegrationCredential,
    Repository,
    RepositoryPolicy,
    RepositoryReview,
)
from app.models.review import (
    AuditAction,
    AuditEvent,
    ReviewRun,
    ReviewStatus,
    SourceArtifact,
)
from app.rules.engine import compute_fingerprint
from app.services.audit_service import record_audit_event
from app.services.review_service import _persist_single_finding, _persist_tool_findings

logger = logging.getLogger(__name__)


class RepoReviewService:
    """
    Coordinates repository scoped analysis across multiple files.
    Enforces aggregate budgets (50 LLM calls, 500k tokens, $5.00 cost, 600s deadline).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.settings = get_settings()

    async def estimate_review_cost(
        self,
        repo: Repository,
        ref_type: str,
        ref_value: str,
        scope_mode: str,
        directory_filter: Optional[str] = None,
        specific_files: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Compute pre-flight cost and token estimate (C1, GET /v1/repositories/{id}/cost-preview).
        NOTE: This is a pre-flight heuristic approximation (1 token per ~4 chars) and is allowed
        to be approximate. Real usage is tracked via LangGraph execution during review.
        """
        if not repo.credential:
            raise ValueError("Repository has no active integration credential")

        client = GitHubClient(
            installation_id=repo.credential.installation_id,
            private_key_ref=repo.credential.encrypted_private_key_ref,
        )

        owner, repo_name = repo.full_name.split("/")
        policy = repo.policy

        files = await resolve_review_scope(
            client=client,
            owner=owner,
            repo=repo_name,
            ref_type=ref_type,
            ref_value=ref_value,
            scope_mode=scope_mode,
            enabled_languages=policy.enabled_languages if policy else ["python", "javascript", "typescript"],
            ignored_paths=policy.ignored_paths if policy else [],
            max_files=policy.max_files_per_review if policy else 500,
            directory_filter=directory_filter,
            specific_files=specific_files,
        )

        total_bytes = sum(f.size_bytes for f in files)
        # Approximate 1 token per 4 characters
        est_input_tokens = sum(len(f.content) // 4 for f in files)
        # Estimate ~500 output tokens per file analyzed
        est_output_tokens = len(files) * 500

        est_cost = (
            est_input_tokens * self.settings.repo_review_input_cost_per_token
            + est_output_tokens * self.settings.repo_review_output_cost_per_token
        )

        cap = self.settings.repo_review_max_cost_usd
        exceeds_cap = est_cost > cap

        return {
            "file_count": len(files),
            "total_bytes": total_bytes,
            "estimated_input_tokens": est_input_tokens,
            "estimated_output_tokens": est_output_tokens,
            "estimated_cost_usd": round(est_cost, 4),
            "cost_cap_usd": cap,
            "exceeds_cap": exceeds_cap,
        }

    async def execute_repo_review(
        self,
        tenant_id: uuid.UUID,
        repo: Repository,
        ref_type: str,
        ref_value: str,
        scope_mode: str,
        directory_filter: Optional[str] = None,
        specific_files: Optional[List[str]] = None,
        requested_by: Optional[uuid.UUID] = None,
    ) -> Tuple[ReviewRun, RepositoryReview]:
        """
        Execute scoped repository review with aggregate budget tracking and zero-persistence.
        """
        start_time = time.time()

        if not repo.credential:
            raise ValueError("Repository has no active integration credential")

        client = GitHubClient(
            installation_id=repo.credential.installation_id,
            private_key_ref=repo.credential.encrypted_private_key_ref,
        )

        owner, repo_name = repo.full_name.split("/")
        policy = repo.policy
        enabled_languages = policy.enabled_languages if policy else ["python", "javascript", "typescript"]
        ignored_paths = policy.ignored_paths if policy else []
        max_files = policy.max_files_per_review if policy else 500

        # 1. Fetch scoped files into memory
        files: List[SnapshotFile] = await resolve_review_scope(
            client=client,
            owner=owner,
            repo=repo_name,
            ref_type=ref_type,
            ref_value=ref_value,
            scope_mode=scope_mode,
            enabled_languages=enabled_languages,
            ignored_paths=ignored_paths,
            max_files=max_files,
            directory_filter=directory_filter,
            specific_files=specific_files,
        )

        # 2. Zero source code persistence: create lightweight placeholder artifact
        total_bytes = sum(f.size_bytes for f in files)
        ref_digest = hashlib.sha256(f"{repo.repository_id}:{ref_value}:{time.time()}".encode()).hexdigest()

        retention_days = getattr(self.settings, "source_artifact_retention_days", 30)
        retention_until = datetime.now(timezone.utc) + timedelta(days=retention_days)

        placeholder_artifact = SourceArtifact(
            tenant_id=tenant_id,
            content="[REPOSITORY_REVIEW_MEMORY_ONLY]",
            checksum=ref_digest,
            language="mixed",
            size_bytes=total_bytes,
            retention_until=retention_until,
            legal_hold=False,
        )
        self.session.add(placeholder_artifact)
        await self.session.flush()

        # 3. Entity ordering (M7): Create ReviewRun first and flush
        review_run = ReviewRun(
            tenant_id=tenant_id,
            artifact_id=placeholder_artifact.artifact_id,
            status=ReviewStatus.running,
            requested_by=requested_by or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            started_at=datetime.now(timezone.utc),
        )
        self.session.add(review_run)
        await self.session.flush()

        # 4. Create RepositoryReview linked to ReviewRun
        repo_review = RepositoryReview(
            tenant_id=tenant_id,
            repository_id=repo.repository_id,
            review_run_id=review_run.run_id,
            ref_type=ref_type,
            ref_value=ref_value,
            scope_mode=scope_mode,
            file_count=len(files),
            llm_calls=0,
            tokens_used=0,
        )
        self.session.add(repo_review)

        # Audit review started
        await record_audit_event(
            db=self.session,
            tenant_id=tenant_id,
            action=AuditAction.GITHUB_REPO_REVIEW_STARTED,
            actor_id=requested_by,
            target_type="repository",
            target_id=str(repo.repository_id),
            metadata={
                "repository_id": str(repo.repository_id),
                "full_name": repo.full_name,
                "ref_type": ref_type,
                "ref_value": ref_value,
                "file_count": len(files),
            },
        )
        await self.session.flush()

        # 5. Budget limits (B2)
        max_llm_calls = self.settings.repo_review_max_llm_calls
        max_tokens = self.settings.repo_review_max_total_tokens
        max_seconds = self.settings.repo_review_max_wall_clock_seconds
        max_cost = self.settings.repo_review_max_cost_usd

        # M8: Cross-file deduplication set: key is (fingerprint, source_file_path)
        seen_findings: set[Tuple[str, str]] = set()

        total_tokens = 0
        total_llm_calls = 0
        total_cost = 0.0
        parked_reason: Optional[str] = None
        total_findings_count = 0

        provider = get_provider(self.settings.llm_provider)

        # 6. Analyze each file using LangGraph review pipeline (B1, B2)
        for file in files:
            # Check elapsed time
            elapsed = time.time() - start_time
            if elapsed >= max_seconds:
                parked_reason = "deadline_exceeded"
                break

            # Check aggregate budget caps before running pipeline (B2)
            if total_cost >= max_cost:
                parked_reason = "cost_cap_exceeded"
                break
            if total_llm_calls >= max_llm_calls:
                parked_reason = "call_budget_exhausted"
                break
            if total_tokens >= max_tokens:
                parked_reason = "token_budget_exhausted"
                break

            # Execute full review graph per file (B1)
            state = await run_review_graph(
                run_id=review_run.run_id,
                tenant_id=tenant_id,
                source_code=file.content,
                language=file.language,
                provider=provider,
            )

            # Aggregate real metrics from state (B2)
            file_tokens = getattr(state, "token_usage", 0) or 0
            file_calls = getattr(state, "iterations", 0) or 0
            total_tokens += file_tokens
            total_llm_calls += file_calls
            real_cost = (file_tokens / 1000.0) * self.settings.llm_cost_per_1k_input_tokens
            total_cost += real_cost

            if getattr(state, "parked_reason", None) and not parked_reason:
                parked_reason = state.parked_reason

            # Persist raw tool findings if present (tool adapter stage)
            tool_finding_map = None
            if getattr(state, "tool_findings", None):
                tool_finding_map = await _persist_tool_findings(
                    self.session, review_run.run_id, tenant_id, state.tool_findings
                )

            # Persist final findings with deduplication and source_file_path (B1, M8)
            for df in state.final_findings:
                ev_kind_val = (
                    df.evidence_kind.value
                    if hasattr(df.evidence_kind, "value")
                    else str(df.evidence_kind)
                )
                fp = compute_fingerprint(
                    rule_id=df.rule_id or "unknown",
                    ast_path=df.ast_path or "",
                    matched_text=df.matched_text or "",
                    evidence_kind=ev_kind_val,
                )

                # Cross-file dedup check (M8): (fingerprint, source_file_path)
                dedup_key = (fp, file.path)
                if dedup_key in seen_findings:
                    continue
                seen_findings.add(dedup_key)

                await _persist_single_finding(
                    db=self.session,
                    run_id=review_run.run_id,
                    tenant_id=tenant_id,
                    df=df,
                    source_file_path=file.path,
                    tool_finding_map=tool_finding_map,
                )
                total_findings_count += 1

            # File processed; discard content from memory immediately (zero persistence)
            del file.content

        # 7. Finalize status and update records
        repo_review.llm_calls = total_llm_calls
        repo_review.tokens_used = total_tokens
        repo_review.budget_paused_reason = parked_reason

        if parked_reason:
            if total_findings_count > 0:
                review_run.status = ReviewStatus.partial
            else:
                review_run.status = ReviewStatus.budget_paused
            review_run.parked_reason = parked_reason
        else:
            review_run.status = ReviewStatus.completed

        review_run.completed_at = datetime.now(timezone.utc)
        await self.session.commit()

        return review_run, repo_review
