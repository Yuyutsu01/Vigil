"""
ReviewGraphState: the shared state object passed through the LangGraph nodes.
See Implementation Plan [B2], [B3].
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from app.rules.engine import DetectedFinding
from app.schemas.finding import RawFinding, RawLLMFinding


@dataclass
class ReviewGraphState:
    """
    Mutable state shared across all agent capabilities in the LangGraph.

    Budget/deadline attributes are checked by policy.py before every LLM call.
    """
    # Input
    run_id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID = field(default_factory=uuid.uuid4)
    source_code: str = ""
    language: str = "python"

    # Parse stage
    syntax_errors: List[str] = field(default_factory=list)
    parse_successful: bool = False
    ast_facts: dict = field(default_factory=dict)  # simplified key facts from AST

    # Rule engine stage
    rule_findings: List[DetectedFinding] = field(default_factory=list)

    # Tool adapter stage (FR-101)
    tool_findings: List[RawFinding] = field(default_factory=list)
    adapter_diagnostics: List[dict] = field(default_factory=list)

    # LLM stage
    llm_security_findings: List[RawLLMFinding] = field(default_factory=list)
    llm_quality_findings: List[RawLLMFinding] = field(default_factory=list)
    prompt_version: Optional[str] = None

    # Triage stage (deterministic — no LLM)
    final_findings: List[DetectedFinding] = field(default_factory=list)

    # Budget / policy tracking [B3]
    iterations: int = 0
    token_usage: int = 0
    deadline_at: Optional[datetime] = None
    budget_remaining: int = 50_000  # tokens
    parked_reason: Optional[str] = None
    retry_count: int = 0

    # Status
    completed: bool = False
    has_error: bool = False
    error_message: Optional[str] = None

    # OTel timing
    started_at: Optional[datetime] = None

    def is_deadline_exceeded(self) -> bool:
        if self.deadline_at is None:
            return False
        return datetime.now(timezone.utc) > self.deadline_at

    def is_budget_exhausted(self) -> bool:
        return self.budget_remaining <= 0

    def is_max_iterations_reached(self, max_iter: int) -> bool:
        return self.iterations >= max_iter
