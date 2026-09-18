"""
ValidationService — manages ephemeral sandbox execution, CI policy command matching, and ValidationRun persistence.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.validation_agent import ValidationAgent, ValidationVerdict
from app.config import get_settings
from app.models.finding import Finding, PatchCandidate, PatchStatus
from app.models.repository import Repository, RepositoryPolicy, RepositoryReviewRun
from app.models.review import AuditAction, AuditEvent, ReviewRun
from app.models.validation import ValidationRun, ValidationVerdictEnum
from app.sandbox.runtime import SandboxRuntime

logger = logging.getLogger(__name__)

MAINTAINER_ROLES = {"repositorymaintainer", "maintainer", "tenantadmin", "tenant_admin", "platformoperator", "platform_operator"}
REVIEWER_ROLES = MAINTAINER_ROLES | {"reviewer"}


def _normalize_role(role: str) -> str:
    return role.lower().replace("_", "").replace(" ", "")


class ValidationService:
    """Service coordinating patch validation in isolated gVisor sandbox."""

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

    async def validate_patch(
        self,
        patch_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: str,
        commands_override: Optional[List[str]] = None,
        runtime: Optional[SandboxRuntime] = None,
    ) -> ValidationRun:
        """
        Execute candidate patch in isolated sandbox against allowlisted repository commands.
        Requires Reviewer or Maintainer role. Developer role is rejected.
        """
        norm_role = _normalize_role(user_role)
        if norm_role not in REVIEWER_ROLES:
            raise PermissionError(f"Role '{user_role}' is not authorized to validate patches")

        # 1. Fetch PatchCandidate and verify tenant
        patch_res = await self.session.execute(
            select(PatchCandidate)
            .join(Finding, PatchCandidate.finding_id == Finding.finding_id)
            .where(PatchCandidate.patch_id == patch_id, Finding.tenant_id == tenant_id)
        )
        patch = patch_res.scalar_one_or_none()
        if not patch:
            raise LookupError(f"PatchCandidate {patch_id} not found")

        from sqlalchemy.orm import selectinload

        # 2. Fetch associated finding
        finding_res = await self.session.execute(
            select(Finding)
            .options(selectinload(Finding.evidence))
            .where(Finding.finding_id == patch.finding_id)
        )
        finding = finding_res.scalar_one_or_none()

        # 3. Retrieve allowed CI commands from RepositoryPolicy
        allowed_ci_commands: List[str] = []
        source_files: Dict[str, str] = {}
        repo_run = None
        policy = None

        if finding:
            # Check repo review run
            repo_run_res = await self.session.execute(
                select(RepositoryReviewRun).where(RepositoryReviewRun.review_run_id == finding.run_id)
            )

            repo_run = repo_run_res.scalar_one_or_none()
            if repo_run:
                repo_res = await self.session.execute(
                    select(Repository)
                    .options(selectinload(Repository.policy))
                    .where(Repository.repository_id == repo_run.repository_id)
                )
                repo = repo_res.scalar_one_or_none()
                if repo and repo.policy:
                    policy = repo.policy
                elif repo and repo.policy_id:
                    pol_res = await self.session.execute(
                        select(RepositoryPolicy).where(RepositoryPolicy.policy_id == repo.policy_id)
                    )
                    policy = pol_res.scalar_one_or_none()
                else:
                    policy = None

                if policy and policy.allowed_ci_commands:
                    allowed_ci_commands = policy.allowed_ci_commands

            # Fetch source code content
            run_res = await self.session.execute(
                select(ReviewRun)
                .options(selectinload(ReviewRun.source_artifact))
                .where(ReviewRun.run_id == finding.run_id)
            )
            review_run = run_res.scalar_one_or_none()
            if review_run and review_run.source_artifact:
                filename = "remediated_code.py"
                source_files[filename] = review_run.source_artifact.content
            elif finding.evidence and finding.evidence[0].code_excerpt:
                source_files["remediated_code.py"] = finding.evidence[0].code_excerpt

            else:
                source_files["remediated_code.py"] = "# source"

        if not allowed_ci_commands:
            allowed_ci_commands = ["pytest", "npm test", "ruff check"]

        # 4. Mark patch status as validating
        patch.status = PatchStatus.validating
        await self.session.commit()

        # 5. Execute Validation Agent (A7)
        agent = ValidationAgent(runtime=runtime, settings=self.settings)
        verdict: ValidationVerdict = await agent.run_validation(
            patch_candidate=patch,
            source_files=source_files,
            allowed_ci_commands=allowed_ci_commands,
            commands_to_run=commands_override,
        )

        # 6. Map verdict to Enum
        try:
            verdict_enum = ValidationVerdictEnum(verdict.verdict)
        except ValueError:
            verdict_enum = ValidationVerdictEnum.error

        # 7. Record ValidationRun
        validation_run = ValidationRun(
            patch_candidate_id=patch.patch_id,
            tenant_id=tenant_id,
            verdict=verdict_enum,
            checks=[c.model_dump() for c in verdict.checks],
            sandbox_metadata=verdict.sandbox_metadata,
            stdout_log=verdict.stdout_log,
            stderr_log=verdict.stderr_log,
            log_dir_ref=verdict.log_dir_ref,
        )
        self.session.add(validation_run)

        # 8. Update patch status based on outcome
        if verdict_enum == ValidationVerdictEnum.passed:
            patch.status = PatchStatus.approved
            # Trigger auto-publication of draft PR review if repository policy specifies auto_after_validation
            if policy and getattr(policy, "pr_comment_publication", None) == "auto_after_validation":
                try:
                    from app.services.pr_review_service import PRReviewService
                    pr_service = PRReviewService(self.session)
                    if repo_run:
                        await pr_service.publish_review(
                            repository_id=repo_run.repository_id,
                            review_id=repo_run.review_run_id,
                            tenant_id=tenant_id,
                            user_id=user_id,
                            user_role=user_role,
                        )
                except Exception as ex:
                    logger.warning("Auto publication after validation skipped/failed: %s", ex)
        else:
            patch.status = PatchStatus.rejected
            patch.rejection_reason = f"validation_{verdict_enum.value}"
            await self._record_audit(
                tenant_id=tenant_id,
                actor_id=user_id,
                action=AuditAction.GITHUB_PATCH_VALIDATION_FAILED,
                target_type="patch_candidate",
                target_id=str(patch.patch_id),
                metadata={
                    "verdict": verdict_enum.value,
                    "validation_id": str(validation_run.validation_id),
                },
            )

        await self.session.commit()
        await self.session.refresh(validation_run)
        return validation_run

    async def get_validation_run(self, validation_id: uuid.UUID, tenant_id: uuid.UUID) -> ValidationRun:
        """Fetch ValidationRun by ID, ensuring tenant isolation."""
        res = await self.session.execute(
            select(ValidationRun).where(
                ValidationRun.validation_id == validation_id,
                ValidationRun.tenant_id == tenant_id,
            )
        )
        run = res.scalar_one_or_none()
        if not run:
            raise LookupError(f"ValidationRun {validation_id} not found")
        return run

    async def list_runs_for_patch(self, patch_id: uuid.UUID, tenant_id: uuid.UUID) -> List[ValidationRun]:
        """List all validation runs executed for a given patch candidate."""
        res = await self.session.execute(
            select(ValidationRun)
            .where(
                ValidationRun.patch_candidate_id == patch_id,
                ValidationRun.tenant_id == tenant_id,
            )
            .order_by(ValidationRun.created_at.desc())
        )
        return list(res.scalars().all())
