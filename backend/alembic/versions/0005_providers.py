"""providers: GitHub/GitLab, repo_url, nullable branch

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-24

"""
import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("provider", sa.String(length=16), nullable=False, server_default="gitlab"),
    )
    op.alter_column("projects", "gitlab_url", new_column_name="repo_url")
    op.alter_column(
        "projects", "gitlab_token_encrypted", new_column_name="token_encrypted"
    )
    op.alter_column(
        "projects",
        "default_branch",
        existing_type=sa.String(length=255),
        nullable=True,
    )
    op.execute("UPDATE projects SET provider = 'github' WHERE repo_url LIKE '%github.com%'")
    op.alter_column("projects", "provider", server_default=None)


def downgrade() -> None:
    op.alter_column(
        "projects",
        "default_branch",
        existing_type=sa.String(length=255),
        nullable=False,
        server_default="main",
    )
    op.execute("UPDATE projects SET default_branch = 'main' WHERE default_branch IS NULL")
    op.alter_column("projects", "token_encrypted", new_column_name="gitlab_token_encrypted")
    op.alter_column("projects", "repo_url", new_column_name="gitlab_url")
    op.drop_column("projects", "provider")
