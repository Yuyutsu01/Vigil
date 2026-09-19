"""Schemas for review submission, run status, and upload sessions."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.models.review import ReviewStatus
from app.schemas.finding import FindingSchema

# Allowed language values for the language field in review requests
ALLOWED_LANGUAGES = {"python", "javascript", "typescript"}


class ReviewCreateRequest(BaseModel):
    """
    POST /v1/reviews request body.
    Content-Type must be application/json (enforced at router level).
    source_text is the pasted code. For file uploads, use POST /v1/uploads first.
    """
    language: str = Field(description="python | javascript | typescript")
    source_text: Optional[str] = Field(
        default=None,
        description="Pasted source code (up to 250 KB UTF-8).",
    )
    # upload_id references a completed POST /v1/uploads session
    upload_id: Optional[uuid.UUID] = Field(default=None)
    options: Optional[dict] = Field(default_factory=dict)

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ALLOWED_LANGUAGES:
            raise ValueError(f"language must be one of {ALLOWED_LANGUAGES}")
        return v

    @field_validator("source_text")
    @classmethod
    def validate_source_text(cls, v: Optional[str]) -> Optional[str]:
        # Maximum allowed size is 250 KB (250 * 1024 bytes) per FR-001
        if v is not None and len(v.encode("utf-8")) > 250 * 1024:
            raise ValueError("source_text exceeds 250 KB limit")
        return v


class ReviewCreateResponse(BaseModel):
    run_id: uuid.UUID
    status: ReviewStatus


class ReviewRunResponse(BaseModel):
    run_id: uuid.UUID
    status: ReviewStatus
    language: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    parked_reason: Optional[str] = None
    prompt_version: Optional[str] = None
    findings: List[FindingSchema] = Field(default_factory=list)
    finding_count: int = 0
    timing_ms: Optional[int] = None
    source_text: Optional[str] = None

    model_config = {"from_attributes": True}


class DeleteReviewResponse(BaseModel):
    run_id: uuid.UUID
    deletion_status: str
    audit_id: uuid.UUID


class UploadCreateResponse(BaseModel):
    upload_id: uuid.UUID
    constraints: dict = Field(
        default={
            "max_bytes": 256 * 1024,
            "allowed_media_types": [
                "application/x-python",
                "text/x-python",
                "text/javascript",
                "application/javascript",
                "application/typescript",
                "text/typescript",
            ],
        }
    )
