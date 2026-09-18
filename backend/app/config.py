"""
Vigil Backend Configuration
Pydantic Settings with RuntimeSettings for agent budget/deadline enforcement.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class RuntimeSettings(BaseSettings):
    """
    Agent execution budget and deadline parameters.
    All values are configurable via environment variables.
    """

    # Maximum LLM tokens allowed per review run (input + output combined estimate)
    token_budget_per_run: int = Field(
        default=50_000,
        alias="VIGIL_TOKEN_BUDGET_PER_RUN",
    )

    # Maximum wall-clock seconds per run (aligned with NFR-001 p95=60s target)
    wall_clock_deadline_seconds: int = Field(
        default=60,
        alias="VIGIL_WALL_CLOCK_DEADLINE_SECONDS",
    )

    # Maximum iterations in the inner agent loop
    max_agent_iterations: int = Field(
        default=8,
        alias="VIGIL_MAX_AGENT_ITERATIONS",
    )

    # Per-capability node timeout in seconds
    per_node_timeout_seconds: int = Field(
        default=15,
        alias="VIGIL_PER_NODE_TIMEOUT_SECONDS",
    )

    model_config = {"populate_by_name": True, "env_file": ".env"}


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Vigil"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, alias="VIGIL_DEBUG")
    environment: str = Field(default="development", alias="VIGIL_ENV")

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://vigil:vigil@localhost:5432/vigil",
        alias="DATABASE_URL",
    )

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # ── JWT ──────────────────────────────────────────────────────────────────
    jwt_secret_key: str = Field(
        default="CHANGE_ME_BEFORE_PRODUCTION_USE_32_BYTES_MIN",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=60, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES"
    )

    # ── Consent ───────────────────────────────────────────────────────────────
    # Current consent policy version. Consent records with an older version are rejected.
    current_consent_version: str = Field(
        default="1.0", alias="VIGIL_CONSENT_POLICY_VERSION"
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    cors_origins: List[str] = Field(
        default=["http://localhost:3000"],
        alias="VIGIL_CORS_ORIGINS",
    )

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    # Per-tenant: requests per minute
    rate_limit_tenant_per_minute: int = Field(
        default=60, alias="VIGIL_RATE_LIMIT_TENANT_PER_MINUTE"
    )
    # Per-user: requests per minute
    rate_limit_user_per_minute: int = Field(
        default=20, alias="VIGIL_RATE_LIMIT_USER_PER_MINUTE"
    )

    # ── LLM Provider ─────────────────────────────────────────────────────────
    # "mock" | "openai" | "anthropic" | "google"
    llm_provider: str = Field(default="mock", alias="VIGIL_LLM_PROVIDER")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    llm_model_name: str = Field(default="gpt-4o-mini", alias="VIGIL_LLM_MODEL")

    # ── Retention defaults ────────────────────────────────────────────────────
    source_artifact_retention_days: int = Field(
        default=30, alias="VIGIL_SOURCE_RETENTION_DAYS"
    )
    findings_retention_days: int = Field(
        default=90, alias="VIGIL_FINDINGS_RETENTION_DAYS"
    )

    # ── Max upload size ───────────────────────────────────────────────────────
    max_upload_bytes: int = Field(
        default=256 * 1024,  # 250 KB with small buffer
        alias="VIGIL_MAX_UPLOAD_BYTES",
    )

    # ── Runtime settings ─────────────────────────────────────────────────────
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v  # type: ignore[return-value]

    model_config = {"populate_by_name": True, "env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
