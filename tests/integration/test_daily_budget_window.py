"""
Integration test for Tenant Daily Budget Fixed UTC Window (FR-108 / [B5]).

Concept:
Tenant daily budget controls cannot use rolling sliding windows with timestamp scans
due to concurrency race conditions and unbounded memory growth.
Instead, Vigil tracks daily spend against a fixed UTC calendar day key:
`tenant:{tenant_id}:cost:24h:YYYY-MM-DD` with a 25-hour TTL (86400 + 3600s).
When spend exceeds the tenant's daily limit:
1. An AuditEvent is recorded with action=TENANT_DAILY_BUDGET_EXCEEDED.
2. An HTTPException(429) is raised with error code 'daily_budget_exceeded'.
3. Transitions across UTC midnight isolate spend into separate daily buckets.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models.review import AuditAction, AuditEvent
from app.models.tenant import Tenant
from app.services.budget_service import assert_tenant_daily_budget, get_tenant_daily_limit
import app.models  # ensure models are registered


class InMemoryAsyncRedis:
    """In-memory async Redis implementation for budget testing."""

    def __init__(self):
        self.data: dict[str, float] = {}
        self.ttls: dict[str, int] = {}

    async def incrbyfloat(self, key: str, amount: float) -> float:
        val = self.data.get(key, 0.0) + amount
        self.data[key] = round(val, 4)
        return self.data[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
        return True

    async def set(self, key: str, val: str, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self.data:
            return False
        self.data[key] = float(val)
        if ex:
            self.ttls[key] = ex
        return True

    async def eval(self, script: str, numkeys: int, key: str, cost: str, ttl: str) -> str:
        val = self.data.get(key, 0.0) + float(cost)
        self.data[key] = round(val, 4)
        self.ttls[key] = int(ttl)
        return str(self.data[key])

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, -2)

    async def delete(self, key: str) -> int:
        self.data.pop(key, None)
        self.ttls.pop(key, None)
        return 1


@pytest.mark.asyncio
async def test_tenant_daily_budget_under_limit():
    """Spend below limit succeeds and returns current spend."""
    fake_redis = InMemoryAsyncRedis()
    tenant_id = uuid.uuid4()
    limit = 50.0

    current = await assert_tenant_daily_budget(
        redis=fake_redis,
        tenant_id=tenant_id,
        added_cost=10.50,
        limit=limit,
    )
    assert current == 10.50

    # Verify key format and 25h TTL
    date_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    expected_key = f"tenant:{tenant_id}:cost:24h:{date_iso}"
    assert fake_redis.data[expected_key] == 10.50
    assert fake_redis.ttls[expected_key] == 90000  # 25 hours (86400 + 3600)


@pytest.mark.asyncio
async def test_tenant_daily_budget_exceeded_raises_429_and_audits():
    """Spend exceeding limit raises HTTPException(429) and records audit event."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with session_maker() as session:
        tenant_id = uuid.uuid4()
        tenant = Tenant(
            tenant_id=tenant_id,
            name="Daily Budget Tenant",
            daily_cost_limit_dollars=50.0,
        )
        session.add(tenant)
        await session.commit()

        limit = await get_tenant_daily_limit(session, tenant_id)
        assert limit == 50.0

        fake_redis = InMemoryAsyncRedis()

        # Step 1: Initial spend of $45.00 (allowed)
        await assert_tenant_daily_budget(
            redis=fake_redis,
            tenant_id=tenant_id,
            added_cost=45.00,
            limit=limit,
            db=session,
        )

        # Step 2: Incremental spend of $6.00 pushes total to $51.00 > $50.00 (fails)
        with pytest.raises(HTTPException) as exc_info:
            await assert_tenant_daily_budget(
                redis=fake_redis,
                tenant_id=tenant_id,
                added_cost=6.00,
                limit=limit,
                db=session,
            )

        assert exc_info.value.status_code == 429
        detail = exc_info.value.detail
        assert detail["code"] == "daily_budget_exceeded"
        assert detail["limit"] == 50.0
        assert detail["current"] == 51.0

        # Step 3: Verify AuditEvent recorded
        audit_stmt = select(AuditEvent).where(
            AuditEvent.action == AuditAction.TENANT_DAILY_BUDGET_EXCEEDED
        )
        res = await session.execute(audit_stmt)
        audits = res.scalars().all()
        assert len(audits) >= 1
        audit = audits[0]
        assert audit.tenant_id == tenant_id
        meta = json.loads(audit.metadata_json or "{}")
        assert meta["limit"] == 50.0
        assert meta["current"] == 51.0


@pytest.mark.asyncio
async def test_budget_key_always_has_ttl_under_concurrency():
    """
    IC1: Fire 100 concurrent assert_tenant_daily_budget calls.
    After all complete, assert redis.ttl(key) > 0.
    """
    import asyncio
    tenant_id = uuid.uuid4()
    date_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    key = f"tenant:{tenant_id}:cost:24h:{date_iso}"

    # Try connecting to real redis if running, otherwise use thread-safe in-memory redis
    use_real = False
    try:
        from app.redis_client import get_redis
        r = get_redis()
        await r.ping()
        use_real = True
        redis_client = r
        await redis_client.delete(key)
    except Exception:
        use_real = False

    if not use_real:
        class ConcurrentAsyncRedis:
            def __init__(self):
                self.data: dict[str, float] = {}
                self.ttls: dict[str, int] = {}
                self._lock = asyncio.Lock()

            async def eval(self, script: str, numkeys: int, k: str, cost: str, ttl: str):
                async with self._lock:
                    val = self.data.get(k, 0.0) + float(cost)
                    self.data[k] = round(val, 4)
                    self.ttls[k] = int(ttl)
                    return str(self.data[k])

            async def incrbyfloat(self, k: str, amount: float) -> float:
                async with self._lock:
                    val = self.data.get(k, 0.0) + amount
                    self.data[k] = round(val, 4)
                    return self.data[k]

            async def expire(self, k: str, seconds: int) -> bool:
                async with self._lock:
                    self.ttls[k] = seconds
                    return True

            async def set(self, k: str, val: str, ex: int | None = None, nx: bool = False):
                async with self._lock:
                    if nx and k in self.data:
                        return False
                    self.data[k] = float(val)
                    if ex:
                        self.ttls[k] = ex
                    return True

            async def ttl(self, k: str) -> int:
                async with self._lock:
                    return self.ttls.get(k, -2)

            async def delete(self, k: str) -> int:
                async with self._lock:
                    self.data.pop(k, None)
                    self.ttls.pop(k, None)
                    return 1

        redis_client = ConcurrentAsyncRedis()

    # Fire 100 concurrent assert_tenant_daily_budget calls
    tasks = [
        assert_tenant_daily_budget(
            redis=redis_client,
            tenant_id=tenant_id,
            added_cost=0.01,
            limit=100.0,
        )
        for _ in range(100)
    ]
    results = await asyncio.gather(*tasks)
    assert len(results) == 100

    ttl = await redis_client.ttl(key)
    assert ttl > 0
    assert ttl <= 90000

    if use_real:
        await redis_client.delete(key)
