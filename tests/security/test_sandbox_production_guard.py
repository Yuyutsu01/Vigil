"""
Security tests for Sandbox Production Guards (H1).
Verifies that:
1. In production, setting sandbox_runtime_type != 'gvisor' halts startup with RuntimeError.
2. In production, setting allow_unsafe_sandbox_fallback=True halts startup with RuntimeError.
3. In development, fallback configuration does not raise RuntimeError.
"""
from unittest.mock import patch
import pytest

from app.config import Settings
from app.main import lifespan, app


@pytest.mark.asyncio
async def test_production_rejects_non_gvisor_runtime():
    """Setting sandbox_runtime_type='docker' in production raises RuntimeError."""
    prod_settings = Settings(
        environment="production",
        sandbox_runtime_type="docker",
        allow_unsafe_sandbox_fallback=False,
        sandbox_image_digest="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )

    with patch("app.main.settings", prod_settings):
        with pytest.raises(RuntimeError, match="Production requires sandbox_runtime_type='gvisor'"):
            async with lifespan(app):
                pass


@pytest.mark.asyncio
async def test_production_rejects_unsafe_fallback_flag():
    """Setting allow_unsafe_sandbox_fallback=True in production raises RuntimeError."""
    prod_settings = Settings(
        environment="production",
        sandbox_runtime_type="gvisor",
        allow_unsafe_sandbox_fallback=True,
        sandbox_image_digest="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    )

    with patch("app.main.settings", prod_settings):
        with pytest.raises(RuntimeError, match="Production forbids allow_unsafe_sandbox_fallback=True"):
            async with lifespan(app):
                pass


@pytest.mark.asyncio
async def test_development_permits_unsafe_fallback():
    """In development, allow_unsafe_sandbox_fallback=True and docker runtime do not raise."""
    dev_settings = Settings(
        environment="development",
        sandbox_runtime_type="docker",
        allow_unsafe_sandbox_fallback=True,
    )

    with patch("app.main.settings", dev_settings), \
         patch("app.main.create_tables"):
        async with lifespan(app):
            # Should enter and exit cleanly without raising
            pass
