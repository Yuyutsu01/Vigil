"""
API v1 router for patch candidate generation, approvals, sandboxed validation, and governed Git Data application.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_db
from app.api.phase4_guards import (
    cache_idempotent_response,
    check_phase4_rate_limit,
    get_cached_idempotent_response,
    require_idempotency_key,
)
from app.config import get_settings
from app.models.validation import ValidationVerdictEnum
from app.services.patch_service import PatchService
from app.services.validation_service import ValidationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["patches"])


# ── Pydantic Request / Response Schemas ─────────────────────────────────────────


class PatchGenerateRequest(BaseModel):
    force: bool = Field(default=False, description="Explicit override required to generate patches for Critical severity findings")


class PatchValidateRequest(BaseModel):
    commands: Optional[List[str]] = Field(default=None, description="Optional override list of validation commands")


class PatchCandidateResponse(BaseModel):
    patch_id: uuid.UUID
    finding_id: Optional[uuid.UUID]
    status: str
    unified_diff: Optional[str]
    rationale: Optional[str]
    assumptions: str
    tests_to_run: List[str]
    approved_by: Optional[uuid.UUID]
    approved_at: Optional[datetime]
    applied_branch: Optional[str]
    applied_pr_number: Optional[int]
    applied_commit_sha: Optional[str]
    rejection_reason: Optional[str]
    created_at: datetime


class ValidationRunResponse(BaseModel):
    validation_id: uuid.UUID
    patch_candidate_id: uuid.UUID
    verdict: str
    checks: List[Dict[str, Any]]
    sandbox_metadata: Dict[str, Any]
    stdout_log: str
    stderr_log: str
    created_at: datetime


class PatchApplyResponse(BaseModel):
    patch_id: str
    status: str
    branch: str
    pr_number: int
    pr_url: str
    commit_sha: str


def _patch_to_response(patch: Any) -> PatchCandidateResponse:
    tests = patch.tests_to_run
    if isinstance(tests, str):
        try:
            tests = json.loads(tests)
        except Exception:
            tests = [tests]
    return PatchCandidateResponse(
        patch_id=patch.patch_id,
        finding_id=patch.finding_id,
        status=patch.status.value if hasattr(patch.status, "value") else str(patch.status),
        unified_diff=patch.unified_diff,
        rationale=patch.rationale,
        assumptions=patch.assumptions,
        tests_to_run=tests or [],
        approved_by=patch.approved_by,
        approved_at=patch.approved_at,
        applied_branch=patch.applied_branch,
        applied_pr_number=patch.applied_pr_number,
        applied_commit_sha=patch.applied_commit_sha,
        rejection_reason=patch.rejection_reason,
        created_at=patch.created_at,
    )


# ── Endpoints ───────────────────────────────────────────────────────────────────

@router.post(
    "/findings/{finding_id}/patches",
    response_model=PatchCandidateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate remediation patch candidate for finding (FR-105)",
)
async def generate_patch_for_finding(
    finding_id: uuid.UUID,
    payload: PatchGenerateRequest = PatchGenerateRequest(),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> Any:
    """Generate patch candidate for a finding. Rate limited to 20/hr."""
    settings = get_settings()
    await check_phase4_rate_limit(
        auth.tenant_id,
        "patch_generation",
        settings.patch_generation_rate_limit_per_hour,
    )

    cached = await get_cached_idempotent_response(auth.tenant_id, "patch_generation", idempotency_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Vigil-Idempotent": "true"}, status_code=201)

    service = PatchService(db)
    try:
        candidate = await service.generate_patch(
            finding_id=finding_id,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            user_role=auth.role,
            force=payload.force,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        # Critical severity requires force=True override
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    resp_obj = _patch_to_response(candidate)
    resp_dict = json.loads(resp_obj.model_dump_json())
    await cache_idempotent_response(auth.tenant_id, "patch_generation", idempotency_key, resp_dict)
    return resp_obj


@router.get(
    "/findings/{finding_id}/patches",
    response_model=List[PatchCandidateResponse],
    summary="List all patches generated for a finding",
)
async def list_patches_for_finding(
    finding_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> List[PatchCandidateResponse]:
    """List patches for a finding. Rate limited to 100/hr."""
    await check_phase4_rate_limit(auth.tenant_id, "patch_list", 100)
    service = PatchService(db)
    patches = await service.list_patches_for_finding(finding_id, auth.tenant_id)
    return [_patch_to_response(p) for p in patches]


@router.post(
    "/patches/{patch_id}/approve",
    response_model=PatchCandidateResponse,
    summary="Approve patch candidate (Human Gate, Reviewer/Maintainer only)",
)
async def approve_patch(
    patch_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> Any:
    """Approve a draft patch candidate. Rate limited to 30/hr."""
    await check_phase4_rate_limit(auth.tenant_id, "patch_approve", 30)

    cached = await get_cached_idempotent_response(auth.tenant_id, "patch_approve", idempotency_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Vigil-Idempotent": "true"})

    service = PatchService(db)
    try:
        patch = await service.approve_patch(
            patch_id=patch_id,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            user_role=auth.role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    resp_obj = _patch_to_response(patch)
    resp_dict = json.loads(resp_obj.model_dump_json())
    await cache_idempotent_response(auth.tenant_id, "patch_approve", idempotency_key, resp_dict)
    return resp_obj


@router.post(
    "/patches/{patch_id}/withdraw",
    response_model=PatchCandidateResponse,
    summary="Withdraw patch candidate (Reviewer/Maintainer only)",
)
async def withdraw_patch(
    patch_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> Any:
    """Withdraw a patch candidate. Rate limited to 30/hr."""
    await check_phase4_rate_limit(auth.tenant_id, "patch_withdraw", 30)

    cached = await get_cached_idempotent_response(auth.tenant_id, "patch_withdraw", idempotency_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Vigil-Idempotent": "true"})

    service = PatchService(db)
    try:
        patch = await service.withdraw_patch(
            patch_id=patch_id,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            user_role=auth.role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    resp_obj = _patch_to_response(patch)
    resp_dict = json.loads(resp_obj.model_dump_json())
    await cache_idempotent_response(auth.tenant_id, "patch_withdraw", idempotency_key, resp_dict)
    return resp_obj


@router.post(
    "/patches/{patch_id}/validate",
    response_model=ValidationRunResponse,
    summary="Validate patch candidate in isolated gVisor sandbox (FR-106)",
)
async def validate_patch_endpoint(
    patch_id: uuid.UUID,
    request: Request,
    payload: PatchValidateRequest = PatchValidateRequest(),
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> Any:
    """Validate patch in sandbox. Rate limited to 20/hr."""
    settings = get_settings()
    await check_phase4_rate_limit(
        auth.tenant_id,
        "patch_validation",
        settings.patch_validation_rate_limit_per_hour,
    )

    cached = await get_cached_idempotent_response(auth.tenant_id, "patch_validation", idempotency_key)
    if cached:
        is_passed = cached.get("verdict") == "passed"
        return JSONResponse(
            content=cached,
            headers={"X-Vigil-Idempotent": "true"},
            status_code=200 if is_passed else 422,
        )

    # Dev/Prod sandbox runtime availability check (IC10, H5)
    if not getattr(request.app.state, "sandbox_available", False):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "sandbox_unavailable",
                "message": "Sandbox runtime is not available.",
            },
        )

    val_service = ValidationService(db)
    try:
        run = await val_service.validate_patch(
            patch_id=patch_id,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            user_role=auth.role,
            commands_override=payload.commands,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    resp_obj = ValidationRunResponse(
        validation_id=run.validation_id,
        patch_candidate_id=run.patch_candidate_id,
        verdict=run.verdict.value,
        checks=run.checks,
        sandbox_metadata=run.sandbox_metadata,
        stdout_log=run.stdout_log,
        stderr_log=run.stderr_log,
        created_at=run.created_at,
    )
    resp_dict = json.loads(resp_obj.model_dump_json())
    await cache_idempotent_response(auth.tenant_id, "patch_validation", idempotency_key, resp_dict)

    if run.verdict == ValidationVerdictEnum.passed:
        return resp_obj
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=resp_dict)


@router.post(
    "/patches/{patch_id}/apply",
    response_model=PatchApplyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply patch to repository via Git Data API on ephemeral branch (Maintainer only)",
)
async def apply_patch_endpoint(
    patch_id: uuid.UUID,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
    idempotency_key: str = Depends(require_idempotency_key),
) -> Any:
    """Apply approved patch. Rate limited to 10/hr. Rejects base SHA drift with 409."""
    settings = get_settings()
    await check_phase4_rate_limit(
        auth.tenant_id,
        "patch_apply",
        settings.patch_apply_rate_limit_per_hour,
    )

    cached = await get_cached_idempotent_response(auth.tenant_id, "patch_apply", idempotency_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Vigil-Idempotent": "true"}, status_code=201)

    service = PatchService(db)
    try:
        apply_res = await service.apply_patch(
            patch_id=patch_id,
            tenant_id=auth.tenant_id,
            user_id=auth.user_id,
            user_role=auth.role,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        msg = str(e)
        if "VALIDATION_FAILED" in msg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "VALIDATION_FAILED", "message": msg},
            )
        if "BASE_SHA_DRIFT" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "BASE_SHA_DRIFT", "message": msg},
            )
        if "status" in msg or "VALIDATION_REQUIRED" in msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "CONFLICT", "message": msg},
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    await cache_idempotent_response(auth.tenant_id, "patch_apply", idempotency_key, apply_res)
    return apply_res
