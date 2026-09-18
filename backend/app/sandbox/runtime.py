"""
SandboxRuntime — abstract interface and runtime factory.
Provides factory resolution for gVisor runtime and fallback/noop stubs.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.config import Settings, get_settings


class SandboxRuntime(ABC):
    """Abstract sandbox runtime interface (FR-106)."""

    @abstractmethod
    async def create_or_reuse(
        self,
        image: str,
        run_id: str,
        files: Optional[Dict[str, str]] = None,
    ) -> str:
        """Create or reuse a sandbox container. Injects in-memory files if provided. Returns sandbox ID."""
        ...

    @abstractmethod
    async def start(self, sandbox_id: str) -> None:
        """Start the sandbox container."""
        ...

    @abstractmethod
    async def execute(
        self,
        sandbox_id: str,
        commands: List[str],
        timeout_seconds: int = 120,
    ) -> Dict[str, Any]:
        """Execute commands in the sandbox. Returns verdict dict."""
        ...

    @abstractmethod
    async def cleanup(self, sandbox_id: str) -> None:
        """Destroy the sandbox and clean up resources."""
        ...


class NoOpSandboxRuntime(SandboxRuntime):
    """
    No-operation sandbox implementation for Phase 1/stubs.
    Every method raises NotImplementedError with clear documentation.
    """

    _MESSAGE = (
        "Sandbox execution is disabled or unconfigured in this environment. "
        "See IMPLEMENTATION_NOTES.md."
    )

    async def create_or_reuse(
        self,
        image: str,
        run_id: str,
        files: Optional[Dict[str, str]] = None,
    ) -> str:
        raise NotImplementedError(self._MESSAGE)

    async def start(self, sandbox_id: str) -> None:
        raise NotImplementedError(self._MESSAGE)

    async def execute(
        self,
        sandbox_id: str,
        commands: List[str],
        timeout_seconds: int = 120,
    ) -> Dict[str, Any]:
        raise NotImplementedError(self._MESSAGE)

    async def cleanup(self, sandbox_id: str) -> None:
        raise NotImplementedError(self._MESSAGE)


def get_sandbox_runtime(settings: Optional[Settings] = None) -> SandboxRuntime:
    """Factory creating the appropriate SandboxRuntime based on configuration."""
    s = settings or get_settings()
    if s.sandbox_runtime_type == "noop":
        return NoOpSandboxRuntime()
    from app.sandbox.gvisor import GVisorSandboxRuntime
    return GVisorSandboxRuntime(settings=s)
