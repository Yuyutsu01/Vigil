"""
Unit tests for A11: Dependency Risk Agent (FR-108).
Validates offline manifest parsing (requirements.txt, package.json) and CVE matching.
"""
from __future__ import annotations

import pytest

from app.agents.dependency_agent import (
    DependencyRiskAgent,
    DependencyRiskInput,
    DependencyRiskOutput,
    run_dependency_agent,
)


@pytest.mark.asyncio
async def test_dependency_agent_python_requirements():
    """Tests CVE detection on Python requirements.txt manifest."""
    manifest_content = (
        "requests==2.25.0\n"
        "urllib3==1.26.4\n"
        "flask==0.12.0\n"
        "secure-pkg==1.0.0\n"
    )
    inp = DependencyRiskInput(
        manifest_files={"requirements.txt": manifest_content},
        lock_files={},
    )

    agent = DependencyRiskAgent()
    output = await agent.analyze_dependencies(inp)

    assert isinstance(output, DependencyRiskOutput)
    assert output.total_dependencies_analyzed == 4
    # urllib3==1.26.4 matches CVE-2021-33503, flask==0.12.0 matches CVE-2018-1000656
    cve_ids = [c.cve_id for c in output.cves_detected]
    assert "CVE-2023-32681" in cve_ids
    assert "CVE-2023-45803" in cve_ids
    assert len(output.findings) >= 2


@pytest.mark.asyncio
async def test_dependency_agent_npm_package_json():
    """Tests CVE detection on JavaScript/Node package.json manifest."""
    package_json = """{
        "dependencies": {
            "lodash": "4.17.20",
            "express": "4.17.1"
        }
    }"""
    inp = DependencyRiskInput(
        manifest_files={"package.json": package_json},
        lock_files={},
    )

    output = await run_dependency_agent(inp)

    assert isinstance(output, DependencyRiskOutput)
    cve_ids = [c.cve_id for c in output.cves_detected]
    assert "CVE-2021-23337" in cve_ids  # lodash Command Injection
    assert len(output.findings) >= 1


@pytest.mark.asyncio
async def test_dependency_agent_clean_manifest():
    """Tests that secure manifests produce zero findings and zero detected CVEs."""
    clean_requirements = "requests==2.31.0\nurllib3==2.0.0\n"
    inp = DependencyRiskInput(
        manifest_files={"requirements.txt": clean_requirements},
        lock_files={},
    )

    output = await run_dependency_agent(inp)
    assert len(output.findings) == 0
    assert len(output.cves_detected) == 0
