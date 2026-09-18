"""
Review service — orchestrates the full review lifecycle.
Handles consent verification, artifact creation, run tracking, and persistence of findings.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.graph import run_review_graph
from app.agents.llm_provider import ModelProvider
from app.config import get_settings
from app.models.finding import (
    Evidence,
    EvidenceKind,
    Finding,
    FindingOrigin,
    Severity,
)
from app.models.review import AuditAction, ReviewRun, ReviewStatus, SourceArtifact
from app.rules.engine import DetectedFinding, compute_fingerprint
from app.services.audit_service import record_audit_event
from app.services.consent_service import verify_consent_for_review

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_and_run_review(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    source_text: str,
    language: str,
    provider: Optional[ModelProvider] = None,
) -> ReviewRun:
    """
    Full review lifecycle:
    1. Verify consent
    2. Create SourceArtifact and ReviewRun
    3. Run LangGraph agent
    4. Persist findings
    5. Update run status
    6. Write audit event
    """
    settings = get_settings()

    # 1. Consent check
    allowed, reason = await verify_consent_for_review(db, user_id, tenant_id)
    if not allowed:
        raise PermissionError(reason)

    # 2. Create SourceArtifact
    content_bytes = source_text.encode("utf-8")
    checksum = hashlib.sha256(content_bytes).hexdigest()
    retention_until = _now() + timedelta(days=settings.source_artifact_retention_days)

    artifact = SourceArtifact(
        artifact_id=uuid.uuid4(),
        tenant_id=tenant_id,
        content=source_text,
        checksum=checksum,
        language=language,
        size_bytes=len(content_bytes),
        retention_until=retention_until,
        legal_hold=False,
    )
    db.add(artifact)
    await db.flush()

    # 3. Create ReviewRun
    run_id = uuid.uuid4()
    run = ReviewRun(
        run_id=run_id,
        tenant_id=tenant_id,
        artifact_id=artifact.artifact_id,
        status=ReviewStatus.running,
        requested_by=user_id,
        legal_hold=False,
        started_at=_now(),
    )
    db.add(run)
    await db.flush()

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=user_id,
        action=AuditAction.CREATE_REVIEW,
        target_type="ReviewRun",
        target_id=str(run_id),
        metadata={"language": language, "size_bytes": len(content_bytes)},
    )
    await db.commit()

    # 4. Run LangGraph agent
    try:
        state = await run_review_graph(
            run_id=run_id,
            tenant_id=tenant_id,
            source_code=source_text,
            language=language,
            provider=provider,
        )
    except Exception as e:
        logger.error("LangGraph failed for run %s: %s", run_id, e, exc_info=True)
        # Update run as failed
        run.status = ReviewStatus.failed
        run.error_message = str(e)
        run.completed_at = _now()
        await db.merge(run)
        await db.commit()
        return run

    # 5. Persist findings
    await _persist_findings(db, run_id, tenant_id, state.final_findings)

    # 6. Update run status
    if state.parked_reason:
        if state.final_findings:
            run.status = ReviewStatus.partial
        else:
            run.status = ReviewStatus.budget_paused
    elif state.has_error:
        run.status = ReviewStatus.failed
    else:
        run.status = ReviewStatus.completed

    run.completed_at = _now()
    run.prompt_version = state.prompt_version
    run.parked_reason = state.parked_reason
    run.error_message = state.error_message

    await db.merge(run)

    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=user_id,
        action=AuditAction.COMPLETE_REVIEW,
        target_type="ReviewRun",
        target_id=str(run_id),
        metadata={
            "status": run.status.value,
            "finding_count": len(state.final_findings),
        },
    )
    await db.commit()
    return run


async def _persist_findings(
    db: AsyncSession,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    detected: List[DetectedFinding],
) -> None:
    """Persist DetectedFinding objects to the database as Finding + Evidence rows."""
    settings = get_settings()

    for df in detected:
        fingerprint = compute_fingerprint(
            df.rule_id or "unknown",
            df.ast_path or "",
            df.matched_text or "",
            df.evidence_kind.value,
        )

        finding = Finding(
            finding_id=uuid.uuid4(),
            run_id=run_id,
            tenant_id=tenant_id,
            fingerprint=fingerprint,
            origin=df.origin,
            rule_id=df.rule_id,
            category=df.category,
            severity=Severity(df.severity) if isinstance(df.severity, str) else df.severity,
            confidence=df.confidence,
            title=df.title[:255],
            rationale=df.rationale,
            remediation=df.remediation,
        )
        db.add(finding)
        await db.flush()

        # Evidence record
        evidence_kind_map = {
            "ast_node": EvidenceKind.ast_node,
            "token_regex": EvidenceKind.token_regex,
            "llm_reasoning": EvidenceKind.llm_reasoning,
        }
        ek = (
            df.evidence_kind
            if isinstance(df.evidence_kind, EvidenceKind)
            else evidence_kind_map.get(str(df.evidence_kind), EvidenceKind.ast_node)
        )

        ev = Evidence(
            evidence_id=uuid.uuid4(),
            finding_id=finding.finding_id,
            start_line=df.start_line,
            start_col=df.start_col,
            end_line=df.end_line,
            end_col=df.end_col,
            ast_path=df.ast_path,
            tool_name="vigil-rules" if df.origin == FindingOrigin.rule else "vigil-agent",
            rule_id=df.rule_id,
            code_excerpt=df.matched_text[:500] if df.matched_text else None,
            evidence_kind=ek,
        )
        db.add(ev)


async def get_review_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Optional[ReviewRun]:
    """Retrieve a ReviewRun with findings, enforcing tenant isolation."""
    result = await db.execute(
        select(ReviewRun)
        .options(
            selectinload(ReviewRun.findings).selectinload(Finding.evidence)
        )
        .where(ReviewRun.run_id == run_id, ReviewRun.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def delete_review_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> tuple[str, uuid.UUID]:
    """
    Delete a review run and its source artifact.
    Returns (deletion_status, audit_event_id).
    Checks legal_hold before deleting [H6].
    """
    run = await get_review_run(db, run_id, tenant_id)
    if not run:
        raise KeyError("run_not_found")

    # Legal hold check
    if run.legal_hold:
        audit_event = await record_audit_event(
            db,
            tenant_id=tenant_id,
            actor_id=user_id,
            action=AuditAction.DELETE_REVIEW,
            target_type="ReviewRun",
            target_id=str(run_id),
            metadata={"result": "blocked_by_legal_hold"},
        )
        await db.commit()
        return "deletion_blocked_by_legal_hold", audit_event.event_id

    # Mark as deleted (soft delete — keeps audit trail)
    run.status = ReviewStatus.deleted

    # Delete source artifact
    if run.source_artifact and not run.source_artifact.legal_hold:
        run.source_artifact.content = ""  # Clear content, keep metadata

    audit_event = await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=user_id,
        action=AuditAction.DELETE_REVIEW,
        target_type="ReviewRun",
        target_id=str(run_id),
        metadata={"result": "deleted"},
    )
    await db.commit()
    return "deleted", audit_event.event_id
