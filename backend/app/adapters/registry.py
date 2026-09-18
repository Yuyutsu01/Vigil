"""
AdapterRegistry: discovers, manages, and dispatches static analysis adapters (FR-101).
Executes adapters concurrently with per-adapter timeouts, bounded LRU, and Redis caching.
"""
from __future__ import annotations

import asyncio
from collections import OrderedDict
import hashlib
import json
import logging
import time
from typing import Dict, List, Optional, Tuple

from app.adapters.bandit import BanditAdapter
from app.adapters.base import ToolAdapter
from app.adapters.eslint import ESLintAdapter
from app.adapters.npm_audit import NpmAuditAdapter
from app.adapters.pip_audit import PipAuditAdapter
from app.adapters.ruff import RuffAdapter
from app.adapters.semgrep import SemgrepAdapter
from app.redis_client import get_redis
from app.schemas.finding import RawFinding
from app.telemetry import create_span

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """
    Manages static analysis adapters and executes them concurrently.
    Provides Redis caching for tool outputs with 1-hour TTL and bounded in-memory LRU.
    """

    _MEMORY_CACHE_MAX: int = 10_000
    _memory_cache: OrderedDict[str, str] = OrderedDict()
    _inflight_tasks: Dict[str, asyncio.Future] = {}
    _inflight_lock: Optional[asyncio.Lock] = None
    _redis_down_until: float = 0.0
    _REDIS_COOLDOWN_SECONDS: float = 60.0

    def __init__(self, adapters: Optional[List[ToolAdapter]] = None):
        if adapters is None:
            self._adapters: List[ToolAdapter] = [
                BanditAdapter(),
                SemgrepAdapter(),
                RuffAdapter(),
                ESLintAdapter(),
                PipAuditAdapter(),
                NpmAuditAdapter(),
            ]
        else:
            self._adapters = adapters

    @classmethod
    def _get_inflight_lock(cls) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if cls._inflight_lock is None or getattr(cls._inflight_lock, "_loop", None) not in (None, loop):
            cls._inflight_lock = asyncio.Lock()
        return cls._inflight_lock

    def get_adapters_for_language(self, language: str) -> List[ToolAdapter]:
        """Return registered adapters that support the specified language."""
        lang_clean = language.lower()
        return [a for a in self._adapters if lang_clean in a.languages]

    async def _run_single_with_cache(
        self,
        adapter: ToolAdapter,
        source_text: str,
        language: str,
        source_hash: str,
    ) -> Tuple[List[RawFinding], Optional[dict]]:
        """Run single adapter with memory + Redis cache lookup and inflight deduplication."""
        cache_key = f"adapter:{source_hash}:{adapter.name}:{adapter.version}"

        # 1. Fast in-memory cache check
        if cache_key in self._memory_cache:
            try:
                self._memory_cache.move_to_end(cache_key)
                cached_data = json.loads(self._memory_cache[cache_key])
                findings = [RawFinding(**item) for item in cached_data.get("findings", [])]
                diagnostic = cached_data.get("diagnostic")
                return findings, diagnostic
            except Exception:
                pass

        # 2. Inflight task deduplication (singleflight) guarded by asyncio.Lock
        lock = self._get_inflight_lock()
        loop = asyncio.get_running_loop()
        async with lock:
            if cache_key in self._inflight_tasks:
                existing = self._inflight_tasks[cache_key]
                reuse = True
            else:
                future = loop.create_future()
                self._inflight_tasks[cache_key] = future
                reuse = False

        if reuse:
            findings, diagnostic = await existing
            # Return copies so caller modifications don't leak
            return [RawFinding(**f.model_dump()) for f in findings], diagnostic

        try:
            redis_client = None

            # 3. Redis cache lookup (skip if in cooldown)
            if time.monotonic() >= AdapterRegistry._redis_down_until:
                try:
                    redis_client = get_redis()
                    cached_str = await asyncio.wait_for(redis_client.get(cache_key), timeout=0.5)
                    if cached_str:
                        AdapterRegistry._redis_down_until = 0.0
                        if len(self._memory_cache) >= self._MEMORY_CACHE_MAX:
                            self._memory_cache.popitem(last=False)
                        self._memory_cache[cache_key] = cached_str
                        cached_data = json.loads(cached_str)
                        findings = [RawFinding(**item) for item in cached_data.get("findings", [])]
                        diagnostic = cached_data.get("diagnostic")
                        logger.debug("Cache hit for adapter %s (%s)", adapter.name, cache_key)
                        future.set_result((findings, diagnostic))
                        return findings, diagnostic
                except Exception as e:
                    AdapterRegistry._redis_down_until = time.monotonic() + AdapterRegistry._REDIS_COOLDOWN_SECONDS
                    logger.debug("Redis cache lookup failed for %s: %s (cooldown for 60s)", cache_key, e)

            # 4. Execute adapter with timing and OpenTelemetry span
            start_time = time.time()
            findings, diagnostic = await adapter.run(source_text, language)
            duration_ms = int((time.time() - start_time) * 1000)

            with create_span(
                f"adapter.{adapter.name}",
                {
                    "tool_name": adapter.name,
                    "duration_ms": duration_ms,
                    "finding_count": len(findings),
                },
            ):
                pass

            # 5. Store in cache (1 hour TTL)
            try:
                serialized = json.dumps({
                    "findings": [f.model_dump() for f in findings],
                    "diagnostic": diagnostic,
                })
                if len(self._memory_cache) >= self._MEMORY_CACHE_MAX:
                    self._memory_cache.popitem(last=False)
                self._memory_cache[cache_key] = serialized

                if redis_client and time.monotonic() >= AdapterRegistry._redis_down_until:
                    try:
                        await asyncio.wait_for(redis_client.set(cache_key, serialized, ex=3600), timeout=0.5)
                        AdapterRegistry._redis_down_until = 0.0
                    except Exception as redis_err:
                        AdapterRegistry._redis_down_until = time.monotonic() + AdapterRegistry._REDIS_COOLDOWN_SECONDS
                        logger.debug("Redis cache write failed: %s", redis_err)
            except Exception as e:
                logger.debug("Failed to write to cache for %s: %s", cache_key, e)

            future.set_result((findings, diagnostic))
            return findings, diagnostic
        except Exception as exc:
            if not future.done():
                future.set_exception(exc)
            try:
                future.exception()
            except Exception:
                pass
            raise
        finally:
            async with lock:
                self._inflight_tasks.pop(cache_key, None)

    async def run_all(
        self,
        source_text: str,
        language: str,
    ) -> Tuple[List[RawFinding], List[dict]]:
        """
        Run all matching adapters in parallel with asyncio.gather.
        Partial failures produce diagnostics and do not fail the overall run.
        """
        applicable = self.get_adapters_for_language(language)
        if not applicable:
            return [], []

        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()

        tasks = [
            self._run_single_with_cache(adapter, source_text, language, source_hash)
            for adapter in applicable
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_findings: List[RawFinding] = []
        diagnostics: List[dict] = []

        for i, res in enumerate(results):
            tool_name = applicable[i].name
            if isinstance(res, Exception):
                logger.error("Adapter %s raised unexpected exception: %s", tool_name, res, exc_info=True)
                diagnostics.append({"tool": tool_name, "status": "error", "error": str(res)})
            else:
                findings, diag = res
                all_findings.extend(findings)
                if diag:
                    diagnostics.append(diag)

        return all_findings, diagnostics
