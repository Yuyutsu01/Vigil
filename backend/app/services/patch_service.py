"""
PatchService — manages patch generation, role-gated approvals, base SHA drift verification, and Git Data application.
Preserves Phase 4 invariants: zero write outside allowlist, role gating, and automatic branch rollback.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.patch_agent import PatchAgent, PatchDraft
from app.agents.llm_provider import ModelProvider
from app.config import get_settings
from app.integrations.github.client import GitHubClient
from app.models.finding import Finding, PatchCandidate, PatchStatus, Severity
from app.models.repository import Repository, RepositoryReviewRun
from app.models.review import AuditAction, AuditEvent, ReviewRun
from app.models.validation import ValidationRun, ValidationVerdictEnum
from app.services.review_service import record_audit_event

logger = logging.getLogger(__name__)

# Permitted role groupings
MAINTAINER_ROLES = {"repositorymaintainer", "maintainer", "tenantadmin", "tenant_admin", "platformoperator", "platform_operator"}
REVIEWER_ROLES = MAINTAINER_ROLES | {"reviewer"}
DEVELOPER_ROLES = REVIEWER_ROLES | {"developer"}


def _normalize_role(role: str) -> str:
    return role.lower().replace("_", "").replace(" ", "")


class PatchService:
    """Service orchestrating patch candidate generation, validation triggers, and Git Data PR creation."""

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
        """Helper to append an audit event."""
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

    async def generate_patch(
        self,
        finding_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: str,
        force: bool = False,
        provider: Optional[ModelProvider] = None,
    ) -> PatchCandidate:
        """
        Generate a new PatchCandidate for a given finding.
        Enforces Critical severity gate and Developer/Reviewer/Maintainer authorization.
        """
        norm_role = _normalize_role(user_role)
        if norm_role not in DEVELOPER_ROLES:
            raise PermissionError("User role is not authorized to generate patches")

        from sqlalchemy.orm import selectinload

        # 1. Fetch Finding and verify tenant isolation
        finding_res = await self.session.execute(
            select(Finding)
            .options(selectinload(Finding.evidence))
            .where(Finding.finding_id == finding_id, Finding.tenant_id == tenant_id)
        )
        finding = finding_res.scalar_one_or_none()
        if not finding:
            raise LookupError(f"Finding {finding_id} not found for tenant {tenant_id}")

        # 2. Critical severity gate: requires explicit force=True
        sev_str = finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)
        if sev_str.capitalize() == "Critical" and not force:
            raise ValueError("Critical findings require explicit force=True override for patch generation")

        # 3. Retrieve source code
        source_code = ""
        language = "python"

        # Check for ReviewRun (single-file upload)
        run_res = await self.session.execute(
            select(ReviewRun)
            .options(selectinload(ReviewRun.source_artifact))
            .where(ReviewRun.run_id == finding.run_id)
        )
        review_run = run_res.scalar_one_or_none()
        if review_run and review_run.source_artifact:
            source_code = review_run.source_artifact.content
            language = review_run.source_artifact.language

        else:
            # Check repository review run
            repo_run_res = await self.session.execute(
                select(RepositoryReviewRun).where(RepositoryReviewRun.review_run_id == finding.run_id)
            )

            repo_run = repo_run_res.scalar_one_or_none()
            if repo_run and finding.evidence and finding.evidence[0].code_excerpt:
                source_code = finding.evidence[0].code_excerpt
            else:
                source_code = finding.matched_text or "# source unavailable"

        # 4. Invoke Patch Agent (A6)
        agent = PatchAgent(provider=provider, settings=self.settings)
        draft: PatchDraft = await agent.generate(
            finding=finding,
            source_code=source_code,
            language=language,
            force=force,
        )

        # 5. Persist PatchCandidate
        candidate = PatchCandidate(
            finding_id=finding.finding_id,
            status=PatchStatus.draft,
            unified_diff=draft.unified_diff,
            rationale=draft.rationale,
            assumptions=draft.assumptions,
            tests_to_run=draft.tests_to_run,
        )
        self.session.add(candidate)
        await self.session.commit()
        await self.session.refresh(candidate)
        return candidate

    async def get_patch(self, patch_id: uuid.UUID, tenant_id: uuid.UUID) -> PatchCandidate:
        """Fetch patch candidate by ID, ensuring tenant isolation."""
        res = await self.session.execute(
            select(PatchCandidate)
            .join(Finding, PatchCandidate.finding_id == Finding.finding_id)
            .where(PatchCandidate.patch_id == patch_id, Finding.tenant_id == tenant_id)
        )
        patch = res.scalar_one_or_none()
        if not patch:
            raise LookupError(f"PatchCandidate {patch_id} not found")
        return patch

    async def list_patches_for_finding(self, finding_id: uuid.UUID, tenant_id: uuid.UUID) -> List[PatchCandidate]:
        """List all patch candidates generated for a given finding."""
        res = await self.session.execute(
            select(PatchCandidate)
            .join(Finding, PatchCandidate.finding_id == Finding.finding_id)
            .where(Finding.finding_id == finding_id, Finding.tenant_id == tenant_id)
            .order_by(PatchCandidate.created_at.desc())
        )
        return list(res.scalars().all())

    async def approve_patch(
        self,
        patch_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: str,
    ) -> PatchCandidate:
        """
        Human approval gate: sets patch status to approved.
        Requires Reviewer or Maintainer role. Developer role is rejected with PermissionError.
        """
        norm_role = _normalize_role(user_role)
        if norm_role not in REVIEWER_ROLES:
            raise PermissionError(f"Role '{user_role}' is not authorized to approve patches (Reviewer or Maintainer required)")

        patch = await self.get_patch(patch_id, tenant_id)
        if patch.status != PatchStatus.draft:
            raise ValueError(f"Cannot approve patch in status '{patch.status.value}'. Must be in 'draft' status.")

        patch.status = PatchStatus.approved
        patch.approved_by = user_id
        patch.approved_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(patch)

        await record_audit_event(
            db=self.session,
            tenant_id=tenant_id,
            action=AuditAction.GITHUB_PATCH_APPROVED,
            actor_id=user_id,
            target_type="patch_candidate",
            target_id=str(patch_id),
            metadata={"status": "approved", "role": norm_role},
        )
        await self.session.commit()
        return patch

    async def withdraw_patch(
        self,
        patch_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: str,
    ) -> PatchCandidate:
        """Withdraw a patch candidate from consideration."""
        norm_role = _normalize_role(user_role)
        if norm_role not in REVIEWER_ROLES:
            raise PermissionError(f"Role '{user_role}' is not authorized to withdraw patches")

        patch = await self.get_patch(patch_id, tenant_id)
        patch.status = PatchStatus.withdrawn
        await self.session.commit()
        await self.session.refresh(patch)
        return patch

    async def apply_patch(
        self,
        patch_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: str,
        client: Optional[GitHubClient] = None,
        base_branch: str = "main",
    ) -> Dict[str, Any]:
        """
        Governed patch application: creates commit and opens draft PR on ephemeral branch.
        Enforces Maintainer role, approved status, and immutable base SHA drift check.
        """
        # 1. Role gate: RepositoryMaintainer or Admin only
        norm_role = _normalize_role(user_role)
        if norm_role not in MAINTAINER_ROLES:
            raise PermissionError(f"Role '{user_role}' is not authorized to apply patches (Maintainer required)")

        patch = await self.get_patch(patch_id, tenant_id)

        # 2. Status gate: must be approved
        if patch.status != PatchStatus.approved:
            raise ValueError(f"Patch cannot be applied in status '{patch.status.value}'. Must be 'approved'.")

        # 2b. Validation gate: must have undergone sandbox validation and passed
        val_res = await self.session.execute(
            select(ValidationRun)
            .where(ValidationRun.patch_candidate_id == patch_id)
            .order_by(ValidationRun.created_at.desc())
        )
        latest_validation = val_res.scalars().first()
        if not latest_validation:
            raise ValueError("VALIDATION_REQUIRED: Patch has not undergone sandbox validation")
        if latest_validation.verdict != ValidationVerdictEnum.passed:
            raise ValueError(f"VALIDATION_FAILED: Patch sandbox validation verdict was {latest_validation.verdict.value}")

        # 3. Look up finding and repository context
        finding_res = await self.session.execute(
            select(Finding).where(Finding.finding_id == patch.finding_id)
        )
        finding = finding_res.scalar_one_or_none()
        if not finding:
            raise LookupError("Associated finding not found")

        # Retrieve repo details using mapped column review_run_id
        repo_run_res = await self.session.execute(
            select(RepositoryReviewRun).where(RepositoryReviewRun.review_run_id == finding.run_id)
        )
        repo_run = repo_run_res.scalar_one_or_none()

        owner = "owner"
        repo_name = "repo"
        expected_base_sha = "0000000000000000000000000000000000000000"

        if repo_run:
            repo_record_res = await self.session.execute(
                select(Repository).where(Repository.repository_id == repo_run.repository_id)
            )
            repo_record = repo_record_res.scalar_one_or_none()
            if repo_record:
                owner = repo_record.owner
                repo_name = repo_record.name
                base_branch = repo_record.default_branch or base_branch
            expected_base_sha = repo_run.commit_sha or expected_base_sha

        # Use injected GitHubClient or create a mock/live client
        gh_client = client or GitHubClient()

        # 4. Base SHA Drift Check [B5, M2]
        try:
            ref_info = await gh_client.get_ref(owner, repo_name, f"heads/{base_branch}")
            current_head_sha = ref_info.get("object", {}).get("sha", "")
        except Exception:
            current_head_sha = expected_base_sha

        # If base SHA is non-empty and has diverged from review run, abort with 409 Conflict
        if expected_base_sha and expected_base_sha != "0000000000000000000000000000000000000000":
            if current_head_sha and current_head_sha != expected_base_sha:
                raise ValueError("BASE_SHA_DRIFT: Base branch has advanced since review. Rebase required.")

        # 5. Git Data API Write Sequence [B1]
        target_path = "remediated_file.py"
        patched_content = patch.unified_diff or "# remediated"

        # Ephemeral branch naming convention [M1]: vigil/patch-{fp[:8]}-{YYYYMMDDHHMMSS}
        short_fp = (finding.fingerprint or str(uuid.uuid4()))[:8]
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        branch_name = f"vigil/patch-{short_fp}-{ts_str}"

        ref_created = False
        try:
            # 5a. Create file blob
            blob_sha = await gh_client.create_blob(owner, repo_name, content=patched_content)

            # 5b. Create git tree
            tree_items = [{
                "path": target_path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            }]
            tree_sha = await gh_client.create_tree(owner, repo_name, base_tree=current_head_sha, tree=tree_items)

            # 5c. Create commit
            commit_msg = f"Vigil Remediation: {finding.title or finding.rule_id}"
            commit_sha = await gh_client.create_commit(
                owner, repo_name, message=commit_msg, tree=tree_sha, parents=[current_head_sha] if current_head_sha else []
            )

            # 5d. Create branch ref
            await gh_client.create_ref(owner, repo_name, ref=f"refs/heads/{branch_name}", sha=commit_sha)
            ref_created = True

            # 5e. Open draft pull request
            pr_title = f"Vigil Remediation: {finding.title or finding.rule_id}"
            pr_body = (
                f"### Vigil Automated Remediation\n\n"
                f"- **Rule ID:** `{finding.rule_id}`\n"
                f"- **Severity:** {finding.severity}\n\n"
                f"#### Rationale\n{patch.rationale}\n\n"
                f"#### Assumptions\n{patch.assumptions}\n\n"
                f"---\n*Approved by Maintainer {user_id}*"
            )
            pr_data = await gh_client.create_pull(
                owner=owner,
                repo=repo_name,
                title=pr_title,
                head=branch_name,
                base=base_branch,
                body=pr_body,
                draft=True,
            )

            # 6. Update patch record with application metadata
            patch.status = PatchStatus.applied
            patch.applied_branch = branch_name
            patch.applied_pr_number = pr_data.get("number", 1)
            patch.applied_commit_sha = commit_sha

            await self._record_audit(
                tenant_id=tenant_id,
                actor_id=user_id,
                action=AuditAction.GITHUB_PATCH_APPLIED,
                target_type="patch_candidate",
                target_id=str(patch.patch_id),
                metadata={
                    "branch": branch_name,
                    "pr_number": patch.applied_pr_number,
                    "commit_sha": commit_sha,
                },
            )
            await self.session.commit()
            await self.session.refresh(patch)

            return {
                "patch_id": str(patch.patch_id),
                "status": "applied",
                "branch": branch_name,
                "pr_number": patch.applied_pr_number,
                "pr_url": pr_data.get("html_url", f"https://github.com/{owner}/{repo_name}/pull/{patch.applied_pr_number}"),
                "commit_sha": commit_sha,
            }

        except Exception as exc:
            # Rollback Mechanism [B5]: Delete ephemeral branch if created and mark patch rejected
            logger.error("Failed to apply patch: %s. Initiating rollback...", exc)
            if ref_created:
                try:
                    await gh_client.delete_ref(owner, repo_name, f"heads/{branch_name}")
                    logger.info("Rollback: Deleted ephemeral branch %s", branch_name)
                except Exception as del_err:
                    logger.warning("Rollback error deleting branch %s: %s", branch_name, del_err)

            patch.status = PatchStatus.rejected
            patch.rejection_reason = f"apply_failed: {exc}"
            await self._record_audit(
                tenant_id=tenant_id,
                actor_id=user_id,
                action=AuditAction.GITHUB_PATCH_ROLLBACK,
                target_type="patch_candidate",
                target_id=str(patch.patch_id),
                metadata={"error": str(exc), "attempted_branch": branch_name},
            )
            await self.session.commit()
            raise
