"""Semgrep static analyzer adapter for cross-language security scanning (FR-101)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from app.adapters.base import ToolAdapter
from app.schemas.finding import RawFinding

logger = logging.getLogger(__name__)


class SemgrepAdapter(ToolAdapter):
    """
    Adapter for Semgrep.
    Invoked with `semgrep scan --json --quiet --config auto <target_path>`.
    """
    name = "semgrep"
    version = "1.90.0"
    languages = ["python", "javascript", "typescript"]

    def build_command(self, target_path: Path) -> List[str]:
        return ["semgrep", "scan", "--json", "--quiet", "--config", "auto", str(target_path)]

    def parse_output(self, stdout: str, stderr: str, return_code: int) -> List[RawFinding]:
        if not stdout.strip():
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.debug("Failed to parse Semgrep JSON output: %s", e)
            return []

        results = data.get("results", [])
        findings: List[RawFinding] = []

        for item in results:
            start = item.get("start", {})
            end = item.get("end", {})
            extra = item.get("extra", {})

            # Map Semgrep severity (ERROR, WARNING, INFO) to normalized severity string
            raw_sev = extra.get("severity", "WARNING").upper()
            sev_mapped = "High" if raw_sev == "ERROR" else ("Medium" if raw_sev == "WARNING" else "Low")

            findings.append(
                RawFinding(
                    tool_name=self.name,
                    tool_version=self.version,
                    rule_id=item.get("check_id", "SEMGREP-UNKNOWN"),
                    severity_raw=sev_mapped,
                    message=extra.get("message", ""),
                    file_path=item.get("path"),
                    start_line=start.get("line"),
                    start_col=start.get("col"),
                    end_line=end.get("line"),
                    end_col=end.get("col"),
                    raw_evidence={
                        "lines": extra.get("lines"),
                        "metadata": extra.get("metadata"),
                    },
                )
            )

        return findings
