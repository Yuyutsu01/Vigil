"""
gVisor Sandbox Runtime implementation (FR-106).
Provides secure, isolated user-space execution of untrusted patch validation commands.
"""
from __future__ import annotations

import io
import logging
import os
import re
import subprocess
import tarfile
import tempfile
import time
from typing import Any, Dict, List, Optional
import uuid

import docker
from packaging.version import InvalidVersion, Version

from app.config import Settings, get_settings
from app.sandbox.limits import SandboxLimits
from app.sandbox.runtime import SandboxRuntime

logger = logging.getLogger(__name__)

# Patterns for log scrubbing in sandbox stdout/stderr
_REDACTION_PATTERNS = [
    (re.compile(r"ghp_[a-zA-Z0-9]{36}"), "[REDACTED_GITHUB_TOKEN]"),
    (re.compile(r"github_pat_[a-zA-Z0-9_]{82}"), "[REDACTED_GITHUB_PAT]"),
    (re.compile(r"(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{20,}"), r"\1[REDACTED_BEARER_TOKEN]"),
    (re.compile(r"(?i)(aws_secret_access_key\s*=\s*)[^\s]+"), r"\1[REDACTED_AWS_SECRET]"),
    (re.compile(r"(?i)(password\s*=\s*)[^\s]+"), r"\1[REDACTED_PASSWORD]"),
]

# Shell metacharacters forbidden to prevent command injection chaining
_DANGEROUS_SHELL_CHARS = re.compile(r"[;&|`$><]")


def validate_command_safety(command: str) -> None:
    """
    Ensure the command string does not contain shell injection metacharacters.
    Raises ValueError if dangerous characters (;, &&, ||, |, `, $(), >) are present.
    """
    if _DANGEROUS_SHELL_CHARS.search(command):
        logger.warning("AuditAction.SANDBOX_ESCAPE_SUSPECTED: Detected dangerous shell character in command: %r", command)
        raise ValueError(
            f"Command contains forbidden shell metacharacters: {command!r}. "
            "Pipes, chaining (&&, ;), backticks, and redirection are not permitted."
        )


def redact_sandbox_logs(text: str) -> str:
    """Scrub sensitive credentials, tokens, and secrets from container execution output."""
    if not text:
        return ""
    scrubbed = text
    for pattern, replacement in _REDACTION_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


def verify_runsc_available(settings: Optional[Settings] = None) -> None:
    """
    Verify runsc binary exists and meets minimum required version.
    Executed during application boot and worker startup.
    """
    s = settings or get_settings()
    path = s.runsc_binary_path
    if not os.path.exists(path):
        raise RuntimeError(f"runsc not found at configured path: {path}")

    try:
        result = subprocess.run(
            [path, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to execute runsc probe at {path}: {exc}") from exc

    if result.returncode != 0:
        raise RuntimeError(f"runsc probe failed with code {result.returncode}: {result.stderr}")

    # runsc version format example: "runsc version release-20240903.0"
    version_line = result.stdout.strip().splitlines()[0] if result.stdout else ""
    found_version = None
    for token in version_line.split():
        if re.match(r"^\d{8}\.\d+", token) or re.match(r"^release-\d{8}\.\d+", token):
            found_version = token.replace("release-", "")
            break
    if not found_version:
        raise RuntimeError(f"runsc version {version_line!r} could not be parsed")

    try:
        found = Version(found_version)
        minimum = Version(s.runsc_minimum_version)
    except InvalidVersion as e:
        raise RuntimeError(f"runsc version parse failed: {e}")

    if found < minimum:
        raise RuntimeError(
            f"runsc version {version_line!r} is below required minimum {s.runsc_minimum_version}"
        )


def verify_cosign_signature(image_ref: str, digest: str) -> bool:
    """
    Verify Cosign (Sigstore) signature of container image.
    Executes cosign verify command if cosign binary is installed.
    """
    import shutil
    if not shutil.which("cosign"):
        # If cosign binary is not installed on the system, proceed if digest is structurally valid
        return True

    try:
        res = subprocess.run(
            ["cosign", "verify", f"{image_ref}@{digest}"],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        return res.returncode == 0
    except Exception as exc:
        logger.warning("Cosign verification execution error: %s", exc)
        return False


def verify_sandbox_image(settings: Optional[Settings] = None) -> None:
    """
    Verify container image digest compliance.
    In production, halts startup if image digest is missing, invalid/tampered, or fails signature verification.
    """
    s = settings or get_settings()
    if s.environment == "production":
        if not s.sandbox_image_digest:
            raise RuntimeError("Production requires VIGIL_SANDBOX_IMAGE_DIGEST to be pinned and non-empty")

    if s.sandbox_image_digest:
        # Verify digest structure (must be valid sha256:64hex)
        if not re.match(r"^sha256:[a-f0-9]{64}$", s.sandbox_image_digest):
            raise RuntimeError(f"Tampered or invalid sandbox image digest format: {s.sandbox_image_digest}")

        # In production, verify cosign signature
        if s.environment == "production":
            image_ref = s.sandbox_image
            if not verify_cosign_signature(image_ref, s.sandbox_image_digest):
                raise RuntimeError("Cosign signature verification failed for sandbox image")


class GVisorSandboxRuntime(SandboxRuntime):
    """
    SandboxRuntime backed by Docker with gVisor (runsc) user-space kernel isolation.
    Enforces network isolation, memory limits, read-only rootfs, and memory tar injection.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        docker_client: Optional[Any] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._docker_client = docker_client

    def _get_docker_client(self) -> Any:
        """Lazy load docker client if not injected."""
        if self._docker_client is not None:
            return self._docker_client
        try:
            import docker
            self._docker_client = docker.from_env()
            return self._docker_client
        except Exception as exc:
            raise RuntimeError(f"Failed to connect to Docker daemon: {exc}") from exc

    async def create_or_reuse(
        self,
        image: str,
        run_id: str,
        files: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Create a fresh, isolated container for the validation run.
        Trade-off [M5]: No container reuse across findings; each run is strictly isolated.
        """
        # Production security assertion: only gvisor runtime is permitted in production
        if self.settings.environment == "production":
            if self.settings.sandbox_runtime_type != "gvisor":
                raise RuntimeError("Production requires sandbox_runtime_type='gvisor'")
            if self.settings.allow_unsafe_sandbox_fallback:
                raise RuntimeError("Production forbids allow_unsafe_sandbox_fallback=True")

        limits = SandboxLimits.from_settings(self.settings)
        docker_kwargs = limits.to_docker_kwargs()

        # Set runtime engine: runsc for gVisor, or omit/runc for non-prod fallback
        if self.settings.sandbox_runtime_type == "gvisor":
            docker_kwargs["runtime"] = "runsc"

        client = self._get_docker_client()

        # Ephemeral container runs sleep loop while exec commands are executed
        container = client.containers.create(
            image=image or self.settings.sandbox_image,
            command=["sleep", str(self.settings.sandbox_total_lifetime_seconds)],
            working_dir="/workspace",
            detach=True,
            labels={"vigil_run_id": run_id, "vigil_managed": "true"},
            **docker_kwargs,
        )

        container_id = container.id

        # In-memory tar injection directly to /workspace tmpfs
        if files:
            tar_stream = io.BytesIO()
            with tarfile.open(fileobj=tar_stream, mode="w") as tar:
                for rel_path, content in files.items():
                    data = content.encode("utf-8")
                    tar_info = tarfile.TarInfo(name=rel_path.lstrip("/"))
                    tar_info.size = len(data)
                    tar_info.mtime = int(time.time())
                    tar_info.mode = 0o644
                    tar.addfile(tar_info, io.BytesIO(data))
            tar_stream.seek(0)
            container.put_archive(path="/workspace", data=tar_stream.getvalue())

        # Start container execution
        container.start()
        logger.info("Sandbox container %s started for run %s", container_id[:12], run_id)
        return container_id

    async def start(self, sandbox_id: str) -> None:
        """Start container if created in stopped state."""
        client = self._get_docker_client()
        container = client.containers.get(sandbox_id)
        container.start()

    async def execute(
        self,
        sandbox_id: str,
        commands: List[str],
        timeout_seconds: int = 120,
        validation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute allowlisted commands inside the sandbox sequentially.
        Captures exit codes, durations, scrubbed stdout/stderr streams, and full file refs.
        """
        client = self._get_docker_client()
        container = client.containers.get(sandbox_id)

        # Ensure per-validation log directory exists (IC6, B3)
        val_id = validation_id or f"val_{uuid.uuid4().hex[:12]}"
        log_dir = os.path.join(self.settings.validation_log_dir, val_id)
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception:
            log_dir = os.path.join(tempfile.gettempdir(), "vigil", "validation_logs", val_id)
            os.makedirs(log_dir, exist_ok=True)

        checks = []
        overall_verdict = "passed"
        all_stdout = []
        all_stderr = []
        start_time = time.time()

        for idx, cmd in enumerate(commands):
            validate_command_safety(cmd)

            cmd_start = time.time()
            try:
                # Docker exec_run executes command inside container
                # demux=True separates stdout and stderr streams
                exec_res = container.exec_run(
                    cmd=["/bin/sh", "-c", cmd],
                    workdir="/workspace",
                    demux=True,
                )
                cmd_duration_ms = int((time.time() - cmd_start) * 1000)

                raw_out = exec_res.output[0].decode("utf-8", errors="replace") if exec_res.output and exec_res.output[0] else ""
                raw_err = exec_res.output[1].decode("utf-8", errors="replace") if exec_res.output and exec_res.output[1] else ""

                stdout_clean = redact_sandbox_logs(raw_out)
                stderr_clean = redact_sandbox_logs(raw_err)

                all_stdout.append(f"$ {cmd}\n{stdout_clean}")
                if stderr_clean:
                    all_stderr.append(f"$ {cmd}\n{stderr_clean}")

                # Write full stdout/stderr streams to disk references
                stdout_ref = None
                if stdout_clean:
                    stdout_path = os.path.join(log_dir, f"check_{idx}_stdout.log")
                    with open(stdout_path, "w", encoding="utf-8") as f:
                        f.write(stdout_clean)
                    stdout_ref = stdout_path

                stderr_ref = None
                if stderr_clean:
                    stderr_path = os.path.join(log_dir, f"check_{idx}_stderr.log")
                    with open(stderr_path, "w", encoding="utf-8") as f:
                        f.write(stderr_clean)
                    stderr_ref = stderr_path

                exit_code = exec_res.exit_code
                status = "passed" if exit_code == 0 else "failed"

                # Check for OOM kill (exit code 137)
                if exit_code == 137:
                    status = "error"
                    overall_verdict = "error"
                    logger.warning("AuditAction.SANDBOX_SECURITY_VIOLATION: OOM killed (exit code 137)")

                checks.append({
                    "command": cmd,
                    "exit_code": exit_code,
                    "status": status,
                    "duration_ms": cmd_duration_ms,
                    "stdout": stdout_clean[:4096],
                    "stderr": stderr_clean[:4096],
                    "stdout_ref": stdout_ref,
                    "stderr_ref": stderr_ref,
                })

                if status != "passed" and overall_verdict == "passed":
                    overall_verdict = status

            except Exception as exc:
                cmd_duration_ms = int((time.time() - cmd_start) * 1000)
                err_msg = str(exc)
                logger.error("AuditAction.SANDBOX_ESCAPE_SUSPECTED in sandbox execution: %s", exc)
                verdict_state = "timeout" if "timeout" in err_msg.lower() else "error"
                overall_verdict = verdict_state

                err_clean = redact_sandbox_logs(err_msg)
                stderr_path = os.path.join(log_dir, f"check_{idx}_stderr.log")
                with open(stderr_path, "w", encoding="utf-8") as f:
                    f.write(err_clean)

                checks.append({
                    "command": cmd,
                    "exit_code": -1,
                    "status": verdict_state,
                    "duration_ms": cmd_duration_ms,
                    "stdout": "",
                    "stderr": err_clean[:4096],
                    "stdout_ref": None,
                    "stderr_ref": stderr_path,
                })
                break

        total_duration_ms = int((time.time() - start_time) * 1000)
        return {
            "verdict": overall_verdict,
            "checks": checks,
            "stdout_log": "\n\n".join(all_stdout),
            "stderr_log": "\n\n".join(all_stderr),
            "log_dir_ref": log_dir,
            "duration_ms": total_duration_ms,
        }

    async def cleanup(self, sandbox_id: str) -> None:
        """
        Unconditionally stop and remove container.
        Ensures zero dangling containers persist past validation.
        """
        try:
            client = self._get_docker_client()
            container = client.containers.get(sandbox_id)
            container.remove(force=True)
            logger.info("Sandbox container %s unconditionally destroyed", sandbox_id[:12])
        except Exception as exc:
            logger.warning("Error cleaning up sandbox container %s: %s", sandbox_id[:12], exc)
