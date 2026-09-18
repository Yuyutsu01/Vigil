"""
Triage service — deterministic deduplication, severity capping, and ranking.
TRIAGE IS DETERMINISTIC. NO LLM IS INVOKED HERE.
See Implementation Plan Design Principles §6, docs/triage_rules.md, [F4].
"""
from __future__ import annotations

from typing import List

from app.rules.engine import DetectedFinding, compute_fingerprint

_SEVERITY_ORDER = {
    "Critical": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
    "Info": 4,
}


def deduplicate_and_rank(findings: List[DetectedFinding]) -> List[DetectedFinding]:
    """
    Deduplicate findings by fingerprint and sort by severity then confidence.
    Rule findings (origin=rule) take precedence over agent findings on fingerprint collision.
    Returns a new sorted list; does not mutate input.
    """
    seen: dict[str, DetectedFinding] = {}

    for f in findings:
        fp = compute_fingerprint(
            f.rule_id or "unknown",
            f.ast_path or "",
            f.matched_text or "",
            f.evidence_kind.value,
        )
        if fp not in seen:
            seen[fp] = f
        else:
            # Rule findings win over LLM findings
            existing = seen[fp]
            if existing.origin.value == "agent" and f.origin.value == "rule":
                seen[fp] = f

    merged = list(seen.values())
    merged.sort(
        key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), -f.confidence)
    )
    return merged
