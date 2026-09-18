"""
Pydantic schemas for the Finding API contract.

finding_id: UUID v7 primary key (database identity).
fingerprint: Deterministic SHA-256 — sha256(rule_id || ast_path || matched_text_hash || evidence_kind).
             Used for deduplication (FR-006) and SARIF partialFingerprints.
             Line-shift-invariant: inserting blank lines never changes this value.
See Implementation Plan [C3], [H3], [M2].
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from pydantic import BaseModel, Field

from app.models.finding import EvidenceKind, FindingOrigin, FindingStatus, Severity


class SourceRangeSchema(BaseModel):
    """SARIF-compatible source location."""
    start_line: Optional[int] = None
    start_col: Optional[int] = None
    end_line: Optional[int] = None
    end_col: Optional[int] = None


class EvidenceSchema(BaseModel):
    evidence_id: uuid.UUID
    source_range: SourceRangeSchema
    ast_path: Optional[str] = None
    tool_name: Optional[str] = None
    rule_id: Optional[str] = None
    code_excerpt: Optional[str] = None
    evidence_kind: EvidenceKind


class FindingSchema(BaseModel):
    """
    Full normalized finding per §10.2 API contract.
    patch_candidate_id is null in Phase 1 (FR-105 deferred to Phase 3).
    """
    finding_id: uuid.UUID
    run_id: uuid.UUID
    # Deterministic SHA-256 fingerprint (line-shift-invariant) for deduplication and SARIF
    fingerprint: str = Field(description="sha256(rule_id||ast_path||matched_text_hash||evidence_kind)")
    origin: FindingOrigin
    tool_name: Optional[str] = None
    tool_version: Optional[str] = None
    raw_evidence_ref: Optional[uuid.UUID] = None
    source_file_path: Optional[str] = None
    rule_id: Optional[str] = None
    category: str
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str
    rationale: str
    remediation: str
    evidence: List[EvidenceSchema] = Field(default_factory=list)
    status: FindingStatus = FindingStatus.open
    # Always null in Phase 1
    patch_candidate_id: Optional[uuid.UUID] = None
    disposition: Optional[str] = None

    model_config = {"from_attributes": True}


class RawFinding(BaseModel):
    """Uniform raw finding returned by static analyzer tool adapters."""
    tool_name: str
    tool_version: Optional[str] = None
    rule_id: Optional[str] = None
    severity_raw: Optional[str] = None
    message: str
    file_path: Optional[str] = None
    start_line: Optional[int] = None
    start_col: Optional[int] = None
    end_line: Optional[int] = None
    end_col: Optional[int] = None
    raw_evidence: Optional[dict] = None


class FeedbackRequest(BaseModel):
    useful: Optional[bool] = None
    disposition: Optional[str] = Field(
        default=None,
        description="accepted | rejected | false_positive",
    )
    comment: Optional[str] = Field(default=None, max_length=2000)
    reason_category: Optional[str] = Field(
        default=None,
        description="false_positive_style | false_positive_test | false_positive_dependency | real_issue | not_applicable",
    )


class FeedbackResponse(BaseModel):
    feedback_id: uuid.UUID
    finding_id: uuid.UUID
    disposition: Optional[str] = None
    reason_category: Optional[str] = None
    indexed_for_learning: bool = False


# Internal schema used during agent output parsing (not API-facing)
class RawLLMFinding(BaseModel):
    """Parsed output from LLM capability node."""
    rule_id: str
    category: str
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    title: str = Field(max_length=255)
    rationale: str = Field(max_length=1000)
    remediation: str = Field(max_length=1000)
    evidence_kind: EvidenceKind = EvidenceKind.llm_reasoning
    ast_path: Optional[str] = None
    matched_text: Optional[str] = None
    start_line: Optional[int] = None
    start_col: Optional[int] = None
    end_line: Optional[int] = None
    end_col: Optional[int] = None


class RawLLMResponse(BaseModel):
    """Outer wrapper for LLM structured response."""
    findings: List[RawLLMFinding] = Field(default_factory=list)
