"""
SandboxRuntime — abstract interface and NoOp implementation.

Phase 1: The SandboxRuntime is INJECTED as a dependency but NEVER INVOKED.
All methods raise NotImplementedError with a clear message.

Sandbox execution (FR-106) is deferred to Phase 4 / M4.
See Implementation Plan [H4] and IMPLEMENTATION_NOTES.md.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class SandboxRuntime(ABC):
    """Abstract sandbox runtime interface (Phase 4 / M4)."""

    @abstractmethod
    async def create_or_reuse(self, image: str, run_id: str) -> str:
        """Create or reuse a sandbox container. Returns sandbox ID."""
        ...

    @abstractmethod
    async def start(self, sandbox_id: str) -> None:
        """Start the sandbox."""
        ...

    @abstractmethod
    async def execute(
        self,
        sandbox_id: str,
        commands: List[str],
        timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        """Execute commands in the sandbox. Returns verdict dict."""
        ...

    @abstractmethod
    async def cleanup(self, sandbox_id: str) -> None:
        """Destroy the sandbox and clean up resources."""
        ...


class NoOpSandboxRuntime(SandboxRuntime):
    """
    No-operation sandbox implementation for Phase 1.
    Every method raises NotImplementedError.
    This instance is injected into the orchestrator but never called in Phase 1.
    """

    _MESSAGE = (
        "Sandbox execution is deferred to Phase 4 / M4 (FR-106). "
        "The SandboxRuntime interface is defined but never invoked in Phase 1. "
        "See IMPLEMENTATION_NOTES.md."
    )

    async def create_or_reuse(self, image: str, run_id: str) -> str:
        raise NotImplementedError(self._MESSAGE)

    async def start(self, sandbox_id: str) -> None:
        raise NotImplementedError(self._MESSAGE)

    async def execute(
        self,
        sandbox_id: str,
        commands: List[str],
        timeout_seconds: int = 60,
    ) -> Dict[str, Any]:
        raise NotImplementedError(self._MESSAGE)

    async def cleanup(self, sandbox_id: str) -> None:
        raise NotImplementedError(self._MESSAGE)
