"""
Privacy tests for Governed Learning Consent Default-Off posture (FR-109, B3).
Asserts:
1. A fresh tenant has no learning consent by default.
2. Finding dispositions are not indexed for learning when consent is absent.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.finding import Finding, Severity, FindingOrigin, FindingFeedback
from app.models.tenant import Tenant, User
from app.services.consent_service import get_latest_consent
from app.services.learning_service import (
    verify_learning_consent,
    index_finding_disposition,
)


class MockRedis:
    def __init__(self):
        self.sets = {}
        self.strings = {}

    async def sadd(self, key, *members):
        self.sets.setdefault(key, set()).update(members)
        return len(members)

    async def scard(self, key):
        return len(self.sets.get(key, set()))

    async def smembers(self, key):
        return set(self.sets.get(key, set()))


@pytest.mark.asyncio
async def test_fresh_tenant_has_no_learning_consent():
    """
    Create a fresh tenant. Query consent service for 'feedback_learning'.
    Assert granted is False (or record absent).
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        fresh_tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # Query consent record directly
        record = await get_latest_consent(session, user_id, fresh_tenant_id, purpose="feedback_learning")
        assert record is None

        # Query verification service
        granted, reason = await verify_learning_consent(session, user_id, fresh_tenant_id)
        assert granted is False
        assert reason == "consent_required"


@pytest.mark.asyncio
async def test_feedback_not_indexed_without_consent():
    """
    Submit a finding disposition for a tenant without learning consent.
    Assert finding_feedback.indexed_for_learning is False and the RAG index is empty for that tenant.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id = uuid.uuid4()
        user_id = uuid.uuid4()
        run_id = uuid.uuid4()
        finding_id = uuid.uuid4()

        # Setup tenant
        tenant = Tenant(tenant_id=tenant_id, name="No Consent Corp")
        session.add(tenant)
        user = User(user_id=user_id, tenant_id=tenant_id, email="dev@noconsent.com", hashed_password="hash")
        session.add(user)

        # Create finding
        finding = Finding(
            finding_id=finding_id,
            run_id=run_id,
            tenant_id=tenant_id,
            fingerprint="fp_12345",
            rule_id="VIGIL-SEC-001",
            category="security",
            severity=Severity.high,
            confidence=0.9,
            title="Insecure command execution",
            rationale="Unsafe shell execution.",
            remediation="Use shlex.quote.",
            origin=FindingOrigin.rule,
        )
        session.add(finding)
        await session.flush()

        # Create user feedback disposition
        feedback = FindingFeedback(
            feedback_id=uuid.uuid4(),
            finding_id=finding_id,
            user_id=user_id,
            disposition="false_positive",
            comment="Standard benign helper script.",
            indexed_for_learning=False,
        )
        session.add(feedback)
        await session.flush()

        redis = MockRedis()

        # Attempt to index finding disposition without consent
        indexed_id = await index_finding_disposition(
            db=session,
            redis=redis,
            finding=finding,
            feedback=feedback,
            user_id=user_id,
            tenant_id=tenant_id,
        )

        # Invariant checks:
        assert indexed_id is None
        assert feedback.indexed_for_learning is False

        # Verify redis index has 0 elements
        assert await redis.scard(f"vigil:learning_keys:{tenant_id}") == 0
