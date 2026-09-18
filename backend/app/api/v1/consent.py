"""
POST /v1/consent — Grant or revoke processing consent.
POST /v1/consent/learning — Grant or revoke governed learning consent (FR-109).
GET /v1/consent/learning/status — Check current learning consent status.
See Implementation Plan [F3], [A4], FR-009, FR-109.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_db
from app.models.review import AuditAction
from app.redis_client import get_redis
from app.schemas.consent import ConsentGrantRequest, ConsentGrantResponse
from app.services.audit_service import record_audit_event
from app.services.consent_service import get_latest_consent, grant_consent
from app.services.learning_service import purge_tenant_learning_data
from app.config import get_settings

router = APIRouter(prefix="/v1/consent", tags=["consent"])


class LearningConsentRequest(BaseModel):
    granted: bool = Field(description="True to grant learning consent, False to revoke.")
    version: Optional[str] = Field(
        default=None,
        description="Policy version consenting to (defaults to current server version).",
    )


class LearningConsentStatusResponse(BaseModel):
    granted: bool
    version: Optional[str] = None
    policy_version: str
    active: bool


@router.post(
    "",
    response_model=ConsentGrantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant or revoke processing consent (FR-009)",
)
async def record_consent(
    body: ConsentGrantRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> ConsentGrantResponse:
    """
    Record consent for code_review_processing.
    - `granted: true` — grant consent for the specified policy version.
    - `granted: false` — revoke consent. Existing data is not deleted automatically
      (that requires a separate data deletion request per GDPR Art. 17).
    Version must match the current policy version from server config.
    """
    settings = get_settings()
    if body.version != settings.current_consent_version:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_consent_version",
                "message": f"Expected version {settings.current_consent_version!r}, got {body.version!r}",
            },
        )

    record = await grant_consent(
        db=db,
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        purpose=body.purpose,
        version=body.version,
        granted=body.granted,
    )

    await record_audit_event(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action=AuditAction.GRANT_CONSENT if body.granted else AuditAction.REVOKE_CONSENT,
        target_type="ConsentRecord",
        target_id=str(record.consent_id),
        metadata={"purpose": body.purpose, "version": body.version},
    )

    return ConsentGrantResponse(
        consent_id=record.consent_id,
        granted_at=record.granted_at,
        version=record.version,
        granted=record.granted,
    )


@router.post(
    "/learning",
    response_model=ConsentGrantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Grant or revoke governed feedback learning consent (FR-109)",
)
async def record_learning_consent(
    body: LearningConsentRequest,
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> ConsentGrantResponse:
    """
    Record consent for feedback_learning (FR-109).
    - `granted: true`: Enables RAG indexing of user feedback dispositions for this tenant.
    - `granted: false`: Revokes consent and triggers an immediate purge of all Redis learning data (AC-109.6).
    """
    settings = get_settings()
    expected_version = getattr(settings, "learning_policy_version", "1.0")

    if body.version is not None and body.version != expected_version:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_consent_version",
                "message": f"Expected version {expected_version!r}, got {body.version!r}",
            },
        )

    actual_version = body.version or expected_version

    record = await grant_consent(
        db=db,
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        purpose="feedback_learning",
        version=actual_version,
        granted=body.granted,
    )

    # If revoking consent, immediately purge all tenant learning precedents (AC-109.6)
    if not body.granted:
        redis = get_redis()
        await purge_tenant_learning_data(db, redis, auth.tenant_id, auth.user_id)

    await record_audit_event(
        db,
        tenant_id=auth.tenant_id,
        actor_id=auth.user_id,
        action=AuditAction.LEARNING_CONSENT_GRANTED if body.granted else AuditAction.LEARNING_CONSENT_REVOKED,
        target_type="ConsentRecord",
        target_id=str(record.consent_id),
        metadata={"purpose": "feedback_learning", "version": actual_version, "granted": body.granted},
    )

    return ConsentGrantResponse(
        consent_id=record.consent_id,
        granted_at=record.granted_at,
        version=record.version,
        granted=record.granted,
    )


@router.get(
    "/learning/status",
    response_model=LearningConsentStatusResponse,
    summary="Get current governed learning consent status (FR-109)",
)
async def get_learning_consent_status(
    auth: AuthContext = Depends(get_auth_context),
    db: AsyncSession = Depends(get_db),
) -> LearningConsentStatusResponse:
    """Returns whether learning consent is currently granted and not stale."""
    settings = get_settings()
    expected_version = getattr(settings, "learning_policy_version", "1.0")

    record = await get_latest_consent(db, auth.user_id, auth.tenant_id, purpose="feedback_learning")
    if record is None:
        return LearningConsentStatusResponse(
            granted=False,
            version=None,
            policy_version=expected_version,
            active=False,
        )

    is_active = record.granted and (record.version == expected_version)
    return LearningConsentStatusResponse(
        granted=record.granted,
        version=record.version,
        policy_version=expected_version,
        active=is_active,
    )
