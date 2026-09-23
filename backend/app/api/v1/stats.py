"""
Tenant stats aggregation endpoint (FR-108 / Dashboard).
Aggregates review counts, findings by severity, token usage, cost, average duration,
and week-over-week trends for the authenticated tenant.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_db
from app.models.finding import Finding, Severity
from app.models.orchestration import AgentCoordinationRun
from app.models.review import ReviewRun, ReviewStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/tenants", tags=["tenants"])


class SeverityCounts(BaseModel):
    Critical: int = 0
    High: int = 0
    Medium: int = 0
    Low: int = 0
    Info: int = 0


class TenantStatsResponse(BaseModel):
    total_reviews: int
    total_findings: int
    findings_by_severity: SeverityCounts
    total_tokens_used: int
    total_cost_usd: float
    avg_review_duration_ms: int
    reviews_last_7_days: int
    reviews_previous_7_days: int


@router.get(
    "/me/stats",
    response_model=TenantStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get aggregated dashboard stats for the authenticated tenant",
)
async def get_tenant_stats(
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> TenantStatsResponse:
    """
    Compute real-time dashboard telemetry strictly isolated to the caller's tenant_id:
    - Total reviews submitted
    - Finding counts aggregated by severity (Critical, High, Medium, Low, Info)
    - Total token consumption and estimated cost across agent orchestration runs
    - Average review turnaround time in milliseconds
    - Week-over-week review volume comparison
    """
    tenant_id: uuid.UUID = auth.tenant_id

    # 1. Total reviews count
    review_count_query = select(func.count(ReviewRun.run_id)).where(
        ReviewRun.tenant_id == tenant_id,
        ReviewRun.status != ReviewStatus.deleted,
    )
    total_reviews_res = await db.execute(review_count_query)
    total_reviews = total_reviews_res.scalar() or 0

    # 2. Findings aggregated by severity (excluding findings from soft-deleted reviews)
    findings_query = (
        select(Finding.severity, func.count(Finding.finding_id))
        .join(ReviewRun, Finding.run_id == ReviewRun.run_id)
        .where(
            Finding.tenant_id == tenant_id,
            ReviewRun.tenant_id == tenant_id,
            ReviewRun.status != ReviewStatus.deleted,
        )
        .group_by(Finding.severity)
    )
    findings_res = await db.execute(findings_query)
    severity_map = {
        "Critical": 0,
        "High": 0,
        "Medium": 0,
        "Low": 0,
        "Info": 0,
    }
    total_findings = 0
    for sev, count in findings_res.all():
        sev_str = str(sev.value if hasattr(sev, "value") else sev).capitalize()
        if sev_str in severity_map:
            severity_map[sev_str] = count
        total_findings += count

    # 3. Total tokens used and estimated cost
    # Unfiltered by design: includes soft-deleted reviews' spend.
    # NOTE: AgentCoordinationRun has ondelete=CASCADE on review_run_id; a
    # future hard-delete of ReviewRun rows would silently reduce this number.
    token_query = select(
        func.coalesce(func.sum(AgentCoordinationRun.total_tokens_consumed), 0)
    ).where(AgentCoordinationRun.tenant_id == tenant_id)
    token_res = await db.execute(token_query)
    total_tokens_used = int(token_res.scalar() or 0)
    
    # Blended token rate ($2.00 per 1M tokens)
    total_cost_usd = round(total_tokens_used * 0.000002, 4)

    # 4. Average review duration (ms)
    runs_query = select(ReviewRun.started_at, ReviewRun.completed_at).where(
        ReviewRun.tenant_id == tenant_id,
        ReviewRun.status != ReviewStatus.deleted,
        ReviewRun.started_at.is_not(None),
        ReviewRun.completed_at.is_not(None),
    )
    runs_res = await db.execute(runs_query)
    durations = [
        (comp - start).total_seconds() * 1000.0
        for start, comp in runs_res.all()
        if comp and start and comp >= start
    ]
    avg_duration_ms = int(sum(durations) / len(durations)) if durations else 0

    # 5. Week-over-week review trends
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)
    fourteen_days_ago = now - timedelta(days=14)

    last_7_query = select(func.count(ReviewRun.run_id)).where(
        ReviewRun.tenant_id == tenant_id,
        ReviewRun.status != ReviewStatus.deleted,
        ReviewRun.started_at >= seven_days_ago,
    )
    last_7_res = await db.execute(last_7_query)
    reviews_last_7_days = last_7_res.scalar() or 0

    prev_7_query = select(func.count(ReviewRun.run_id)).where(
        ReviewRun.tenant_id == tenant_id,
        ReviewRun.status != ReviewStatus.deleted,
        ReviewRun.started_at >= fourteen_days_ago,
        ReviewRun.started_at < seven_days_ago,
    )
    prev_7_res = await db.execute(prev_7_query)
    reviews_previous_7_days = prev_7_res.scalar() or 0

    return TenantStatsResponse(
        total_reviews=total_reviews,
        total_findings=total_findings,
        findings_by_severity=SeverityCounts(**severity_map),
        total_tokens_used=total_tokens_used,
        total_cost_usd=total_cost_usd,
        avg_review_duration_ms=avg_duration_ms,
        reviews_last_7_days=reviews_last_7_days,
        reviews_previous_7_days=reviews_previous_7_days,
    )
