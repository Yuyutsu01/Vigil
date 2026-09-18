"""
Unit tests for sandbox image supply chain digest requirements (H5).
Verifies that production halts if sandbox_image_digest is missing, while non-production proceeds.
"""
import pytest
from app.config import Settings
from app.sandbox.gvisor import verify_sandbox_image


def test_production_requires_image_digest():
    """Verify production halts with RuntimeError if sandbox_image_digest is empty."""
    settings = Settings(
        environment="production",
        sandbox_image_digest="",
    )
    with pytest.raises(RuntimeError, match="Production requires VIGIL_SANDBOX_IMAGE_DIGEST"):
        verify_sandbox_image(settings)


def test_production_with_valid_image_digest_succeeds():
    """Verify production proceeds when sandbox_image_digest is supplied."""
    settings = Settings(
        environment="production",
        sandbox_image_digest="sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    # Must complete without exception
    verify_sandbox_image(settings)


def test_development_allows_empty_image_digest():
    """Verify development and test environments permit empty sandbox_image_digest."""
    settings = Settings(
        environment="development",
        sandbox_image_digest="",
    )
    # Must complete without exception
    verify_sandbox_image(settings)
