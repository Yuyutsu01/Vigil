"""
Outer policy wrapper for the agent loop.
Enforces budget, deadline, iteration limits, and retry-once logic.
Every LLM call MUST be routed through this module.
See Implementation Plan [B2], [B3], [A5].
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from pydantic import ValidationError

from app.agents.state import ReviewGraphState
from app.config import RuntimeSettings, get_settings
from app.schemas.finding import RawLLMResponse

logger = logging.getLogger(__name__)


def initialize_policy(state: ReviewGraphState, settings: Optional[RuntimeSettings] = None) -> None:
    """Set up deadline and budget on a new ReviewGraphState."""
    s = settings or get_settings().runtime
    state.budget_remaining = s.token_budget_per_run
    state.deadline_at = datetime.now(timezone.utc) + timedelta(
        seconds=s.wall_clock_deadline_seconds
    )
    state.iterations = 0
    state.retry_count = 0


def check_policy(
    state: ReviewGraphState,
    settings: Optional[RuntimeSettings] = None,
    estimated_tokens: int = 0,
) -> tuple[bool, str]:
    """
    Check whether a LLM call is permitted under current policy.
    Returns (allowed: bool, reason: str).
    Must be called before EVERY LLM invocation.
    """
    s = settings or get_settings().runtime

    if state.is_max_iterations_reached(s.max_agent_iterations):
        return False, f"max_iterations_reached ({s.max_agent_iterations})"

    if state.is_deadline_exceeded():
        return False, "wall_clock_deadline_exceeded"

    if state.budget_remaining - estimated_tokens <= 0:
        return False, f"token_budget_exhausted (remaining={state.budget_remaining})"

    return True, "ok"


async def invoke_llm_with_policy(
    state: ReviewGraphState,
    llm_callable: Callable,
    estimated_tokens: int = 5000,
    settings: Optional[RuntimeSettings] = None,
) -> Optional[RawLLMResponse]:
    """
    Invoke an LLM capability after verifying policy.
    Implements retry-once on schema validation failure [B3].

    Returns the parsed RawLLMResponse or None if policy blocks or both attempts fail.
    """
    s = settings or get_settings().runtime

    allowed, reason = check_policy(state, s, estimated_tokens)
    if not allowed:
        logger.warning(
            "LLM call blocked by policy: %s (run_id=%s)", reason, state.run_id
        )
        state.parked_reason = reason
        return None

    # First attempt
    state.iterations += 1
    try:
        result = await asyncio.wait_for(
            llm_callable(),
            timeout=s.per_node_timeout_seconds,
        )
        if isinstance(result, RawLLMResponse):
            # Deduct estimated token usage
            state.budget_remaining = max(0, state.budget_remaining - estimated_tokens)
            return result
        else:
            raise ValueError(f"Expected RawLLMResponse, got {type(result)}")

    except (ValidationError, ValueError) as e:
        logger.warning("LLM response validation failed (attempt 1): %s", e)
        state.retry_count += 1

        # Retry-once
        if state.retry_count <= 1:
            allowed, reason = check_policy(state, s, estimated_tokens)
            if not allowed:
                logger.warning("Retry blocked by policy: %s", reason)
                state.parked_reason = reason
                return None

            try:
                state.iterations += 1
                result = await asyncio.wait_for(
                    llm_callable(),
                    timeout=s.per_node_timeout_seconds,
                )
                if isinstance(result, RawLLMResponse):
                    state.budget_remaining = max(0, state.budget_remaining - estimated_tokens)
                    return result
            except Exception as e2:
                logger.error("LLM call failed on retry: %s", e2)

        logger.error(
            "LLM call failed after retry-once; proceeding with partial results (run_id=%s)",
            state.run_id,
        )
        return None

    except asyncio.TimeoutError:
        logger.warning(
            "LLM call timed out after %ds (run_id=%s)",
            s.per_node_timeout_seconds,
            state.run_id,
        )
        state.parked_reason = "per_node_timeout"
        return None

    except Exception as e:
        logger.error("Unexpected LLM error: %s", e, exc_info=True)
        return None


def park_state(state: ReviewGraphState, reason: str) -> None:
    """Mark state as budget_paused with a reason. Partial results are preserved."""
    state.parked_reason = reason
    logger.info("Run %s parked: %s", state.run_id, reason)
