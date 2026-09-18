"""
Unit tests for AdapterRegistry caching, LRU eviction, Redis cooldown, and singleflight (B5).
"""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.adapters.base import ToolAdapter
from app.adapters.registry import AdapterRegistry
from app.schemas.finding import RawFinding


class FastAdapter(ToolAdapter):
    name = "fast_tool"
    version = "1.0.0"
    languages = ["python"]

    def __init__(self):
        self.run_count = 0

    def build_command(self, target_path):
        return ["dummy"]

    def parse_output(self, stdout: str, stderr: str, return_code: int):
        return []

    async def run(self, source_text: str, language: str):
        self.run_count += 1
        finding = RawFinding(
            tool_name=self.name,
            tool_version=self.version,
            rule_id="FAST001",
            message="Fast message",
            file_path="dummy.py",
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=10,
            raw_evidence={"snippet": "fast"},
        )
        return [finding], None


class SlowAdapter(ToolAdapter):
    name = "slow_tool"
    version = "1.0.0"
    languages = ["python"]

    def __init__(self):
        self.run_count = 0

    def build_command(self, target_path):
        return ["dummy"]

    def parse_output(self, stdout: str, stderr: str, return_code: int):
        return []

    async def run(self, source_text: str, language: str):
        self.run_count += 1
        await asyncio.sleep(0.05)
        finding = RawFinding(
            tool_name=self.name,
            tool_version=self.version,
            rule_id="SLOW001",
            message="Slow message",
            file_path="dummy.py",
            start_line=1,
            start_col=1,
            end_line=1,
            end_col=10,
            raw_evidence={"snippet": "slow"},
        )
        return [finding], None


@pytest.mark.asyncio
async def test_lru_eviction():
    """Test LRU eviction: inserting 10,001 keys evicts the first key."""
    AdapterRegistry._memory_cache.clear()

    # Populate 10,000 keys
    for i in range(AdapterRegistry._MEMORY_CACHE_MAX):
        key = f"key_{i}"
        AdapterRegistry._memory_cache[key] = f"val_{i}"

    assert len(AdapterRegistry._memory_cache) == 10_000
    assert "key_0" in AdapterRegistry._memory_cache

    registry = AdapterRegistry()
    adapter = FastAdapter()
    source_hash = "unique_source_hash_for_lru"
    cache_key = f"adapter:{source_hash}:{adapter.name}:{adapter.version}"

    with patch("app.adapters.registry.get_redis", side_effect=Exception("No Redis")):
        await registry._run_single_with_cache(adapter, "source_code", "python", source_hash)

    assert len(AdapterRegistry._memory_cache) == AdapterRegistry._MEMORY_CACHE_MAX
    # First key should be evicted
    assert "key_0" not in AdapterRegistry._memory_cache
    # Newest key should be present
    assert cache_key in AdapterRegistry._memory_cache


@pytest.mark.asyncio
async def test_redis_cooldown():
    """Simulate failure, assert second call within 60s skips Redis, advance past 60s and assert retry occurs."""
    AdapterRegistry._memory_cache.clear()
    AdapterRegistry._redis_down_until = 0.0

    registry = AdapterRegistry()
    adapter = FastAdapter()

    mock_redis = MagicMock()
    mock_redis.get = AsyncMock(side_effect=Exception("Redis connection refused"))
    mock_redis.set = AsyncMock(side_effect=Exception("Redis connection refused"))

    start_monotonic = 1000.0

    with patch("app.adapters.registry.time.monotonic", return_value=start_monotonic), \
         patch("app.adapters.registry.get_redis", return_value=mock_redis):
        # 1. First run: Redis lookup fails, sets cooldown
        await registry._run_single_with_cache(adapter, "test1", "python", "hash1")
        assert mock_redis.get.call_count == 1
        assert AdapterRegistry._redis_down_until == start_monotonic + 60.0

    # Clear memory cache so next call would check Redis if not in cooldown
    AdapterRegistry._memory_cache.clear()

    with patch("app.adapters.registry.time.monotonic", return_value=start_monotonic + 30.0), \
         patch("app.adapters.registry.get_redis", return_value=mock_redis):
        # 2. Second run within 30s: skips Redis entirely
        await registry._run_single_with_cache(adapter, "test2", "python", "hash2")
        # Call count remains 1 because Redis was skipped
        assert mock_redis.get.call_count == 1

    AdapterRegistry._memory_cache.clear()

    # Set mock_redis.get to succeed on retry
    mock_redis.get.side_effect = None
    mock_redis.get.return_value = json.dumps({
        "findings": [],
        "diagnostic": None,
    })

    with patch("app.adapters.registry.time.monotonic", return_value=start_monotonic + 65.0), \
         patch("app.adapters.registry.get_redis", return_value=mock_redis):
        # 3. Third run after 65s: retry occurs
        await registry._run_single_with_cache(adapter, "test3", "python", "hash3")
        assert mock_redis.get.call_count == 2
        # On success, cooldown reset to 0.0
        assert AdapterRegistry._redis_down_until == 0.0


@pytest.mark.asyncio
async def test_singleflight():
    """10 concurrent calls with same cache_key -> adapter.run invoked exactly once."""
    AdapterRegistry._memory_cache.clear()
    AdapterRegistry._inflight_tasks.clear()
    AdapterRegistry._redis_down_until = 0.0

    registry = AdapterRegistry()
    adapter = SlowAdapter()
    source_hash = "same_source_hash"

    with patch("app.adapters.registry.get_redis", side_effect=Exception("No Redis")):
        tasks = [
            registry._run_single_with_cache(adapter, "def foo(): pass", "python", source_hash)
            for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)

    assert len(results) == 10
    # Exactly one adapter.run execution
    assert adapter.run_count == 1
    # All tasks received findings
    for findings, diag in results:
        assert len(findings) == 1
        assert findings[0].rule_id == "SLOW001"
