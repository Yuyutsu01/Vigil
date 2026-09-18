"""
Integration test for Governed Feedback Loop and RAG Retrieval (FR-109).

Concept:
When developers provide dispositions on findings, the Governed Feedback Loop:
1. Validates opt-in consent for purpose='feedback_learning'.
2. Passes user commentary through multi-stage sanitization (redacting secrets, file paths, line numbers, and code patterns).
3. Indexes only allowlisted metadata and similarity hashes into tenant-isolated Redis storage.
4. PrecedentRetriever retrieves matching precedents (threshold >= 0.82) to augment subsequent risk evaluations.
5. Immediate right-to-be-forgotten purge clears all Redis keys, updates database models, and logs audit events.
"""
from __future__ import annotations

import json
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
    verify_learning_consent,
)
import app.models  # ensure models are registered


class InMemoryAsyncRedis:
    """In-memory async Redis simulation supporting strings, sets, and pipelines."""

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
async def test_governed_feedback_loop_indexing_retrieval_and_purge():
    """
    End-to-end test of:
    1. Consent check gating indexing.
    2. Comment sanitization and Redis indexing.
    3. Precedent retrieval with similarity threshold >= 0.82.
    4. Instant tenant learning data purge.
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

        # 1. Seed Tenant, User, SourceArtifact, and ReviewRun
        tenant = Tenant(tenant_id=tenant_id, name="Learning Loop Tenant")
        user = User(
            user_id=user_id,
            tenant_id=tenant_id,
            email="dev@example.com",
            hashed_password="argon2_fake_hash",
        )
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content="os.system(cmd)",
            checksum="chk_learning_test",
            language="python",
            size_bytes=16,
            retention_until=datetime.now(timezone.utc),
        )
        review_run = ReviewRun(
            run_id=run_id,
            tenant_id=tenant_id,
            artifact_id=artifact_id,
            status=ReviewStatus.completed,
            requested_by=user_id,
        )
        session.add(tenant)
        session.add(user)
        await session.flush()
        session.add(artifact)
        await session.flush()
        session.add(review_run)
        await session.flush()

        # 2. Seed Finding and FindingFeedback
        finding = Finding(
            finding_id=finding_id,
            run_id=run_id,
            tenant_id=tenant_id,
            fingerprint="fp_learning_001",
            origin=FindingOrigin.rule,
            rule_id="SEC-001",
            category="security",
            severity=Severity.medium,
            confidence=0.85,
            title="Command injection",
            rationale="Unsanitized cmd execution",
            remediation="Use subprocess.run with list arguments",
            source_file_path="backend/app/main.py",
        )
        # Feedback includes secret token and internal file path that MUST be sanitized
        raw_comment = (
            "False alarm: verified internal utility at backend/app/main.py line 45. "
            "Internal token AKIAIOSFODNN7EXAMPLE is revoked in test."
        )
        feedback = FindingFeedback(
            feedback_id=feedback_id,
            finding_id=finding_id,
            user_id=user_id,
            useful=False,
            disposition="false_positive",
            comment=raw_comment,
            reason_category="intentional_pattern",
        )
        session.add(finding)
        await session.flush()
        session.add(feedback)
        await session.commit()

        redis = InMemoryAsyncRedis()

        # 3. Test without consent -> indexing must be denied
        allowed, _ = await verify_learning_consent(session, user_id, tenant_id)
        assert allowed is False

        idx_res = await index_finding_disposition(
            db=session,
            redis=redis,
            finding=finding,
            feedback=feedback,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        assert idx_res is None
        assert feedback.indexed_for_learning is False
        assert len(redis.strings) == 0

        # 4. Grant consent for 'feedback_learning'
        consent = ConsentRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            purpose="feedback_learning",
            granted=True,
            version="1.0",
        )
        session.add(consent)
        await session.commit()

        allowed, _ = await verify_learning_consent(session, user_id, tenant_id)
        assert allowed is True

        # 5. Index finding disposition with active consent
        idx_res = await index_finding_disposition(
            db=session,
            redis=redis,
            finding=finding,
            feedback=feedback,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        await session.commit()
        assert idx_res is not None
        assert feedback.indexed_for_learning is True
        assert feedback.learning_precedent_id == idx_res

        # 6. Verify sanitized Redis storage
        doc_key = f"vigil:learning:{tenant_id}:{feedback.feedback_id}"
        assert doc_key in redis.strings
        stored_doc = json.loads(redis.strings[doc_key])

        # Assert zero tenant source code in doc
        assert "os.system(cmd)" not in redis.strings[doc_key]

        # Assert secret redacted and file path/line reference stripped
        sanitized_comment = stored_doc["user_comment_sanitized"]
        assert "AKIAIOSFODNN7EXAMPLE" not in sanitized_comment
        assert "[REDACTED_SECRET" in sanitized_comment or "[REDACTED" in sanitized_comment
        assert "backend/app/main.py" not in sanitized_comment
        assert "line 45" not in sanitized_comment

        # 7. Test PrecedentRetriever matching
        retriever = PrecedentRetriever(redis_client=redis)
        precedents = await retriever.retrieve_precedents(
            tenant_id=tenant_id,
            rule_id="SEC-001",
            category="security",
            language="python",
            limit=5,
        )
        assert len(precedents) == 1
        prec = precedents[0]
        assert prec.rule_id == "SEC-001"
        assert prec.disposition == "false_positive"
        assert prec.reason_category == "intentional_pattern"
        assert prec.similarity_score >= 0.82

        # 8. Test Purge / Right to be Forgotten
        purged = await purge_tenant_learning_data(
            db=session,
            redis=redis,
            tenant_id=tenant_id,
            actor_id=user_id,
        )
        await session.commit()
        assert purged == 1

        # Assert Redis keys are completely removed
        assert doc_key not in redis.strings
        set_key = f"vigil:learning_keys:{tenant_id}"
        assert set_key not in redis.sets or len(redis.sets[set_key]) == 0

        # Assert retriever returns empty list after purge
        precedents_after = await retriever.retrieve_precedents(
            tenant_id=tenant_id,
            rule_id="SEC-001",
            category="security",
            language="python",
        )
        assert len(precedents_after) == 0

        # Assert feedback record updated
        check_fb_stmt = select(FindingFeedback).where(FindingFeedback.feedback_id == feedback_id)
        fb_res = await session.execute(check_fb_stmt)
        fb_updated = fb_res.scalar_one()
        assert fb_updated.indexed_for_learning is False
