"""
POST /v1/auth/token & POST /v1/auth/register — PROTOTYPE_ONLY local authentication.
TODO: Replace with OIDC/OAuth2 token exchange before any external pilot.
See IMPLEMENTATION_NOTES.md [F2] and [N50].
"""
# PROTOTYPE_ONLY
import logging
import time
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.api.rate_limit import _sliding_window_check
from app.config import get_settings
from app.models.review import AuditAction
from app.models.tenant import ConsentRecord, Tenant, User
from app.redis_client import get_redis
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    TokenResponse,
)
from app.services.audit_service import record_audit_event
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    hash_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


async def check_register_rate_limit(request: Request, email: str) -> None:
    """
    Sliding-window rate limiter for registration using Redis sorted sets.
    Keyed by client IP and email domain to curb registration abuse.
    1-hour window enforcing register_rate_limit_per_hour (default 5).
    """
    settings = get_settings()
    client_ip = request.client.host if request.client else "127.0.0.1"
    # Check X-Forwarded-For if behind reverse proxy
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()

    domain = email.split("@")[1].lower() if "@" in email else "unknown"
    key = f"rl:register:{client_ip}:{domain}"
    now_ms = int(time.time() * 1000)
    window_ms = 3_600_000  # 1 hour
    limit = settings.register_rate_limit_per_hour

    try:
        client = get_redis()
        is_ok = await _sliding_window_check(
            client,
            key,
            now_ms,
            window_ms,
            limit,
        )
        if not is_ok:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "rate_limited", "message": "Too many attempts. Try again later."},
                headers={"Retry-After": "3600"},
            )
    except HTTPException:
        raise
    except Exception as exc:
        # In production, fail-closed per architecture requirements
        if settings.vigil_env == "production":
            logger.error("Rate limiter Redis unavailable during registration: %s (fail-closed)", exc)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "service_unavailable", "message": "Rate limiter unavailable"},
            )
        # In development and local unit testing, allow gracefully if Redis is offline
        logger.warning("Redis unavailable for registration rate limiting: %s (allowed in dev)", exc)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Issue access token (PROTOTYPE_ONLY)",
)
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Issue access token - login alias (PROTOTYPE_ONLY)",
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
    settings = get_settings()
    if not settings.allow_local_auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )

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


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new organization tenant and user (PROTOTYPE_ONLY)",
)
async def register(
    body: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RegisterResponse:
    """
    # PROTOTYPE_ONLY
    Provision a new Tenant, initial User with Argon2id hashed credentials,
    default consent record, and immediate JWT issuance in a single atomic transaction.
    """
    settings = get_settings()
    if not settings.allow_local_auth:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not Found",
        )

    # 1. Enforce sliding-window rate limit (IP + domain)
    await check_register_rate_limit(request, body.email)

    # 2. Reject duplicate email (case-insensitive)
    existing = await db.execute(
        select(User).where(func.lower(User.email) == body.email.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_taken", "message": "Email already registered"},
        )

    # 3. Create Tenant
    tenant = Tenant(
        tenant_id=uuid.uuid4(),
        name=body.organization_name,
        source_retention_days=settings.source_artifact_retention_days,
        findings_retention_days=settings.findings_retention_days,
        model_policy="mock",
        created_at=datetime.now(timezone.utc),
    )
    db.add(tenant)
    await db.flush()

    # 4. Create User (developer role by default for prototype)
    user = User(
        user_id=uuid.uuid4(),
        tenant_id=tenant.tenant_id,
        email=body.email.lower(),
        hashed_password=hash_password(body.password),
        role="developer",
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    # 5. Record base consent for code_review_processing (FR-009)
    consent = ConsentRecord(
        consent_id=uuid.uuid4(),
        user_id=user.user_id,
        tenant_id=tenant.tenant_id,
        purpose="code_review_processing",
        version=settings.current_consent_version,
        granted=True,
        granted_at=datetime.now(timezone.utc),
    )
    db.add(consent)

    # 6. Issue JWT with tenant_id claim
    token = create_access_token(
        user_id=user.user_id,
        tenant_id=tenant.tenant_id,
        role=user.role,
    )

    # 7. Audit event record
    await record_audit_event(
        db=db,
        tenant_id=tenant.tenant_id,
        actor_id=user.user_id,
        action=AuditAction.LOGIN,
        target_type="User",
        target_id=str(user.user_id),
        metadata={"email_prefix": user.email.split("@")[0], "action": "register"},
    )

    await db.commit()

    return RegisterResponse(
        access_token=token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        tenant_id=str(tenant.tenant_id),
        user_id=str(user.user_id),
        role=user.role,
    )
