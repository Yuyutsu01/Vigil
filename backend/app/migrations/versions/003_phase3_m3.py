"""Phase 3 (M3) schema additions: IntegrationCredential, RepositoryPolicy, Repository, RepositoryReview, WebhookEvent, and Finding.source_file_path.

Revision ID: 003_phase3_m3
Revises: 002_phase2_m2
Create Date: 2026-09-18 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "003_phase3_m3"
down_revision: Union[str, None] = "002_phase2_m2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Expand audit_action enum on PostgreSQL
    if bind.dialect.name == "postgresql":
        new_actions = [
            "GITHUB_APP_INSTALLED",
            "GITHUB_APP_REVOKED",
            "GITHUB_REPO_CONNECTED",
            "GITHUB_REPO_DISCONNECTED",
            "GITHUB_WEBHOOK_RECEIVED",
            "GITHUB_WEBHOOK_REJECTED",
            "GITHUB_REPO_REVIEW_STARTED",
            "GITHUB_OAUTH_STATE_INVALID",
        ]
        for action in new_actions:
            op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'")

    # 2. Add source_file_path to findings table (for multi-file repository reviews)
    with op.batch_alter_table("findings") as batch_op:
        batch_op.add_column(
            sa.Column("source_file_path", sa.String(1024), nullable=True)
        )
        batch_op.create_index("ix_findings_source_file_path", ["source_file_path"])

    # 3. integration_credentials table
    op.create_table(
        "integration_credentials",
        sa.Column("credential_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False, server_default="github"),
        sa.Column("installation_id", sa.BigInteger(), nullable=False),
        sa.Column("encrypted_private_key_ref", sa.Text(), nullable=False),
        sa.Column("scopes", _JSON, nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_integration_credentials_tenant_id", "integration_credentials", ["tenant_id"])
    op.create_index("ix_integration_credentials_installation_id", "integration_credentials", ["installation_id"])

    # 4. repository_policies table
    op.create_table(
        "repository_policies",
        sa.Column("policy_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("enabled_languages", _JSON, nullable=False),
        sa.Column("ignored_paths", _JSON, nullable=False),
        sa.Column("ignored_rules", _JSON, nullable=False),
        sa.Column("max_files_per_review", sa.Integer(), nullable=False, server_default="500"),
        sa.Column("auto_review_on_push", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("auto_review_on_pr", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("review_fork_prs", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("review_draft_prs", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_repository_policies_tenant_id", "repository_policies", ["tenant_id"])

    # 5. repositories table
    op.create_table(
        "repositories",
        sa.Column("repository_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False, server_default="github"),
        sa.Column("external_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("default_branch", sa.String(128), nullable=False, server_default="main"),
        sa.Column(
            "installation_id",
            UUID(as_uuid=True),
            sa.ForeignKey("integration_credentials.credential_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "policy_id",
            UUID(as_uuid=True),
            sa.ForeignKey("repository_policies.policy_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_connected", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "external_id", name="uq_repositories_provider_external_id"),
    )
    op.create_index("ix_repositories_tenant_id", "repositories", ["tenant_id"])
    op.create_index("ix_repositories_external_id", "repositories", ["external_id"])

    # 6. repository_reviews table
    op.create_table(
        "repository_reviews",
        sa.Column("repository_review_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "repository_id",
            UUID(as_uuid=True),
            sa.ForeignKey("repositories.repository_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "review_run_id",
            UUID(as_uuid=True),
            sa.ForeignKey("review_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ref_type", sa.String(32), nullable=False),
        sa.Column("ref_value", sa.Text(), nullable=False),
        sa.Column("scope_mode", sa.String(32), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("budget_paused_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_repository_reviews_tenant_id", "repository_reviews", ["tenant_id"])
    op.create_index("ix_repository_reviews_repository_id", "repository_reviews", ["repository_id"])
    op.create_index("ix_repository_reviews_review_run_id", "repository_reviews", ["review_run_id"])

    # 7. webhook_events table
    op.create_table(
        "webhook_events",
        sa.Column("webhook_event_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("delivery_id", sa.String(128), unique=True, nullable=False),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(32), nullable=False, server_default="github"),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
    )
    op.create_index("ix_webhook_events_delivery_id", "webhook_events", ["delivery_id"])
    op.create_index("ix_webhook_events_tenant_id", "webhook_events", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("repository_reviews")
    op.drop_table("repositories")
    op.drop_table("repository_policies")
    op.drop_table("integration_credentials")

    with op.batch_alter_table("findings") as batch_op:
        batch_op.drop_index("ix_findings_source_file_path")
        batch_op.drop_column("source_file_path")
