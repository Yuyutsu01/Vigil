"""
Consent service — records and verifies user consent.
See Implementation Plan [F3], [A4], FR-009.
"""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.tenant import ConsentRecord

logger = logging.getLogger(__name__)


async def grant_consent(
    db: AsyncSession,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    purpose: str,
    version: str,
    granted: bool,
) -> ConsentRecord:
    """Create or update a ConsentRecord for the user."""
    record = ConsentRecord(
        consent_id=uuid.uuid4(),
        user_id=user_id,
        tenant_id=tenant_id,
        purpose=purpose,
        version=version,
        granted=granted,
    )
    db.add(record)
    await db.flush()
    return record


async def get_latest_consent(
    db: AsyncSession,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    purpose: str,
) -> Optional[ConsentRecord]:
    """Return the most recent ConsentRecord for this user/tenant/purpose."""
    result = await db.execute(
        select(ConsentRecord)
        .where(
            and_(
                ConsentRecord.user_id == user_id,
                ConsentRecord.tenant_id == tenant_id,
                ConsentRecord.purpose == purpose,
            )
        )
        .order_by(ConsentRecord.granted_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def verify_consent_for_review(
    db: AsyncSession,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    purpose: str = "code_review_processing",
) -> tuple[bool, str]:
    """
    Verify that an active, current-version consent exists.
    Returns (allowed: bool, error_code: str).
    [A4]: Compares consent version against current policy version.
    """
    settings = get_settings()
    current_version = settings.current_consent_version

    record = await get_latest_consent(db, user_id, tenant_id, purpose)

    if record is None:
        return False, "consent_required"

    if not record.granted:
        return False, "consent_required"

    if record.version != current_version:
        return False, "consent_version_stale"

    return True, "ok"
