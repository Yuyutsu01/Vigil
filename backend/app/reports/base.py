"""
Base abstractions and data structures for Report Export (FR-102).
Builds executive summaries, trends, and remediation plans.
Ensures code excerpts are redacted and full source code is never exposed.
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from app.models.finding import Finding
from app.models.review import ReviewRun
from app.services.redaction_service import redact


_SEVERITY_ORDER = {
    "Critical": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
    "Info": 4,
}


@dataclass
class FindingReportItem:
    finding_id: str
    fingerprint: str
    origin: str
    tool_name: Optional[str]
    rule_id: Optional[str]
    category: str
    severity: str
    confidence: float
    title: str
    rationale: str
    remediation: str
    code_excerpt: Optional[str] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    source_file_path: Optional[str] = None


@dataclass
class ReportData:
    run_id: str
    tenant_id: str
    generated_at: str
    language: str
    config_version: str
    prompt_version: str
    # Executive summary
    total_findings: int
    severity_counts: Dict[str, int]
    top_risks: List[FindingReportItem]
    affected_files: List[str]
    files_affected_summary: Dict[str, int]
    languages_reviewed: List[str]
    # Detailed findings
    findings: List[FindingReportItem]
    # Trends
    new_findings_count: int
    resolved_findings_count: int
    prior_runs_analyzed: int
    # Remediation plan
    remediation_by_category: Dict[str, List[FindingReportItem]]
    # Appendix
    appendix: Dict[str, Any]


def build_report_data(
    run: ReviewRun,
    findings: List[Finding],
    prior_runs: Optional[List[ReviewRun]] = None,
) -> ReportData:
    """Extract, aggregate, and redact review data into structured ReportData."""
    severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    report_items: List[FindingReportItem] = []

    for f in findings:
        sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        severity_counts[sev] = severity_counts.get(sev, 0) + 1

        # Extract primary evidence excerpt and line range if present
        excerpt = None
        start_l = None
        end_l = None
        if f.evidence:
            first_ev = f.evidence[0]
            start_l = first_ev.start_line
            end_l = first_ev.end_line
            if first_ev.code_excerpt:
                excerpt = redact(first_ev.code_excerpt)

        report_items.append(
            FindingReportItem(
                finding_id=str(f.finding_id),
                fingerprint=f.fingerprint,
                origin=f.origin.value if hasattr(f.origin, "value") else str(f.origin),
                tool_name=f.tool_name,
                rule_id=f.rule_id,
                category=f.category,
                severity=sev,
                confidence=f.confidence,
                title=redact(f.title),
                rationale=redact(f.rationale),
                remediation=redact(f.remediation),
                code_excerpt=excerpt,
                start_line=start_l,
                end_line=end_l,
                source_file_path=getattr(f, "source_file_path", None),
            )
        )

    # Sort report items by severity then confidence
    report_items.sort(
        key=lambda item: (_SEVERITY_ORDER.get(item.severity, 99), -item.confidence)
    )

    top_risks = report_items[:5]

    # Calculate affected files and files_affected_summary
    distinct_files = [getattr(f, "source_file_path", None) for f in findings if getattr(f, "source_file_path", None)]
    affected_files = sorted(list(set(distinct_files))) if distinct_files else [f"{run.run_id}_{run.source_artifact.language if run.source_artifact else 'unknown'}"]
    files_affected_summary: Dict[str, int] = {}
    for fpath in distinct_files:
        files_affected_summary[fpath] = files_affected_summary.get(fpath, 0) + 1

    # Trends: check prior runs for this tenant
    prior_fingerprints = set()
    if prior_runs:
        for pr in prior_runs:
            if pr.run_id != run.run_id:
                for pf in pr.findings:
                    prior_fingerprints.add(pf.fingerprint)

    current_fingerprints = {item.fingerprint for item in report_items}
    new_count = len(current_fingerprints - prior_fingerprints) if prior_runs else len(current_fingerprints)
    resolved_count = len(prior_fingerprints - current_fingerprints) if prior_runs else 0

    # Remediation plan grouped by category, sorted by severity
    remediation_by_category: Dict[str, List[FindingReportItem]] = {}
    for item in report_items:
        remediation_by_category.setdefault(item.category, []).append(item)

    for cat in remediation_by_category:
        remediation_by_category[cat].sort(
            key=lambda x: (_SEVERITY_ORDER.get(x.severity, 99), -x.confidence)
        )

    lang = run.source_artifact.language if run.source_artifact else "unknown"

    appendix = {
        "tool_versions": {
            "bandit": "1.9.4",
            "semgrep": "1.90.0",
            "ruff": "0.6.9",
            "eslint": "9.13.0",
            "pip_audit": "2.7.3",
            "npm_audit": "10.8.2",
        },
        "ruleset_version": "1.0.0",
        "prompt_version": run.prompt_version or "v1.0",
        "config_version": run.config_version or "default-m2",
    }

    return ReportData(
        run_id=str(run.run_id),
        tenant_id=str(run.tenant_id),
        generated_at=datetime.now(timezone.utc).isoformat(),
        language=lang,
        config_version=run.config_version or "default-m2",
        prompt_version=run.prompt_version or "v1.0",
        total_findings=len(report_items),
        severity_counts=severity_counts,
        top_risks=top_risks,
        affected_files=affected_files,
        files_affected_summary=files_affected_summary,
        languages_reviewed=[lang],
        findings=report_items,
        new_findings_count=new_count,
        resolved_findings_count=resolved_count,
        prior_runs_analyzed=len(prior_runs or []),
        remediation_by_category=remediation_by_category,
        appendix=appendix,
    )


class ReportRenderer(abc.ABC):
    """Abstract interface for format-specific report generators."""
    media_type: str = "application/octet-stream"
    file_extension: str = "bin"

    @abc.abstractmethod
    def render(self, data: ReportData) -> bytes:
        raise NotImplementedError
