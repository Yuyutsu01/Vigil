"""pip-audit adapter for Python dependency vulnerability scanning (FR-101)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from app.adapters.base import ToolAdapter
from app.schemas.finding import RawFinding

logger = logging.getLogger(__name__)


class PipAuditAdapter(ToolAdapter):
    """
    Adapter for pip-audit dependency scanner.
    Invoked with `pip-audit -f json -r <target_path>`. Never executes submitted code.
    """
    name = "pip-audit"
    version = "2.7.3"
    languages = ["python"]

    def build_command(self, target_path: Path) -> List[str]:
        return ["pip-audit", "-f", "json", "-r", str(target_path)]

    def parse_output(self, stdout: str, stderr: str, return_code: int) -> List[RawFinding]:
        if not stdout.strip():
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.debug("Failed to parse pip-audit JSON output: %s", e)
            return []

        dependencies = data.get("dependencies", [])
        findings: List[RawFinding] = []

        for dep in dependencies:
            name = dep.get("name")
            version = dep.get("version")
            vulns = dep.get("vulns", [])
            for v in vulns:
                cve_id = v.get("id", "CVE-UNKNOWN")
                desc = v.get("description", f"Vulnerability in {name}=={version}")
                findings.append(
                    RawFinding(
                        tool_name=self.name,
                        tool_version=self.version,
                        rule_id=cve_id,
                        severity_raw="High",
                        message=desc,
                        file_path=None,
                        start_line=None,
                        start_col=None,
                        end_line=None,
                        end_col=None,
                        raw_evidence={
                            "package": name,
                            "version": version,
                            "fix_versions": v.get("fix_versions", []),
                            "aliases": v.get("aliases", []),
                        },
                    )
                )

        return findings
