"""
Unit tests for Multi-Agent Orchestrator OpenTelemetry Observability (FR-108, M3).
Validates root span (vigil.orchestration_run) and child spans (vigil.agent.{agent_name}).
"""
from __future__ import annotations

import contextlib
from unittest.mock import patch
import uuid
import pytest

from app.agents.llm_provider import MockProvider
from app.agents.orchestrator import (
    MultiAgentOrchestrator,
    ReviewContextSnapshot,
)


@pytest.mark.asyncio
async def test_orchestrator_otel_spans_emission():
    """
    [M3] OpenTelemetry Observability:
    Root span: vigil.orchestration_run with attributes (coordination_id, review_run_id, tenant_id).
    Child spans per agent: vigil.agent.{agent_name} with attributes (agent_name, task_id, coordination_id).
    """
    emitted_spans = []

    @contextlib.contextmanager
    def mock_create_span(name: str, attributes: dict = None):
        span_data = {"name": name, "attributes": attributes or {}}
        emitted_spans.append(span_data)
        yield span_data

    run_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    snapshot = ReviewContextSnapshot(
        run_id=run_id,
        tenant_id=tenant_id,
        source_code="x = 1\n",
        language="python",
    )

    provider = MockProvider()
    orchestrator = MultiAgentOrchestrator(provider=provider)

    with patch("app.agents.orchestrator.create_span", side_effect=mock_create_span):
        result = await orchestrator.run(snapshot)

    # 1. Verify Root Span
    root_spans = [s for s in emitted_spans if s["name"] == "vigil.orchestration_run"]
    assert len(root_spans) == 1
    root = root_spans[0]
    assert root["attributes"]["review_run_id"] == str(run_id)
    assert root["attributes"]["tenant_id"] == str(tenant_id)
    assert root["attributes"]["coordination_id"] == str(result.coordination_id)

    # 2. Verify Child Spans per agent
    child_spans = [s for s in emitted_spans if s["name"].startswith("vigil.agent.")]
    child_names = [s["name"] for s in child_spans]

    assert "vigil.agent.security" in child_names
    assert "vigil.agent.quality" in child_names
    assert "vigil.agent.dependency_risk" in child_names
    assert "vigil.agent.dataflow" in child_names
    assert "vigil.agent.executive_summary" in child_names

    # Verify child span attributes
    for cs in child_spans:
        assert "agent_name" in cs["attributes"]
        assert "coordination_id" in cs["attributes"]
        assert cs["attributes"]["coordination_id"] == str(result.coordination_id)
