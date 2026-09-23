"""
Regression tests for STAT-01: Ensuring tenant statistics calculations
exclude soft-deleted review runs across all aggregate metrics while preserving
historical token consumption and cost.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # ensure models are registered
from app.api.deps import get_db
from app.database import Base
from app.main import app as fastapi_app
from app.models.finding import Finding, FindingOrigin, Severity
from app.models.orchestration import AgentCoordinationRun
from app.models.review import ReviewRun, ReviewStatus, SourceArtifact
from app.services.auth_service import create_access_token


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
async def test_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield session_maker
    fastapi_app.dependency_overrides.pop(get_db, None)
    await engine.dispose()


def _create_token(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    return create_access_token(
        user_id=user_id,
        tenant_id=tenant_id,
        role="developer",
    )


async def _seed_review(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    status: ReviewStatus = ReviewStatus.completed,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    findings_severities: list[Severity] | None = None,
    tokens_consumed: int = 0,
) -> ReviewRun:
    artifact = SourceArtifact(
        artifact_id=uuid.uuid4(),
        tenant_id=tenant_id,
        content="print('hello')",
        checksum=uuid.uuid4().hex,
        language="python",
        size_bytes=14,
        retention_until=_now(),
    )
    session.add(artifact)
    await session.flush()

    run = ReviewRun(
        run_id=uuid.uuid4(),
        tenant_id=tenant_id,
        artifact_id=artifact.artifact_id,
        status=status,
        requested_by=user_id,
        started_at=started_at if started_at is not None else (_now() if status != ReviewStatus.pending else None),
        completed_at=completed_at if completed_at is not None else (_now() if status == ReviewStatus.completed else None),
    )
    session.add(run)
    await session.flush()

    if findings_severities:
        for idx, sev in enumerate(findings_severities):
            f = Finding(
                finding_id=uuid.uuid4(),
                run_id=run.run_id,
                tenant_id=tenant_id,
                fingerprint=f"fp_{run.run_id}_{idx}",
                origin=FindingOrigin.rule,
                rule_id=f"RULE-{idx}",
                category="Security",
                severity=sev,
                confidence=0.9,
                title=f"Finding {idx}",
                rationale="test rationale",
                remediation="test remediation",
            )
            session.add(f)
        await session.flush()

    if tokens_consumed > 0:
        coord = AgentCoordinationRun(
            coordination_id=uuid.uuid4(),
            review_run_id=run.run_id,
            tenant_id=tenant_id,
            status="completed",
            total_tokens_consumed=tokens_consumed,
            total_wall_clock_ms=500,
        )
        session.add(coord)
        await session.flush()

    await session.commit()
    return run


@pytest.mark.asyncio
async def test_1_total_reviews_excludes_deleted(test_db_session: async_sessionmaker):
    """GET /v1/tenants/me/stats excludes reviews with status=deleted from total_reviews count."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = _create_token(tenant_id, user_id)

    async with test_db_session() as session:
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed)
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed)
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.deleted)

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/tenants/me/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_reviews"] == 2


@pytest.mark.asyncio
async def test_2_total_findings_excludes_deleted(test_db_session: async_sessionmaker):
    """GET /v1/tenants/me/stats excludes findings belonging to deleted reviews from total_findings count."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = _create_token(tenant_id, user_id)

    async with test_db_session() as session:
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed, findings_severities=[Severity.high])
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed, findings_severities=[Severity.medium])
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.deleted, findings_severities=[Severity.critical, Severity.critical])

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/tenants/me/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_findings"] == 2


@pytest.mark.asyncio
async def test_3_severity_counts_exclude_deleted(test_db_session: async_sessionmaker):
    """GET /v1/tenants/me/stats excludes findings of deleted reviews from severity breakdown."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = _create_token(tenant_id, user_id)

    async with test_db_session() as session:
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed, findings_severities=[Severity.critical, Severity.high])
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed, findings_severities=[Severity.medium])
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.deleted, findings_severities=[Severity.critical, Severity.critical])

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/tenants/me/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        counts = data["findings_by_severity"]
        assert counts["Critical"] == 1
        assert counts["High"] == 1
        assert counts["Medium"] == 1


@pytest.mark.asyncio
async def test_4_avg_duration_excludes_deleted(test_db_session: async_sessionmaker):
    """GET /v1/tenants/me/stats excludes deleted reviews from avg_review_duration_ms."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = _create_token(tenant_id, user_id)
    t0 = datetime(2026, 9, 20, 10, 0, 0, tzinfo=timezone.utc)

    async with test_db_session() as session:
        # Run 1: 10s = 10,000ms
        await _seed_review(
            session, tenant_id, user_id, status=ReviewStatus.completed,
            started_at=t0, completed_at=t0 + timedelta(seconds=10),
        )
        # Run 2: 20s = 20,000ms
        await _seed_review(
            session, tenant_id, user_id, status=ReviewStatus.completed,
            started_at=t0, completed_at=t0 + timedelta(seconds=20),
        )
        # Run 3 (deleted): 90s = 90,000ms
        await _seed_review(
            session, tenant_id, user_id, status=ReviewStatus.deleted,
            started_at=t0, completed_at=t0 + timedelta(seconds=90),
        )

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/tenants/me/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        # Expected average of non-deleted runs: (10,000 + 20,000) / 2 = 15,000ms
        assert data["avg_review_duration_ms"] == 15000


@pytest.mark.asyncio
async def test_5_activity_window_excludes_deleted(test_db_session: async_sessionmaker):
    """GET /v1/tenants/me/stats excludes deleted reviews from reviews_last_7_days."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = _create_token(tenant_id, user_id)
    now = datetime.now(timezone.utc)

    async with test_db_session() as session:
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed, started_at=now - timedelta(days=1))
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed, started_at=now - timedelta(days=2))
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.deleted, started_at=now - timedelta(days=1))

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/tenants/me/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["reviews_last_7_days"] == 2


@pytest.mark.asyncio
async def test_6_dashboard_agrees_with_list(test_db_session: async_sessionmaker):
    """STAT-01 core invariant: stats.total_reviews == list_reviews.total."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = _create_token(tenant_id, user_id)

    async with test_db_session() as session:
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed)
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.pending)
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.deleted)

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        stats_resp = await client.get("/v1/tenants/me/stats", headers={"Authorization": f"Bearer {token}"})
        assert stats_resp.status_code == 200
        stats_total = stats_resp.json()["total_reviews"]

        list_resp = await client.get("/v1/reviews", headers={"Authorization": f"Bearer {token}"})
        assert list_resp.status_code == 200
        list_total = list_resp.json()["total"]

        assert stats_total == list_total
        assert stats_total == 2


@pytest.mark.asyncio
async def test_7_tokens_cost_unchanged_by_deletion(test_db_session: async_sessionmaker):
    """Decision 1: total_tokens_used and total_cost_usd remain unchanged after review soft-deletion."""
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    token = _create_token(tenant_id, user_id)

    run_to_delete_id: uuid.UUID
    async with test_db_session() as session:
        await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed, tokens_consumed=5000)
        run_del = await _seed_review(session, tenant_id, user_id, status=ReviewStatus.completed, tokens_consumed=3000)
        run_to_delete_id = run_del.run_id

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Before soft-delete
        resp_before = await client.get("/v1/tenants/me/stats", headers={"Authorization": f"Bearer {token}"})
        data_before = resp_before.json()
        assert data_before["total_tokens_used"] == 8000
        assert data_before["total_cost_usd"] == 0.016

        # Soft-delete the second run
        async with test_db_session() as session:
            r = await session.get(ReviewRun, run_to_delete_id)
            if r:
                r.status = ReviewStatus.deleted
                await session.commit()

        # After soft-delete
        resp_after = await client.get("/v1/tenants/me/stats", headers={"Authorization": f"Bearer {token}"})
        data_after = resp_after.json()
        assert data_after["total_tokens_used"] == 8000
        assert data_after["total_cost_usd"] == 0.016
