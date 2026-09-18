"""
Sanitization module for Governed Learning Loop (FR-109, B2).
Provides canonical entry point for disposition comment sanitization.
"""
from __future__ import annotations

from typing import Optional

from app.services.learning_service import sanitize_user_comment


def sanitize_disposition_comment(comment: Optional[str]) -> str:
    """
    Canonical entry point for disposition comment sanitization.
    Delegates to the implementation in learning_service.

    Enforces:
    1. Secret redaction via RedactionFilter / regex.
    2. 500-character ceiling.
    3. Newline flattening.
    4. Stripping file paths and line number references.
    5. Detecting and replacing code-like syntax patterns.

    Returns the sanitized string (empty string if input is empty or None).
    """
    if not comment:
        return ""
    cleaned, _, _ = sanitize_user_comment(comment)
    return cleaned or ""
