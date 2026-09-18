"""Consent schemas for POST /v1/consent."""
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ConsentGrantRequest(BaseModel):
    purpose: str = Field(
        default="code_review_processing",
        description="Purpose identifier for this consent grant.",
    )
    version: str = Field(description="Policy version the user is consenting to.")
    granted: bool = Field(description="True = grant; False = revoke.")


class ConsentGrantResponse(BaseModel):
    consent_id: uuid.UUID
    granted_at: datetime
    version: str
    granted: bool
