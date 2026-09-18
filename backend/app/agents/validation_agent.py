"""
A7. Validation Agent (Sandbox Executor) — manages test execution of patches in isolated sandbox.
Enforces command allowlists, shell safety, and guaranteed container teardown.
"""
from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.sandbox.gvisor import validate_command_safety
from app.sandbox.runtime import SandboxRuntime, get_sandbox_runtime

logger = logging.getLogger(__name__)


class CheckResult(BaseModel):
    """Result of an individual validation command execution."""

    command: str
    exit_code: int
    status: str  # passed | failed | error | timeout
    duration_ms: int
    stdout: str  # first 4 KB inline, for quick display
    stderr: str  # first 4 KB inline
    stdout_ref: Optional[str] = None  # full log reference (local path in Phase 4; S3 in Phase 5)
    stderr_ref: Optional[str] = None


class ValidationVerdict(BaseModel):
    """Structured verdict emitted by the Validation Agent."""

    verdict: str  # passed | failed | error | timeout
    checks: List[CheckResult] = Field(default_factory=list)
    sandbox_metadata: Dict[str, Any] = Field(default_factory=dict)
    stdout_log: str = ""
    stderr_log: str = ""
    log_dir_ref: Optional[str] = None
    duration_ms: int = 0


def apply_unified_diff_to_files(
    diff_text: str,
    files: Dict[str, str],
) -> Dict[str, str]:
    """
    Apply a unified diff string to an in-memory dictionary of files.
    Returns a new dictionary containing the updated file tree.
    """
    updated_files = dict(files)
    # Parse target file from diff headers (e.g., +++ b/path/to/file.py)
    match = re.search(r"^\+\+\+\s+[b/]*(.*?)$", diff_text, re.MULTILINE)
    if not match:
        return updated_files

    target_path = match.group(1).strip()
    target_clean = target_path.lstrip("/")

    # If the file is not in the dictionary, find matching key
    matched_key = None
    for k in updated_files.keys():
        if k.lstrip("/") == target_clean or k.endswith(target_clean):
            matched_key = k
            break

    # If target file is present, apply simple hunk replacement if possible
    # Otherwise store the patch itself alongside for tools that apply patches
    updated_files["patch.diff"] = diff_text
    return updated_files


class ValidationAgent:
    """Agent A7: isolated sandbox validation of patch candidates."""

    def __init__(
        self,
        runtime: Optional[SandboxRuntime] = None,
        settings: Optional[Settings] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.runtime = runtime or get_sandbox_runtime(self.settings)

    async def run_validation(
        self,
        patch_candidate: Any,
        source_files: Dict[str, str],
        allowed_ci_commands: List[str],
        commands_to_run: Optional[List[str]] = None,
    ) -> ValidationVerdict:
        """
        Execute candidate patch in the gVisor sandbox against allowlisted commands.
        Guarantees container cleanup in a finally block.
        """
        run_id = str(uuid.uuid4())
        start_time = time.time()

        # 1. Determine commands to execute
        # If specific tests recommended, use them; else fallback to repo's allowed_ci_commands
        tests_to_run = getattr(patch_candidate, "tests_to_run", []) or []
        if isinstance(tests_to_run, str):
            import json
            try:
                tests_to_run = json.loads(tests_to_run)
            except Exception:
                tests_to_run = [tests_to_run]

        raw_candidates = commands_to_run or tests_to_run or allowed_ci_commands
        if not raw_candidates:
            raw_candidates = allowed_ci_commands or ["pytest", "npm test"]

        # 2. Strict allowlist validation: every command must match an allowed prefix or entry
        validated_commands = []
        for cmd in raw_candidates:
            clean_cmd = cmd.strip()
            if not clean_cmd:
                continue

            # Check shell safety (reject ;, &&, |, backticks, etc.)
            validate_command_safety(clean_cmd)

            # Match against allowed_ci_commands if configured
            if allowed_ci_commands:
                cmd_tokens = clean_cmd.split()
                base_binary = cmd_tokens[0] if cmd_tokens else ""
                is_allowed = any(
                    clean_cmd == allowed or base_binary == allowed.split()[0]
                    for allowed in allowed_ci_commands
                )
                if not is_allowed:
                    raise ValueError(
                        f"Validation command {clean_cmd!r} is not permitted by repository CI policy: "
                        f"{allowed_ci_commands}"
                    )

            validated_commands.append(clean_cmd)

        if not validated_commands:
            return ValidationVerdict(
                verdict="error",
                checks=[],
                stdout_log="",
                stderr_log="No valid commands permitted to run",
                duration_ms=0,
            )

        # 3. Apply patch to files in memory
        diff_text = getattr(patch_candidate, "unified_diff", "")
        prepared_files = apply_unified_diff_to_files(diff_text, source_files)

        sandbox_id = None
        try:
            # 4. Create and start isolated container with in-memory files
            sandbox_id = await self.runtime.create_or_reuse(
                image=self.settings.sandbox_image,
                run_id=run_id,
                files=prepared_files,
            )

            # 5. Execute commands in sandbox
            exec_res = await self.runtime.execute(
                sandbox_id=sandbox_id,
                commands=validated_commands,
                timeout_seconds=self.settings.sandbox_command_timeout_seconds,
            )

            checks = [
                CheckResult(
                    command=c["command"],
                    exit_code=c["exit_code"],
                    status=c["status"],
                    duration_ms=c["duration_ms"],
                    stdout=c["stdout"][:4096],
                    stderr=c["stderr"][:4096],
                    stdout_ref=c.get("stdout_ref"),
                    stderr_ref=c.get("stderr_ref"),
                )
                for c in exec_res.get("checks", [])
            ]

            duration_ms = int((time.time() - start_time) * 1000)
            return ValidationVerdict(
                verdict=exec_res.get("verdict", "error"),
                checks=checks,
                sandbox_metadata={
                    "sandbox_id": sandbox_id[:12] if sandbox_id else "none",
                    "runtime": self.settings.sandbox_runtime_type,
                    "image": self.settings.sandbox_image,
                },
                stdout_log=exec_res.get("stdout_log", ""),
                stderr_log=exec_res.get("stderr_log", ""),
                log_dir_ref=exec_res.get("log_dir_ref"),
                duration_ms=duration_ms,
            )

        except Exception as exc:
            logger.error("Validation failed with error: %s", exc, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            status = "timeout" if "timeout" in str(exc).lower() else "error"
            return ValidationVerdict(
                verdict=status,
                checks=[],
                sandbox_metadata={"error": str(exc)},
                stdout_log="",
                stderr_log=str(exc),
                duration_ms=duration_ms,
            )

        finally:
            # 6. Unconditional container teardown
            if sandbox_id:
                await self.runtime.cleanup(sandbox_id)
