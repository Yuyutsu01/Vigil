"""
Evaluation Corpus Loader.
Loads test cases strictly from disk (tests/evaluation/corpus/).
NEVER touches the tenant database.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# Root path for the evaluation corpus
_CORPUS_ROOT = Path(__file__).parents[3] / "tests" / "evaluation" / "corpus"


@dataclass
class CorpusTestCase:
    name: str
    suite: str
    language: str
    source_path: Path
    source_code: str
    is_vulnerable: bool
    expected_rule_ids: List[str] = field(default_factory=list)


class CorpusLoader:
    """Loads evaluation corpus files from disk."""

    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or _CORPUS_ROOT

    def load_suite(self, suite: str = "all") -> List[CorpusTestCase]:
        """
        Load test cases for python, javascript, or all.
        Finds vulnerable and clean files, matching sidecar or expected/ JSON definitions.
        """
        suites = ["python", "javascript"] if suite.lower() == "all" else [suite.lower()]
        test_cases: List[CorpusTestCase] = []

        for s in suites:
            suite_dir = self.root_dir / s
            if not suite_dir.exists():
                continue

            lang = "python" if s == "python" else "javascript"
            ext = ".py" if s == "python" else ".js"

            # 1. Vulnerable files
            vuln_dir = suite_dir / "vulnerable"
            if vuln_dir.exists():
                for code_file in vuln_dir.glob(f"*{ext}"):
                    # Look for sidecar JSON or expected/<name>.json
                    expected_rules: List[str] = []
                    sidecar = code_file.with_suffix(".json")
                    expected_json = self.root_dir / "expected" / f"{code_file.stem}.json"

                    if sidecar.exists():
                        try:
                            data = json.loads(sidecar.read_text(encoding="utf-8"))
                            expected_rules = [item.get("rule_id") for item in data if "rule_id" in item]
                        except Exception:
                            pass
                    elif expected_json.exists():
                        try:
                            data = json.loads(expected_json.read_text(encoding="utf-8"))
                            expected_rules = [item.get("rule_id") for item in data if "rule_id" in item]
                        except Exception:
                            pass

                    test_cases.append(
                        CorpusTestCase(
                            name=code_file.stem,
                            suite=s,
                            language=lang,
                            source_path=code_file,
                            source_code=code_file.read_text(encoding="utf-8"),
                            is_vulnerable=True,
                            expected_rule_ids=expected_rules,
                        )
                    )

            # 2. Clean files
            clean_dir = suite_dir / "clean"
            if clean_dir.exists():
                for code_file in clean_dir.glob(f"*{ext}"):
                    test_cases.append(
                        CorpusTestCase(
                            name=code_file.stem,
                            suite=s,
                            language=lang,
                            source_path=code_file,
                            source_code=code_file.read_text(encoding="utf-8"),
                            is_vulnerable=False,
                            expected_rule_ids=[],
                        )
                    )

        return test_cases
