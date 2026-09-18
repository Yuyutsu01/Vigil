"""
Unit tests for the agent policy layer.
AC-7: Budget and deadline enforcement must block LLM calls when exhausted.
"""
import asyncio
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))


class TestPolicyEnforcement:
    """AC-7: Policy layer enforces budget and deadline limits."""

    def _make_state(self):
        from app.agents.state import ReviewGraphState
        return ReviewGraphState(
            run_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            source_code="x = 1",
            language="python",
        )

    def test_policy_allows_when_within_limits(self) -> None:
        from app.agents.policy import check_policy, initialize_policy
        state = self._make_state()
        initialize_policy(state)

        allowed, reason = check_policy(state)
        assert allowed, f"Policy should allow call, got reason: {reason}"

    def test_policy_blocks_when_deadline_exceeded(self) -> None:
        from app.agents.policy import check_policy
        from app.config import RuntimeSettings
        state = self._make_state()

        # Set deadline in the past
        state.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        allowed, reason = check_policy(state)
        assert not allowed, "Policy must block when deadline exceeded"
        assert "deadline" in reason.lower()

    def test_policy_blocks_when_budget_exhausted(self) -> None:
        from app.agents.policy import check_policy
        state = self._make_state()
        state.budget_remaining = 0
        state.deadline_at = datetime.now(timezone.utc) + timedelta(hours=1)

        allowed, reason = check_policy(state, estimated_tokens=1)
        assert not allowed, "Policy must block when budget exhausted"
        assert "budget" in reason.lower() or "token" in reason.lower()

    def test_policy_blocks_when_max_iterations_reached(self) -> None:
        from app.agents.policy import check_policy
        from app.config import RuntimeSettings
        settings = RuntimeSettings()

        state = self._make_state()
        state.iterations = settings.max_agent_iterations
        state.deadline_at = datetime.now(timezone.utc) + timedelta(hours=1)
        state.budget_remaining = 50_000

        allowed, reason = check_policy(state, settings)
        assert not allowed, "Policy must block when max iterations reached"
        assert "iteration" in reason.lower()

    def test_policy_parks_state_on_block(self) -> None:
        from app.agents.policy import park_state
        state = self._make_state()

        park_state(state, "wall_clock_deadline_exceeded")
        assert state.parked_reason == "wall_clock_deadline_exceeded"

    def test_invoke_llm_blocks_when_deadline_expired(self) -> None:
        """invoke_llm_with_policy must return None when policy blocks."""
        from app.agents.policy import invoke_llm_with_policy

        state = self._make_state()
        state.deadline_at = datetime.now(timezone.utc) - timedelta(seconds=1)

        call_count = [0]

        async def mock_llm():
            call_count[0] += 1
            from app.schemas.finding import RawLLMResponse
            return RawLLMResponse(findings=[])

        result = asyncio.run(invoke_llm_with_policy(state, mock_llm))
        assert result is None, "Must return None when deadline exceeded"
        assert call_count[0] == 0, "LLM must not be called when policy blocks"

    def test_initialize_policy_sets_deadline_and_budget(self) -> None:
        from app.agents.policy import initialize_policy
        from app.config import RuntimeSettings
        settings = RuntimeSettings()
        state = self._make_state()

        before = datetime.now(timezone.utc)
        initialize_policy(state, settings)
        after = datetime.now(timezone.utc)

        assert state.budget_remaining == settings.token_budget_per_run
        assert state.deadline_at is not None
        expected_deadline = before + timedelta(seconds=settings.wall_clock_deadline_seconds)
        assert state.deadline_at > before
        assert state.deadline_at <= after + timedelta(seconds=settings.wall_clock_deadline_seconds + 1)
