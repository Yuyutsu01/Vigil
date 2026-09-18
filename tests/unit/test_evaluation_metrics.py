import sys
from pathlib import Path

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.evaluation.metrics import compute_metrics
from app.models.finding import EvidenceKind
from app.rules.engine import DetectedFinding


def test_metrics_calculation_perfect_match():
    # 2 samples, both vulnerable and matched
    sample_finding = DetectedFinding(
        rule_id="RULE-1",
        category="security",
        severity="High",
        confidence=0.9,
        title="Test",
        rationale="Test",
        remediation="Test",
        evidence_kind=EvidenceKind.ast_node,
    )
    evaluations = [
        {
            "name": "sample1",
            "is_vulnerable": True,
            "expected_rule_ids": ["RULE-1"],
            "detected_rule_ids": ["RULE-1"],
            "findings": [sample_finding],
        },
        {
            "name": "sample2",
            "is_vulnerable": False,
            "expected_rule_ids": [],
            "detected_rule_ids": [],
            "findings": [],
        },
    ]

    metrics = compute_metrics(evaluations)
    assert metrics.true_positives == 1
    assert metrics.false_positives == 0
    assert metrics.false_negatives == 0
    assert metrics.true_negatives == 1
    assert metrics.precision == 1.0
    assert metrics.recall == 1.0
    assert metrics.f1 == 1.0
    assert metrics.evidence_completeness == 1.0


def test_metrics_calculation_with_false_positive_and_false_negative():
    evaluations = [
        # Expected RULE-1, but detected RULE-2 -> 1 FN (missed RULE-1), 1 FP (unexpected RULE-2)
        {
            "name": "vuln_sample",
            "is_vulnerable": True,
            "expected_rule_ids": ["RULE-1"],
            "detected_rule_ids": ["RULE-2"],
            "findings": [],
        },
        # Clean sample with 1 FP detected
        {
            "name": "clean_sample",
            "is_vulnerable": False,
            "expected_rule_ids": [],
            "detected_rule_ids": ["RULE-3"],
            "findings": [],
        },
    ]

    metrics = compute_metrics(evaluations)
    assert metrics.true_positives == 0
    assert metrics.false_positives == 2
    assert metrics.false_negatives == 1
    assert metrics.precision == 0.0
    assert metrics.recall == 0.0
    assert metrics.f1 == 0.0
    assert "RULE-1" in metrics.per_rule_breakdown
    assert metrics.per_rule_breakdown["RULE-1"]["fn"] == 1
