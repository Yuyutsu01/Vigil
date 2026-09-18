"""Phase 5 (M5) schema additions: Multi-Agent Orchestration and Governed Learning Loop.

Revision ID: 005_phase5_m5
Revises: 004_phase4_m4
Create Date: 2026-09-19 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "005_phase5_m5"
down_revision: Union[str, None] = "004_phase4_m4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Expand audit_action enum on PostgreSQL
    if bind.dialect.name == "postgresql":
        new_actions = [
            "LEARNING_CONSENT_GRANTED",
            "LEARNING_CONSENT_REVOKED",
            "FEEDBACK_DISPOSITION_RECORDED",
            "LEARNING_INDEX_PURGED",
            "AGENT_EXECUTION_STARTED",
            "AGENT_EXECUTION_COMPLETED",
            "AGENT_EXECUTION_FAILED",
            "AGENT_PERMISSION_DENIED",
            "AGENT_BUDGET_EXCEEDED",
            "TENANT_DAILY_BUDGET_EXCEEDED",
        ]
        for action in new_actions:
            op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'")

    # 2. Create learning_disposition_indices table
    op.create_table(
        "learning_disposition_indices",
        sa.Column("index_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vector_index_name", sa.String(128), nullable=False),
        sa.Column("entry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_purged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_learning_disposition_indices_tenant_id",
        "learning_disposition_indices",
        ["tenant_id"],
    )

    # 3. Create agent_coordination_runs table
    op.create_table(
        "agent_coordination_runs",
        sa.Column("coordination_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "review_run_id",
            sa.Uuid(),
            sa.ForeignKey("review_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(32), server_default="running", nullable=False),
        sa.Column("total_tokens_consumed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_wall_clock_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_agents", _JSON, server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_agent_coordination_runs_review_run_id",
        "agent_coordination_runs",
        ["review_run_id"],
    )
    op.create_index(
        "ix_agent_coordination_runs_tenant_id",
        "agent_coordination_runs",
        ["tenant_id"],
    )

    # 4. Create agent_task_executions table
    op.create_table(
        "agent_task_executions",
        sa.Column("task_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "coordination_id",
            sa.Uuid(),
            sa.ForeignKey("agent_coordination_runs.coordination_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="running", nullable=False),
        sa.Column("tokens_consumed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("partial_output", _JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_agent_task_executions_coordination_id",
        "agent_task_executions",
        ["coordination_id"],
    )

    # 5. Alter tenants table: add daily_cost_limit_dollars
    op.add_column(
        "tenants",
        sa.Column("daily_cost_limit_dollars", sa.Float(), server_default="50.0", nullable=False),
    )

    # 6. Alter repository_policies table: add specialist agent flags
    op.add_column(
        "repository_policies",
        sa.Column("enable_specialist_risk_scoring", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "repository_policies",
        sa.Column("enable_dependency_risk", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "repository_policies",
        sa.Column("enable_dataflow_investigation", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "repository_policies",
        sa.Column("enable_test_generation_agent", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "repository_policies",
        sa.Column("enable_executive_summary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "repository_policies",
        sa.Column("enable_feedback_learning", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    # 7. Alter finding_feedback table: add reason_category, indexed_for_learning, learning_precedent_id with FK (B4)
    with op.batch_alter_table("finding_feedback") as batch_op:
        batch_op.add_column(
            sa.Column("reason_category", sa.String(64), nullable=True),
        )
        batch_op.add_column(
            sa.Column("indexed_for_learning", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        )
        batch_op.add_column(
            sa.Column(
                "learning_precedent_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "learning_disposition_indices.index_id",
                    ondelete="SET NULL",
                    name="fk_feedback_learning_precedent",
                ),
                nullable=True,
            ),
        )


def downgrade() -> None:
    # 1. Drop finding_feedback additions
    with op.batch_alter_table("finding_feedback") as batch_op:
        batch_op.drop_constraint("fk_feedback_learning_precedent", type_="foreignkey")
        batch_op.drop_column("learning_precedent_id")
        batch_op.drop_column("indexed_for_learning")
        batch_op.drop_column("reason_category")

    # 2. Drop repository_policies flags
    with op.batch_alter_table("repository_policies") as batch_op:
        batch_op.drop_column("enable_feedback_learning")
        batch_op.drop_column("enable_executive_summary")
        batch_op.drop_column("enable_test_generation_agent")
        batch_op.drop_column("enable_dataflow_investigation")
        batch_op.drop_column("enable_dependency_risk")
        batch_op.drop_column("enable_specialist_risk_scoring")

    # 3. Drop tenants daily_cost_limit_dollars
    with op.batch_alter_table("tenants") as batch_op:
        batch_op.drop_column("daily_cost_limit_dollars")

    # 4. Drop tables in reverse order
    op.drop_index("ix_agent_task_executions_coordination_id", table_name="agent_task_executions")
    op.drop_table("agent_task_executions")

    op.drop_index("ix_agent_coordination_runs_tenant_id", table_name="agent_coordination_runs")
    op.drop_index("ix_agent_coordination_runs_review_run_id", table_name="agent_coordination_runs")
    op.drop_table("agent_coordination_runs")

    op.drop_index("ix_learning_disposition_indices_tenant_id", table_name="learning_disposition_indices")
    op.drop_table("learning_disposition_indices")
