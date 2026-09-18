"""
Privacy test for Zero Tenant Source Code Persistence (FR-109 / AC-109.1).

Concept:
Under no circumstances may tenant source code be stored in the learning index or Redis.
The index persists strictly one-way hashes and high-level structural metadata:
- SHA-256 fingerprint
- Rule ID & Category
- AST node type path
- One-way hash of matched excerpt
- Sanitized user comment
Tenant proprietary algorithms, variable names, logic, and raw statements must NEVER appear.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.finding import Finding, FindingFeedback, FindingOrigin, Severity
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import ConsentRecord, Tenant, User
from app.services.learning_service import index_finding_disposition
import app.models  # ensure models are registered


class InMemoryAsyncRedis:
    def __init__(self):
        self.strings: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}

    async def get(self, key: str):
        return self.strings.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.strings[key] = value
        return True

    async def sadd(self, key: str, *members: str):
        if key not in self.sets:
            self.sets[key] = set()
        for m in members:
            self.sets[key].add(m)
        return len(members)

    async def smembers(self, key: str):
        return set(self.sets.get(key, set()))


@pytest.mark.asyncio
async def test_zero_raw_code_persisted_in_redis_learning_index():
    """
    Assert that indexing a finding disposition stores zero proprietary source code in Redis.
    Only non-reversible structural hashes and metadata may be stored.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        run_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        finding_id = uuid.uuid4()
        feedback_id = uuid.uuid4()

        # Proprietary code snippets that must NEVER be persisted in the learning index
        secret_algo = "def proprietary_quantum_cipher(seed):\n    k = compute_secret(seed)\n    return k ^ 0xDEADBEEF"
        suspicious_statement = "os.system(untrusted_variable_containing_payload)"

        # 1. Seed models
        tenant = Tenant(tenant_id=tenant_id, name="Zero Code Tenant")
        user = User(
            user_id=user_id,
            tenant_id=tenant_id,
            email="researcher@enterprise.com",
            hashed_password="hash",
        )
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content=secret_algo,
            checksum="chk_zero_code",
            language="python",
            size_bytes=len(secret_algo),
            retention_until=datetime.now(timezone.utc),
        )
        review_run = ReviewRun(
            run_id=run_id,
            tenant_id=tenant_id,
            artifact_id=artifact_id,
            status=ReviewStatus.completed,
            requested_by=user_id,
        )
        consent = ConsentRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            purpose="feedback_learning",
            granted=True,
            version="1.0",
        )
        session.add_all([tenant, user, artifact, review_run, consent])
        await session.commit()

        # 2. Seed finding
        finding = Finding(
            finding_id=finding_id,
            run_id=run_id,
            tenant_id=tenant_id,
            fingerprint="fp_zero_code_001",
            origin=FindingOrigin.rule,
            rule_id="VIGIL-SEC-001",
            category="security",
            severity=Severity.high,
            confidence=0.9,
            title="Dangerous command execution",
            rationale="Untrusted input passed to OS system call",
            remediation="Replace with safe API",
            source_file_path="src/proprietary/crypto.py",
        )
        feedback = FindingFeedback(
            feedback_id=feedback_id,
            finding_id=finding_id,
            user_id=user_id,
            useful=False,
            disposition="false_positive",
            comment="Safe internal test utility without network access.",
            reason_category="intentional_pattern",
        )
        session.add_all([finding, feedback])
        await session.commit()

        redis = InMemoryAsyncRedis()

        # 3. Index disposition
        idx_id = await index_finding_disposition(
            db=session,
            redis=redis,
            finding=finding,
            feedback=feedback,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        assert idx_id is not None

        # 4. Inspect every Redis entry stored
        doc_key = f"vigil:learning:{tenant_id}:{feedback.feedback_id}"
        assert doc_key in redis.strings
        raw_payload = redis.strings[doc_key]
        doc = json.loads(raw_payload)

        # Assert proprietary code fragments NEVER appear in Redis payload
        assert "proprietary_quantum_cipher" not in raw_payload
        assert "compute_secret" not in raw_payload
        assert "0xDEADBEEF" not in raw_payload
        assert suspicious_statement not in raw_payload
        assert "src/proprietary/crypto.py" not in raw_payload

        # Assert only allowlisted keys are present
        allowed_keys = {
            "index_id",
            "feedback_id",
            "finding_id",
            "tenant_id",
            "rule_id",
            "category",
            "language",
            "ast_path",
            "matched_text_hash",
            "disposition",
            "reason_category",
            "user_comment_sanitized",
            "user_comment_was_truncated",
            "user_comment_redaction_count",
            "created_at",
        }
        assert set(doc.keys()).issubset(allowed_keys)
