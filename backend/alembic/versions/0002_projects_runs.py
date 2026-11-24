"""projects and analysis_runs

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-24

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("gitlab_url", sa.String(length=1024), nullable=False),
        sa.Column("default_branch", sa.String(length=255), nullable=False),
        sa.Column("gitlab_token_encrypted", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "queued",
                "running",
                "done",
                "failed",
                name="run_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("commit_sha", sa.String(length=64), nullable=True),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analysis_runs_project_id", "analysis_runs", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_analysis_runs_project_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_table("projects")
