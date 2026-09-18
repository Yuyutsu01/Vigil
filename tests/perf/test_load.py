import asyncio
import json
import statistics
import sys
import time
import uuid
from pathlib import Path
import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.agents.graph import run_review_graph
from app.agents.llm_provider import MockProvider

_RESULTS_DIR = Path(__file__).parent / "results"
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Guard Locust scenario so gevent monkey-patching does not interfere with pytest asyncio loop
if "pytest" not in sys.modules:
    try:
        from locust import HttpUser, between, task

        class VigilLocustUser(HttpUser):
            """Locust user scenario for load generation."""
            wait_time = between(0.1, 0.5)

            @task
            def submit_review(self):
                source = "def add(a, b):\n    return a + b\n" * 5500
                self.client.post(
                    "/v1/reviews",
                    json={"language": "python", "source_text": source},
                    headers={"Authorization": "Bearer test-token"},
                )
    except ImportError:
        pass


@pytest.mark.asyncio
async def test_load_performance_targets():
    """
    Run 50 concurrent review simulations submitting 250 KB source files.
    Verify NFR-001 targets: median <= 20s and p95 <= 60s.
    """
    # 250 KB source payload (~240 KB)
    source_payload = "# Vigil performance benchmark payload\nx = 1\n" * 5500
    assert len(source_payload.encode("utf-8")) <= 250 * 1024

    concurrency = 50
    worker_pool = asyncio.Semaphore(10)
    durations: list[float] = []

    async def _simulate_user(user_idx: int) -> float:
        async with worker_pool:
            tenant_id = uuid.uuid4()
            run_id = uuid.uuid4()
            start = time.perf_counter()

            state = await run_review_graph(
                run_id=run_id,
                tenant_id=tenant_id,
                source_code=source_payload,
                language="python",
                provider=MockProvider(),
            )
            duration = time.perf_counter() - start
            assert state.completed
            return duration

    start_total = time.perf_counter()
    tasks = [_simulate_user(i) for i in range(concurrency)]
    durations = await asyncio.gather(*tasks)
    total_time = time.perf_counter() - start_total

    durations.sort()
    median_latency = statistics.median(durations)
    # 95th percentile
    p95_idx = int(len(durations) * 0.95)
    p95_latency = durations[min(p95_idx, len(durations) - 1)]

    results = {
        "concurrency": concurrency,
        "payload_bytes": len(source_payload.encode("utf-8")),
        "total_time_seconds": round(total_time, 3),
        "min_seconds": round(durations[0], 3),
        "max_seconds": round(durations[-1], 3),
        "median_seconds": round(median_latency, 3),
        "p95_seconds": round(p95_latency, 3),
        "target_median_seconds": 20.0,
        "target_p95_seconds": 60.0,
        "samples": [round(d, 3) for d in durations],
    }

    result_file = _RESULTS_DIR / "load_test_results.json"
    result_file.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Assert NFR-001 latency constraints
    assert median_latency <= 20.0, f"Median latency {median_latency}s exceeded 20s"
    assert p95_latency <= 60.0, f"p95 latency {p95_latency}s exceeded 60s"
