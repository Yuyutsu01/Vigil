"""
Security test for Offline Dependency Risk Agent Zero-Egress Invariant (FR-108, Air-Gapped Operation).

Concept:
The Dependency Risk Agent (A11) performs vulnerability identification purely offline.
It must never make network calls to PyPI, npm, OSV, or external APIs.
This test asserts:
1. Manifest parsing and advisory lookup succeed in an air-gapped environment.
2. Any socket connection or HTTP request is blocked and raises an exception.
3. The agent succeeds with zero network egress.
"""
from __future__ import annotations

import socket
import pytest

from app.agents.dependency_agent import (
    DependencyRiskInput,
    run_dependency_agent,
)
from app.agents.permissions import assert_permission


def test_dependency_agent_permission_envelope_forbids_network():
    """Verify static permission envelope declares allow_network=False."""
    with pytest.raises(Exception):
        assert_permission("dependency_risk", "allow_network")


@pytest.mark.asyncio
async def test_dependency_agent_executes_with_zero_network_calls(monkeypatch):
    """
    Block all outbound socket connections and verify run_dependency_agent completes successfully
    without attempting any network I/O.
    """
    def _blocked_connect(*args, **kwargs):
        raise RuntimeError("Security violation: DependencyRiskAgent attempted network connection!")

    monkeypatch.setattr(socket.socket, "connect", _blocked_connect)

    manifest_files = {
        "requirements.txt": (
            "requests==2.25.0\n"
            "cryptography==3.3.1\n"
            "django==3.1.0\n"
            "safe-package==1.0.0\n"
        ),
        "package.json": (
            '{\n'
            '  "dependencies": {\n'
            '    "lodash": "4.17.20",\n'
            '    "express": "4.16.0"\n'
            '  }\n'
            '}\n'
        ),
    }

    dep_input = DependencyRiskInput(
        manifest_files=manifest_files,
        lock_files={},
    )

    # Execute dependency agent under blocked network socket
    output = await run_dependency_agent(dep_input)

    # Output findings must be populated from offline advisories
    assert len(output.cves_detected) >= 2
    vuln_names = {c.package_name for c in output.cves_detected}
    assert "requests" in vuln_names
    assert "lodash" in vuln_names
    assert output.total_dependencies_analyzed >= 2
