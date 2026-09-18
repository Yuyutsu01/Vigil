"""Ruff Python linter and code quality adapter (FR-101)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from app.adapters.base import ToolAdapter
from app.schemas.finding import RawFinding

logger = logging.getLogger(__name__)


class RuffAdapter(ToolAdapter):
    """
    Adapter for Ruff fast Python linter.
    Invoked with `ruff check --output-format json <target_path>`.
    """
    name = "ruff"
    version = "0.6.9"
    languages = ["python"]

    def build_command(self, target_path: Path) -> List[str]:
        return ["ruff", "check", "--output-format", "json", str(target_path)]

    def parse_output(self, stdout: str, stderr: str, return_code: int) -> List[RawFinding]:
        if not stdout.strip():
            return []

        try:
            results = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.debug("Failed to parse Ruff JSON output: %s", e)
            return []

        if not isinstance(results, list):
            return []

        findings: List[RawFinding] = []
        for item in results:
            loc = item.get("location", {})
            end_loc = item.get("end_location", {})
            code = item.get("code", "RUFF-UNKNOWN")

            # Security rules (Sxxx in flake8-bandit) are High/Medium, formatting/lint rules are Low
            sev = "High" if code.startswith("S") else "Low"

            findings.append(
                RawFinding(
                    tool_name=self.name,
                    tool_version=self.version,
                    rule_id=code,
                    severity_raw=sev,
                    message=item.get("message", ""),
                    file_path=item.get("filename"),
                    start_line=loc.get("row"),
                    start_col=loc.get("column"),
                    end_line=end_loc.get("row"),
                    end_col=end_loc.get("column"),
                    raw_evidence={
                        "fix": item.get("fix"),
                        "cell": item.get("cell"),
                    },
                )
            )

        return findings
