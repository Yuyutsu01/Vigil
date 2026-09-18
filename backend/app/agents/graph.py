"""
LangGraph StateGraph orchestration.
Nodes are capability functions. The outer policy.py wrapper governs LLM calls.
See Implementation Plan [F5], Design Principles §2.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.agents.capabilities import (
    capability_llm_quality,
    capability_llm_security,
    capability_parse,
    capability_run_rules,
    capability_triage,
)
from app.agents.llm_provider import ModelProvider, MockProvider, get_provider
from app.agents.policy import initialize_policy
from app.agents.state import ReviewGraphState
from app.config import get_settings
from app.sandbox.runtime import NoOpSandboxRuntime, SandboxRuntime

logger = logging.getLogger(__name__)

# NoOpSandboxRuntime is injected but NEVER invoked in Phase 1 (FR-106 deferred to M4)
_sandbox: SandboxRuntime = NoOpSandboxRuntime()


async def run_review_graph(
    run_id: uuid.UUID,
    tenant_id: uuid.UUID,
    source_code: str,
    language: str,
    provider: Optional[ModelProvider] = None,
) -> ReviewGraphState:
    """
    Execute the full review LangGraph for a single submission.

    Sequence of capability nodes (LangGraph think→act→observe per iteration):
      1. parse_capability       — syntax validation
      2. rules_capability       — deterministic baseline rules
      3. llm_security_capability — bounded AI security reasoning (policy-guarded)
      4. llm_quality_capability  — bounded AI quality reasoning (policy-guarded)
      5. triage_capability       — deterministic deduplication and ranking (NO LLM)

    The outer policy layer (policy.py) enforces budget/deadline/retry-once before
    every LLM call. The sandbox (NoOpSandboxRuntime) is injected but not invoked.
    """
    settings = get_settings()

    if provider is None:
        provider = get_provider(
            settings.llm_provider,
            model_name=settings.llm_model_name,
            api_key=settings.openai_api_key or settings.anthropic_api_key,
        )

    # Initialize state
    state = ReviewGraphState(
        run_id=run_id,
        tenant_id=tenant_id,
        source_code=source_code,
        language=language,
        started_at=datetime.now(timezone.utc),
    )
    initialize_policy(state)

    try:
        # ── Node 1: Parse ──────────────────────────────────────────────────
        state = await capability_parse(state)
        state.iterations += 1

        # ── Node 2: Rules ──────────────────────────────────────────────────
        state = await capability_run_rules(state)
        state.iterations += 1

        # ── Node 3: LLM Security (policy-guarded) ─────────────────────────
        state = await capability_llm_security(state, provider)
        state.iterations += 1

        # ── Node 4: LLM Quality (policy-guarded) ──────────────────────────
        # Only if budget/deadline still permits
        if not state.is_deadline_exceeded() and not state.is_budget_exhausted():
            state = await capability_llm_quality(state, provider)
            state.iterations += 1

        # ── Node 5: Triage (deterministic — NO LLM) ───────────────────────
        state = await capability_triage(state)
        state.iterations += 1

        state.completed = True

    except Exception as e:
        logger.error(
            "Review graph failed: run_id=%s error=%s",
            run_id,
            e,
            exc_info=True,
        )
        state.has_error = True
        state.error_message = str(e)

    return state
