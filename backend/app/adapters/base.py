"""
Abstract base class and execution sandbox for static analyzer adapters (FR-101).
Enforces zero code execution of submitted code, read-only scratch isolation,
explicit argument lists, shell=False, timeouts, output caps, and secret redaction.
"""
from __future__ import annotations

import abc
import asyncio
import logging
import os
import shutil
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from app.schemas.finding import RawFinding
from app.services.redaction_service import redact

logger = logging.getLogger(__name__)


class ToolAdapter(abc.ABC):
    """
    Base contract for all static analysis tool adapters.
    Adapters run tools strictly in analysis mode (parsing / scanning),
    never executing submitted code as an executable program.
    """
    name: str = "base_tool"
    version: str = "1.0.0"
    languages: List[str] = []
    timeout_seconds: int = 30
    max_output_bytes: int = 1_048_576  # 1 MB

    @abc.abstractmethod
    def build_command(self, target_path: Path) -> List[str]:
        """
        Build an explicit list of command-line arguments.
        NEVER returns a string. NEVER uses shell=True.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def parse_output(self, stdout: str, stderr: str, return_code: int) -> List[RawFinding]:
        """
        Parse tool's native JSON output into uniform RawFinding instances.

        NOTE: RawFinding.raw_evidence MUST contain ONLY the matched tool output fragment
        (e.g. specific tool issue dictionary or matched snippet), NEVER the whole source file.
        Raw evidence is bounded and must not exceed 8 KB per finding.
        """
        raise NotImplementedError

    def is_available(self) -> bool:
        """Check whether the underlying binary is installed and discoverable on PATH."""
        binary = self.build_command(Path("dummy"))[0]
        return shutil.which(binary) is not None

    async def run(self, source_text: str, language: str) -> Tuple[List[RawFinding], Optional[dict]]:
        """
        Execute adapter on source_text safely inside an isolated read-only scratch directory.
        Returns (findings, diagnostic_if_any).
        """
        if not self.is_available():
            diagnostic = {
                "tool": self.name,
                "status": "skipped",
                "reason": f"Binary for {self.name} is not installed or not in PATH",
            }
            logger.info("Adapter %s skipped: binary unavailable", self.name)
            return [], diagnostic

        # 1. Create isolated scratch directory with UUID filename
        scratch_dir = tempfile.mkdtemp(prefix=f"vigil_tool_{self.name}_")
        ext = ".py" if language == "python" else (".ts" if language == "typescript" else ".js")
        file_name = f"{uuid.uuid4()}{ext}"
        target_path = Path(scratch_dir) / file_name

        try:
            # Write source code
            target_path.write_text(source_text, encoding="utf-8")

            # Mark target file read-only to guarantee submitted code is never mutated
            try:
                os.chmod(target_path, stat.S_IREAD | stat.S_IRGRP | stat.S_IROTH)
            except Exception as e:
                logger.debug("Could not set read-only permission on %s: %s", target_path, e)

            # 2. Build explicit argument list
            cmd = self.build_command(target_path)
            if not isinstance(cmd, list):
                raise TypeError(f"Command must be a list of strings, got {type(cmd)}")

            logger.debug("Running adapter %s with command: %s (shell=False)", self.name, cmd)

            # 3. Execute in subprocess with shell=False and strict timeout
            # Dedicated worker thread pool execution
            def _execute_proc():
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=False,  # CRITICAL SECURITY REQUIREMENT: Never shell=True
                    cwd=scratch_dir,
                )
                try:
                    raw_stdout, raw_stderr = proc.communicate(timeout=self.timeout_seconds)
                    return raw_stdout, raw_stderr, proc.returncode
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()
                    raise

            try:
                raw_out, raw_err, return_code = await asyncio.to_thread(_execute_proc)
            except subprocess.TimeoutExpired:
                diagnostic = {
                    "tool": self.name,
                    "status": "timeout",
                    "reason": f"Execution exceeded {self.timeout_seconds}s timeout",
                }
                logger.warning("Adapter %s timed out after %ds", self.name, self.timeout_seconds)
                return [], diagnostic

            # 4. Cap output size to 1 MB
            capped_out = raw_out[:self.max_output_bytes]
            capped_err = raw_err[:self.max_output_bytes]

            out_text = capped_out.decode("utf-8", errors="replace")
            err_text = capped_err.decode("utf-8", errors="replace")

            # 5. Redact any secrets in stdout/stderr before parsing or storage
            redacted_out = redact(out_text)
            redacted_err = redact(err_text)

            # 6. Parse normalized findings
            findings = self.parse_output(redacted_out, redacted_err, return_code)
            # Ensure tool_name and tool_version are populated
            for f in findings:
                f.tool_name = self.name
                f.tool_version = self.version

            return findings, None

        except FileNotFoundError:
            diagnostic = {
                "tool": self.name,
                "status": "skipped",
                "reason": f"Binary for {self.name} could not be executed",
            }
            return [], diagnostic
        except Exception as e:
            logger.error("Adapter %s failed with unexpected exception: %s", self.name, e, exc_info=True)
            diagnostic = {
                "tool": self.name,
                "status": "failed",
                "reason": str(e),
            }
            return [], diagnostic
        finally:
            # Clean up scratch directory and restore write permission if needed for deletion
            try:
                if target_path.exists():
                    os.chmod(target_path, stat.S_IWRITE | stat.S_IREAD)
                shutil.rmtree(scratch_dir, ignore_errors=True)
            except Exception:
                pass
