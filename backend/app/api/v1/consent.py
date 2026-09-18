"""
POST /v1/consent — Grant or revoke processing consent.
See Implementation Plan [F3], [A4], FR-009.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_auth_context, get_db
from app.models.review import AuditAction
from app.schemas.consent import ConsentGrantRequest, ConsentGrantResponse
from app.services.audit_service import record_audit_event
from app.services.consent_service import grant_consent
from app.config import get_settings

router = APIRouter(prefix="/v1/consent", tags=["consent"])


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
