import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

BACKEND_SRC = Path(__file__).parents[2] / "backend"
sys.path.insert(0, str(BACKEND_SRC))

from app.adapters.bandit import BanditAdapter
from app.adapters.eslint import ESLintAdapter
from app.adapters.npm_audit import NpmAuditAdapter
from app.adapters.pip_audit import PipAuditAdapter
from app.adapters.registry import AdapterRegistry
from app.adapters.ruff import RuffAdapter
from app.adapters.semgrep import SemgrepAdapter
from app.schemas.finding import RawFinding


def test_bandit_parse_output():
    adapter = BanditAdapter()
    sample_output = json.dumps({
        "results": [
            {
                "code": "eval('2+2')",
                "filename": "test.py",
                "issue_confidence": "HIGH",
                "issue_cwe": {"id": 95},
                "issue_severity": "HIGH",
                "issue_text": "Use of possibly insecure function - eval was detected.",
                "line_number": 5,
                "line_range": [5],
                "test_id": "B307",
                "test_name": "blacklist",
            }
        ]
    })
    findings = adapter.parse_output(sample_output, "", 0)
    assert len(findings) == 1
    f = findings[0]
    assert f.tool_name == "bandit"
    assert f.rule_id == "B307"
    assert f.severity_raw == "High"
    assert f.start_line == 5
    assert "eval" in f.message


def test_semgrep_parse_output():
    adapter = SemgrepAdapter()
    sample_output = json.dumps({
        "results": [
            {
                "check_id": "rules.python.security.sql_injection",
                "path": "app.py",
                "start": {"line": 12, "col": 4},
                "end": {"line": 12, "col": 40},
                "extra": {
                    "message": "Potential SQL injection",
                    "severity": "ERROR",
                    "metadata": {"cwe": "CWE-89"},
                    "lines": "cursor.execute(query)",
                },
            }
        ]
    })
    findings = adapter.parse_output(sample_output, "", 0)
    assert len(findings) == 1
    f = findings[0]
    assert f.tool_name == "semgrep"
    assert f.rule_id == "rules.python.security.sql_injection"
    assert f.severity_raw == "High"
    assert f.start_line == 12


def test_ruff_parse_output():
    adapter = RuffAdapter()
    sample_output = json.dumps([
        {
            "code": "S101",
            "message": "Use of assert detected",
            "location": {"row": 3, "column": 1},
            "end_location": {"row": 3, "column": 15},
            "filename": "main.py",
            "fix": None,
        }
    ])
    findings = adapter.parse_output(sample_output, "", 0)
    assert len(findings) == 1
    f = findings[0]
    assert f.tool_name == "ruff"
    assert f.rule_id == "S101"
    assert f.severity_raw == "High"
    assert f.start_line == 3


def test_eslint_parse_output():
    adapter = ESLintAdapter()
    sample_output = json.dumps([
        {
            "filePath": "src/index.js",
            "messages": [
                {
                    "ruleId": "no-eval",
                    "severity": 2,
                    "message": "eval can be harmful.",
                    "line": 8,
                    "column": 5,
                    "endLine": 8,
                    "endColumn": 15,
                }
            ],
        }
    ])
    findings = adapter.parse_output(sample_output, "", 0)
    assert len(findings) == 1
    f = findings[0]
    assert f.tool_name == "eslint"
    assert f.rule_id == "no-eval"
    assert f.severity_raw == "High"
    assert f.start_line == 8


def test_pip_audit_parse_output():
    adapter = PipAuditAdapter()
    sample_output = json.dumps({
        "dependencies": [
            {
                "name": "requests",
                "version": "2.0.0",
                "vulns": [
                    {
                        "id": "PYSEC-2018-01",
                        "description": "Information disclosure in requests",
                        "fix_versions": ["2.20.0"],
                    }
                ],
            }
        ]
    })
    findings = adapter.parse_output(sample_output, "", 0)
    assert len(findings) == 1
    f = findings[0]
    assert f.tool_name == "pip-audit"
    assert f.rule_id == "PYSEC-2018-01"
    assert "requests" in f.message


def test_npm_audit_parse_output():
    adapter = NpmAuditAdapter()
    sample_output = json.dumps({
        "vulnerabilities": {
            "tar": {
                "name": "tar",
                "severity": "high",
                "range": "<6.1.9",
                "fixAvailable": True,
            }
        }
    })
    findings = adapter.parse_output(sample_output, "", 0)
    assert len(findings) == 1
    f = findings[0]
    assert f.tool_name == "npm-audit"
    assert "TAR" in f.rule_id
    assert f.severity_raw == "High"


@pytest.mark.asyncio
async def test_adapter_registry_dispatch_and_cache():
    mock_adapter = MagicMock(spec=BanditAdapter)
    mock_adapter.name = "mock_bandit"
    mock_adapter.version = "1.0.0"
    mock_adapter.languages = ["python"]
    mock_finding = RawFinding(
        tool_name="mock_bandit",
        rule_id="RULE-1",
        message="Test issue",
        severity_raw="Medium",
    )
    mock_adapter.run = AsyncMock(return_value=([mock_finding], None))

    registry = AdapterRegistry(adapters=[mock_adapter])
    assert len(registry.get_adapters_for_language("python")) == 1
    assert len(registry.get_adapters_for_language("javascript")) == 0

    # Execute run_all
    findings, diags = await registry.run_all("x = 1", "python")
    assert len(findings) == 1
    assert findings[0].rule_id == "RULE-1"
    assert diags == []


@pytest.mark.asyncio
async def test_adapter_registry_handles_tool_failure_gracefully():
    failing_adapter = MagicMock(spec=BanditAdapter)
    failing_adapter.name = "crashing_tool"
    failing_adapter.version = "1.0.0"
    failing_adapter.languages = ["python"]
    failing_adapter.run = AsyncMock(side_effect=RuntimeError("Subprocess segmentation fault"))

    registry = AdapterRegistry(adapters=[failing_adapter])
    findings, diags = await registry.run_all("x = 1", "python")
    # Must not crash; returns diagnostic
    assert len(findings) == 0
    assert len(diags) == 1
    assert diags[0]["tool"] == "crashing_tool"


def test_raw_evidence_bounded():
    """Verify that RawFinding.raw_evidence contains only bounded fragment <= 8 KB (N3)."""
    adapter = BanditAdapter()
    sample_output = json.dumps({
        "results": [
            {
                "code": "eval('2+2')",
                "filename": "test.py",
                "issue_confidence": "HIGH",
                "issue_cwe": {"id": 95},
                "issue_severity": "HIGH",
                "issue_text": "Use of possibly insecure function - eval was detected.",
                "line_number": 5,
                "line_range": [5],
                "test_id": "B307",
                "test_name": "blacklist",
            }
        ]
    })
    findings = adapter.parse_output(sample_output, "", 0)
    assert len(findings) == 1
    for f in findings:
        raw_evidence_as_json = json.dumps(f.raw_evidence)
        assert len(raw_evidence_as_json) <= 8192

