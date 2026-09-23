"""
Unit tests verifying consistency of upload and source text size limits
across configuration, Pydantic schemas, and API error messages.
"""
from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.schemas.review import ReviewCreateRequest, UploadCreateResponse
from app.services.auth_service import create_access_token


def test_1_inline_source_text_uses_config_limit() -> None:
    """ReviewCreateRequest allows source_text of exactly settings.max_upload_bytes and rejects max_upload_bytes + 1."""
    settings = get_settings()
    max_bytes = settings.max_upload_bytes

    # Exactly max_upload_bytes (256 KB = 262,144 bytes)
    valid_text = "a" * max_bytes
    req = ReviewCreateRequest(language="python", source_text=valid_text)
    assert req.source_text == valid_text

    # max_upload_bytes + 1 bytes -> must raise ValueError
    invalid_text = "a" * (max_bytes + 1)
    with pytest.raises(ValueError, match="exceeds"):
        ReviewCreateRequest(language="python", source_text=invalid_text)


def test_2_schema_constraint_matches_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """UploadCreateResponse advertised constraints max_bytes dynamically matches settings.max_upload_bytes."""
    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_bytes", 128 * 1024)
    dummy_id = uuid.uuid4()
    resp = UploadCreateResponse(upload_id=dummy_id)
    assert resp.constraints["max_bytes"] == 128 * 1024


def test_3_upload_error_message_uses_actual_limit() -> None:
    """POST /v1/uploads returns 413 with error message reflecting the actual config limit in KB/bytes."""
    settings = get_settings()
    user_id = uuid.uuid4()
    tenant_id = uuid.uuid4()
    token = create_access_token(user_id=user_id, tenant_id=tenant_id, role="developer")

    client = TestClient(app)
    oversized_data = b"x" * (settings.max_upload_bytes + 100)

    resp = client.post(
        "/v1/uploads",
        files={"file": ("test.py", oversized_data, "text/x-python")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 413
    msg = resp.json()["detail"]["message"]

    # Expected: dynamic KB representation based on max_upload_bytes (e.g. 256 KB)
    expected_kb_str = f"{settings.max_upload_bytes // 1024} KB"
    assert expected_kb_str in msg
    assert "250 KB limit" not in msg
