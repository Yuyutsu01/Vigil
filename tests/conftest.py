"""
pytest configuration and fixtures.
Uses in-memory SQLite for unit/acceptance tests.
Integration tests use the DATABASE_URL env var (real PostgreSQL).
"""
import sys
import uuid
from pathlib import Path

import pytest
import pytest_asyncio

# Add backend to Python path
BACKEND_SRC = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(BACKEND_SRC))


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_tenant_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def mock_user_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def sandbox_enabled():
    """Explicit fixture for tests requiring sandbox validation endpoints [H1]."""
    from app.main import app
    app.state.sandbox_available = True
    yield
    app.state.sandbox_available = False
