"""
A11: Dependency Risk Agent (FR-108, D1, D5).
Analyzes dependency manifests (requirements.txt, package.json) against offline CVE advisories.
Strictly offline — zero network egress.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.agents.permissions import assert_permission
from app.models.finding import Severity

logger = logging.getLogger(__name__)

# Curated offline advisory database (OSV / PyPI / npm advisory cache)
OFFLINE_CVE_ADVISORIES: List[Dict[str, Any]] = [
    {
        "package_name": "requests",
        "cve_id": "CVE-2023-32681",
        "vulnerable_pattern": r"^(0\.|1\.|2\.[0-9]\.|2\.[0-2][0-9]\.|2\.30\.)",
        "vulnerable_versions": "< 2.31.0",
        "fixed_version": "2.31.0",
        "severity": Severity.medium,
        "title": "Unintended leak of Proxy-Authorization header in requests",
        "rationale": "Requests vulnerable to information disclosure when following redirects with proxies.",
    },
    {
        "package_name": "urllib3",
        "cve_id": "CVE-2023-45803",
        "vulnerable_pattern": r"^(0\.|1\.[0-9]\.|1\.[0-1][0-9]\.|1\.2[0-5]\.|1\.26\.[0-9]\b|1\.26\.1[0-7]\b)",
        "vulnerable_versions": "< 1.26.18",
        "fixed_version": "1.26.18",
        "severity": Severity.high,
        "title": "urllib3 HTTP request body not stripped after redirect",
        "rationale": "Body data may leak to cross-origin server upon 303 redirect.",
    },
    {
        "package_name": "jinja2",
        "cve_id": "CVE-2024-22195",
        "vulnerable_pattern": r"^(0\.|1\.|2\.|3\.0\.|3\.1\.[0-2]\b)",
        "vulnerable_versions": "< 3.1.3",
        "fixed_version": "3.1.3",
        "severity": Severity.medium,
        "title": "HTML attribute injection in xmlattr filter",
        "rationale": "Keys containing spaces or control characters in xmlattr dict allow attribute injection.",
    },
    {
        "package_name": "lodash",
        "cve_id": "CVE-2021-23337",
        "vulnerable_pattern": r"^(0\.|1\.|2\.|3\.|4\.[0-9]\.|4\.[0-1][0-6]\.|4\.17\.[0-9]\b|4\.17\.1[0-9]\b|4\.17\.20\b)",
        "vulnerable_versions": "< 4.17.21",
        "fixed_version": "4.17.21",
        "severity": Severity.high,
        "title": "Command Injection in lodash template",
        "rationale": "Unsanitized template compilation allows arbitrary code execution.",
    },
    {
        "package_name": "axios",
        "cve_id": "CVE-2021-3749",
        "vulnerable_pattern": r"^(0\.[0-9]\.|0\.[0-1][0-9]\.|0\.2[0-1]\.[0-1]\b)",
        "vulnerable_versions": "< 0.21.2",
        "fixed_version": "0.21.2",
        "severity": Severity.medium,
        "title": "Regular Expression Denial of Service in axios trim",
        "rationale": "ReDoS vulnerability when parsing whitespace in authorization headers.",
    },
]


class CVEItem(BaseModel):
    cve_id: str
    package_name: str
    vulnerable_versions: str
    fixed_version: Optional[str] = None
    severity: str


class DependencyRiskInput(BaseModel):
    manifest_files: Dict[str, str] = Field(default_factory=dict)  # filename -> raw text
    lock_files: Dict[str, str] = Field(default_factory=dict)


class DependencyRiskOutput(BaseModel):
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    cves_detected: List[CVEItem] = Field(default_factory=list)
    total_dependencies_analyzed: int = 0


class DependencyAgent:
    """
    A11 Specialist Agent inspecting project manifests for supply-chain & dependency vulnerabilities.
    Operates strictly offline without external network egress.
    """

    def __init__(self, advisory_database: Optional[List[Dict[str, Any]]] = None):
        self.advisory_db = advisory_database or OFFLINE_CVE_ADVISORIES

    def _parse_requirements_txt(self, content: str) -> List[tuple[str, str]]:
        """Parse requirements.txt into (pkg_name, version) pairs."""
        pkgs = []
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Match pkg==1.2.3 or pkg>=1.2.3, etc.
            m = re.match(r"^([A-Za-z0-9_\-\.]+)\s*([=<>~!]+)\s*([A-Za-z0-9_\-\.]+)", line)
            if m:
                pkgs.append((m.group(1).lower(), m.group(3)))
        return pkgs

    def _parse_package_json(self, content: str) -> List[tuple[str, str]]:
        """Parse package.json dependencies into (pkg_name, version) pairs."""
        pkgs = []
        try:
            data = json.loads(content)
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            for name, ver in deps.items():
                clean_ver = re.sub(r"^[\^~>=<]+", "", ver)
                pkgs.append((name.lower(), clean_ver))
        except Exception:
            pass
        return pkgs

    async def analyze_dependencies(self, input_data: DependencyRiskInput) -> DependencyRiskOutput:
        # Enforce static permission envelope (D5): LLM allowed, network forbidden
        assert_permission("dependency_risk", "allow_llm")

        extracted_packages: List[tuple[str, str, str]] = []  # (pkg, ver, filename)

        for filename, content in input_data.manifest_files.items():
            if "requirements" in filename or filename.endswith(".txt"):
                for pkg, ver in self._parse_requirements_txt(content):
                    extracted_packages.append((pkg, ver, filename))
            elif filename.endswith("package.json"):
                for pkg, ver in self._parse_package_json(content):
                    extracted_packages.append((pkg, ver, filename))

        cves_detected: List[CVEItem] = []
        findings: List[Dict[str, Any]] = []

        for pkg, ver, filename in extracted_packages:
            for advisory in self.advisory_db:
                if advisory["package_name"].lower() == pkg:
                    pattern = advisory["vulnerable_pattern"]
                    if re.search(pattern, ver):
                        cve = CVEItem(
                            cve_id=advisory["cve_id"],
                            package_name=pkg,
                            vulnerable_versions=advisory["vulnerable_versions"],
                            fixed_version=advisory.get("fixed_version"),
                            severity=str(advisory["severity"]),
                        )
                        cves_detected.append(cve)

                        findings.append({
                            "finding_id": str(uuid.uuid4()),
                            "rule_id": f"VIGIL-DEP-{advisory['cve_id']}",
                            "category": "dependency",
                            "severity": advisory["severity"],
                            "confidence": 0.95,
                            "title": f"Vulnerable dependency {pkg}=={ver} ({advisory['cve_id']})",
                            "rationale": advisory["rationale"],
                            "remediation": f"Upgrade {pkg} to {advisory.get('fixed_version', 'latest version')}.",
                            "source_file_path": filename,
                            "tool_name": "dependency_risk_agent",
                        })

        return DependencyRiskOutput(
            findings=findings,
            cves_detected=cves_detected,
            total_dependencies_analyzed=len(extracted_packages),
        )


# Backward compatibility alias
DependencyRiskAgent = DependencyAgent


async def run_dependency_agent(inp: DependencyRiskInput) -> DependencyRiskOutput:
    """Async entrypoint for A11 Dependency Risk Agent."""
    agent = DependencyAgent()
    return await agent.analyze_dependencies(inp)
