"""Phase 2 (M2) schema additions: ToolFinding, EvaluationRun, ReportArtifact, and Finding tool origin.

Revision ID: 002_phase2_m2
Revises: 001_phase1_m1
Create Date: 2026-09-18 12:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "002_phase2_m2"
down_revision: Union[str, None] = "001_phase1_m1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# M1: Use JSONB on PostgreSQL, JSON on SQLite
_JSON = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    bind = op.get_bind()

    # B2: Dialect-aware enum expansion for finding_origin
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE finding_origin ADD VALUE IF NOT EXISTS 'tool'"
        )

    # B3: Create tool_findings table BEFORE adding foreign key from findings
    op.create_table(
        "tool_findings",
        sa.Column("tool_finding_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("review_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("tool_version", sa.String(32), nullable=False),
        sa.Column("rule_id", sa.String(128), nullable=True),
        sa.Column("severity_raw", sa.String(32), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("file_path", sa.String(1024), nullable=True),
        sa.Column("start_line", sa.Integer(), nullable=True),
        sa.Column("start_col", sa.Integer(), nullable=True),
        sa.Column("end_line", sa.Integer(), nullable=True),
        sa.Column("end_col", sa.Integer(), nullable=True),
        sa.Column("raw_evidence", _JSON, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_tool_findings_run_id", "tool_findings", ["run_id"])
    op.create_index("ix_tool_findings_tenant_id", "tool_findings", ["tenant_id"])

    # B3: Add tool-tracking columns to findings with foreign key constraint and SET NULL on delete
    with op.batch_alter_table("findings") as batch_op:
        batch_op.add_column(sa.Column("tool_name", sa.String(128), nullable=True))
        batch_op.add_column(sa.Column("tool_version", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column(
                "raw_evidence_ref",
                UUID(as_uuid=True),
                sa.ForeignKey(
                    "tool_findings.tool_finding_id",
                    ondelete="SET NULL",
                    name="fk_findings_raw_evidence_ref",
                ),
                nullable=True,
            )
        )

    # 3. Create evaluation_runs table
    op.create_table(
        "evaluation_runs",
        sa.Column("evaluation_run_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("suite", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("precision", sa.Float(), nullable=False),
        sa.Column("recall", sa.Float(), nullable=False),
        sa.Column("f1", sa.Float(), nullable=False),
        sa.Column("per_rule_breakdown", _JSON, nullable=False),
        sa.Column("metadata", _JSON, nullable=True),
    )

    # 4. Create report_artifacts table
    op.create_table(
        "report_artifacts",
        sa.Column("report_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("review_runs.run_id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("content_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_report_artifacts_run_id", "report_artifacts", ["run_id"])
    op.create_index("ix_report_artifacts_tenant_id", "report_artifacts", ["tenant_id"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("report_artifacts")
    op.drop_table("evaluation_runs")

    with op.batch_alter_table("findings") as batch_op:
        batch_op.drop_constraint("fk_findings_raw_evidence_ref", type_="foreignkey")
        batch_op.drop_column("raw_evidence_ref")
        batch_op.drop_column("tool_version")
        batch_op.drop_column("tool_name")

    op.drop_table("tool_findings")

    # Note: PostgreSQL does not support dropping enum values safely (ALTER TYPE ... DROP VALUE).
    # Leaving 'tool' in finding_origin does not affect Phase 1 rollback integrity.
