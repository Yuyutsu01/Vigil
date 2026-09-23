"""
Integration tests for GET /v1/reviews endpoint (WS4b).

Requirements:
- test_1_returns_empty_list_for_new_tenant: Returns empty items and total=0 for a tenant with no reviews.
- test_2_lists_only_own_tenant_reviews: Strictly isolates reviews by tenant_id.
- test_3_pagination: Supports limit & offset, hard cap limit <= 100, rejects limit > 100 or < 1 or offset < 0 with 422.
- test_4_excludes_soft_deleted: Excludes reviews with status=deleted.
- test_5_status_filter: Filters by ?status=<value>, rejects ?status=deleted with 422.
- test_6_severity_counts_correct: Aggregates severity counts accurately per review item.
- test_7_requires_auth: Rejects unauthenticated requests with 401.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # ensure models are registered
from app.api.deps import get_db
from app.database import Base
from app.main import app as fastapi_app
from app.models.finding import Finding, FindingOrigin, Severity
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
    language: str = "python",
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    findings_severities: list[Severity] | None = None,
) -> ReviewRun:
    artifact = SourceArtifact(
        artifact_id=uuid.uuid4(),
        tenant_id=tenant_id,
        content="print('hello')",
        checksum=uuid.uuid4().hex,
        language=language,
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

    await session.commit()
    return run


@pytest.mark.asyncio
async def test_1_returns_empty_list_for_new_tenant(test_db_session):
    """Two tenants. Tenant A has no reviews. GET /v1/reviews returns {items: [], total: 0, limit: 20, offset: 0}."""
    tenant_a = uuid.uuid4()
    user_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_b = uuid.uuid4()

    async with test_db_session() as session:
        # Seed Tenant B with 1 review
        await _seed_review(session, tenant_b, user_b)

    token_a = _create_token(tenant_a, user_a)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/reviews", headers=headers_a)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["limit"] == 20
        assert data["offset"] == 0


@pytest.mark.asyncio
async def test_2_lists_only_own_tenant_reviews(test_db_session):
    """
    Tenant A has 3 reviews. Tenant B has 2 reviews.
    Tenant A GET /v1/reviews returns exactly 3 items, no B rows.
    Tenant B GET /v1/reviews returns exactly 2 items.
    """
    tenant_a = uuid.uuid4()
    user_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    user_b = uuid.uuid4()

    async with test_db_session() as session:
        for _ in range(3):
            await _seed_review(session, tenant_a, user_a)
        for _ in range(2):
            await _seed_review(session, tenant_b, user_b)

    token_a = _create_token(tenant_a, user_a)
    token_b = _create_token(tenant_b, user_b)

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp_a = await client.get("/v1/reviews", headers={"Authorization": f"Bearer {token_a}"})
        assert resp_a.status_code == 200
        data_a = resp_a.json()
        assert data_a["total"] == 3
        assert len(data_a["items"]) == 3

        resp_b = await client.get("/v1/reviews", headers={"Authorization": f"Bearer {token_b}"})
        assert resp_b.status_code == 200
        data_b = resp_b.json()
        assert data_b["total"] == 2
        assert len(data_b["items"]) == 2


@pytest.mark.asyncio
async def test_3_pagination(test_db_session):
    """
    Tenant A has 5 reviews.
    - limit=2, offset=0 -> 2 items, total=5.
    - limit=2, offset=4 -> 1 item, total=5.
    - limit=200 -> 422.
    - limit=-1 or offset=-1 -> 422.
    """
    tenant_a = uuid.uuid4()
    user_a = uuid.uuid4()

    async with test_db_session() as session:
        for _ in range(5):
            await _seed_review(session, tenant_a, user_a)

    token_a = _create_token(tenant_a, user_a)
    headers = {"Authorization": f"Bearer {token_a}"}

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Page 1
        resp1 = await client.get("/v1/reviews?limit=2&offset=0", headers=headers)
        assert resp1.status_code == 200
        d1 = resp1.json()
        assert len(d1["items"]) == 2
        assert d1["total"] == 5
        assert d1["limit"] == 2
        assert d1["offset"] == 0

        # Page 3 (offset=4)
        resp2 = await client.get("/v1/reviews?limit=2&offset=4", headers=headers)
        assert resp2.status_code == 200
        d2 = resp2.json()
        assert len(d2["items"]) == 1
        assert d2["total"] == 5

        # limit > 100 hard cap -> 422
        resp_over = await client.get("/v1/reviews?limit=200", headers=headers)
        assert resp_over.status_code == 422

        # limit <= 0 -> 422
        resp_neg_lim = await client.get("/v1/reviews?limit=-1", headers=headers)
        assert resp_neg_lim.status_code == 422

        # offset < 0 -> 422
        resp_neg_off = await client.get("/v1/reviews?offset=-1", headers=headers)
        assert resp_neg_off.status_code == 422


@pytest.mark.asyncio
async def test_4_excludes_soft_deleted(test_db_session):
    """
    Tenant A has 3 reviews, one with status=deleted.
    GET /v1/reviews returns 2 items, total=2.
    """
    tenant_a = uuid.uuid4()
    user_a = uuid.uuid4()

    async with test_db_session() as session:
        await _seed_review(session, tenant_a, user_a, status=ReviewStatus.completed)
        await _seed_review(session, tenant_a, user_a, status=ReviewStatus.completed)
        await _seed_review(session, tenant_a, user_a, status=ReviewStatus.deleted)

    token_a = _create_token(tenant_a, user_a)
    headers = {"Authorization": f"Bearer {token_a}"}

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/reviews", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert all(item["status"] != "deleted" for item in data["items"])


@pytest.mark.asyncio
async def test_5_status_filter(test_db_session):
    """
    Tenant A has 2 completed, 1 pending.
    ?status=completed returns 2 items.
    ?status=deleted returns 422.
    """
    tenant_a = uuid.uuid4()
    user_a = uuid.uuid4()

    async with test_db_session() as session:
        await _seed_review(session, tenant_a, user_a, status=ReviewStatus.completed)
        await _seed_review(session, tenant_a, user_a, status=ReviewStatus.completed)
        await _seed_review(session, tenant_a, user_a, status=ReviewStatus.pending)

    token_a = _create_token(tenant_a, user_a)
    headers = {"Authorization": f"Bearer {token_a}"}

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp_comp = await client.get("/v1/reviews?status=completed", headers=headers)
        assert resp_comp.status_code == 200
        data_comp = resp_comp.json()
        assert data_comp["total"] == 2
        assert len(data_comp["items"]) == 2
        assert all(item["status"] == "completed" for item in data_comp["items"])

        resp_del = await client.get("/v1/reviews?status=deleted", headers=headers)
        assert resp_del.status_code == 422


@pytest.mark.asyncio
async def test_6_severity_counts_correct(test_db_session):
    """Review with findings of each severity. Response severity_counts matches."""
    tenant_a = uuid.uuid4()
    user_a = uuid.uuid4()

    severities = [
        Severity.critical,
        Severity.high,
        Severity.high,
        Severity.medium,
        Severity.low,
        Severity.info,
    ]

    async with test_db_session() as session:
        await _seed_review(
            session,
            tenant_a,
            user_a,
            status=ReviewStatus.completed,
            findings_severities=severities,
        )

    token_a = _create_token(tenant_a, user_a)
    headers = {"Authorization": f"Bearer {token_a}"}

    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/reviews", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        item = data["items"][0]
        assert item["finding_count"] == 6
        assert item["severity_counts"] == {
            "critical": 1,
            "high": 2,
            "medium": 1,
            "low": 1,
            "info": 1,
        }


@pytest.mark.asyncio
async def test_7_requires_auth():
    """No Authorization header -> 401."""
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/reviews")
        assert resp.status_code == 401
