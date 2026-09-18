"""
HTML Report Renderer using Jinja2 with strict auto-escaping (FR-102).
Prevents template injection and XSS via mandatory autoescape.
"""
from __future__ import annotations

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.reports.base import ReportData, ReportRenderer

_TEMPLATES_DIR = Path(__file__).parent / "templates"


class HTMLReportRenderer(ReportRenderer):
    """Renders human-readable HTML security and quality review reports."""
    media_type = "text/html; charset=utf-8"
    file_extension = "html"

    def __init__(self, template_name: str = "report.html"):
        self.template_name = template_name
        self.env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html", "xml"]),  # CRITICAL: Prevent injection
        )

    def render(self, data: ReportData) -> bytes:
        template = self.env.get_template(self.template_name)
        html_str = template.render(data=data)
        return html_str.encode("utf-8")
