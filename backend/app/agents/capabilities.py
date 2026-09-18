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


# ─── Capability: Triage (DETERMINISTIC — NO LLM) ─────────────────────────────

async def capability_triage(state: ReviewGraphState) -> ReviewGraphState:
    """
    Deterministic deduplication, severity cap enforcement, and ranking.
    TRIAGE DOES NOT INVOKE AN LLM. See Design Principles §6 and docs/triage_rules.md.

    Algorithm:
    1. Convert LLM findings to DetectedFinding format with capped severity.
    2. Merge rule findings + LLM findings.
    3. Deduplicate by fingerprint (deterministic rule findings take precedence).
    4. Sort by severity (Critical first) then confidence (descending).
    """
    from app.rules.engine import compute_fingerprint
    from app.models.finding import EvidenceKind as EK, FindingOrigin, Severity as S

    # 1. Convert and cap LLM findings
    llm_converted: List[DetectedFinding] = []
    for f in state.llm_security_findings + state.llm_quality_findings:
        # LLM findings from quality review are capped at Medium
        capped_severity = f.severity.value
        if f in state.llm_quality_findings:
            if capped_severity in {"Critical", "High"}:
                capped_severity = "Medium"

        ast_path = f.ast_path or f"line_{f.start_line or 0}/llm_reasoning"
        matched_text = f.matched_text or f.title

        df = DetectedFinding(
            rule_id=f.rule_id,
            category=f.category,
            severity=capped_severity,
            confidence=f.confidence,
            title=f.title,
            rationale=f.rationale,
            remediation=f.remediation,
            evidence_kind=EK.llm_reasoning,
            ast_path=ast_path,
            matched_text=matched_text[:200],
            start_line=f.start_line,
            start_col=f.start_col,
            end_line=f.end_line,
            end_col=f.end_col,
            origin=FindingOrigin.agent,
        )
        llm_converted.append(df)

    # 2. Compute fingerprints for all findings
    def _fp(f: DetectedFinding) -> str:
        return compute_fingerprint(
            f.rule_id or "unknown",
            f.ast_path or "",
            f.matched_text or "",
            f.evidence_kind.value,
        )

    # 3. Deduplicate: rule findings take precedence over LLM findings
    seen: dict[str, DetectedFinding] = {}

    # Insert rule findings first (highest priority)
    for f in state.rule_findings:
        fp = _fp(f)
        seen[fp] = f

    # Insert LLM findings, skip if fingerprint already exists (from rule)
    for f in llm_converted:
        fp = _fp(f)
        if fp not in seen:
            seen[fp] = f

    # 4. Sort by severity (Critical=0), then confidence descending
    merged = list(seen.values())
    merged.sort(
        key=lambda f: (_SEVERITY_ORDER.get(f.severity, 99), -f.confidence)
    )

    state.final_findings = merged
    logger.debug(
        "Triage: run_id=%s total_findings=%d (rule=%d, llm=%d, after_dedup=%d)",
        state.run_id,
        len(merged),
        len(state.rule_findings),
        len(llm_converted),
        len(merged),
    )
    return state
