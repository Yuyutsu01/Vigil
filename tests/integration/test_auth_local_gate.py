"""
Integration tests for VIGIL_ALLOW_LOCAL_AUTH soft gate (WS1, AUTH-01).

Behavior under test:
- VIGIL_ALLOW_LOCAL_AUTH defaults to False.
- When False: POST /v1/auth/register, /v1/auth/login, /v1/auth/token return 404.
- When True: all three endpoints function normally.
- When True AND VIGIL_ENV=production: main.py startup emits logger.critical warning
  containing 'prototype local auth', but startup succeeds.
"""
import uuid
from unittest.mock import AsyncMock, patch
import httpx
import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.config import get_settings
from app.database import Base
from app.main import app, lifespan


@pytest.mark.asyncio
async def test_1_local_auth_disabled_returns_404(monkeypatch):
    """
    Test 1: With VIGIL_ENV=production and VIGIL_ALLOW_LOCAL_AUTH=False (or unset),
    POST /v1/auth/register, /v1/auth/login, and /v1/auth/token MUST return 404.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    settings = get_settings()
    prod_settings = settings.model_copy(
        update={
            "environment": "production",
            "allow_local_auth": False,
        }
    )

    try:
        with patch("app.api.v1.auth.get_settings", return_value=prod_settings):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp_reg = await client.post(
                    "/v1/auth/register",
                    json={
                        "organization_name": "Acme Corp",
                        "email": "user@acme.com",
                        "password": "SecurePassword123!",
                    },
                )
                print("UNFIXED_REGISTER_STATUS:", resp_reg.status_code)
                print("UNFIXED_REGISTER_BODY:", resp_reg.text[:200])
                assert resp_reg.status_code == 404, (
                    f"Expected 404 for /register on disabled auth, got {resp_reg.status_code}: {resp_reg.text[:200]}"
                )

                resp_login = await client.post(
                    "/v1/auth/login",
                    json={
                        "email": "user@acme.com",
                        "password": "SecurePassword123!",
                    },
                )
                assert resp_login.status_code == 404, f"Expected 404 for /login, got {resp_login.status_code}"

                resp_token = await client.post(
                    "/v1/auth/token",
                    json={
                        "email": "user@acme.com",
                        "password": "SecurePassword123!",
                    },
                )
                assert resp_token.status_code == 404, f"Expected 404 for /token, got {resp_token.status_code}"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_2_local_auth_enabled_works_in_development(monkeypatch):
    """
    Test 2: With VIGIL_ENV=development and VIGIL_ALLOW_LOCAL_AUTH=True,
    all three routes reach their handlers, register provisions Tenant + User,
    and login returns a verifiable JWT access token.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db

    settings = get_settings()
    dev_settings = settings.model_copy(
        update={
            "environment": "development",
            "allow_local_auth": True,
        }
    )

    test_email = f"developer_{uuid.uuid4().hex[:8]}@example.com"
    test_password = "StrongPassword456!"

    try:
        with patch("app.api.v1.auth.get_settings", return_value=dev_settings):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. Register
                resp_reg = await client.post(
                    "/v1/auth/register",
                    json={
                        "organization_name": "Dev Org",
                        "email": test_email,
                        "password": test_password,
                    },
                )
                assert resp_reg.status_code == 201, f"Expected 201 for /register, got {resp_reg.status_code}: {resp_reg.text}"
                reg_data = resp_reg.json()
                assert "access_token" in reg_data
                assert reg_data["role"] == "developer"

                # 2. Login
                resp_login = await client.post(
                    "/v1/auth/login",
                    json={
                        "email": test_email,
                        "password": test_password,
                    },
                )
                assert resp_login.status_code == 200, f"Expected 200 for /login, got {resp_login.status_code}: {resp_login.text}"
                login_data = resp_login.json()
                token = login_data["access_token"]

                # 3. Decode JWT and verify signature
                decoded = jwt.decode(
                    token,
                    settings.jwt_secret_key,
                    algorithms=[settings.jwt_algorithm],
                    options={"verify_aud": False},
                )
                assert decoded["sub"] == str(reg_data["user_id"])
                assert decoded["tenant_id"] == str(reg_data["tenant_id"])

                # 4. Token endpoint alias
                resp_token = await client.post(
                    "/v1/auth/token",
                    json={
                        "email": test_email,
                        "password": test_password,
                    },
                )
                assert resp_token.status_code == 200, f"Expected 200 for /token, got {resp_token.status_code}"
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_3_local_auth_enabled_in_production_emits_critical_log(monkeypatch):
    """
    Test 3: With VIGIL_ENV=production and VIGIL_ALLOW_LOCAL_AUTH=True,
    application startup succeeds and logger.critical is called with a message
    containing 'prototype local auth'.
    """
    settings = get_settings()
    prod_local_settings = settings.model_copy(
        update={
            "environment": "production",
            "allow_local_auth": True,
            "sandbox_runtime_type": "gvisor",
            "allow_unsafe_sandbox_fallback": False,
            "sandbox_image_digest": "sha256:" + "a" * 64,
        }
    )

    with patch("app.main.settings", prod_local_settings), \
         patch("app.main.create_tables", new_callable=AsyncMock), \
         patch("app.sandbox.gvisor.verify_runsc_available"), \
         patch("app.sandbox.gvisor.verify_sandbox_image"), \
         patch("app.main.logger.critical") as mock_critical:

        async with lifespan(app):
            # Startup must succeed without raising RuntimeError
            assert mock_critical.called, "logger.critical must be called when local auth is enabled in production"
            # Verify the log message contains 'prototype local auth'
            critical_messages = [call.args[0] for call in mock_critical.call_args_list if call.args]
            assert any("prototype local auth" in msg.lower() for msg in critical_messages), (
                f"Expected warning containing 'prototype local auth', got: {critical_messages}"
            )
