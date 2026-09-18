"""JSON report renderer (FR-102)."""
from __future__ import annotations

import dataclasses
import json

from app.reports.base import ReportData, ReportRenderer


class JSONReportRenderer(ReportRenderer):
    """Generates machine-readable JSON export of review findings and executive summary."""
    media_type = "application/json"
    file_extension = "json"

    def render(self, data: ReportData) -> bytes:
        raw_dict = dataclasses.asdict(data)
        serialized = json.dumps(raw_dict, indent=2, ensure_ascii=False)
        return serialized.encode("utf-8")
