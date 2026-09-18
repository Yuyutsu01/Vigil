"""
POST /v1/uploads — file upload handler (multipart/form-data).
Allowed Content-Types (six raw media types per §7.2):
  application/x-python, text/x-python,
  text/javascript, application/javascript,
  application/typescript, text/typescript
Max size: 250 KB UTF-8. FR-001.
"""
from __future__ import annotations

import hashlib
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.deps import AuthContext, get_auth_context
from app.schemas.review import UploadCreateResponse
from app.config import get_settings

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])

ALLOWED_CONTENT_TYPES = {
    "application/x-python",
    "text/x-python",
    "text/javascript",
    "application/javascript",
    "application/typescript",
    "text/typescript",
}

LANGUAGE_MAP = {
    "application/x-python": "python",
    "text/x-python": "python",
    "text/javascript": "javascript",
    "application/javascript": "javascript",
    "application/typescript": "typescript",
    "text/typescript": "typescript",
}

# In-memory ephemeral upload store (TTL-evicted; use Redis in production)
_upload_store: dict[str, dict] = {}


@router.post(
    "",
    response_model=UploadCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload source file for review (FR-001)",
)
async def upload_file(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_auth_context),
) -> UploadCreateResponse:
    """
    Accept a source code file upload.
    Content-Type must be one of the six allowed raw media types.
    Returns an upload_id that can be referenced in POST /v1/reviews.
    Max file size: 250 KB UTF-8.
    """
    settings = get_settings()

    # Content-Type validation
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "unsupported_media_type",
                "message": f"Content-Type {content_type!r} is not allowed. "
                           f"Allowed: {sorted(ALLOWED_CONTENT_TYPES)}",
            },
        )

    # Read content
    content = await file.read()

    # Size check (250 KB)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "payload_too_large",
                "message": f"File size {len(content)} bytes exceeds 250 KB limit",
            },
        )

    # UTF-8 validation
    try:
        source_text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "encoding_error", "message": "File must be UTF-8 encoded"},
        )

    language = LANGUAGE_MAP[content_type]
    checksum = hashlib.sha256(content).hexdigest()
    upload_id = uuid.uuid4()

    # Store upload (ephemeral, scoped to tenant)
    _upload_store[str(upload_id)] = {
        "upload_id": str(upload_id),
        "tenant_id": str(auth.tenant_id),
        "source_text": source_text,
        "language": language,
        "checksum": checksum,
        "size_bytes": len(content),
    }

    return UploadCreateResponse(upload_id=upload_id)


def pop_upload(upload_id: uuid.UUID, tenant_id: uuid.UUID) -> dict | None:
    """Retrieve and remove an upload from the store, validating tenant ownership."""
    record = _upload_store.get(str(upload_id))
    if not record:
        return None
    if record["tenant_id"] != str(tenant_id):
        return None  # Tenant isolation
    del _upload_store[str(upload_id)]
    return record
