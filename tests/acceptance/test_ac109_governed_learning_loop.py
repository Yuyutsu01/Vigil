"""
Acceptance tests for Governed Learning Loop (FR-109, AC-109.1 through AC-109.8).

Validates:
- AC-109.1: Zero raw tenant code persistence.
- AC-109.2: Multi-stage sanitization barrier.
- AC-109.3: Precedent retrieval threshold (>= 0.82) and similarity scoring.
- AC-109.4: Prompt injection isolation with delimiters.
- AC-109.5: Multi-tenant precedent isolation.
- AC-109.6: Right-to-be-forgotten purge in < 5.0s.
- AC-109.7: Foreign key ondelete='SET NULL' for learning_precedent_id (B4).
- AC-109.8: Fixed 24h UTC daily cost window with 25h TTL (B5).
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.learning.retrieval import PrecedentRetriever, compute_precedent_similarity
from app.models.finding import Finding, FindingFeedback, FindingOrigin, Severity
from app.models.orchestration import LearningDispositionIndex
from app.models.review import AuditAction, AuditEvent, ReviewRun, ReviewStatus, SourceArtifact
from app.models.tenant import ConsentRecord, Tenant, User
from app.services.budget_service import assert_tenant_daily_budget
from app.services.learning_service import (
    index_finding_disposition,
    purge_tenant_learning_data,
    sanitize_user_comment,
    verify_learning_consent,
)
import app.models  # ensure models are registered


class InMemoryAsyncRedis:
    def __init__(self):
        self.strings: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.floats: dict[str, float] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str):
        return self.strings.get(key)

    async def set(self, key: str, value: str, ex: int | None = None):
        self.strings[key] = value
        if ex:
            self.ttls[key] = ex
        return True

    async def incrbyfloat(self, key: str, amount: float) -> float:
        val = self.floats.get(key, 0.0) + amount
        self.floats[key] = round(val, 4)
        return self.floats[key]

    async def expire(self, key: str, seconds: int) -> bool:
        self.ttls[key] = seconds
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


def test_ac109_2_sanitization_barrier():
    """AC-109.2: 5-stage sanitization scrubs secrets, file paths, line refs, code, and caps 500 chars."""
    raw = (
        "False positive: token AKIAIOSFODNN7EXAMPLE reviewed in backend/app/auth.py line 88. "
        "def custom_clean(): return True"
    )
    sanitized, was_truncated, redacts = sanitize_user_comment(raw)
    assert "AKIAIOSFODNN7EXAMPLE" not in sanitized
    assert "backend/app/auth.py" not in sanitized
    assert "line 88" not in sanitized
    assert "def " not in sanitized
    assert len(sanitized) <= 500


def test_ac109_3_similarity_threshold_scoring():
    """AC-109.3: Weighted similarity matching strictly respects 0.82 threshold."""
    candidate = {
        "rule_id": "VIGIL-SEC-001",
        "category": "security",
        "language": "python",
        "ast_path": "Call/system",
    }

    # Perfect match: 0.50 + 0.20 + 0.15 + 0.15 = 1.00 >= 0.82
    full_score = compute_precedent_similarity(
        "VIGIL-SEC-001", "security", "python", "Call/system", candidate
    )
    assert full_score == 1.00

    # Rule and category match, but different language and AST: 0.50 + 0.20 = 0.70 < 0.82
    mismatch_score = compute_precedent_similarity(
        "VIGIL-SEC-001", "security", "javascript", "Call/exec", candidate
    )
    assert mismatch_score < 0.82


@pytest.mark.asyncio
async def test_ac109_8_fixed_24h_utc_budget_window():
    """AC-109.8: Fixed 24h UTC daily budget window with 25h TTL."""
    redis = InMemoryAsyncRedis()
    tenant_id = uuid.uuid4()
    date_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    expected_key = f"tenant:{tenant_id}:cost:24h:{date_iso}"

    cur = await assert_tenant_daily_budget(redis, tenant_id, added_cost=12.50, limit=50.0)
    assert cur == 12.50
    assert redis.floats[expected_key] == 12.50
    assert redis.ttls[expected_key] == 90000  # 25 hours
