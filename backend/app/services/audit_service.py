"""
Audit service — append-only audit event writer.
NEVER stores source code content or secrets in audit events.
See Implementation Plan [A2], §9.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import AuditAction, AuditEvent
from app.services.redaction_service import redact_dict

logger = logging.getLogger(__name__)


async def record_audit_event(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    action: AuditAction,
    actor_id: Optional[uuid.UUID] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditEvent:
    """
    Write an append-only audit event.
    Metadata is sanitized through the redaction filter before storage.
    Source code and secrets MUST NOT be passed as metadata.
    """
    # Sanitize metadata — strip any secret-shaped strings
    safe_meta = redact_dict(metadata or {})

    event = AuditEvent(
        event_id=uuid.uuid4(),
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        metadata_json=json.dumps(safe_meta),
    )
    db.add(event)
    # Note: caller is responsible for flushing / committing the session

    logger.info(
        "audit action=%s actor=%s target_type=%s target_id=%s tenant=%s",
        action.value,
        actor_id,
        target_type,
        target_id,
        tenant_id,
    )
    return event
