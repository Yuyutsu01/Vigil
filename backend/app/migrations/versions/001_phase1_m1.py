"""Phase 1 (M1) baseline schema migration.

Revision ID: 001_phase1_m1
Revises: None
Create Date: 2026-09-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "001_phase1_m1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enums
review_status_enum = sa.Enum(
    "pending", "running", "partial", "completed", "failed", "budget_paused", "deleted",
    name="review_status",
)
audit_action_enum = sa.Enum(
    "LOGIN", "GRANT_CONSENT", "REVOKE_CONSENT", "CREATE_REVIEW", "COMPLETE_REVIEW",
    "DELETE_REVIEW", "SUBMIT_FEEDBACK", "RATE_LIMIT_TRIGGERED", "TENANT_MISMATCH_REJECTED",
    name="audit_action",
)
finding_origin_enum = sa.Enum(
    "rule", "agent",
    name="finding_origin",
)
finding_severity_enum = sa.Enum(
    "Critical", "High", "Medium", "Low", "Info",
    name="finding_severity",
)
finding_status_enum = sa.Enum(
    "open", "accepted", "rejected", "false_positive",
    name="finding_status",
)
evidence_kind_enum = sa.Enum(
    "ast_node", "token_regex", "llm_reasoning",
    name="evidence_kind",
)


def upgrade() -> None:
    # 1. tenants table
    op.create_table(
        "tenants",
        sa.Column("tenant_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("findings_retention_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("model_policy", sa.String(64), nullable=False, server_default="mock"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 2. users table
    op.create_table(
        "users",
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("hashed_password", sa.Text(), nullable=False),
        sa.Column("role", sa.String(64), nullable=False, server_default="developer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 3. consent_records table
    op.create_table(
        "consent_records",
        sa.Column("consent_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(128), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 4. source_artifacts table
    op.create_table(
        "source_artifacts",
        sa.Column("artifact_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("language", sa.String(32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_source_artifacts_tenant_id", "source_artifacts", ["tenant_id"])

    # 5. review_runs table
    op.create_table(
        "review_runs",
        sa.Column("run_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False),
        sa.Column("artifact_id", UUID(as_uuid=True), sa.ForeignKey("source_artifacts.artifact_id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", review_status_enum, nullable=False, server_default="pending"),
        sa.Column("requested_by", UUID(as_uuid=True), nullable=False),
        sa.Column("config_version", sa.String(64), nullable=True),
        sa.Column("prompt_version", sa.String(64), nullable=True),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("parked_reason", sa.String(255), nullable=True),
    )
    op.create_index("ix_review_runs_tenant_id", "review_runs", ["tenant_id"])

    # 6. audit_events table
    op.create_table(
        "audit_events",
        sa.Column("event_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", audit_action_enum, nullable=False),
        sa.Column("target_type", sa.String(64), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])

    # 7. findings table
    op.create_table(
        "findings",
        sa.Column("finding_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("review_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("origin", finding_origin_enum, nullable=False),
        sa.Column("rule_id", sa.String(64), nullable=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", finding_severity_enum, nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("remediation", sa.Text(), nullable=False),
        sa.Column("status", finding_status_enum, nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_findings_run_id", "findings", ["run_id"])
    op.create_index("ix_findings_tenant_id", "findings", ["tenant_id"])
    op.create_index("ix_findings_fingerprint", "findings", ["fingerprint"])

    # 8. evidence table
    op.create_table(
        "evidence",
        sa.Column("evidence_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("finding_id", UUID(as_uuid=True), sa.ForeignKey("findings.finding_id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("start_col", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("end_col", sa.Integer(), nullable=True),
        sa.Column("ast_path", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.String(128), nullable=True),
        sa.Column("rule_id", sa.String(64), nullable=True),
        sa.Column("code_excerpt", sa.Text(), nullable=True),
        sa.Column("evidence_kind", evidence_kind_enum, nullable=False),
    )
    op.create_index("ix_evidence_finding_id", "evidence", ["finding_id"])

    # 9. patch_candidates table (nullable stub)
    op.create_table(
        "patch_candidates",
        sa.Column("patch_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("finding_id", UUID(as_uuid=True), sa.ForeignKey("findings.finding_id", ondelete="CASCADE"), nullable=True),
        sa.Column("base_checksum", sa.String(64), nullable=True),
        sa.Column("unified_diff", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("approval_status", sa.String(32), nullable=True),
    )

    # 10. finding_feedback table
    op.create_table(
        "finding_feedback",
        sa.Column("feedback_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("finding_id", UUID(as_uuid=True), sa.ForeignKey("findings.finding_id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("useful", sa.Boolean(), nullable=True),
        sa.Column("disposition", sa.String(32), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("finding_feedback")
    op.drop_table("patch_candidates")
    op.drop_table("evidence")
    op.drop_table("findings")
    op.drop_table("audit_events")
    op.drop_table("review_runs")
    op.drop_table("source_artifacts")
    op.drop_table("consent_records")
    op.drop_table("users")
    op.drop_table("tenants")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        evidence_kind_enum.drop(bind, checkfirst=True)
        finding_status_enum.drop(bind, checkfirst=True)
        finding_severity_enum.drop(bind, checkfirst=True)
        finding_origin_enum.drop(bind, checkfirst=True)
        audit_action_enum.drop(bind, checkfirst=True)
        review_status_enum.drop(bind, checkfirst=True)
