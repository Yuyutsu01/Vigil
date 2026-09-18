"""
GitHub Webhook Ingestion API (FR-103, FR-104, B4, H4).
Fast acknowledgment (<200ms), dual HMAC verification, delivery deduplication, and async enqueuing.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.config import get_settings
from app.integrations.github.webhook import (
    check_and_record_delivery,
    verify_webhook_signature,
)
from app.models.repository import WebhookEvent
from app.models.review import AuditAction
from app.services.audit_service import record_audit_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post(
    "/github",
    status_code=status.HTTP_202_ACCEPTED,
    summary="GitHub App webhook ingestion endpoint (FR-103, B4, H4)",
)
async def github_webhook_endpoint(
    request: Request,
    response: Response,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: Optional[str] = Header(None, alias="X-GitHub-Delivery"),
    x_github_event: Optional[str] = Header(None, alias="X-GitHub-Event"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Handle GitHub webhook deliveries.
    Verifies dual HMAC-SHA256 signature, deduplicates delivery ID, persists WebhookEvent,
    enqueues to ARQ background worker, and returns 202 in <200ms.
    """
    body_bytes = await request.body()
    settings = get_settings()

    # 1. Dual-secret HMAC signature verification (H4)
    valid_sig = verify_webhook_signature(
        payload_bytes=body_bytes,
        signature_header=x_hub_signature_256,
        secret_primary=settings.github_app_webhook_secret,
        secret_previous=settings.github_app_webhook_secret_previous,
    )

    if not valid_sig:
        logger.warning("Rejected GitHub webhook with invalid signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    delivery_id = x_github_delivery or hashlib.sha256(body_bytes).hexdigest()

    # 2. Check and record delivery ID (deduplication)
    is_new = await check_and_record_delivery(delivery_id)
    if not is_new:
        logger.info("Ignoring duplicate webhook delivery %s", delivery_id)
        response.status_code = status.HTTP_200_OK
        return {"status": "ignored", "reason": "duplicate_delivery"}

    # Double check database in case of cache loss
    from sqlalchemy import select
    existing = await db.execute(select(WebhookEvent).where(WebhookEvent.delivery_id == delivery_id))
    if existing.scalar_one_or_none():
        logger.info("Ignoring duplicate webhook delivery (db check) %s", delivery_id)
        response.status_code = status.HTTP_200_OK
        return {"status": "ignored", "reason": "duplicate_delivery"}

    # Parse payload json
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception:
        payload = {}

    action = payload.get("action")
    payload_hash = hashlib.sha256(body_bytes).hexdigest()

    # 3. Persist WebhookEvent record
    event_record = WebhookEvent(
        delivery_id=delivery_id,
        provider="github",
        event_type=x_github_event or "unknown",
        action=action,
        payload_hash=payload_hash,
        status="pending",
    )
    db.add(event_record)
    await db.commit()

    # 4. Enqueue to ARQ worker using lifespan singleton pool (H1)
    try:
        arq_pool = getattr(request.app.state, "arq_pool", None)
        if arq_pool:
            await arq_pool.enqueue_job(
                "process_webhook_job",
                delivery_id=delivery_id,
                event_type=x_github_event or "unknown",
                action=action,
                payload=payload,
            )
        else:
            logger.warning("ARQ pool not available on app.state; marking delivery %s as failed", delivery_id)
            event_record.status = "failed"
            await db.commit()
    except Exception as eq_err:
        logger.error("Could not enqueue webhook job to ARQ: %s", eq_err)
        event_record.status = "failed"
        await db.commit()

    return {"status": "accepted", "delivery_id": delivery_id}
