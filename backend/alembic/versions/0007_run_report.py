"""architecture_snapshots.report

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-25

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "architecture_snapshots",
        sa.Column("report", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("architecture_snapshots", "report")
