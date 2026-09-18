"""ESLint static analysis adapter for JavaScript and TypeScript (FR-101)."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import List

from app.adapters.base import ToolAdapter
from app.schemas.finding import RawFinding

logger = logging.getLogger(__name__)


class ESLintAdapter(ToolAdapter):
    """
    Adapter for ESLint linter.
    Runs `npx eslint -f json <target_path>` or `eslint -f json <target_path>`.
    """
    name = "eslint"
    version = "9.13.0"
    languages = ["javascript", "typescript"]

    def _get_binary(self) -> str:
        if shutil.which("eslint"):
            return "eslint"
        return "npx"

    def build_command(self, target_path: Path) -> List[str]:
        binary = self._get_binary()
        if binary == "npx":
            return ["npx", "--no-install", "eslint", "-f", "json", str(target_path)]
        return ["eslint", "-f", "json", str(target_path)]

    def is_available(self) -> bool:
        return shutil.which("eslint") is not None or shutil.which("npx") is not None

    def parse_output(self, stdout: str, stderr: str, return_code: int) -> List[RawFinding]:
        if not stdout.strip():
            return []

        try:
            results = json.loads(stdout)
        except json.JSONDecodeError as e:
            logger.debug("Failed to parse ESLint JSON output: %s", e)
            return []

        if not isinstance(results, list):
            return []

        findings: List[RawFinding] = []
        for file_entry in results:
            messages = file_entry.get("messages", [])
            file_path = file_entry.get("filePath")
            for msg in messages:
                # ESLint severity: 1 = warning, 2 = error
                sev_code = msg.get("severity", 1)
                sev_str = "High" if sev_code == 2 else "Medium"

                findings.append(
                    RawFinding(
                        tool_name=self.name,
                        tool_version=self.version,
                        rule_id=msg.get("ruleId", "ESLINT-UNKNOWN"),
                        severity_raw=sev_str,
                        message=msg.get("message", ""),
                        file_path=file_path,
                        start_line=msg.get("line"),
                        start_col=msg.get("column"),
                        end_line=msg.get("endLine"),
                        end_col=msg.get("endColumn"),
                        raw_evidence={
                            "nodeType": msg.get("nodeType"),
                            "fatal": msg.get("fatal", False),
                        },
                    )
                )

        return findings
