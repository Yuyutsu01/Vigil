"""Bandit static security analyzer adapter for Python code (FR-101)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List

from app.adapters.base import ToolAdapter
from app.schemas.finding import RawFinding

logger = logging.getLogger(__name__)


class BanditAdapter(ToolAdapter):
    """
    Adapter for Bandit Python security linter.
    Invoked with `-f json -q <target_path>`. Never executes submitted code.
    """
    name = "bandit"
    version = "1.9.4"
    languages = ["python"]

    def build_command(self, target_path: Path) -> List[str]:
        return ["bandit", "-f", "json", "-q", str(target_path)]

    def parse_output(self, stdout: str, stderr: str, return_code: int) -> List[RawFinding]:
        if not stdout.strip():
            return []

        try:
            data = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.debug("Failed to parse Bandit JSON output: %s", e)
            return []

        results = data.get("results", [])
        findings: List[RawFinding] = []

        for item in results:
            line_no = item.get("line_number")
            line_range = item.get("line_range", [])
            end_line = line_range[-1] if line_range else line_no

            findings.append(
                RawFinding(
                    tool_name=self.name,
                    tool_version=self.version,
                    rule_id=item.get("test_id", "BANDIT-UNKNOWN"),
                    severity_raw=item.get("issue_severity", "MEDIUM").capitalize(),
                    message=item.get("issue_text", ""),
                    file_path=item.get("filename"),
                    start_line=line_no,
                    start_col=1,
                    end_line=end_line,
                    end_col=None,
                    raw_evidence={
                        "code": item.get("code"),
                        "cwe": item.get("issue_cwe"),
                        "confidence": item.get("issue_confidence"),
                        "test_name": item.get("test_name"),
                    },
                )
            )

        return findings
