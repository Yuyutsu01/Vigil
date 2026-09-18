"""npm audit adapter for Node.js dependency vulnerability scanning (FR-101)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from app.adapters.base import ToolAdapter
from app.schemas.finding import RawFinding

logger = logging.getLogger(__name__)


class NpmAuditAdapter(ToolAdapter):
    """
    Adapter for npm audit.
    Invoked with `npm audit --json`. Only reads dependency lockfile, never executes code.
    """
    name = "npm-audit"
    version = "10.8.2"
    languages = ["javascript", "typescript"]

    def build_command(self, target_path: Path) -> List[str]:
        return ["npm", "audit", "--json"]

    def parse_output(self, stdout: str, stderr: str, return_code: int) -> List[RawFinding]:
        if not stdout.strip():
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.debug("Failed to parse npm audit JSON output: %s", e)
            return []

        vulns = data.get("vulnerabilities", {})
        findings: List[RawFinding] = []

        if isinstance(vulns, dict):
            for pkg_name, info in vulns.items():
                if not isinstance(info, dict):
                    continue
                raw_sev = info.get("severity", "moderate").capitalize()
                sev_mapped = "Critical" if raw_sev == "Critical" else (
                    "High" if raw_sev == "High" else (
                        "Medium" if raw_sev in {"Moderate", "Medium"} else "Low"
                    )
                )

                findings.append(
                    RawFinding(
                        tool_name=self.name,
                        tool_version=self.version,
                        rule_id=f"NPM-AUDIT-{pkg_name.upper()}",
                        severity_raw=sev_mapped,
                        message=f"Vulnerable dependency: {pkg_name} ({info.get('range', '')})",
                        file_path="package-lock.json",
                        start_line=None,
                        start_col=None,
                        end_line=None,
                        end_col=None,
                        raw_evidence={
                            "name": pkg_name,
                            "severity": raw_sev,
                            "fixAvailable": info.get("fixAvailable"),
                        },
                    )
                )

        return findings
