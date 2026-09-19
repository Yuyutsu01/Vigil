"""
Vigil Backend Configuration
Pydantic Settings with RuntimeSettings for agent budget/deadline enforcement.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, List, Union

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
    cors_origins: Union[str, List[str]] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
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

    # ── Phase 3 GitHub Integration (FR-103, FR-104) ─────────────────────────
    github_app_id: int | None = Field(default=None, alias="GITHUB_APP_ID")
    github_app_private_key_path: str | None = Field(
        default=None, alias="GITHUB_APP_PRIVATE_KEY_PATH"
    )
    github_app_webhook_secret: str | None = Field(
        default=None, alias="GITHUB_APP_WEBHOOK_SECRET"
    )
    github_app_webhook_secret_previous: str | None = Field(
        default=None, alias="GITHUB_APP_WEBHOOK_SECRET_PREVIOUS"
    )
    github_app_slug: str = Field(
        default="vigil-security", alias="GITHUB_APP_SLUG"
    )
    github_api_base: str = Field(
        default="https://api.github.com", alias="GITHUB_API_BASE"
    )
    github_api_base_url: str = Field(
        default="https://api.github.com", alias="GITHUB_API_BASE_URL"
    )
    github_diff_max_files: int = Field(
        default=1000, alias="GITHUB_DIFF_MAX_FILES"
    )

    # ── Phase 3 Repository Review Aggregated Budget & Cost Guard ───────────
    repo_review_max_llm_calls: int = Field(
        default=50, alias="REPO_REVIEW_MAX_LLM_CALLS"
    )
    repo_review_max_total_tokens: int = Field(
        default=500_000, alias="REPO_REVIEW_MAX_TOTAL_TOKENS"
    )
    repo_review_max_wall_clock_seconds: int = Field(
        default=600, alias="REPO_REVIEW_MAX_WALL_CLOCK_SECONDS"
    )
    repo_review_max_cost_usd: float = Field(
        default=5.0, alias="REPO_REVIEW_MAX_COST_USD"
    )
    repo_review_input_cost_per_token: float = Field(
        default=0.000003, alias="REPO_REVIEW_INPUT_COST_PER_TOKEN"
    )
    repo_review_output_cost_per_token: float = Field(
        default=0.000015, alias="REPO_REVIEW_OUTPUT_COST_PER_TOKEN"
    )
    llm_cost_per_1k_input_tokens: float = Field(
        default=0.003, alias="VIGIL_LLM_COST_PER_1K_INPUT_TOKENS"
    )

    # ── Phase 4 Patch Generation Caps & Rate Limits (FR-105) ─────────────────
    patch_generation_max_cost_usd: float = Field(
        default=1.00, alias="VIGIL_PATCH_MAX_COST_USD"
    )
    patch_generation_max_tokens: int = Field(
        default=100_000, alias="VIGIL_PATCH_MAX_TOKENS"
    )
    patch_generation_max_patches_per_finding: int = Field(
        default=3, alias="VIGIL_PATCH_MAX_PER_FINDING"
    )
    patch_generation_max_wall_clock_seconds: int = Field(
        default=60, alias="VIGIL_PATCH_MAX_WALL_CLOCK_SECONDS"
    )
    patch_generation_rate_limit_per_hour: int = Field(
        default=20, alias="VIGIL_PATCH_GEN_RATE_LIMIT"
    )
    patch_validation_rate_limit_per_hour: int = Field(
        default=20, alias="VIGIL_PATCH_VAL_RATE_LIMIT"
    )
    patch_apply_rate_limit_per_hour: int = Field(
        default=10, alias="VIGIL_PATCH_APPLY_RATE_LIMIT"
    )
    patch_agent_max_prompt_tokens: int = Field(
        default=8000, alias="VIGIL_PATCH_MAX_PROMPT_TOKENS"
    )

    # ── Phase 4 Sandbox Resource Controls & runsc Pins (FR-106) ──────────────
    sandbox_runtime_type: str = Field(
        default="gvisor", alias="VIGIL_SANDBOX_RUNTIME"  # gvisor | docker
    )
    sandbox_image: str = Field(
        default="vigil-sandbox:phase4", alias="VIGIL_SANDBOX_IMAGE"
    )
    sandbox_image_digest: str = Field(
        default="", alias="VIGIL_SANDBOX_IMAGE_DIGEST"
    )
    runsc_minimum_version: str = Field(
        default="20240903.0", alias="VIGIL_RUNSC_MIN_VERSION"
    )
    runsc_binary_path: str = Field(
        default="/usr/local/bin/runsc", alias="VIGIL_RUNSC_PATH"
    )
    sandbox_max_cpu_cores: float = Field(
        default=1.0, alias="VIGIL_SANDBOX_MAX_CPU"
    )
    sandbox_memory_limit_mb: int = Field(
        default=512, alias="VIGIL_SANDBOX_MAX_MEMORY_MB"
    )
    sandbox_disk_limit_mb: int = Field(
        default=1024, alias="VIGIL_SANDBOX_MAX_DISK_MB"
    )
    sandbox_command_timeout_seconds: int = Field(
        default=120, alias="VIGIL_SANDBOX_COMMAND_TIMEOUT"
    )
    sandbox_total_lifetime_seconds: int = Field(
        default=600, alias="VIGIL_SANDBOX_TOTAL_LIFETIME"
    )
    allow_unsafe_sandbox_fallback: bool = Field(
        default=False, alias="VIGIL_ALLOW_UNSAFE_SANDBOX_FALLBACK"
    )
    validation_log_dir: str = Field(
        default="/var/lib/vigil/validation_logs", alias="VIGIL_VALIDATION_LOG_DIR"
    )

    # ── Phase 4 PR Review Agent Caps & Publication Controls (FR-107) ──────────
    pr_review_generation_max_cost_usd: float = Field(
        default=0.50, alias="VIGIL_PR_REVIEW_MAX_COST_USD"
    )
    pr_review_generation_max_tokens: int = Field(
        default=50_000, alias="VIGIL_PR_REVIEW_MAX_TOKENS"
    )
    pr_review_generate_rate_limit_per_hour: int = Field(
        default=20, alias="VIGIL_PR_REVIEW_GEN_RATE_LIMIT"
    )
    pr_review_publish_rate_limit_per_hour: int = Field(
        default=10, alias="VIGIL_PR_REVIEW_PUB_RATE_LIMIT"
    )
    pr_comment_rate_limit_per_hour: int = Field(
        default=5, alias="VIGIL_PR_COMMENT_RATE_LIMIT"
    )
    pr_comment_max_chars: int = Field(
        default=4096, alias="VIGIL_PR_COMMENT_MAX_CHARS"
    )
    draft_pr_review_retention_days: int = Field(
        default=30, alias="VIGIL_DRAFT_PR_RETENTION_DAYS"
    )

    # ── Phase 5 Multi-Agent Orchestration & Governed Learning (FR-108, FR-109) ─
    killswitch_key: str = Field(
        default="vigil:killswitch:multi_agent", alias="VIGIL_KILLSWITCH_KEY"
    )
    learning_policy_version: str = Field(
        default="1.0", alias="VIGIL_LEARNING_POLICY_VERSION"
    )
    tenant_daily_budget_dollars: float = Field(
        default=50.0, alias="VIGIL_TENANT_DAILY_BUDGET_DOLLARS"
    )
    aggregate_review_token_budget: int = Field(
        default=200_000, alias="VIGIL_AGGREGATE_REVIEW_TOKEN_BUDGET"
    )
    aggregate_review_deadline_seconds: int = Field(
        default=90, alias="VIGIL_AGGREGATE_REVIEW_DEADLINE_SECONDS"
    )
    rag_match_threshold: float = Field(
        default=0.82, alias="VIGIL_RAG_MATCH_THRESHOLD"
    )
    queue_shed_threshold_llm: int = Field(
        default=500, alias="VIGIL_QUEUE_SHED_THRESHOLD_LLM"
    )
    queue_shed_threshold_cpu: int = Field(
        default=250, alias="VIGIL_QUEUE_SHED_THRESHOLD_CPU"
    )
    queue_shed_threshold_sandbox: int = Field(
        default=50, alias="VIGIL_QUEUE_SHED_THRESHOLD_SANDBOX"
    )
    arq_llm_worker_count: int = Field(
        default=32, alias="VIGIL_ARQ_LLM_WORKER_COUNT"
    )
    arq_cpu_worker_count: int = Field(
        default=16, alias="VIGIL_ARQ_CPU_WORKER_COUNT"
    )
    arq_sandbox_worker_count: int = Field(
        default=4, alias="VIGIL_ARQ_SANDBOX_WORKER_COUNT"
    )

    # ── Runtime settings ─────────────────────────────────────────────────────
    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)


    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> List[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v  # type: ignore[return-value]

    @field_validator("github_app_id", mode="before")
    @classmethod
    def parse_github_app_id(cls, v: object) -> Any:
        if v == "" or v is None:
            return None
        return v

    model_config = {"populate_by_name": True, "env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
