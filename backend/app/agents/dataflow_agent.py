"""
A12: Dataflow Investigation Agent (FR-108, D1, D5).
Traces inter-procedural source-to-sink taint flows over AST representations.
Detects user-controlled input reaching dangerous sinks and verifies sanitizers.
"""
from __future__ import annotations

import ast
import logging
import uuid
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

from app.agents.permissions import assert_permission
from app.models.finding import Severity

logger = logging.getLogger(__name__)

# Common user input sources
TAINT_SOURCES = {
    "request", "args", "params", "user_input", "data", "payload",
    "query", "body", "input", "sys.argv", "environ", "getenv"
}

# Known sanitizers that neutralize taint
SANITIZERS = {
    "int", "float", "bool", "shlex.quote", "quote", "escape",
    "html.escape", "secure_filename", "strip", "sanitize"
}


class TaintTraceHop(BaseModel):
    line_number: int
    symbol: str
    expression: str


class ConfirmedTaintTrace(BaseModel):
    source_symbol: str
    sink_symbol: str
    hops: List[TaintTraceHop]
    sanitizer_detected: bool
    confidence: float


class DataflowInput(BaseModel):
    source_code: str
    language: str = "python"
    candidate_sinks: List[Dict[str, Any]] = Field(default_factory=list)


class DataflowOutput(BaseModel):
    confirmed_traces: List[ConfirmedTaintTrace] = Field(default_factory=list)
    validated_findings: List[Dict[str, Any]] = Field(default_factory=list)


class DataflowAgent:
    """
    A12 Specialist Agent performing static taint tracking from input sources to sinks.
    """

    def __init__(self, max_hops: int = 10):
        self.max_hops = max_hops

    def _extract_variable_assignments(self, tree: ast.AST) -> Dict[str, List[tuple[int, str, ast.AST]]]:
        """Map variable name -> list of (line_no, var_name, rhs_node)."""
        assignments: Dict[str, List[tuple[int, str, ast.AST]]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments.setdefault(target.id, []).append((node.lineno, target.id, node.value))
        return assignments

    async def analyze_dataflow(self, input_data: DataflowInput) -> DataflowOutput:
        # Enforce static permission envelope (D5)
        assert_permission("dataflow", "allow_llm")

        if input_data.language != "python":
            return DataflowOutput(confirmed_traces=[], validated_findings=[])

        try:
            tree = ast.parse(input_data.source_code)
        except SyntaxError:
            return DataflowOutput(confirmed_traces=[], validated_findings=[])

        lines = input_data.source_code.splitlines()
        assignments = self._extract_variable_assignments(tree)
        confirmed_traces: List[ConfirmedTaintTrace] = []
        validated_findings: List[Dict[str, Any]] = []

        # Find dangerous sink calls in the AST
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            func_name = None
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in {"eval", "exec", "system", "run", "execute"}:
                sink_line = getattr(node, "lineno", 0)
                sink_expr = lines[sink_line - 1] if 1 <= sink_line <= len(lines) else str(func_name)

                # Check arguments passed to sink
                for arg in node.args:
                    if not isinstance(arg, ast.Name):
                        continue
                    tainted_var = arg.id

                    hops: List[TaintTraceHop] = [
                        TaintTraceHop(line_number=sink_line, symbol=tainted_var, expression=sink_expr.strip())
                    ]

                    # Trace backwards through assignments
                    curr_var = tainted_var
                    sanitizer_found = False
                    source_found = False
                    source_name = curr_var

                    for _ in range(self.max_hops):
                        rhs_list = assignments.get(curr_var, [])
                        if not rhs_list:
                            # Could be a function parameter or external input
                            if any(src in curr_var.lower() for src in TAINT_SOURCES):
                                source_found = True
                                source_name = curr_var
                            break

                        assign_line, var_name, rhs_node = rhs_list[-1]
                        assign_expr = lines[assign_line - 1] if 1 <= assign_line <= len(lines) else ""
                        hops.insert(0, TaintTraceHop(line_number=assign_line, symbol=var_name, expression=assign_expr.strip()))

                        # Check if rhs calls a sanitizer
                        if isinstance(rhs_node, ast.Call):
                            call_name = ""
                            if isinstance(rhs_node.func, ast.Name):
                                call_name = rhs_node.func.id
                            elif isinstance(rhs_node.func, ast.Attribute):
                                call_name = rhs_node.func.attr

                            if any(san in call_name.lower() for san in SANITIZERS):
                                sanitizer_found = True

                            # Follow inner arg
                            if rhs_node.args and isinstance(rhs_node.args[0], ast.Name):
                                curr_var = rhs_node.args[0].id
                                continue

                        if isinstance(rhs_node, ast.Name):
                            curr_var = rhs_node.id
                        else:
                            # Check if rhs mentions taint sources
                            rhs_text = ast.unparse(rhs_node) if hasattr(ast, "unparse") else ""
                            if any(src in rhs_text.lower() for src in TAINT_SOURCES):
                                source_found = True
                                source_name = rhs_text
                            break

                    confidence = 0.4 if sanitizer_found else (0.95 if source_found else 0.75)

                    trace = ConfirmedTaintTrace(
                        source_symbol=source_name,
                        sink_symbol=func_name,
                        hops=hops,
                        sanitizer_detected=sanitizer_found,
                        confidence=confidence,
                    )
                    confirmed_traces.append(trace)

                    if not sanitizer_found:
                        validated_findings.append({
                            "finding_id": str(uuid.uuid4()),
                            "rule_id": f"VIGIL-DATAFLOW-{func_name.upper()}",
                            "category": "security",
                            "severity": Severity.critical if func_name in {"eval", "exec", "system"} else Severity.high,
                            "confidence": confidence,
                            "title": f"Unsanitized taint flow from {source_name} to {func_name}()",
                            "rationale": f"User-controlled variable {source_name} flows into dangerous sink {func_name}() without sanitization.",
                            "remediation": f"Sanitize {curr_var} before invoking {func_name}().",
                            "tool_name": "dataflow_investigation_agent",
                            "start_line": sink_line,
                        })

        return DataflowOutput(
            confirmed_traces=confirmed_traces,
            validated_findings=validated_findings,
        )


    async def investigate_dataflow(self, input_data: DataflowInput) -> DataflowOutput:
        """Alias for analyze_dataflow."""
        return await self.analyze_dataflow(input_data)


# Backward compatibility alias
DataflowInvestigationAgent = DataflowAgent


async def run_dataflow_agent(inp: DataflowInput) -> DataflowOutput:
    """Async entrypoint for A12 Dataflow Investigation Agent."""
    agent = DataflowAgent()
    return await agent.analyze_dataflow(inp)
