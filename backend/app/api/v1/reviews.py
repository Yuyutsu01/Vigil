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

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_db
from app.models.finding import FindingFeedback
from app.models.review import AuditAction, ReviewStatus
from app.schemas.finding import FeedbackRequest, FeedbackResponse, FindingSchema, EvidenceSchema, SourceRangeSchema
from app.schemas.review import (
    DeleteReviewResponse,
    ReviewCreateRequest,
    ReviewCreateResponse,
    ReviewListItem,
    ReviewListResponse,
    ReviewRunResponse,
)
from app.services.audit_service import record_audit_event
from app.services.review_service import (
    create_and_run_review,
    delete_review_run,
    get_review_run,
    list_review_runs,
)

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
    Submit Python, JavaScript, or TypeScript code (UTF-8) for review.
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

    # 1. Load shedding check ([M2])
    from app.config import get_settings
    from app.redis_client import get_redis
    from app.services.budget_service import assert_tenant_daily_budget, get_tenant_daily_limit

    settings = get_settings()
    redis = get_redis()
    try:
        llm_depth = await redis.llen("vigil:queue:llm")
        if llm_depth > getattr(settings, "queue_shed_threshold_llm", 500):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "queue_saturated", "message": "Worker queue depth exceeded capacity. Retry after backoff."},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.debug("Redis queue depth check bypassed: %s", e)

    # 2. Daily cost budget check ([B5])
    try:
        daily_limit = await get_tenant_daily_limit(db, auth.tenant_id)
        await assert_tenant_daily_budget(redis, auth.tenant_id, added_cost=0.01, limit=daily_limit, db=db)
    except HTTPException:
        raise
    except Exception as e:
        logger.debug("Daily budget check bypassed: %s", e)

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


# ─── GET /v1/reviews ─────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=ReviewListResponse,
    summary="List review runs for tenant",
)
async def list_reviews(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_param: Optional[str] = Query(None, alias="status"),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> ReviewListResponse:
    """
    List review runs for the authenticated tenant with pagination and optional status filter.
    Soft-deleted runs are excluded.
    """
    status_filter: Optional[ReviewStatus] = None
    if status_param is not None:
        if status_param.lower() == "deleted":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_status", "message": "status=deleted is not listable"},
            )
        try:
            status_filter = ReviewStatus(status_param.lower())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "invalid_status", "message": f"Invalid status filter: {status_param}"},
            )

    runs, total, severity_map = await list_review_runs(
        db=db,
        tenant_id=auth.tenant_id,
        limit=limit,
        offset=offset,
        status_filter=status_filter,
    )

    items = []
    for r in runs:
        sev_counts = severity_map.get(
            r.run_id,
            {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        )
        total_findings = sum(sev_counts.values())
        lang = r.source_artifact.language if r.source_artifact else "unknown"
        items.append(
            ReviewListItem(
                run_id=r.run_id,
                status=r.status,
                language=lang,
                started_at=r.started_at,
                completed_at=r.completed_at,
                legal_hold=r.legal_hold,
                finding_count=total_findings,
                severity_counts=sev_counts,
            )
        )

    return ReviewListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


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
            tool_name=f.tool_name,
            tool_version=f.tool_version,
            raw_evidence_ref=f.raw_evidence_ref,
            source_file_path=f.source_file_path,
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
        source_text=artifact.content if artifact else None,
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
        reason_category=body.reason_category,
    )
    db.add(feedback)
    await db.flush()

    # Index for feedback learning if disposition is provided (FR-109)
    if body.disposition:
        from app.redis_client import get_redis
        from app.services.learning_service import index_finding_disposition
        redis = get_redis()
        try:
            await index_finding_disposition(
                db=db,
                redis=redis,
                finding=finding,
                feedback=feedback,
                user_id=auth.user_id,
                tenant_id=auth.tenant_id,
            )
        except Exception as e:
            logger.warning("Feedback learning indexing failed: %s", e)

    await record_audit_event(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action=AuditAction.SUBMIT_FEEDBACK,
        target_type="Finding",
        target_id=str(finding_id),
        metadata={
            "useful": body.useful,
            "disposition": body.disposition,
            "reason_category": body.reason_category,
            "indexed_for_learning": feedback.indexed_for_learning,
        },
    )
    await db.flush()

    return FeedbackResponse(
        feedback_id=feedback.feedback_id,
        finding_id=finding_id,
        disposition=body.disposition,
        reason_category=feedback.reason_category,
        indexed_for_learning=feedback.indexed_for_learning,
    )


# ─── GET /v1/reviews/{run_id}/agent-tree (FR-108, AC-108.8) ───────────────────

@router.get(
    "/{run_id}/agent-tree",
    summary="Get multi-agent orchestration execution tree and telemetry (FR-108, AC-108.8)",
)
async def get_agent_tree(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Returns full execution tree details, durations, token attributions,
    and partial failure statuses for all specialist agents.
    """
    from sqlalchemy import select
    from app.models.orchestration import AgentCoordinationRun, AgentTaskExecution

    stmt = select(AgentCoordinationRun).where(
        AgentCoordinationRun.review_run_id == run_id,
        AgentCoordinationRun.tenant_id == auth.tenant_id,
    )
    res = await db.execute(stmt)
    coord = res.scalar_one_or_none()
    if not coord:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "agent_tree_not_found", "message": f"No agent coordination run for review {run_id}"},
        )

    task_stmt = (
        select(AgentTaskExecution)
        .where(AgentTaskExecution.coordination_id == coord.coordination_id)
        .order_by(AgentTaskExecution.created_at.asc())
    )
    task_res = await db.execute(task_stmt)
    tasks = task_res.scalars().all()

    task_list = [
        {
            "task_id": str(t.task_id),
            "agent_name": t.agent_name,
            "status": t.status,
            "duration_ms": t.duration_ms,
            "tokens_consumed": t.tokens_consumed,
            "error_message": t.error_message,
        }
        for t in tasks
    ]
    return {
        "coordination_id": str(coord.coordination_id),
        "review_run_id": str(coord.review_run_id),
        "tenant_id": str(coord.tenant_id),
        "status": coord.status,
        "total_tokens_consumed": coord.total_tokens_consumed,
        "total_wall_clock_ms": coord.total_wall_clock_ms,
        "failed_agents": coord.failed_agents,
        "tasks": task_list,
        "agents": task_list,
    }


# ─── GET /v1/reviews/{run_id}/report (FR-102) ───────────────────────────────

@router.get(
    "/{run_id}/report",
    summary="Export review report in JSON, HTML, or PDF format (FR-102)",
)
async def get_review_report(
    run_id: uuid.UUID,
    format: str = "json",
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Export security and quality review findings in JSON, HTML, or PDF format.
    Includes executive summary, severity breakdown, trends, and remediation plan.
    Code excerpts are redacted; full source code is never exposed.
    """
    from fastapi.responses import Response
    from app.reports.base import build_report_data
    from app.reports.json_report import JSONReportRenderer
    from app.reports.html_report import HTMLReportRenderer
    from app.reports.pdf_report import PDFReportRenderer

    run = await get_review_run(db, run_id, auth.tenant_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Review run {run_id} not found"},
        )

    report_data = build_report_data(run, run.findings)

    fmt = format.lower()
    if fmt == "json":
        renderer = JSONReportRenderer()
    elif fmt == "html":
        renderer = HTMLReportRenderer(template_name="report.html")
    elif fmt == "pdf":
        renderer = PDFReportRenderer(template_name="report.html")
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_format", "message": f"Unsupported report format: {format}"},
        )

    content_bytes = renderer.render(report_data)
    filename = f"vigil_report_{run_id}.{renderer.file_extension}"

    return Response(
        content=content_bytes,
        media_type=renderer.media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── GET /v1/reviews/{run_id}/report/executive.pdf (FR-102) ──────────────────

@router.get(
    "/{run_id}/report/executive.pdf",
    summary="Download one-page executive summary PDF report (FR-102)",
)
async def get_executive_pdf_report(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate and download a one-page executive summary PDF report.
    Contains severity breakdown and risk priorities without code snippets.
    """
    from fastapi.responses import Response
    from app.reports.base import build_report_data
    from app.reports.pdf_report import PDFReportRenderer

    run = await get_review_run(db, run_id, auth.tenant_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Review run {run_id} not found"},
        )

    report_data = build_report_data(run, run.findings)
    renderer = PDFReportRenderer(template_name="executive.html")
    content_bytes = renderer.render(report_data)
    filename = f"vigil_executive_{run_id}.pdf"

    return Response(
        content=content_bytes,
        media_type=renderer.media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── GET /v1/reviews/{run_id}/tool-findings (FR-101) ────────────────────────

@router.get(
    "/{run_id}/tool-findings",
    summary="Retrieve raw static analyzer tool findings (FR-101)",
)
async def get_review_tool_findings(
    run_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve verbatim raw static analyzer tool findings (Bandit, Semgrep, ESLint, Ruff).
    Scoped strictly to authenticated tenant.
    """
    from app.services.review_service import get_tool_findings

    run = await get_review_run(db, run_id, auth.tenant_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Review run {run_id} not found"},
        )

    tool_findings = await get_tool_findings(db, run_id, auth.tenant_id)
    return [
        {
            "tool_finding_id": str(tf.tool_finding_id),
            "run_id": str(tf.run_id),
            "tool_name": tf.tool_name,
            "tool_version": tf.tool_version,
            "rule_id": tf.rule_id,
            "severity_raw": tf.severity_raw,
            "message": tf.message,
            "file_path": tf.file_path,
            "start_line": tf.start_line,
            "start_col": tf.start_col,
            "end_line": tf.end_line,
            "end_col": tf.end_col,
            "raw_evidence": tf.raw_evidence,
            "created_at": tf.created_at.isoformat() if tf.created_at else None,
        }
        for tf in tool_findings
    ]
