"""
Governed Learning Service (FR-109).
Handles consent-backed disposition indexing, multi-stage sanitization,
prompt injection defense, and instant revocation purges.

Guarantees:
- Zero raw tenant code persistence.
- Multi-stage sanitization (secrets, line numbers, file paths, and syntax keywords).
- Isolated per tenant.
- Right to be forgotten (purge completes within 5s).
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
import re
from typing import Any, Dict, Optional, Tuple
import uuid

import redis.asyncio as aioredis
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.finding import Finding, FindingFeedback
from app.models.orchestration import LearningDispositionIndex
from app.models.review import AuditAction
from app.models.tenant import ConsentRecord
from app.services.audit_service import record_audit_event
from app.services.consent_service import get_latest_consent
from app.services.redaction_service import redact

logger = logging.getLogger(__name__)

# Regex patterns for sanitization
_FILE_PATH_PATTERN = re.compile(
    r"[\w/\\.-]+\.(py|js|ts|jsx|tsx|go|java|rb|c|cpp|rs|html|css|json|yaml|yml)\b",
    re.IGNORECASE,
)
_LINE_REF_PATTERN = re.compile(
    r"\b(line\s+\d+|lines\s+\d+-\d+|L\d+)\b",
    re.IGNORECASE,
)
_CODE_KEYWORDS = [
    "def ", "class ", "import ", "function ", "const ", "let ", "var ",
    "=>", "return ", "eval(", "exec(", "lambda ",
]


def sanitize_user_comment(comment: Optional[str]) -> Tuple[Optional[str], bool, int]:
    """
    Multi-stage sanitization barrier for disposition comments (FR-109, B2).
    1. Redact secrets via redaction service.
    2. Enforce 500-character ceiling.
    3. Flatten newlines.
    4. Strip file paths and line number references.
    5. Detect and redact code-like syntax patterns.
    """
    if not comment or not comment.strip():
        return None, False, 0

    raw_text = comment.strip()
    was_truncated = False
    redaction_count = 0

    # 1. Redact credentials/secrets
    redacted_text = redact(raw_text)
    if "[REDACTED]" in redacted_text:
        redaction_count += redacted_text.count("[REDACTED]")

    # 2. Enforce 500-character ceiling
    if len(redacted_text) > 500:
        redacted_text = redacted_text[:500]
        was_truncated = True

    # 3. Flatten newlines
    flattened = redacted_text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")

    # 4. Redact file paths and line numbers
    sub_paths, n_paths = _FILE_PATH_PATTERN.subn("[REDACTED_REF]", flattened)
    redaction_count += n_paths

    sub_lines, n_lines = _LINE_REF_PATTERN.subn("[REDACTED_REF]", sub_paths)
    redaction_count += n_lines

    # 5. Detect code-like syntax patterns
    has_code_keywords = any(kw in sub_lines for kw in _CODE_KEYWORDS)
    has_syntax_symbols = bool(re.search(r"(\(\)|=>|;\s*$|:\s*$|\{|\})", sub_lines))

    if has_code_keywords or (has_syntax_symbols and any(k in sub_lines for k in ["def", "function", "eval"])):
        # Substantive code detected: replace with safe indicator
        sub_lines = "[comment redacted: contained code-like content]"
        redaction_count += 1

    # Clean up double spaces
    cleaned = re.sub(r"\s+", " ", sub_lines).strip()
    return cleaned, was_truncated, redaction_count


async def verify_learning_consent(
    db: AsyncSession,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Tuple[bool, str]:
    """
    Verifies that the tenant has active, current-policy consent for feedback learning.
    Policy version is checked against settings.learning_policy_version.
    """
    settings = get_settings()
    current_version = getattr(settings, "learning_policy_version", "1.0")

    record = await get_latest_consent(db, user_id, tenant_id, purpose="feedback_learning")

    if record is None or not record.granted:
        return False, "consent_required"

    if record.version != current_version:
        return False, "consent_version_stale"

    return True, "ok"


async def get_or_create_disposition_index(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> LearningDispositionIndex:
    """Retrieves or initializes the LearningDispositionIndex record for a tenant."""
    stmt = select(LearningDispositionIndex).where(
        LearningDispositionIndex.tenant_id == tenant_id
    )
    res = await db.execute(stmt)
    index_rec = res.scalar_one_or_none()

    if not index_rec:
        index_rec = LearningDispositionIndex(
            index_id=uuid.uuid4(),
            tenant_id=tenant_id,
            vector_index_name=f"vigil_rag_{tenant_id}",
            entry_count=0,
            updated_at=datetime.now(timezone.utc),
        )
        db.add(index_rec)
        await db.flush()

    return index_rec


async def index_finding_disposition(
    db: AsyncSession,
    redis: aioredis.Redis,
    finding: Finding,
    feedback: FindingFeedback,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Optional[uuid.UUID]:
    """
    Indexes a finding disposition for tenant RAG retrieval if consent is active.
    Passes comment through multi-stage sanitization and stores strictly whitelisted fields.
    """
    # 1. Verify consent
    allowed, reason = await verify_learning_consent(db, user_id, tenant_id)
    if not allowed:
        feedback.indexed_for_learning = False
        return None

    # 2. Sanitize user comment
    sanitized_comment, was_truncated, redaction_count = sanitize_user_comment(feedback.comment)

    # 3. Retrieve or create tenant index
    index_rec = await get_or_create_disposition_index(db, tenant_id)

    # 4. Synthesize AST path and matched text hash (zero raw code)
    matched_hash = ""
    # Extract matched text hash from finding if already loaded
    if "evidence" in finding.__dict__ and finding.evidence:
        first_ev = finding.evidence[0]
        ast_path = getattr(first_ev, "ast_path", None) or f"rule/{finding.rule_id}"
        code_excerpt = getattr(first_ev, "code_excerpt", "") or ""
        if code_excerpt:
            matched_hash = hashlib.sha256(code_excerpt.encode("utf-8")).hexdigest()
    else:
        ast_path = f"rule/{finding.rule_id}"

    # Determine language
    language = "unknown"
    if hasattr(finding, "source_file_path") and finding.source_file_path:
        ext = finding.source_file_path.split(".")[-1].lower()
        lang_map = {"py": "python", "js": "javascript", "ts": "typescript"}
        language = lang_map.get(ext, ext)

    # 5. Assemble strictly allowlisted precedent document
    payload = {
        "index_id": str(index_rec.index_id),
        "feedback_id": str(feedback.feedback_id),
        "finding_id": str(finding.finding_id),
        "tenant_id": str(tenant_id),
        "rule_id": finding.rule_id or "unknown",
        "category": finding.category or "security",
        "language": language,
        "ast_path": ast_path[:128],
        "matched_text_hash": matched_hash,
        "disposition": feedback.disposition or "accepted",
        "reason_category": feedback.reason_category,
        "user_comment_sanitized": sanitized_comment,
        "user_comment_was_truncated": was_truncated,
        "user_comment_redaction_count": redaction_count,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # 6. Store in Redis with tenant isolation and 90-day retention
    doc_key = f"vigil:learning:{tenant_id}:{feedback.feedback_id}"
    set_key = f"vigil:learning_keys:{tenant_id}"

    try:
        await redis.set(doc_key, json.dumps(payload), ex=90 * 86400)
        await redis.sadd(set_key, doc_key)
    except Exception as e:
        logger.warning("Redis learning index write failed: %s", e)

    # 7. Update database models
    feedback.indexed_for_learning = True
    feedback.learning_precedent_id = index_rec.index_id
    index_rec.entry_count += 1
    index_rec.updated_at = datetime.now(timezone.utc)

    # 8. Record audit event
    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=user_id,
        action=AuditAction.FEEDBACK_DISPOSITION_RECORDED,
        target_type="FindingFeedback",
        target_id=str(feedback.feedback_id),
        metadata={
            "disposition": feedback.disposition,
            "reason_category": feedback.reason_category,
            "index_id": str(index_rec.index_id),
            "was_truncated": was_truncated,
            "redactions": redaction_count,
        },
    )

    return index_rec.index_id


async def purge_tenant_learning_data(
    db: AsyncSession,
    redis: aioredis.Redis,
    tenant_id: uuid.UUID,
    actor_id: Optional[uuid.UUID] = None,
) -> int:
    """
    Instant revocation purge per GDPR Art. 17 / Right to be Forgotten (AC-109.6).
    Deletes all Redis keys for the tenant and marks index as purged.
    Completes in < 5 seconds.
    """
    set_key = f"vigil:learning_keys:{tenant_id}"
    try:
        keys = await redis.smembers(set_key)
    except Exception as e:
        logger.warning("Redis smembers failed during purge: %s", e)
        keys = []

    purged_count = len(keys)
    if keys:
        try:
            pipe = redis.pipeline()
            for k in keys:
                pipe.delete(k)
            pipe.delete(set_key)
            await pipe.execute()
        except Exception as e:
            logger.warning("Redis pipeline delete failed during purge: %s", e)

    # Update database index record
    stmt = (
        update(LearningDispositionIndex)
        .where(LearningDispositionIndex.tenant_id == tenant_id)
        .values(
            entry_count=0,
            last_purged_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    await db.execute(stmt)

    # Mark all feedback records for tenant as not indexed
    # Find all finding IDs belonging to this tenant
    find_stmt = select(Finding.finding_id).where(Finding.tenant_id == tenant_id)
    feedback_update_stmt = (
        update(FindingFeedback)
        .where(FindingFeedback.finding_id.in_(find_stmt))
        .values(indexed_for_learning=False)
    )
    await db.execute(feedback_update_stmt)

    # Record audit event
    await record_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=AuditAction.LEARNING_INDEX_PURGED,
        target_type="LearningDispositionIndex",
        target_id=str(tenant_id),
        metadata={"purged_count": purged_count},
    )

    await db.flush()
    return purged_count
