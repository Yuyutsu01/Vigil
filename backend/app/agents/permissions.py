"""
Agent Permission Envelopes & Runtime Assertion (FR-108, D5).
Guarantees static least-privilege boundaries and forbids runtime privilege escalation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


class PermissionDeniedError(Exception):
    """Raised when an agent attempts an action outside its declared permission envelope."""
    pass


@dataclass(frozen=True)
class AgentPermissions:
    """
    Immutable permission envelope declared statically per agent.
    Runtime escalation is strictly forbidden.
    """
    allow_llm: bool = False
    allow_network: bool = False
    allow_fs_read: bool = False
    allow_fs_write: bool = False
    allow_github: bool = False
    allow_sandbox: bool = False


# Static registry of permission boundaries for all Phase 5 agents
SPECIALIST_PERMISSIONS: Dict[str, AgentPermissions] = {
    # A3: Security Reasoning Agent
    "security": AgentPermissions(allow_llm=True),
    # A4: Quality Review Agent
    "quality": AgentPermissions(allow_llm=True),
    # A6: Patch Generation Agent
    "patch": AgentPermissions(allow_llm=True),
    # A7: Validation Agent (isolated sandbox execution)
    "validation": AgentPermissions(allow_sandbox=True),
    # A9: PR Review Agent
    "pr_review": AgentPermissions(allow_llm=True, allow_github=True),
    # A10: Risk Scoring Agent (LLM-only advisory scoring, no IO)
    "risk_scoring": AgentPermissions(allow_llm=True),
    # A11: Dependency Risk Agent (offline manifest parsing & advisory cache, zero network)
    "dependency_risk": AgentPermissions(allow_llm=True, allow_network=False),
    # A12: Dataflow Investigation Agent (AST/CFG taint analysis, LLM validation, zero network)
    "dataflow": AgentPermissions(allow_llm=True),
    # A13: Test Generation Agent (test synthesis, delegated sandbox execution)
    "test_generation": AgentPermissions(allow_llm=True, allow_sandbox=True),
    # A14: Executive Summary Agent (LLM synthesis only)
    "executive_summary": AgentPermissions(allow_llm=True),
}


def assert_permission(agent_name: str, required_permission: str) -> None:
    """
    Assert that agent has declared the required permission.
    Raises PermissionDeniedError if permission is not granted in the static envelope.
    """
    envelope = SPECIALIST_PERMISSIONS.get(agent_name)
    if not envelope:
        raise PermissionDeniedError(f"Agent {agent_name!r} has no registered permission envelope.")

    if not getattr(envelope, required_permission, False):
        raise PermissionDeniedError(
            f"Permission denied: Agent {agent_name!r} does not have '{required_permission}' permission. "
            f"Envelope: {envelope}"
        )
