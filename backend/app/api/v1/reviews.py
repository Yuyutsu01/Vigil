"""
Review API router.
POST /v1/reviews       — submit code for review (application/json only)
GET  /v1/reviews/{id} — retrieve results
DELETE /v1/reviews/{id} — request data deletion (FR-008)
POST /v1/reviews/{id}/findings/{fid}/feedback — submit finding feedback (FR-009)
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_db
from app.models.finding import FindingFeedback
from app.schemas.finding import FeedbackRequest, FeedbackResponse, FindingSchema, EvidenceSchema, SourceRangeSchema
from app.schemas.review import (
    DeleteReviewResponse,
    ReviewCreateRequest,
    ReviewCreateResponse,
    ReviewRunResponse,
)
from app.services.audit_service import record_audit_event
from app.services.review_service import (
    create_and_run_review,
    delete_review_run,
    get_review_run,
)
from app.models.review import AuditAction

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/reviews", tags=["reviews"])

# ─── POST /v1/reviews ────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=ReviewCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit source code for review (FR-001 to FR-007)",
)
async def create_review(
    request: Request,
    body: ReviewCreateRequest,
    background_tasks: BackgroundTasks,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> ReviewCreateResponse:
    """
    Submit Python, JavaScript, or TypeScript code (≤250 KB, UTF-8) for review.
    Content-Type must be application/json. For file uploads, use POST /v1/uploads first.
    Returns a run_id immediately; polling GET /v1/reviews/{run_id} for results.
    """
    # Content-Type enforcement (application/json only for this endpoint)
    ct = request.headers.get("content-type", "")
    if not ct.startswith("application/json"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "unsupported_media_type",
                "message": "POST /v1/reviews requires Content-Type: application/json",
            },
        )

    # Resolve source_text (from paste or upload reference)
    source_text = body.source_text
    if source_text is None and body.upload_id is not None:
        from app.api.v1.uploads import pop_upload
        upload = pop_upload(body.upload_id, auth.tenant_id)
        if upload is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "upload_not_found", "message": "upload_id not found or wrong tenant"},
            )
        source_text = upload["source_text"]

    if not source_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "empty_source", "message": "source_text or upload_id is required"},
        )

    # Idempotency key caching (Redis-backed middleware writes run_id after creation)
    idem_key = getattr(request.state, "idempotency_key", None)
    idem_client = getattr(request.state, "idempotency_client", None)

    try:
        run = await create_and_run_review(
            db=db,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            source_text=source_text,
            language=body.language,
        )
    except PermissionError as e:
        error_code = str(e)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": error_code, "message": "Consent required for code review processing"},
        )

    # Cache run_id in idempotency store
    if idem_key and idem_client:
        try:
            payload = {"run_id": str(run.run_id), "status": run.status.value}
            await idem_client.setex(idem_key, 86400, json.dumps(payload))
        except Exception as e:
            logger.warning("Idempotency store write failed: %s", e)

    return ReviewCreateResponse(run_id=run.run_id, status=run.status)


# ─── GET /v1/reviews/{run_id} ────────────────────────────────────────────────

@router.get(
    "/{run_id}",
    response_model=ReviewRunResponse,
    summary="Get review results (FR-007)",
)
async def get_review(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> ReviewRunResponse:
    """Retrieve review results for a run. Tenant isolation enforced via JWT claim."""
    run = await get_review_run(db, run_id, auth.tenant_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Run {run_id} not found"},
        )

    # Build finding schemas
    finding_schemas = []
    for f in run.findings or []:
        ev_schemas = []
        for ev in f.evidence or []:
            ev_schemas.append(EvidenceSchema(
                evidence_id=ev.evidence_id,
                source_range=SourceRangeSchema(
                    start_line=ev.start_line,
                    start_col=ev.start_col,
                    end_line=ev.end_line,
                    end_col=ev.end_col,
                ),
                ast_path=ev.ast_path,
                tool_name=ev.tool_name,
                rule_id=ev.rule_id,
                code_excerpt=ev.code_excerpt,
                evidence_kind=ev.evidence_kind,
            ))
        finding_schemas.append(FindingSchema(
            finding_id=f.finding_id,
            run_id=f.run_id,
            fingerprint=f.fingerprint,
            origin=f.origin,
            rule_id=f.rule_id,
            category=f.category,
            severity=f.severity,
            confidence=f.confidence,
            title=f.title,
            rationale=f.rationale,
            remediation=f.remediation,
            evidence=ev_schemas,
            status=f.status,
        ))

    started_at = run.started_at
    completed_at = run.completed_at
    timing_ms = None
    if started_at and completed_at:
        timing_ms = int((completed_at - started_at).total_seconds() * 1000)

    artifact = run.source_artifact
    return ReviewRunResponse(
        run_id=run.run_id,
        status=run.status,
        language=artifact.language if artifact else None,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        parked_reason=run.parked_reason,
        prompt_version=run.prompt_version,
        findings=finding_schemas,
        finding_count=len(finding_schemas),
        timing_ms=timing_ms,
    )


# ─── DELETE /v1/reviews/{run_id} ─────────────────────────────────────────────

@router.delete(
    "/{run_id}",
    response_model=DeleteReviewResponse,
    summary="Request data deletion (FR-008)",
)
async def delete_review(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DeleteReviewResponse:
    """
    Delete a review run and its source artifact.
    Legal hold prevents deletion and is logged in the audit trail.
    """
    try:
        deletion_status, audit_id = await delete_review_run(
            db=db,
            run_id=run_id,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
        )
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Run {run_id} not found"},
        )

    return DeleteReviewResponse(
        run_id=run_id,
        deletion_status=deletion_status,
        audit_id=audit_id,
    )


# ─── POST /v1/reviews/{run_id}/findings/{finding_id}/feedback ────────────────

@router.post(
    "/{run_id}/findings/{finding_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit finding feedback (FR-009)",
)
async def submit_feedback(
    run_id: uuid.UUID,
    finding_id: uuid.UUID,
    body: FeedbackRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """
    Record user disposition on a finding (useful/not, accepted/rejected/false_positive).
    Tenant isolation enforced: finding must belong to an authenticated tenant run.
    """
    from sqlalchemy import select
    from app.models.finding import Finding

    # Verify finding belongs to this tenant
    result = await db.execute(
        select(Finding).where(
            Finding.finding_id == finding_id,
            Finding.run_id == run_id,
            Finding.tenant_id == auth.tenant_id,
        )
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "finding_not_found", "message": f"Finding {finding_id} not found"},
        )

    feedback = FindingFeedback(
        finding_id=finding_id,
        user_id=auth.user_id,
        useful=body.useful,
        disposition=body.disposition,
        comment=body.comment,
    )
    db.add(feedback)

    await record_audit_event(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action=AuditAction.SUBMIT_FEEDBACK,
        target_type="Finding",
        target_id=str(finding_id),
        metadata={"useful": body.useful, "disposition": body.disposition},
    )
    await db.flush()

    return FeedbackResponse(
        feedback_id=feedback.feedback_id,
        finding_id=finding_id,
        disposition=body.disposition,
    )
