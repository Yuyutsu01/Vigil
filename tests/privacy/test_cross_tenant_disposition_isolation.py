"""
Privacy test for Multi-Tenant Historical Disposition Isolation (FR-109 / AC-109.5).

Concept:
Historical learning precedents and dispositions must remain strictly isolated within each tenant's boundary.
Tenant A's historical false positive determinations or commentary must NEVER be accessible
to or influence reviews conducted for Tenant B, even for identical rule IDs, files, or languages.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.learning.retrieval import PrecedentRetriever
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
async def test_tenant_disposition_complete_cross_tenant_isolation():
    """
    Assert that Tenant B can never retrieve Tenant A's indexed precedents,
    even for identical rule ID, category, and language.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        # Tenant A setup
        tenant_a_id = uuid.uuid4()
        user_a_id = uuid.uuid4()
        run_a_id = uuid.uuid4()
        art_a_id = uuid.uuid4()
        find_a_id = uuid.uuid4()
        fb_a_id = uuid.uuid4()

        tenant_a = Tenant(tenant_id=tenant_a_id, name="Tenant A")
        user_a = User(user_id=user_a_id, tenant_id=tenant_a_id, email="dev@tenanta.com", hashed_password="pw")
        art_a = SourceArtifact(
            artifact_id=art_a_id,
            tenant_id=tenant_a_id,
            content="exec(code)",
            checksum="chk_a",
            language="python",
            size_bytes=10,
            retention_until=datetime.now(timezone.utc),
        )
        run_a = ReviewRun(run_id=run_a_id, tenant_id=tenant_a_id, artifact_id=art_a_id, requested_by=user_a_id)
        consent_a = ConsentRecord(tenant_id=tenant_a_id, user_id=user_a_id, purpose="feedback_learning", granted=True, version="1.0")
        session.add_all([tenant_a, user_a, art_a, run_a, consent_a])
        await session.commit()

        # Tenant B setup
        tenant_b_id = uuid.uuid4()
        user_b_id = uuid.uuid4()
        tenant_b = Tenant(tenant_id=tenant_b_id, name="Tenant B")
        user_b = User(user_id=user_b_id, tenant_id=tenant_b_id, email="dev@tenantb.com", hashed_password="pw")
        consent_b = ConsentRecord(tenant_id=tenant_b_id, user_id=user_b_id, purpose="feedback_learning", granted=True, version="1.0")
        session.add_all([tenant_b, user_b, consent_b])
        await session.commit()

        # Finding & feedback in Tenant A
        finding_a = Finding(
            finding_id=find_a_id,
            run_id=run_a_id,
            tenant_id=tenant_a_id,
            fingerprint="fp_shared_rule_001",
            origin=FindingOrigin.rule,
            rule_id="VIGIL-SEC-001",
            category="security",
            severity=Severity.medium,
            confidence=0.9,
            title="Dynamic code execution",
            rationale="Unsafe exec call",
            remediation="Avoid dynamic execution",
            source_file_path="tenanta/app.py",
        )
        feedback_a = FindingFeedback(
            feedback_id=fb_a_id,
            finding_id=find_a_id,
            user_id=user_a_id,
            useful=False,
            disposition="false_positive",
            comment="Tenant A approved design exception.",
            reason_category="intentional_pattern",
        )
        session.add_all([finding_a, feedback_a])
        await session.commit()

        redis = InMemoryAsyncRedis()

        # Index disposition for Tenant A
        idx_res = await index_finding_disposition(
            db=session,
            redis=redis,
            finding=finding_a,
            feedback=feedback_a,
            user_id=user_a_id,
            tenant_id=tenant_a_id,
        )
        assert idx_res is not None

        retriever = PrecedentRetriever(redis_client=redis)

        # 1. Tenant A retrieves its own precedent
        precedents_a = await retriever.retrieve_precedents(
            tenant_id=tenant_a_id,
            rule_id="VIGIL-SEC-001",
            category="security",
            language="python",
        )
        assert len(precedents_a) == 1
        assert precedents_a[0].disposition == "false_positive"
        assert precedents_a[0].user_comment_sanitized == "Tenant A approved design exception."

        # 2. Tenant B queries for the exact same rule, category, and language
        precedents_b = await retriever.retrieve_precedents(
            tenant_id=tenant_b_id,
            rule_id="VIGIL-SEC-001",
            category="security",
            language="python",
        )
        # Must be strictly empty — zero cross-tenant precedent leakage!
        assert len(precedents_b) == 0
