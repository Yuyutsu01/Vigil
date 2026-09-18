"""
Evaluation Metrics Calculator: computes precision, recall, F1, and per-rule breakdown.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set


@dataclass
class MetricSummary:
    total_samples: int
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1: float
    evidence_completeness: float
    per_rule_breakdown: Dict[str, Dict[str, int]] = field(default_factory=dict)


def compute_metrics(
    evaluations: List[dict],
) -> MetricSummary:
    """
    Computes standard classification metrics:
    - TP: expected vulnerability correctly identified
    - FP: finding raised on clean code or rule not in ground truth
    - FN: expected vulnerability missed
    - TN: clean code with zero findings
    """
    tp = 0
    fp = 0
    fn = 0
    tn = 0
    total_findings_count = 0
    findings_with_evidence_count = 0
    per_rule: Dict[str, Dict[str, int]] = {}

    for item in evaluations:
        expected_rules: Set[str] = set(item.get("expected_rule_ids", []))
        detected_rules: Set[str] = set(item.get("detected_rule_ids", []))
        is_vuln: bool = item.get("is_vulnerable", False)
        findings = item.get("findings", [])

        # Evidence completeness check
        for f in findings:
            total_findings_count += 1
            if getattr(f, "evidence_kind", None) is not None:
                findings_with_evidence_count += 1

        if not is_vuln:
            if not detected_rules:
                tn += 1
            else:
                fp += len(detected_rules)
                for r in detected_rules:
                    per_rule.setdefault(r, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1
        else:
            if not expected_rules:
                # If marked vulnerable without specific rules, presence of any finding is TP
                if detected_rules:
                    tp += 1
                else:
                    fn += 1
            else:
                # Rule-level matching
                matched = expected_rules & detected_rules
                unmatched_expected = expected_rules - detected_rules
                unmatched_detected = detected_rules - expected_rules

                tp += len(matched)
                fn += len(unmatched_expected)
                fp += len(unmatched_detected)

                for r in matched:
                    per_rule.setdefault(r, {"tp": 0, "fp": 0, "fn": 0})["tp"] += 1
                for r in unmatched_expected:
                    per_rule.setdefault(r, {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1
                for r in unmatched_detected:
                    per_rule.setdefault(r, {"tp": 0, "fp": 0, "fn": 0})["fp"] += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if fn == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if fp == 0 else 0.0)
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    evidence_comp = (
        findings_with_evidence_count / total_findings_count
        if total_findings_count > 0
        else 1.0
    )

    return MetricSummary(
        total_samples=len(evaluations),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        evidence_completeness=round(evidence_comp, 4),
        per_rule_breakdown=per_rule,
    )
