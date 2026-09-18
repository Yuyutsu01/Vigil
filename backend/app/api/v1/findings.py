"""
Findings API router (FR-009, FR-109).
POST /v1/findings/{finding_id}/feedback — Submit finding disposition and feedback.
"""
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_db
from app.models.finding import Finding, FindingFeedback
from app.models.review import AuditAction
from app.redis_client import get_redis
from app.schemas.finding import FeedbackRequest, FeedbackResponse
from app.services.audit_service import record_audit_event
from app.services.learning_service import index_finding_disposition

router = APIRouter(prefix="/v1/findings", tags=["findings"])


@router.post(
    "/{finding_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit finding feedback (FR-009, FR-109)",
)
async def submit_direct_feedback(
    finding_id: uuid.UUID,
    body: FeedbackRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    """
    Direct endpoint to record user disposition on a finding without specifying run_id in the URL.
    Tenant isolation enforced: finding must belong to the authenticated tenant.
    """
    result = await db.execute(
        select(Finding).where(
            Finding.finding_id == finding_id,
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

    if body.disposition:
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
        except Exception:
            pass

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
