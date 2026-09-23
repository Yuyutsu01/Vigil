"""
Security tests for Sandbox Image Verification & Cosign Sigstore Checks (H5).
Verifies that:
1. Tampered or invalid image digest format raises RuntimeError.
2. Unsigned image in production fails Cosign verification with RuntimeError.
3. Properly signed image passes startup probe without error.
"""
from unittest.mock import patch
import pytest

from app.config import Settings
from app.sandbox.gvisor import verify_sandbox_image


def test_tampered_image_digest_fails_verification():
    """An image digest that has been tampered with or malformed raises RuntimeError."""
    tampered_settings = Settings(
        environment="production",
        sandbox_image_digest="sha256:not_a_valid_64_hex_hash_tampered_digest",
    )
    with pytest.raises(RuntimeError, match="Tampered or invalid sandbox image digest"):
        verify_sandbox_image(tampered_settings)


def test_unsigned_image_fails_cosign_verification_in_production():
    """In production, an image that fails cosign signature verification raises RuntimeError."""
    valid_digest = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    prod_settings = Settings(
        environment="production",
        sandbox_image="vigil-sandbox:phase4",
        sandbox_image_digest=valid_digest,
    )

    # Mock verify_cosign_signature returning False (unsigned or invalid signature)
    with patch("app.sandbox.gvisor.verify_cosign_signature", return_value=False):
        with pytest.raises(RuntimeError, match="Cosign signature verification failed"):
            verify_sandbox_image(prod_settings)


def test_properly_signed_image_passes_verification():
    """A valid digest with verified Cosign signature passes startup verification."""
    valid_digest = "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    prod_settings = Settings(
        environment="production",
        sandbox_image="vigil-sandbox:phase4",
        sandbox_image_digest=valid_digest,
    )

    # Mock verify_cosign_signature returning True (valid cryptographic signature)
    with patch("app.sandbox.gvisor.verify_cosign_signature", return_value=True):
        # Should not raise any error
        verify_sandbox_image(prod_settings)


def test_cosign_missing_fails_closed_in_production():
    """In production, missing cosign binary fails closed (returns False) and logs critical."""
    from app.sandbox.gvisor import verify_cosign_signature
    prod_settings = Settings(environment="production")
    with patch("app.sandbox.gvisor.get_settings", return_value=prod_settings), \
         patch("shutil.which", return_value=None), \
         patch("app.sandbox.gvisor.logger.critical") as mock_critical:
        result = verify_cosign_signature("vigil-sandbox", "sha256:" + "a" * 64)
        assert result is False, f"Expected verify_cosign_signature to return False in production when cosign is missing, got {result}"
        assert mock_critical.called, "Expected logger.critical to be called when cosign is missing in production"


def test_cosign_missing_warns_and_allows_in_development():
    """In development, missing cosign binary logs a warning and allows startup (returns True)."""
    from app.sandbox.gvisor import verify_cosign_signature
    dev_settings = Settings(environment="development")
    with patch("app.sandbox.gvisor.get_settings", return_value=dev_settings), \
         patch("shutil.which", return_value=None), \
         patch("app.sandbox.gvisor.logger.warning") as mock_warning:
        result = verify_cosign_signature("vigil-sandbox", "sha256:" + "a" * 64)
        assert result is True, f"Expected verify_cosign_signature to return True in development when cosign is missing, got {result}"
        assert mock_warning.called, "Expected logger.warning to be called when cosign is missing in development"

