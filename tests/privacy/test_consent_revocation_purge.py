"""
Privacy test for Instant Consent Revocation and Right-to-be-Forgotten Purge (FR-109 / AC-109.6).

Concept:
Under GDPR Art. 17 / Right to be Forgotten, when a tenant revokes learning consent:
1. All Redis disposition keys and index sets are deleted in < 5 seconds.
2. The database LearningDispositionIndex has entry_count reset to 0 and last_purged_at updated.
3. All FindingFeedback records for that tenant are reset to indexed_for_learning=False.
4. AuditEvents for LEARNING_CONSENT_REVOKED and LEARNING_INDEX_PURGED are recorded.
5. Subsequent retrieval queries for that tenant return 0 precedents immediately.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.learning.retrieval import PrecedentRetriever
from app.models.finding import Finding, FindingFeedback, FindingOrigin, Severity
from app.models.orchestration import LearningDispositionIndex
from app.models.review import AuditAction, AuditEvent, ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import ConsentRecord, Tenant, User
from app.services.learning_service import (
    index_finding_disposition,
    purge_tenant_learning_data,
)
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

    def pipeline(self):
        class FakePipeline:
            def __init__(self, outer):
                self.outer = outer
                self.ops = []

            def delete(self, key):
                self.ops.append(key)

            async def execute(self):
                for k in self.ops:
                    self.outer.strings.pop(k, None)
                    self.outer.sets.pop(k, None)
                return [True] * len(self.ops)

        return FakePipeline(self)


@pytest.mark.asyncio
async def test_instant_purge_upon_consent_revocation():
    """
    Verify that revoking consent triggers an immediate purge of all tenant learning data in < 5s,
    clears Redis keys, resets database index counts, and records audit events.
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

        # 1. Seed models with active consent
        tenant = Tenant(tenant_id=tenant_id, name="Purge Test Tenant")
        user = User(
            user_id=user_id,
            tenant_id=tenant_id,
            email="admin@purge.com",
            hashed_password="hash",
        )
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content="var x = 1;",
            checksum="chk_purge",
            language="javascript",
            size_bytes=10,
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

        finding = Finding(
            finding_id=finding_id,
            run_id=run_id,
            tenant_id=tenant_id,
            fingerprint="fp_purge_001",
            origin=FindingOrigin.rule,
            rule_id="JS-SEC-001",
            category="security",
            severity=Severity.medium,
            confidence=0.8,
            title="Insecure eval",
            rationale="Untrusted code execution",
            remediation="Avoid eval",
            source_file_path="app.js",
        )
        feedback = FindingFeedback(
            feedback_id=feedback_id,
            finding_id=finding_id,
            user_id=user_id,
            useful=True,
            disposition="accepted",
            comment="Confirmed vulnerability, scheduled for sprint fix.",
            reason_category="intentional_pattern",
        )
        session.add_all([finding, feedback])
        await session.commit()

        redis = InMemoryAsyncRedis()

        # 2. Index finding disposition
        idx_id = await index_finding_disposition(
            db=session,
            redis=redis,
            finding=finding,
            feedback=feedback,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        await session.commit()
        assert idx_id is not None
        assert feedback.indexed_for_learning is True

        # Precedent must be retrievable before purge
        retriever = PrecedentRetriever(redis_client=redis)
        before_precedents = await retriever.retrieve_precedents(
            tenant_id=tenant_id,
            rule_id="JS-SEC-001",
            category="security",
            language="javascript",
        )
        assert len(before_precedents) == 1

        # 3. Trigger Right to be Forgotten Purge and measure execution latency
        start_purge = time.perf_counter()
        purged_count = await purge_tenant_learning_data(
            db=session,
            redis=redis,
            tenant_id=tenant_id,
            actor_id=user_id,
        )
        await session.commit()
        purge_latency = time.perf_counter() - start_purge

        # Must complete in strictly under 5.0 seconds (AC-109.6)
        assert purge_latency < 5.0, f"Purge exceeded 5s latency requirement: {purge_latency:.3f}s"
        assert purged_count == 1

        # 4. Assert Redis keys are completely removed
        doc_key = f"vigil:learning:{tenant_id}:{feedback.feedback_id}"
        assert doc_key not in redis.strings
        set_key = f"vigil:learning_keys:{tenant_id}"
        assert set_key not in redis.sets or len(redis.sets[set_key]) == 0

        # 5. Assert RAG query immediately returns empty list
        after_precedents = await retriever.retrieve_precedents(
            tenant_id=tenant_id,
            rule_id="JS-SEC-001",
            category="security",
            language="javascript",
        )
        assert len(after_precedents) == 0

        # 6. Assert DB records updated
        index_stmt = select(LearningDispositionIndex).where(LearningDispositionIndex.tenant_id == tenant_id)
        idx_res = await session.execute(index_stmt)
        db_index = idx_res.scalar_one()
        assert db_index.entry_count == 0
        assert db_index.last_purged_at is not None

        fb_stmt = select(FindingFeedback).where(FindingFeedback.feedback_id == feedback_id)
        fb_res = await session.execute(fb_stmt)
        fb_record = fb_res.scalar_one()
        assert fb_record.indexed_for_learning is False

        # 7. Assert AuditEvent recorded
        audit_stmt = select(AuditEvent).where(AuditEvent.action == AuditAction.LEARNING_INDEX_PURGED)
        audit_res = await session.execute(audit_stmt)
        purge_audits = audit_res.scalars().all()
        assert len(purge_audits) == 1
        assert purge_audits[0].tenant_id == tenant_id
