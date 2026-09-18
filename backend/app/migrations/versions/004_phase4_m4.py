"""Phase 4 (M4) schema additions: PatchCandidate extensions, ValidationRun, DraftPRReview, DraftPRComment, and policy fields.

Revision ID: 004_phase4_m4
Revises: 003_phase3_m3
Create Date: 2026-09-18 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "004_phase4_m4"
down_revision: Union[str, None] = "003_phase3_m3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JSON = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Expand audit_action enum on PostgreSQL
    if bind.dialect.name == "postgresql":
        new_actions = [
            "GITHUB_WRITE_MUTATION",
            "GITHUB_PATCH_APPLIED",
            "GITHUB_PATCH_APPROVED",
            "GITHUB_PATCH_ROLLBACK",
            "GITHUB_PATCH_VALIDATION_FAILED",
            "SANDBOX_SECURITY_VIOLATION",
            "SANDBOX_ESCAPE_SUSPECTED",
            "PR_REVIEW_PUBLISHED",
        ]
        for action in new_actions:
            op.execute(f"ALTER TYPE audit_action ADD VALUE IF NOT EXISTS '{action}'")

    # 2. Additive-only verification for patch_candidates (M6)
    count = bind.execute(sa.text("SELECT COUNT(*) FROM patch_candidates")).scalar()
    if count and count > 0:
        raise RuntimeError(
            f"Additive migration aborted: patch_candidates contains {count} unexpected rows."
        )

    # 3. Create Enum types if not existing
    if bind.dialect.name == "postgresql":
        op.execute(
            "DO $$ BEGIN "
            "CREATE TYPE patch_status AS ENUM ('draft', 'approved', 'withdrawn', 'validating', 'applied', 'rejected'); "
            "EXCEPTION WHEN duplicate_object THEN null; END $$;"
        )
        op.execute(
            "DO $$ BEGIN "
            "CREATE TYPE validation_verdict AS ENUM ('passed', 'failed', 'error', 'timeout'); "
            "EXCEPTION WHEN duplicate_object THEN null; END $$;"
        )
        op.execute(
            "DO $$ BEGIN "
            "CREATE TYPE draft_pr_status AS ENUM ('draft', 'approved', 'published', 'orphaned'); "
            "EXCEPTION WHEN duplicate_object THEN null; END $$;"
        )
        from sqlalchemy.dialects.postgresql import ENUM as PGEnum

        patch_status_enum = PGEnum(
            "draft", "approved", "withdrawn", "validating", "applied", "rejected",
            name="patch_status",
            create_type=False,
        )
        validation_verdict_enum = PGEnum(
            "passed", "failed", "error", "timeout",
            name="validation_verdict",
            create_type=False,
        )
        draft_status_enum = PGEnum(
            "draft", "approved", "published", "orphaned",
            name="draft_pr_status",
            create_type=False,
        )
    else:
        patch_status_enum = sa.Enum(
            "draft", "approved", "withdrawn", "validating", "applied", "rejected",
            name="patch_status",
        )
        validation_verdict_enum = sa.Enum(
            "passed", "failed", "error", "timeout",
            name="validation_verdict",
        )
        draft_status_enum = sa.Enum(
            "draft", "approved", "published", "orphaned",
            name="draft_pr_status",
        )


    # 4. Add Phase 4 columns to patch_candidates
    with op.batch_alter_table("patch_candidates") as batch_op:


        batch_op.add_column(
            sa.Column("status", patch_status_enum, nullable=False, server_default="draft")
        )
        batch_op.add_column(
            sa.Column("assumptions", sa.Text(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column("tests_to_run", _JSON, nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column(
                "approved_by",
                UUID(as_uuid=True),
                sa.ForeignKey("users.user_id", ondelete="SET NULL", name="fk_patch_candidates_approved_by"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("applied_branch", sa.String(255), nullable=True)
        )
        batch_op.add_column(
            sa.Column("applied_pr_number", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("applied_commit_sha", sa.String(40), nullable=True)
        )
        batch_op.add_column(
            sa.Column("rejection_reason", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())
        )

    # 4. Add Phase 4 columns to repository_policies
    with op.batch_alter_table("repository_policies") as batch_op:
        batch_op.add_column(
            sa.Column("allowed_ci_commands", _JSON, nullable=False, server_default="[]")
        )
        batch_op.add_column(
            sa.Column("pr_comment_publication", sa.String(32), nullable=False, server_default="human_required")
        )
        batch_op.add_column(
            sa.Column("pr_review_generation", sa.String(32), nullable=False, server_default="on_demand")
        )

    # 5. validation_runs table
    op.create_table(
        "validation_runs",
        sa.Column("validation_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "patch_candidate_id",
            UUID(as_uuid=True),
            sa.ForeignKey("patch_candidates.patch_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("verdict", validation_verdict_enum, nullable=False),
        sa.Column("checks", _JSON, nullable=False, server_default="[]"),
        sa.Column("sandbox_metadata", _JSON, nullable=False, server_default="{}"),
        sa.Column("stdout_log", sa.Text(), nullable=False, server_default=""),
        sa.Column("stderr_log", sa.Text(), nullable=False, server_default=""),
        sa.Column("log_dir_ref", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 6. draft_pr_reviews table
    op.create_table(

        "draft_pr_reviews",
        sa.Column("review_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.tenant_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "repository_id",
            UUID(as_uuid=True),
            sa.ForeignKey("repositories.repository_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("pr_number", sa.Integer(), nullable=False, index=True),
        sa.Column("status", draft_status_enum, nullable=False, server_default="draft"),
        sa.Column("summary_markdown", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # 7. draft_pr_comments table
    op.create_table(
        "draft_pr_comments",
        sa.Column("comment_id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "review_id",
            UUID(as_uuid=True),
            sa.ForeignKey("draft_pr_reviews.review_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("body", sa.String(4096), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("line", sa.Integer(), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("status", draft_status_enum, nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Drop tables
    op.drop_table("draft_pr_comments")
    op.drop_table("draft_pr_reviews")
    op.drop_table("validation_runs")

    # Remove repository_policies columns
    with op.batch_alter_table("repository_policies") as batch_op:
        batch_op.drop_column("pr_review_generation")
        batch_op.drop_column("pr_comment_publication")
        batch_op.drop_column("allowed_ci_commands")

    # Remove patch_candidates columns
    with op.batch_alter_table("patch_candidates") as batch_op:
        batch_op.drop_column("created_at")
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("applied_commit_sha")
        batch_op.drop_column("applied_pr_number")
        batch_op.drop_column("applied_branch")
        batch_op.drop_column("approved_at")
        batch_op.drop_column("approved_by")
        batch_op.drop_column("tests_to_run")
        batch_op.drop_column("assumptions")
        batch_op.drop_column("status")

    # Drop enums on postgres
    if bind.dialect.name == "postgresql":
        op.execute("DROP TYPE IF EXISTS draft_pr_status")
        op.execute("DROP TYPE IF EXISTS validation_verdict")
        op.execute("DROP TYPE IF EXISTS patch_status")
