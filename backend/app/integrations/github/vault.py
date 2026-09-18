"""
Vault resolver abstraction for resolving private keys and secrets (FR-103, B3).
Provides a pluggable VaultResolver interface and an EnvVaultResolver for Phase 3.
"""
from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

from app.config import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class VaultResolver(Protocol):
    """Protocol defining interface for retrieving secret/private key materials."""

    async def resolve_private_key(self, ref: str) -> str:
        """Resolve a private key reference URI into PEM text."""
        ...


class EnvVaultResolver:
    """
    Resolves private keys from environment variables or file paths.
    Recognizes prefixes:
      - 'env://VAR_NAME': reads from os.environ[VAR_NAME]
      - 'file:///path/to/key.pem': reads file contents
      - raw path or direct PEM string (if starting with '-----BEGIN')
    """

    async def resolve_private_key(self, ref: str) -> str:
        # Check production security posture
        settings = get_settings()
        if settings.environment == "production" and (ref.startswith("env://") or ref.startswith("file://")):
            logger.warning(
                "Production environment using EnvVaultResolver with %s; "
                "HashiCorp Vault or Cloud KMS recommended for enterprise deployments.",
                ref[:10],
            )

        # 1. Direct PEM content passed in
        if ref.strip().startswith("-----BEGIN"):
            return ref.strip()

        # 2. Environment variable reference: env://VAR_NAME
        if ref.startswith("env://"):
            var_name = ref[len("env://"):]
            val = os.environ.get(var_name)
            if not val:
                raise ValueError(f"Environment variable '{var_name}' referenced by vault ref is not set.")
            return val.replace("\\n", "\n").strip()

        # 3. File URI or path
        path = ref
        if path.startswith("file://"):
            path = path[len("file://"):]

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()

        # If none of the above matched, attempt environment variable fallback
        val = os.environ.get(ref)
        if val:
            return val.replace("\\n", "\n").strip()

        raise ValueError(f"Could not resolve private key reference: {ref}")


def get_vault_resolver() -> VaultResolver:
    """Return configured VaultResolver instance."""
    return EnvVaultResolver()
