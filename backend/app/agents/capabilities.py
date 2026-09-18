"""
Modular agent capabilities invoked by the LangGraph StateGraph.
Each capability is a focused, independently testable function.
TRIAGE IS DETERMINISTIC — no LLM invoked. See Design Principles §6.
"""
from __future__ import annotations

import logging
from typing import List

from app.agents.llm_provider import ModelProvider
from app.agents.policy import invoke_llm_with_policy
from app.agents.prompt_loader import format_quality_prompt, format_security_prompt
from app.agents.state import ReviewGraphState
from app.models.finding import EvidenceKind
from app.parser.syntax_validator import validate_syntax
from app.rules.engine import DetectedFinding, RuleEngine
from app.schemas.finding import RawFinding

logger = logging.getLogger(__name__)

_rule_engine = RuleEngine()

# Severity ordering for triage (lower = more severe)
_SEVERITY_ORDER = {
    "Critical": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
    "Info": 4,
}


# ─── Capability: Parse ────────────────────────────────────────────────────────

async def capability_parse(state: ReviewGraphState) -> ReviewGraphState:
    """
    Parse the source code and check for syntax errors.
    If syntax errors are found, set state.syntax_errors and return early.
    ZERO code execution — only ast/tree-sitter parsing.
    """
    errors = validate_syntax(state.source_code, state.language)
    state.syntax_errors = [f"Line {e.line}, Col {e.col}: {e.message}" for e in errors]
    state.parse_successful = len(errors) == 0

    # Compute basic AST facts (line count, size) for OTel span attributes
    lines = state.source_code.splitlines()
    state.ast_facts = {
        "line_count": len(lines),
        "size_bytes": len(state.source_code.encode("utf-8")),
    }

    logger.debug(
        "Parse: run_id=%s language=%s errors=%d",
        state.run_id,
        state.language,
        len(state.syntax_errors),
    )
    return state


# ─── Capability: Run Rules ────────────────────────────────────────────────────

async def capability_run_rules(state: ReviewGraphState) -> ReviewGraphState:
    """
    Run all deterministic baseline rules against the source code.
    Only runs if parse was successful.
    """
    if not state.parse_successful:
        logger.debug("Skipping rules: parse not successful (run_id=%s)", state.run_id)
        return state

    findings, _ = _rule_engine.run(state.source_code, state.language)
    state.rule_findings = findings
    logger.debug(
        "Rules: run_id=%s findings=%d",
        state.run_id,
        len(findings),
    )
    return state


# ─── Capability: Run Adapters (FR-101) ────────────────────────────────────────

async def capability_run_adapters(state: ReviewGraphState) -> ReviewGraphState:
    """
    Run configured static analyzer adapters (Bandit, Semgrep, Ruff, ESLint, etc.).
    Only runs if parse was successful.
    Executes in parallel with asyncio.gather and per-adapter timeouts.
    """
    if not state.parse_successful:
        logger.debug("Skipping adapters: parse not successful (run_id=%s)", state.run_id)
        return state

    from app.adapters.registry import AdapterRegistry
    registry = AdapterRegistry()

    findings, diagnostics = await registry.run_all(state.source_code, state.language)
    state.tool_findings = findings
    state.adapter_diagnostics = diagnostics

    logger.debug(
        "Adapters: run_id=%s findings=%d diagnostics=%d",
        state.run_id,
        len(findings),
        len(diagnostics),
    )
    return state


# ─── Capability: LLM Security Reasoning ──────────────────────────────────────

async def capability_llm_security(
    state: ReviewGraphState,
    provider: ModelProvider,
) -> ReviewGraphState:
    """
    Call the security reasoning LLM via the policy layer.
    Budget and deadline are checked before the call.
    """
    if not state.parse_successful:
        return state

    existing_ids = [f.rule_id for f in state.rule_findings]
    prompt, version = format_security_prompt(
        state.source_code, state.language, existing_ids
    )
    # Record prompt version (last writer wins if multiple prompts)
    state.prompt_version = version

    from app.schemas.finding import RawLLMResponse  # avoid circular

    async def _call():
        return await provider.generate_structured(prompt, RawLLMResponse)

    response = await invoke_llm_with_policy(state, _call, estimated_tokens=6000)
    if response:
        state.llm_security_findings = response.findings

    return state


# ─── Capability: LLM Quality Review ──────────────────────────────────────────

async def capability_llm_quality(
    state: ReviewGraphState,
    provider: ModelProvider,
) -> ReviewGraphState:
    """
    Call the quality review LLM via the policy layer.
    Budget and deadline are checked before the call.
    """
    if not state.parse_successful:
        return state

    prompt, version = format_quality_prompt(state.source_code, state.language)
    if state.prompt_version is None:
        state.prompt_version = version

    from app.schemas.finding import RawLLMResponse  # avoid circular

    async def _call():
        return await provider.generate_structured(prompt, RawLLMResponse)

    response = await invoke_llm_with_policy(state, _call, estimated_tokens=4000)
    if response:
        state.llm_quality_findings = response.findings

    return state


def _convert_llm_finding(f: RawLLMFinding, cap_severity: bool) -> DetectedFinding:
    """
    Convert a RawLLMFinding to a DetectedFinding.
    If cap_severity is True (quality findings), Critical and High are capped to Medium.
    """
    from app.models.finding import FindingOrigin

    sev = f.severity.value
    if cap_severity and sev in {"Critical", "High"}:
        sev = "Medium"
    ast_path = f.ast_path or f"line_{f.start_line or 0}/llm_reasoning"
    matched_text = f.matched_text or f.title
    return DetectedFinding(
        rule_id=f.rule_id,
        category=f.category,
        severity=sev,
        confidence=f.confidence,
        title=f.title,
        rationale=f.rationale,
        remediation=f.remediation,
        evidence_kind=f.evidence_kind or EvidenceKind.llm_reasoning,
        ast_path=ast_path,
        matched_text=matched_text[:200],
        start_line=f.start_line,
        start_col=f.start_col,
        end_line=f.end_line,
        end_col=f.end_col,
        origin=FindingOrigin.agent,
    )


def _convert_tool_finding(f: RawFinding) -> DetectedFinding:
    """Convert a tool RawFinding to a normalized DetectedFinding."""
    from app.models.finding import FindingOrigin

    # Determine category
    rule_id_upper = (f.rule_id or "").upper()
    if any(k in rule_id_upper for k in ["SEC", "B1", "B2", "B3", "CVE", "VULN", "INJECT", "EVAL"]):
        category = "security"
    else:
        category = "quality"

    raw_sev = (f.severity_raw or "Medium").capitalize()
    if raw_sev not in {"Critical", "High", "Medium", "Low", "Info"}:
        raw_sev = "Medium"

    ast_path = f"tool_{f.tool_name}/{f.rule_id or 'finding'}"
    matched_text = f.message[:200]
    evidence_kind = EvidenceKind.ast_node if f.start_line is not None else EvidenceKind.token_regex

    return DetectedFinding(
        rule_id=f.rule_id or f"{f.tool_name.upper()}-001",
        category=category,
        severity=raw_sev,
        confidence=0.85,
        title=f.message[:255],
        rationale=f.message,
        remediation=f"Address finding reported by {f.tool_name}",
        evidence_kind=evidence_kind,
        ast_path=ast_path,
        matched_text=matched_text,
        start_line=f.start_line,
        start_col=f.start_col,
        end_line=f.end_line,
        end_col=f.end_col,
        origin=FindingOrigin.tool,
        tool_name=f.tool_name,
        tool_version=f.tool_version,
        raw_evidence=f.raw_evidence,
    )


# ─── Capability: Triage (DETERMINISTIC — NO LLM) ─────────────────────────────

async def capability_triage(state: ReviewGraphState) -> ReviewGraphState:
    """
    Deterministic deduplication, severity cap enforcement, and ranking.
    TRIAGE DOES NOT INVOKE AN LLM. See Design Principles §6 and docs/triage_rules.md.

    Algorithm:
    1. Convert LLM findings to DetectedFinding format with capped severity.
    2. Convert tool adapter findings to DetectedFinding format.
    3. Merge three sources: rule findings + tool findings + LLM findings.
    4. Deduplicate by fingerprint with strict precedence: rule > tool > agent.
    5. Sort by severity (Critical first) then confidence (descending).
    """
    from app.rules.engine import compute_fingerprint

    # 1. Convert and cap LLM findings
    llm_converted: List[DetectedFinding] = []

    # Security findings: severity unchanged
    for f in state.llm_security_findings:
        llm_converted.append(_convert_llm_finding(f, cap_severity=False))

    # Quality findings: Critical/High capped to Medium
    for f in state.llm_quality_findings:
        llm_converted.append(_convert_llm_finding(f, cap_severity=True))

    # 2. Convert tool findings
    tool_converted: List[DetectedFinding] = [
        f if isinstance(f, DetectedFinding) else _convert_tool_finding(f)
        for f in state.tool_findings
    ]

    # 3. Compute fingerprints for all findings
    def _fp(f: DetectedFinding) -> str:
        return compute_fingerprint(
            f.rule_id or "unknown",
            f.ast_path or "",
            f.matched_text or "",
            f.evidence_kind.value,
        )

    # 4. Deduplicate: rule > tool > agent precedence
    seen: dict[str, DetectedFinding] = {}

    # Insert rule findings first (highest priority)
    for f in state.rule_findings:
        fp = _fp(f)
        seen[fp] = f

    # Insert tool findings next (rule > tool > agent)
    for f in tool_converted:
        fp = _fp(f)
        if fp not in seen:
            seen[fp] = f

    # Insert LLM findings, skip if fingerprint already exists
    for f in llm_converted:
        fp = _fp(f)
        if fp not in seen:
            seen[fp] = f

    # 5. Sort by severity (Critical=0), then confidence descending
    merged = list(seen.values())
    merged.sort(
        key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), -f.confidence)
    )

    state.final_findings = merged
    logger.debug(
        "Triage: run_id=%s total_findings=%d (rule=%d, tool=%d, llm=%d, after_dedup=%d)",
        state.run_id,
        len(merged),
        len(state.rule_findings),
        len(tool_converted),
        len(llm_converted),
        len(merged),
    )
    return state
