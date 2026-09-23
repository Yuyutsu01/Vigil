import os
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import fakeredis
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


@pytest.fixture(autouse=True)
def redis_client(request):
    """
    Autouse Redis fixture providing in-memory FakeAsyncRedis across test suites.
    Opt out via @pytest.mark.needs_real_redis when VIGIL_TEST_USE_REAL_REDIS=1 is set.
    """
    if "needs_real_redis" in request.keywords:
        if os.environ.get("VIGIL_TEST_USE_REAL_REDIS") != "1":
            pytest.skip("Test requires real Redis and VIGIL_TEST_USE_REAL_REDIS=1 is not set")
        import app.redis_client
        yield app.redis_client.get_redis()
        return

    import app.redis_client

    fake_server = fakeredis.FakeServer()
    fake_client = fakeredis.FakeAsyncRedis(server=fake_server, decode_responses=True)

    old_client = app.redis_client._redis_client
    old_loop = app.redis_client._redis_loop
    app.redis_client._redis_client = fake_client

    def _get_fake_redis():
        return fake_client

    # Patch canonical get_redis on app.redis_client and all app modules importing it
    # Dynamic patching covers modules that executed `from app.redis_client import get_redis`
    # at top-level before this test fixture was invoked, ensuring they receive fake_client.
    patchers = [patch("app.redis_client.get_redis", side_effect=_get_fake_redis)]
    for mod_name, mod in list(sys.modules.items()):
        if mod and (mod_name.startswith("app.") or mod_name == "app") and hasattr(mod, "get_redis"):
            patchers.append(patch(f"{mod_name}.get_redis", side_effect=_get_fake_redis))

    for p in patchers:
        p.start()

    try:
        yield fake_client
    finally:
        for p in patchers:
            p.stop()
        app.redis_client._redis_client = old_client
        app.redis_client._redis_loop = old_loop
