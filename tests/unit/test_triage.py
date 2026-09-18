"""
Unit tests for the deterministic triage capability.
AC-4: Triage produces identical output for identical input.
"""
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))


class TestTriageService:
    """Tests for deterministic triage deduplication and ranking."""

    def _make_finding(self, rule_id, category, severity, confidence, ast_path, matched_text, origin="rule"):
        from app.rules.engine import DetectedFinding
        from app.models.finding import EvidenceKind, FindingOrigin
        return DetectedFinding(
            rule_id=rule_id,
            category=category,
            severity=severity,
            confidence=confidence,
            title=f"Test finding {rule_id}",
            rationale="Test rationale",
            remediation="Test remediation",
            evidence_kind=EvidenceKind.ast_node,
            ast_path=ast_path,
            matched_text=matched_text,
            origin=FindingOrigin.rule if origin == "rule" else FindingOrigin.agent,
        )

    def test_deduplication_by_fingerprint(self) -> None:
        """Duplicate findings with same fingerprint must be collapsed to one."""
        from app.services.triage_service import deduplicate_and_rank

        f1 = self._make_finding("R1", "cat", "High", 0.9, "Module/Call", "eval(x)")
        f2 = self._make_finding("R1", "cat", "High", 0.9, "Module/Call", "eval(x)")

        result = deduplicate_and_rank([f1, f2])
        assert len(result) == 1, "Duplicate findings must be collapsed"

    def test_rule_findings_override_agent_findings(self) -> None:
        """Rule findings must win over agent findings on fingerprint collision."""
        from app.services.triage_service import deduplicate_and_rank

        rule_finding = self._make_finding("R1", "cat", "High", 0.9, "Module/Call", "eval(x)", "rule")
        agent_finding = self._make_finding("R1", "cat", "Medium", 0.7, "Module/Call", "eval(x)", "agent")

        result = deduplicate_and_rank([agent_finding, rule_finding])
        assert len(result) == 1
        # Rule finding should win (origin=rule)
        from app.models.finding import FindingOrigin
        assert result[0].origin == FindingOrigin.rule

    def test_findings_sorted_by_severity(self) -> None:
        """Findings must be sorted Critical → High → Medium → Low → Info."""
        from app.services.triage_service import deduplicate_and_rank

        findings = [
            self._make_finding("R-L", "cat", "Low", 0.9, "path1", "text1"),
            self._make_finding("R-C", "cat", "Critical", 0.9, "path2", "text2"),
            self._make_finding("R-M", "cat", "Medium", 0.9, "path3", "text3"),
            self._make_finding("R-H", "cat", "High", 0.9, "path4", "text4"),
        ]

        result = deduplicate_and_rank(findings)
        severities = [f.severity for f in result]
        assert severities == ["Critical", "High", "Medium", "Low"], (
            f"Expected Critical→High→Medium→Low, got: {severities}"
        )

    def test_same_severity_sorted_by_confidence_descending(self) -> None:
        """Same severity: higher confidence comes first."""
        from app.services.triage_service import deduplicate_and_rank

        findings = [
            self._make_finding("R1", "cat", "High", 0.6, "path1", "text1"),
            self._make_finding("R2", "cat", "High", 0.9, "path2", "text2"),
        ]

        result = deduplicate_and_rank(findings)
        assert result[0].confidence > result[1].confidence

    def test_triage_deterministic(self) -> None:
        """Same input must always produce same output (AC-4)."""
        from app.services.triage_service import deduplicate_and_rank

        findings = [
            self._make_finding("R1", "injection", "Critical", 0.9, "path1", "text1"),
            self._make_finding("R2", "secrets", "High", 0.85, "path2", "text2"),
            self._make_finding("R3", "crypto", "Medium", 0.7, "path3", "text3"),
        ]

        result1 = deduplicate_and_rank(findings)
        result2 = deduplicate_and_rank(findings)

        assert [f.rule_id for f in result1] == [f.rule_id for f in result2]

    def test_no_patch_fields_in_phase1(self) -> None:
        """Phase 1 must never produce patch_candidate on findings."""
        from app.rules.engine import DetectedFinding, RuleEngine
        engine = RuleEngine()

        source = "import pickle\npickle.loads(data)"
        findings, _ = engine.run(source, "python")

        for f in findings:
            # DetectedFinding has no patch_candidate attribute — it's only on the DB model
            assert not hasattr(f, "unified_diff"), "No patch generation in Phase 1"
            assert not hasattr(f, "patch_diff"), "No patch generation in Phase 1"
