"""
Security tests: SSRF protection against unauthorized host routing in GitHubClient (FR-103).
"""
import pytest

from app.integrations.github.client import GitHubClient


def test_ssrf_protection_blocks_external_hosts():
    client = GitHubClient(
        installation_id=12345,
        private_key_ref="env://TEST_KEY",
        base_url="https://api.github.com",
    )

    # Valid internal paths
    assert client._validate_url("/repos/vigil/test") == "https://api.github.com/repos/vigil/test"
    assert client._validate_url("https://api.github.com/installation/repositories") == "https://api.github.com/installation/repositories"

    # Block attacker hosts
    with pytest.raises(ValueError, match="SSRF blocked"):
        client._validate_url("http://169.254.169.254/latest/meta-data")

    with pytest.raises(ValueError, match="SSRF blocked"):
        client._validate_url("https://evil.internal.corp/admin")


@pytest.mark.asyncio
async def test_installation_token_ssrf_blocked(monkeypatch):
    """Verifies that non-allowlisted github_api_base raises ValueError via validate_github_url (H3)."""
    from unittest.mock import AsyncMock
    from app.config import get_settings
    from app.integrations.github.app_auth import (
        generate_ephemeral_rsa_keypair,
        get_installation_access_token,
    )

    settings = get_settings()
    monkeypatch.setattr(settings, "github_api_base", "https://evil.example")
    monkeypatch.setattr(settings, "github_api_base_url", "https://evil.example")

    priv_pem, _ = generate_ephemeral_rsa_keypair()
    mock_vault = AsyncMock()
    mock_vault.resolve_private_key.return_value = priv_pem
    monkeypatch.setattr("app.integrations.github.app_auth.get_vault_resolver", lambda: mock_vault)

    with pytest.raises(ValueError, match="SSRF blocked"):
        await get_installation_access_token(
            installation_id=99999,
            private_key_ref="vault://dummy-ref",
            force_refresh=True,
        )
