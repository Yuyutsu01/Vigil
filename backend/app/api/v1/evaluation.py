"""
Internal Evaluation API router.
Gated strictly to PlatformOperator role.
GET /v1/internal/evaluation/run?suite=python|javascript|all
GET /v1/internal/evaluation/results?run_id=...
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_db
from app.evaluation.runner import EvaluationRunner
from app.models.evaluation import EvaluationRun

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/internal/evaluation", tags=["internal-evaluation"])


def _require_platform_operator(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
    """Restricts access to PlatformOperator role. All other roles receive 403 Forbidden."""
    if auth.role != "PlatformOperator":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "forbidden",
                "message": "Evaluation endpoints require PlatformOperator role",
            },
        )
    return auth


@router.get("/run", summary="Trigger evaluation corpus run and calculate metrics")
async def run_evaluation_suite(
    suite: str = Query(default="all", pattern="^(python|javascript|all)$"),
    auth: AuthContext = Depends(_require_platform_operator),
    db: AsyncSession = Depends(get_db),
):
    """
    Execute versioned test corpus from disk and compute precision, recall, and F1.
    Restricted to PlatformOperator.
    """
    runner = EvaluationRunner()
    eval_run, metrics = await runner.run_suite(
        suite=suite,
        triggered_by=auth.user_id,
        db=db,
    )

    return {
        "evaluation_run_id": str(eval_run.evaluation_run_id),
        "suite": eval_run.suite,
        "started_at": eval_run.started_at.isoformat() if eval_run.started_at else None,
        "completed_at": eval_run.completed_at.isoformat() if eval_run.completed_at else None,
        "precision": eval_run.precision,
        "recall": eval_run.recall,
        "f1": eval_run.f1,
        "evidence_completeness": metrics.evidence_completeness,
        "per_rule_breakdown": eval_run.per_rule_breakdown,
    }


@router.get("/results", summary="Retrieve stored metrics for an evaluation run")
async def get_evaluation_results(
    run_id: uuid.UUID = Query(..., alias="run_id"),
    auth: AuthContext = Depends(_require_platform_operator),
    db: AsyncSession = Depends(get_db),
):
    """
    Retrieve stored evaluation metrics by evaluation_run_id.
    Restricted to PlatformOperator.
    """
    result = await db.execute(
        select(EvaluationRun).where(EvaluationRun.evaluation_run_id == run_id)
    )
    eval_run = result.scalar_one_or_none()
    if not eval_run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "run_not_found", "message": f"Evaluation run {run_id} not found"},
        )

    return {
        "evaluation_run_id": str(eval_run.evaluation_run_id),
        "suite": eval_run.suite,
        "started_at": eval_run.started_at.isoformat() if eval_run.started_at else None,
        "completed_at": eval_run.completed_at.isoformat() if eval_run.completed_at else None,
        "precision": eval_run.precision,
        "recall": eval_run.recall,
        "f1": eval_run.f1,
        "per_rule_breakdown": eval_run.per_rule_breakdown,
    }
