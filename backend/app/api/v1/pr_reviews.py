"""
API v1 router for Governed PR Review draft generation, inspection, and rate-limited publication (FR-107).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_db
from app.api.phase4_guards import (
    cache_idempotent_response,
    check_phase4_rate_limit,
    get_cached_idempotent_response,
    require_idempotency_key,
)
from app.config import get_settings
from app.services.pr_review_service import PRReviewService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["pr_reviews"])


# ── Schemas ─────────────────────────────────────────────────────────────────────


class DraftPRCommentResponse(BaseModel):
    comment_id: uuid.UUID
    review_id: uuid.UUID
    body: str
    path: str
    line: int
    commit_sha: str
    status: str
    created_at: datetime


class DraftPRReviewResponse(BaseModel):
    review_id: uuid.UUID
    tenant_id: uuid.UUID
    repository_id: uuid.UUID
    pr_number: int
    status: str
    summary_markdown: str
    comments: List[DraftPRCommentResponse] = []
    created_at: datetime


class PRReviewPublishResponse(BaseModel):
    review_id: str
    status: str
    pr_number: int
    comments_published: int
    github_review_id: Optional[int] = None


def _draft_to_response(draft: Any) -> DraftPRReviewResponse:
    comments = [
        DraftPRCommentResponse(
            comment_id=c.comment_id,
            review_id=c.review_id,
            body=c.body,
            path=c.path,
            line=c.line,
            commit_sha=c.commit_sha,
            status=c.status.value if hasattr(c.status, "value") else str(c.status),
            created_at=c.created_at,
        )
        for c in getattr(draft, "comments", []) or []
    ]
    return DraftPRReviewResponse(
        review_id=draft.review_id,
        tenant_id=draft.tenant_id,
        repository_id=draft.repository_id,
        pr_number=draft.pr_number,
        status=draft.status.value if hasattr(draft.status, "value") else str(draft.status),
        summary_markdown=draft.summary_markdown,
        comments=comments,
        created_at=draft.created_at,
    )


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post(
    "/repositories/{repository_id}/reviews/{review_id}/generate-draft-review",
    response_model=DraftPRReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate draft PR review summary and inline comments (FR-107, A9)",
)
@router.post(
    "/repositories/{repository_id}/reviews/{review_id}/generate-pr-review",
    response_model=DraftPRReviewResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate draft PR review summary and inline comments (alias)",
)
async def generate_draft_pr_review_endpoint(
    repository_id: uuid.UUID,
    review_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> Any:
    """Generate draft PR review. Rate limited to 20/hr."""
    settings = get_settings()
    await check_phase4_rate_limit(
        auth.tenant_id,
        "pr_review_generate",
        settings.pr_review_generate_rate_limit_per_hour,
    )

    cached = await get_cached_idempotent_response(auth.tenant_id, "pr_review_generate", idempotency_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Vigil-Idempotent": "true"}, status_code=201)

    service = PRReviewService(db)
    try:
        draft = await service.generate_draft_review(
            repository_id=repository_id,
            review_id=review_id,
            tenant_id=auth.tenant_id,
            user_role=auth.role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    resp_obj = _draft_to_response(draft)
    resp_dict = json.loads(resp_obj.model_dump_json())
    await cache_idempotent_response(auth.tenant_id, "pr_review_generate", idempotency_key, resp_dict)
    return resp_obj


@router.get(
    "/repositories/{repository_id}/reviews/{review_id}/draft-review",
    response_model=DraftPRReviewResponse,
    summary="Get draft PR review for inspection",
)
async def get_draft_pr_review_endpoint(
    repository_id: uuid.UUID,
    review_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> DraftPRReviewResponse:
    """Get draft PR review. Rate limited to 100/hr."""
    await check_phase4_rate_limit(auth.tenant_id, "pr_review_get", 100)
    service = PRReviewService(db)
    try:
        draft = await service.get_draft_review(repository_id, review_id, auth.tenant_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return _draft_to_response(draft)


@router.post(
    "/repositories/{repository_id}/reviews/{review_id}/publish-review",
    response_model=PRReviewPublishResponse,
    summary="Publish draft review and comments to GitHub PR (Reviewer/Maintainer only)",
)
async def publish_pr_review_endpoint(
    repository_id: uuid.UUID,
    review_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> Any:
    """Publish draft review. Rate limited to 10/hr. Enforces comment publication policy and PR comment caps."""
    settings = get_settings()
    await check_phase4_rate_limit(
        auth.tenant_id,
        "pr_review_publish",
        settings.pr_review_publish_rate_limit_per_hour,
    )

    cached = await get_cached_idempotent_response(auth.tenant_id, "pr_review_publish", idempotency_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Vigil-Idempotent": "true"})

    service = PRReviewService(db)
    try:
        pub_res = await service.publish_review(
            repository_id=repository_id,
            review_id=review_id,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            user_role=auth.role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except RuntimeError as e:
        # Rate limit of 5 comments/PR/hr exceeded
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": "3600"},
        )

    await cache_idempotent_response(auth.tenant_id, "pr_review_publish", idempotency_key, pub_res)
    return pub_res
