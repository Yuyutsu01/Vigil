"""
Security tests for Sandbox Isolation and Resource Constraints (FR-106).

Category A tests verify configuration. Category B tests verify
runtime behavior and require runsc. On hosts without runsc,
Category B is skipped, not failed.
"""
import os
import shutil
from unittest.mock import MagicMock
import pytest

from app.config import Settings
from app.sandbox.gvisor import GVisorSandboxRuntime, redact_sandbox_logs
from app.sandbox.limits import SandboxLimits

docker = pytest.importorskip("docker")


def _is_runsc_available() -> bool:
    if not shutil.which("runsc"):
        return False
    try:
        client = docker.from_env()
        info = client.info()
        runtimes = info.get("Runtimes", {})
        return "runsc" in runtimes
    except Exception:
        return False


RUNSC_AVAILABLE = _is_runsc_available()
skip_without_runsc = pytest.mark.skipif(
    not RUNSC_AVAILABLE,
    reason="runsc runtime not available; install gVisor to run",
)


# ── Category A: Configuration Assertions (Mocked, run everywhere) ────────────

def test_sandbox_docker_kwargs_strict_isolation():
    """Verify that Docker container parameters enforce all required security flags."""
    limits = SandboxLimits(
        cpu_cores=1.0,
        memory_limit_mb=512,
        disk_limit_mb=1024,
        command_timeout_seconds=120,
        total_lifetime_seconds=600,
        pids_limit=256,
    )
    kwargs = limits.to_docker_kwargs()

    # Network egress denial: must be 'none'
    assert kwargs["network_mode"] == "none"

    # Rootfs protection: must be read-only
    assert kwargs["read_only"] is True

    # Memory limits and swap disabling
    assert kwargs["mem_limit"] == 512 * 1024 * 1024
    assert kwargs["memswap_limit"] == 512 * 1024 * 1024

    # Process containment
    assert kwargs["pids_limit"] == 256

    # Drop all capabilities
    assert kwargs["cap_drop"] == ["ALL"]

    # Tmpfs isolation
    assert "/workspace" in kwargs["tmpfs"]
    assert "size=1024m" in kwargs["tmpfs"]["/workspace"]
    assert "/tmp" in kwargs["tmpfs"]
    assert "noexec" in kwargs["tmpfs"]["/tmp"]


def test_zero_host_credentials_passed_to_container():
    """Verify that container environment excludes host secrets, API keys, and database URLs."""
    mock_docker = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "mock_container_12345"
    mock_docker.containers.create.return_value = mock_container

    runtime = GVisorSandboxRuntime(
        settings=Settings(
            sandbox_runtime_type="gvisor",
            github_app_private_key="FAKE_RSA_PRIVATE_KEY_SECRET",
            openai_api_key="sk-fake-secret-key",
            anthropic_api_key="sk-ant-fake-secret-key",
            database_url="postgresql+asyncpg://postgres:supersecret@localhost/vigil",
        ),
        docker_client=mock_docker,
    )

    # Trigger container creation
    import asyncio
    asyncio.run(runtime.create_or_reuse(image="vigil-sandbox:phase4", run_id="test_run_1"))

    # Inspect call args to containers.create
    create_kwargs = mock_docker.containers.create.call_args.kwargs
    container_env = create_kwargs.get("environment", {})

    # Assert container environment contains zero host secrets
    env_str = str(container_env)
    assert "FAKE_RSA_PRIVATE_KEY" not in env_str
    assert "sk-fake" not in env_str
    assert "sk-ant" not in env_str
    assert "supersecret" not in env_str
    assert "GITHUB" not in env_str


def test_log_scrubbing_redacts_credentials():
    """Verify that redact_sandbox_logs redacts GitHub tokens, AWS secrets, and Bearer tokens."""
    raw_logs = (
        "Output from test suite:\n"
        "Configured token: ghp_123456789012345678901234567890123456\n"
        "Fine-grained token: github_pat_11AAAAAAA0000000000000000000000000000000000000000000000000000000000000000000000000\n"
        "Authorization: Bearer secret_jwt_token_sample_here_12345\n"
        "AWS credentials: aws_secret_access_key=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n"
        "Database password: password=SuperSecretPassword123\n"
        "Tests finished successfully."
    )

    scrubbed = redact_sandbox_logs(raw_logs)

    assert "ghp_123456789012345678901234567890123456" not in scrubbed
    assert "[REDACTED_GITHUB_TOKEN]" in scrubbed

    assert "github_pat_" not in scrubbed
    assert "[REDACTED_GITHUB_PAT]" in scrubbed

    assert "secret_jwt_token_sample_here_12345" not in scrubbed
    assert "[REDACTED_BEARER_TOKEN]" in scrubbed

    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in scrubbed
    assert "[REDACTED_AWS_SECRET]" in scrubbed

    assert "SuperSecretPassword123" not in scrubbed
    assert "[REDACTED_PASSWORD]" in scrubbed


# ── Category B: Real Container Isolation (Require runsc) ─────────────────────

@skip_without_runsc
@pytest.mark.timeout(30)
def test_egress_denial_real_container():
    """Verify egress denial in real gVisor container (network_mode='none')."""
    client = docker.from_env()
    limits = SandboxLimits()
    kwargs = limits.to_docker_kwargs()
    container = client.containers.run(
        image="python:3.11-alpine",
        command=["python", "-c", "import urllib.request; urllib.request.urlopen('http://8.8.8.8', timeout=2)"],
        detach=True,
        runtime="runsc",
        **kwargs,
    )
    try:
        res = container.wait(timeout=25)
        logs = container.logs().decode("utf-8", errors="replace")
        assert res["StatusCode"] != 0
        assert any(term in logs for term in ("Network is unreachable", "unreachable", "timed out", "NetworkError", "URLError"))
    finally:
        container.remove(force=True)


@skip_without_runsc
@pytest.mark.timeout(30)
def test_rootfs_protection_real_container():
    """Verify read-only rootfs enforcement in real gVisor container."""
    client = docker.from_env()
    limits = SandboxLimits()
    kwargs = limits.to_docker_kwargs()
    container = client.containers.run(
        image="python:3.11-alpine",
        command=["touch", "/usr/bin/test_rootfs_write"],
        detach=True,
        runtime="runsc",
        **kwargs,
    )
    try:
        res = container.wait(timeout=25)
        logs = container.logs().decode("utf-8", errors="replace")
        assert res["StatusCode"] != 0
        assert "Read-only file system" in logs or res["StatusCode"] == 1
    finally:
        container.remove(force=True)


@skip_without_runsc
@pytest.mark.timeout(30)
def test_pids_limit_enforced_real_container():
    """Verify process bomb containment (pids_limit) in real gVisor container."""
    client = docker.from_env()
    limits = SandboxLimits(pids_limit=64)
    kwargs = limits.to_docker_kwargs()
    script = "import os, time; [os.fork() for _ in range(7)]; time.sleep(1)"
    container = client.containers.run(
        image="python:3.11-alpine",
        command=["python", "-c", script],
        detach=True,
        runtime="runsc",
        **kwargs,
    )
    try:
        res = container.wait(timeout=25)
        logs = container.logs().decode("utf-8", errors="replace")
        assert res["StatusCode"] != 0 or "Resource temporarily unavailable" in logs or "BlockingIOError" in logs
    finally:
        container.remove(force=True)


@skip_without_runsc
@pytest.mark.timeout(30)
def test_memory_limit_enforced_real_container():
    """Verify memory boundary enforcement (mem_limit) in real gVisor container."""
    client = docker.from_env()
    limits = SandboxLimits(memory_limit_mb=64)
    kwargs = limits.to_docker_kwargs()
    script = "bytearray(128 * 1024 * 1024)"
    container = client.containers.run(
        image="python:3.11-alpine",
        command=["python", "-c", script],
        detach=True,
        runtime="runsc",
        **kwargs,
    )
    try:
        res = container.wait(timeout=25)
        logs = container.logs().decode("utf-8", errors="replace")
        assert res["StatusCode"] in (137, 1) or "MemoryError" in logs or "Cannot allocate memory" in logs
    finally:
        container.remove(force=True)


@skip_without_runsc
@pytest.mark.timeout(30)
def test_proc_environ_has_no_secrets_real_container():
    """Verify that container process environment does not contain host credentials."""
    client = docker.from_env()
    limits = SandboxLimits()
    kwargs = limits.to_docker_kwargs()
    container = client.containers.run(
        image="python:3.11-alpine",
        command=["cat", "/proc/self/environ"],
        detach=True,
        runtime="runsc",
        **kwargs,
    )
    try:
        res = container.wait(timeout=25)
        raw_env = container.logs().decode("utf-8", errors="replace")
        assert res["StatusCode"] == 0
        assert "GITHUB" not in raw_env
        assert "OPENAI" not in raw_env
        assert "ANTHROPIC" not in raw_env
        assert "DATABASE_URL" not in raw_env
        assert "SECRET" not in raw_env
    finally:
        container.remove(force=True)
