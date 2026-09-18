"""
Resource limit definitions and Docker parameter conversion for sandbox execution.
Enforces strict boundaries on CPU, memory, PIDs, disk, and execution timeout.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.config import Settings, get_settings


@dataclass(frozen=True)
class SandboxLimits:
    """Immutable resource boundaries for untrusted code execution."""

    cpu_cores: float = 1.0
    memory_limit_mb: int = 512
    disk_limit_mb: int = 1024
    command_timeout_seconds: int = 120
    total_lifetime_seconds: int = 600
    pids_limit: int = 256

    @classmethod
    def from_settings(cls, settings: Optional[Settings] = None) -> SandboxLimits:
        """Create resource limits populated from application settings."""
        s = settings or get_settings()
        return cls(
            cpu_cores=s.sandbox_max_cpu_cores,
            memory_limit_mb=s.sandbox_memory_limit_mb,
            disk_limit_mb=s.sandbox_disk_limit_mb,
            command_timeout_seconds=s.sandbox_command_timeout_seconds,
            total_lifetime_seconds=s.sandbox_total_lifetime_seconds,
            pids_limit=256,
        )

    def validate(self) -> None:
        """Validate that resource boundaries do not exceed safe operational maximums."""
        if not (0.1 <= self.cpu_cores <= 4.0):
            raise ValueError(f"cpu_cores must be between 0.1 and 4.0, got {self.cpu_cores}")
        if not (64 <= self.memory_limit_mb <= 2048):
            raise ValueError(f"memory_limit_mb must be between 64 and 2048, got {self.memory_limit_mb}")
        if not (64 <= self.disk_limit_mb <= 4096):
            raise ValueError(f"disk_limit_mb must be between 64 and 4096, got {self.disk_limit_mb}")
        if not (1 <= self.command_timeout_seconds <= 300):
            raise ValueError(f"command_timeout_seconds must be between 1 and 300, got {self.command_timeout_seconds}")
        if not (1 <= self.total_lifetime_seconds <= 1200):
            raise ValueError(f"total_lifetime_seconds must be between 1 and 1200, got {self.total_lifetime_seconds}")

    def to_docker_kwargs(self) -> Dict[str, Any]:
        """
        Convert resource limits into Docker container creation parameters.
        Enforces read-only rootfs, no network, drop all capabilities, and tmpfs workspace.
        """
        self.validate()
        return {
            # CPU quota: 1.0 core = 1,000,000,000 nano_cpus
            "nano_cpus": int(self.cpu_cores * 1_000_000_000),
            # Memory and swap boundaries: swap disabled by equating memswap to mem_limit
            "mem_limit": self.memory_limit_mb * 1024 * 1024,
            "memswap_limit": self.memory_limit_mb * 1024 * 1024,
            # Process table containment
            "pids_limit": self.pids_limit,
            # Strict network egress denial
            "network_mode": "none",
            # Read-only root filesystem
            "read_only": True,
            # Tmpfs mounts for workspace and tmp directory
            "tmpfs": {
                "/workspace": f"size={self.disk_limit_mb}m,exec",
                "/tmp": "size=64m,noexec",
            },
            # Drop all kernel capabilities
            "cap_drop": ["ALL"],
            # Strict file descriptor ceiling
            "ulimits": [{"name": "nofile", "soft": 1024, "hard": 1024}],
        }
