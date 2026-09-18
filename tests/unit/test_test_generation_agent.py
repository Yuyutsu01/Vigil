"""
Unit tests for A13: Test Generation Agent (FR-108, AC-108.6).
Validates test command and code generation, framework hints, and shell safety rejection.
"""
from __future__ import annotations

import pytest

from app.agents.llm_provider import MockProvider
from app.agents.test_generation_agent import (
    TestGenerationAgent,
    TestGenerationInput,
    TestGenerationOutput,
    run_test_generation_agent,
    validate_test_command_safety,
)


@pytest.mark.asyncio
async def test_test_generation_contract_python():
    """Validates test code and command generation for a Python patch diff."""
    diff = (
        "--- a/app/calc.py\n"
        "+++ b/app/calc.py\n"
        "@@ -1,3 +1,3 @@\n"
        "-def add(a, b): return a - b\n"
        "+def add(a, b): return a + b\n"
    )
    inp = TestGenerationInput(
        patch_diff=diff,
        target_file_path="app/calc.py",
        framework_hints=["pytest"],
    )

    provider = MockProvider()
    agent = TestGenerationAgent(provider=provider)
    output = await agent.generate_tests(inp)

    assert isinstance(output, TestGenerationOutput)
    assert output.target_framework == "pytest"
    assert len(output.test_commands) >= 1
    assert "pytest" in output.test_commands[0]
    assert output.generated_test_code is not None


@pytest.mark.asyncio
async def test_test_generation_contract_javascript():
    """Validates framework detection and command selection for JS files."""
    diff = "--- a/index.js\n+++ b/index.js\n"
    inp = TestGenerationInput(
        patch_diff=diff,
        target_file_path="src/index.js",
        framework_hints=["jest"],
    )

    output = await run_test_generation_agent(inp)
    assert output.target_framework == "jest"
    assert any("npm test" in cmd or "jest" in cmd for cmd in output.test_commands)


def test_command_safety_rejection():
    """
    [AC-108.6] Test Generation Agent rejecting a command with forbidden characters
    (pytest; rm -rf /) raises ValueError before sandbox execution is invoked.
    """
    dangerous_commands = [
        "pytest; rm -rf /",
        "pytest && curl https://malicious.com",
        "pytest | cat /etc/passwd",
        "pytest `whoami`",
        "pytest $(cat secrets.txt)",
        "pytest > /dev/null",
        "pytest < /etc/shadow",
    ]

    for cmd in dangerous_commands:
        with pytest.raises(ValueError, match="forbidden shell metacharacters"):
            validate_test_command_safety(cmd)

    # Clean command should pass without error
    validate_test_command_safety("pytest tests/test_calc.py -v")
    validate_test_command_safety("npm test -- --coverage")
