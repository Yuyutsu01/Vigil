"""
POST /v1/auth/token — PROTOTYPE_ONLY local authentication.
TODO: Replace with OIDC/OAuth2 token exchange before any external pilot.
See IMPLEMENTATION_NOTES.md [F2].
"""
# PROTOTYPE_ONLY
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.review import AuditAction
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.audit_service import record_audit_event
from app.services.auth_service import authenticate_user, create_access_token

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Issue access token (PROTOTYPE_ONLY)",
)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    # PROTOTYPE_ONLY
    Exchange email + password for a short-lived JWT access token.
    Production deployments MUST use an OIDC provider.
    """
    user = await authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Invalid email or password"},
        )

    token = create_access_token(
        user_id=user.user_id,
        tenant_id=user.tenant_id,
        role=user.role,
    )

    await record_audit_event(
        db,
        tenant_id=user.tenant_id,
        actor_id=user.user_id,
        action=AuditAction.LOGIN,
        target_type="User",
        target_id=str(user.user_id),
        metadata={"email_prefix": user.email.split("@")[0]},
    )
    return TokenResponse(access_token=token)
