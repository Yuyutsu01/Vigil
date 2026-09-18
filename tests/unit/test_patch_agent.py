"""
Unit tests for Agent A6 (Patch Agent).
Verifies unified diff generation, Critical severity gating, budget limit enforcement, and retry behavior.
"""
import pytest
from app.agents.patch_agent import PatchAgent, PatchDraft, is_valid_unified_diff
from app.agents.llm_provider import MockProvider
from app.config import get_settings


@pytest.mark.asyncio
async def test_patch_agent_successful_generation():
    """Verify PatchAgent generates valid PatchDraft with unified diff, rationale, and tests."""
    agent = PatchAgent(provider=MockProvider())
    finding = {
        "rule_id": "VIGIL-SEC-001",
        "title": "SQL Injection vulnerability",
        "severity": "High",
        "category": "security",
        "start_line": 10,
        "end_line": 12,
        "matched_text": "cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')",
        "rationale": "Direct string interpolation into SQL query",
    }
    source_code = "def get_user(user_id):\n    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n"

    draft = await agent.generate(finding, source_code, language="python", force=False)

    assert isinstance(draft, PatchDraft)
    assert is_valid_unified_diff(draft.unified_diff)
    assert "--- " in draft.unified_diff
    assert "+++ " in draft.unified_diff
    assert len(draft.rationale) > 0
    assert len(draft.tests_to_run) > 0


@pytest.mark.asyncio
async def test_critical_severity_requires_force():
    """Verify Critical findings reject patch generation unless force=True is passed."""
    agent = PatchAgent(provider=MockProvider())
    finding = {
        "rule_id": "VIGIL-SEC-001",
        "title": "Remote Code Execution",
        "severity": "Critical",
        "category": "security",
        "matched_text": "eval(user_input)",
    }
    source = "eval(user_input)"

    # Must raise ValueError when force=False
    with pytest.raises(ValueError, match="force=True"):
        await agent.generate(finding, source, language="python", force=False)

    # Must succeed when force=True
    draft = await agent.generate(finding, source, language="python", force=True)
    assert isinstance(draft, PatchDraft)


@pytest.mark.asyncio
async def test_budget_cap_enforcement():
    """Verify cost guard halts patch generation when cost or token caps are breached."""
    agent = PatchAgent(provider=MockProvider())
    finding = {"rule_id": "VIGIL-001", "severity": "Medium"}

    # Exceed cost ceiling
    exhausted_cost = {"total_cost_usd": 1.05, "total_tokens": 5000}
    with pytest.raises(RuntimeError, match="budget exhausted"):
        await agent.generate(finding, "x = 1", language="python", cost_guard=exhausted_cost)

    # Exceed token ceiling
    exhausted_tokens = {"total_cost_usd": 0.20, "total_tokens": 105_000}
    with pytest.raises(RuntimeError, match="budget exhausted"):
        await agent.generate(finding, "x = 1", language="python", cost_guard=exhausted_tokens)


def test_is_valid_unified_diff_helper():
    """Test unified diff syntax validation."""
    valid_diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1,2 +1,2 @@\n-old\n+new\n"
    assert is_valid_unified_diff(valid_diff) is True

    invalid_diff = "this is not a unified diff"
    assert is_valid_unified_diff(invalid_diff) is False
    assert is_valid_unified_diff("") is False


@pytest.mark.asyncio
async def test_prompt_too_long_rejected():
    """Verify that prompts exceeding patch_agent_max_prompt_tokens (8000) are rejected with ValueError (H4, IC7)."""
    agent = PatchAgent(provider=MockProvider())
    finding = {
        "rule_id": "VIGIL-SEC-001",
        "title": "Buffer Overflow",
        "severity": "High",
    }
    # 8000 tokens * 4 chars/token = 32000 chars; generate 40000 chars to comfortably exceed limit
    huge_source = "x = 1\n" * 7000

    with pytest.raises(ValueError, match="Patch prompt exceeds 8000 token limit"):
        await agent.generate(finding, huge_source, language="python", force=False)

