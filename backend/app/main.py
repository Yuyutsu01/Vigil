"""
Vigil Phase 1 — FastAPI application entry point.
Registers all middleware, routers, and startup/shutdown hooks.
"""
from __future__ import annotations

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
settings = get_settings()

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Hint"],
    expose_headers=["X-Vigil-Idempotent", "Retry-After"],
)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthContextMiddleware)

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


# ── Startup / shutdown ────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup() -> None:
    logger.info("Vigil v1.0.0 starting up (env=%s)", settings.environment)
    if settings.environment in {"development", "test"}:
        await create_tables()
        logger.info("Database tables created/verified")


@app.on_event("shutdown")
async def shutdown() -> None:
    logger.info("Vigil shutting down")


# ── Global exception handler ──────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"code": "internal_server_error", "message": "An unexpected error occurred"},
    )
