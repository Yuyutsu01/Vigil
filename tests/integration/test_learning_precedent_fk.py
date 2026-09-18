"""
Integration test for Learning Precedent Foreign Key ondelete='SET NULL' (FR-109 / [B4]).

Concept:
When a tenant revokes learning consent or exercises their right-to-be-forgotten, their entries
in `learning_disposition_indices` are purged immediately.
To prevent cascading deletion of historical review findings (which would violate audit invariants),
the foreign key `findings.learning_precedent_id` must use `ondelete='SET NULL'`.
Deleting a precedent row must set the referencing finding's `learning_precedent_id` to NULL
while leaving the finding record and its historical audit trail completely intact.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.finding import Finding, FindingFeedback, FindingOrigin, Severity
from app.models.orchestration import LearningDispositionIndex
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import Tenant
import app.models  # ensure models are registered


@pytest.mark.asyncio
async def test_learning_precedent_deletion_sets_null():
    """
    Assert that deleting a LearningDispositionIndex row sets finding_feedback.learning_precedent_id to NULL
    and does NOT delete the FindingFeedback record.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Enable SQLite foreign key enforcement for all connections
    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        # 1. Seed tenant, source artifact, and review run
        tenant_id = uuid.uuid4()
        run_id = uuid.uuid4()
        artifact_id = uuid.uuid4()
        finding_id = uuid.uuid4()
        feedback_id = uuid.uuid4()
        index_id = uuid.uuid4()
        user_id = uuid.uuid4()

        tenant = Tenant(tenant_id=tenant_id, name="FK Null Tenant")
        artifact = SourceArtifact(
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            content="def foo(): pass",
            checksum="chk_fk_test",
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
        await session.flush()
        session.add(artifact)
        await session.flush()
        session.add(review_run)
        await session.flush()

        # 2. Seed a LearningDispositionIndex
        index_rec = LearningDispositionIndex(
            index_id=index_id,
            tenant_id=tenant_id,
            vector_index_name=f"tenant_{tenant_id}_rag",
            entry_count=1,
        )
        session.add(index_rec)
        await session.flush()

        # 3. Seed a Finding
        finding = Finding(
            finding_id=finding_id,
            run_id=run_id,
            tenant_id=tenant_id,
            fingerprint="fp_finding_001",
            origin=FindingOrigin.rule,
            rule_id="SEC-001",
            category="security",
            severity=Severity.medium,
            confidence=0.85,
            title="Possible insecure execution",
            rationale="Untrusted input passed to function",
            remediation="Sanitize input before execution",
        )
        session.add(finding)
        await session.flush()

        # 4. Seed FindingFeedback referencing learning_precedent_id
        feedback = FindingFeedback(
            feedback_id=feedback_id,
            finding_id=finding_id,
            user_id=user_id,
            useful=True,
            disposition="accepted",
            comment="Verified safe sanitization pattern",
            reason_category="intentional_pattern",
            indexed_for_learning=True,
            learning_precedent_id=index_id,
        )
        session.add(feedback)
        await session.commit()

        # Verify initial linkage
        check_stmt = select(FindingFeedback).where(FindingFeedback.feedback_id == feedback_id)
        res = await session.execute(check_stmt)
        persisted_fb = res.scalar_one()
        assert persisted_fb.learning_precedent_id == index_id

        # 5. Delete the learning index (simulating right-to-be-forgotten tenant purge)
        await session.delete(index_rec)
        await session.commit()

        # Expire cache to ensure reading fresh from SQLite database
        session.expire_all()

        # 6. Assert that FindingFeedback still exists, and learning_precedent_id is now NULL
        res_after = await session.execute(check_stmt)
        fb_after = res_after.scalar_one_or_none()
        assert fb_after is not None, "FindingFeedback was unexpectedly cascade-deleted!"
        assert fb_after.learning_precedent_id is None, "learning_precedent_id was not set to NULL!"
