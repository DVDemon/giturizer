"""architecture_snapshots

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-24

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "architecture_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("dsl", sa.Text(), nullable=False),
        sa.Column("workspace", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_architecture_snapshots_project_id", "architecture_snapshots", ["project_id"]
    )
    op.create_index(
        "ix_architecture_snapshots_run_id", "architecture_snapshots", ["run_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_architecture_snapshots_run_id", table_name="architecture_snapshots")
    op.drop_index(
        "ix_architecture_snapshots_project_id", table_name="architecture_snapshots"
    )
    op.drop_table("architecture_snapshots")
