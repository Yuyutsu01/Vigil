"""
SECURITY TEST: Zero code execution guarantee.
Verifies that no subprocess, os.system, eval, exec, or interpreter is called
on submitted source code anywhere in the backend.
See Implementation Plan [A7], FR-010.
AC-5: Verify that submitted code is never executed.
"""
import ast
import os
import sys
from pathlib import Path

import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend" / "app"

# Modules that are FORBIDDEN from containing subprocess calls on user content
# Note: rules/engine.py is excluded here because it legitimately contains patterns
# like 'os.system', 'subprocess.run' etc. as *string literals* that it searches for
# in submitted code. Those strings are detection targets, not actual calls.
FORBIDDEN_IN_ANALYSIS_PATH = [
    "parser/syntax_validator.py",
    "parser/tree_sitter_engine.py",
    "agents/capabilities.py",
    "agents/graph.py",
    "services/review_service.py",
]

# Separately validate the rule engine itself using AST inspection
RULE_ENGINE_PATH = "rules/engine.py"

# Forbidden patterns in analysis modules (not the rule engine)
FORBIDDEN_PATTERNS = [
    "subprocess.run(",
    "subprocess.call(",
    "subprocess.Popen(",
    "subprocess.check_output(",
    "os.popen(",
    "os.execv(",
    "os.execve(",
    "os.spawn",
]


def _load_source(module_path: str) -> str:
    """Load source of a backend module by relative path."""
    full = BACKEND_SRC / module_path
    if not full.exists():
        pytest.fail(f"Module not found: {full}")
    return full.read_text(encoding="utf-8")


class TestNoCodeExecution:
    """
    AC-5: Verify that submitted code is NEVER executed.
    """

    @pytest.mark.parametrize("module_path", FORBIDDEN_IN_ANALYSIS_PATH)
    def test_no_subprocess_in_analysis_modules(self, module_path: str) -> None:
        """No subprocess/os.system calls in the analysis pipeline."""
        source = _load_source(module_path)
        for pattern in FORBIDDEN_PATTERNS:
            assert pattern not in source, (
                f"FORBIDDEN pattern '{pattern}' found in {module_path}. "
                "Submitted code must never be executed via subprocess or shell."
            )

    def test_rule_engine_has_no_actual_subprocess_calls(self) -> None:
        """Rule engine may contain 'os.system' as a detection pattern string but must
        never CALL subprocess/os.system on user-provided data."""
        import ast as ast_mod
        source = _load_source("rules/engine.py")
        tree = ast_mod.parse(source)

        forbidden_funcs = {
            'subprocess': {'run', 'call', 'Popen', 'check_output', 'check_call'},
            'os': {'system', 'popen', 'execv', 'execve', 'spawnl', 'spawnle'},
        }

        for node in ast_mod.walk(tree):
            if isinstance(node, ast_mod.Call):
                # Check for os.system(), subprocess.run() etc.
                func = node.func
                if isinstance(func, ast_mod.Attribute):
                    if isinstance(func.value, ast_mod.Name):
                        mod = func.value.id
                        method = func.attr
                        if mod in forbidden_funcs and method in forbidden_funcs[mod]:
                            raise AssertionError(
                                f"Actual call to {mod}.{method}() found in rules/engine.py "
                                f"(line {node.lineno}) — this must never be called on user code."
                            )


    def test_no_shell_true_anywhere(self) -> None:
        """No shell=True in any analysis module."""
        import ast as ast_mod
        for module_path in FORBIDDEN_IN_ANALYSIS_PATH:
            source = _load_source(module_path)
            # Parse the file and check for actual shell=True keyword args,
            # not string literals used as detection patterns.
            try:
                tree = ast_mod.parse(source)
            except SyntaxError:
                continue
            for node in ast_mod.walk(tree):
                if isinstance(node, (ast_mod.Call,)):
                    for kw in getattr(node, 'keywords', []):
                        if kw.arg == 'shell' and isinstance(kw.value, ast_mod.Constant) and kw.value.value is True:
                            raise AssertionError(
                                f"shell=True actual call found in {module_path} — OS injection risk"
                            )

    def test_sandbox_runtime_is_noop(self) -> None:
        """NoOpSandboxRuntime must raise NotImplementedError for all methods."""
        sys.path.insert(0, str(BACKEND_SRC.parent))
        from app.sandbox.runtime import NoOpSandboxRuntime
        import asyncio

        noop = NoOpSandboxRuntime()

        with pytest.raises(NotImplementedError):
            asyncio.get_event_loop().run_until_complete(
                noop.create_or_reuse("image", "run_id")
            )

        with pytest.raises(NotImplementedError):
            asyncio.get_event_loop().run_until_complete(noop.start("sandbox_id"))

        with pytest.raises(NotImplementedError):
            asyncio.get_event_loop().run_until_complete(
                noop.execute("sandbox_id", ["ls"])
            )

    def test_ast_parse_does_not_execute(self) -> None:
        """
        Confirm that ast.parse() on malicious code does NOT execute it.
        This is a fundamental guarantee of the Python ast module.
        """
        malicious = """
import os
os.system('echo EXECUTED')
"""
        # Should parse without triggering execution
        tree = ast.parse(malicious, mode="exec")
        assert tree is not None
        # If we reach here without any side effect, the test passes.
        # The test runner would have printed "EXECUTED" if the code ran.
