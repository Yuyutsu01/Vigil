"""
Vigil Phase 1 — FastAPI application entry point.
Registers all middleware, routers, and startup/shutdown hooks.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import time

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import v1_router
from app.api.auth_context_middleware import AuthContextMiddleware
from app.api.rate_limit import RateLimitMiddleware
from app.api.idempotency import IdempotencyMiddleware
from app.config import get_settings
from app.database import create_tables
from app.redis_client import check_redis_health
from app.services.redaction_service import RedactionFilter

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Attach redaction filter to root logger
_root_logger = logging.getLogger()
_root_logger.addFilter(RedactionFilter())

logger = logging.getLogger(__name__)
from arq import create_pool
from arq.connections import RedisSettings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Vigil v1.0.0 starting up (env=%s)", settings.environment)
    if settings.environment in {"development", "test"}:
        await create_tables()
        logger.info("Database tables created/verified")

    # Log active LLM provider
    from app.agents.llm_provider import get_provider
    provider = get_provider(
        settings.llm_provider,
        api_key=settings.groq_api_key if settings.llm_provider == "groq" else settings.openai_api_key,
        model_name=settings.llm_model_name,
    )
    logger.info("Active LLM provider: %s", provider.provider_name)

    # Phase 4 Sandbox Security & Runtime Probes [H1, H5, H6, IC10]
    app.state.sandbox_available = False
    if settings.environment == "production":
        if settings.sandbox_runtime_type != "gvisor":
            raise RuntimeError("Production requires sandbox_runtime_type='gvisor'")
        if settings.allow_unsafe_sandbox_fallback:
            raise RuntimeError("Production forbids allow_unsafe_sandbox_fallback=True")
        if not settings.sandbox_image_digest:
            raise RuntimeError("Production requires VIGIL_SANDBOX_IMAGE_DIGEST to be pinned and non-empty")
        from app.sandbox.gvisor import verify_runsc_available, verify_sandbox_image
        verify_runsc_available(settings)
        verify_sandbox_image(settings)
        app.state.sandbox_available = True
    elif settings.environment == "development":
        app.state.sandbox_available = False
        try:
            from app.sandbox.gvisor import verify_runsc_available, verify_sandbox_image
            verify_runsc_available(settings)
            verify_sandbox_image(settings)
            app.state.sandbox_available = True
        except RuntimeError as e:
            logger.warning(
                "Sandbox runtime unavailable in development: %s. "
                "Patch validation endpoints will return 503.",
                e,
            )
    else:
        # test environment: default False to prevent false-positive assumptions [R1, H1]
        app.state.sandbox_available = False

    # Singleton ARQ connection pool attached to app.state (H1)
    try:
        app.state.arq_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        logger.info("ARQ connection pool initialized on app.state")
    except Exception as e:
        logger.warning("Could not initialize ARQ pool in lifespan: %s", e)
        app.state.arq_pool = None

    yield

    logger.info("Vigil shutting down")
    if getattr(app.state, "arq_pool", None) is not None:
        try:
            if hasattr(app.state.arq_pool, "aclose"):
                await app.state.arq_pool.aclose()
            else:
                await app.state.arq_pool.close()
            logger.info("ARQ connection pool closed")
        except Exception as e:
            logger.warning("Error closing ARQ pool: %s", e)


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    lifespan=lifespan,
    title="Vigil — Agentic Code Review API",
    description=(
        "Phase 1 (M1) prototype of the Vigil agentic code review and security assistant. "
        "Detects security vulnerabilities and quality issues in Python, JavaScript, and TypeScript. "
        "NEVER executes submitted code."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.state.sandbox_available = True

# ── Middleware Registration ───────────────────────────────────────────────────
# Starlette wraps middleware in reverse registration order: app.user_middleware is
# traversed in reverse when constructing the ASGI middleware stack.
# Therefore, middleware registered LAST executes FIRST on the incoming request path.
#
# Request path order:
#   1. AuthContextMiddleware (parses Bearer JWT, populates request.state.tenant_id/user_id)
#   2. RateLimitMiddleware (enforces per-tenant and per-user sliding window via Redis)
#   3. IdempotencyMiddleware (intercepts duplicate POST /v1/reviews for same tenant + source)
#   4. CORSMiddleware (handles CORS headers / preflight requests)
#   5. Endpoint dependencies & handlers (get_auth_context validates and enforces authorization)
#
# Response path order is the reverse of request path order.
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthContextMiddleware)

# CORSMiddleware registered LAST so it wraps as the outermost layer and intercepts all preflights
cors_list = list(settings.cors_origins) if isinstance(settings.cors_origins, list) else [settings.cors_origins]
for origin in ["http://localhost:3000", "http://127.0.0.1:3000"]:
    if origin not in cors_list:
        cors_list.append(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Vigil-Idempotent", "Retry-After"],
)

# ── Request ID / timing middleware ────────────────────────────────────────────
@app.middleware("http")
async def add_request_id(request: Request, call_next) -> Response:
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start = time.time()
    response = await call_next(request)
    elapsed_ms = int((time.time() - start) * 1000)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(v1_router)


# ── Health endpoint ───────────────────────────────────────────────────────────
@app.get("/health", tags=["infra"], summary="Liveness and readiness probe")
async def health() -> dict:
    redis_ok = await check_redis_health()
    return {
        "status": "ok",
        "version": "1.0.0",
        "redis": "ok" if redis_ok else "degraded",
    }


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": "internal_server_error", "message": "An unexpected error occurred"},
    )
