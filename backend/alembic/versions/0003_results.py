"""tech_registries, api_specs, deployment_models, run_artifacts

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-24

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    op.create_table(
        "tech_registries",
        sa.Column("technologies", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_columns(),
    )
    op.create_index("ix_tech_registries_project_id", "tech_registries", ["project_id"])
    op.create_index("ix_tech_registries_run_id", "tech_registries", ["run_id"])

    op.create_table(
        "api_specs",
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=1024), nullable=False),
        sa.Column("spec", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_columns(),
    )
    op.create_index("ix_api_specs_project_id", "api_specs", ["project_id"])
    op.create_index("ix_api_specs_run_id", "api_specs", ["run_id"])

    op.create_table(
        "deployment_models",
        sa.Column("model", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        *_common_columns(),
    )
    op.create_index("ix_deployment_models_project_id", "deployment_models", ["project_id"])
    op.create_index("ix_deployment_models_run_id", "deployment_models", ["run_id"])

    op.create_table(
        "run_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_run_artifacts_run_id", "run_artifacts", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_run_artifacts_run_id", table_name="run_artifacts")
    op.drop_table("run_artifacts")
    op.drop_index("ix_deployment_models_run_id", table_name="deployment_models")
    op.drop_index("ix_deployment_models_project_id", table_name="deployment_models")
    op.drop_table("deployment_models")
    op.drop_index("ix_api_specs_run_id", table_name="api_specs")
    op.drop_index("ix_api_specs_project_id", table_name="api_specs")
    op.drop_table("api_specs")
    op.drop_index("ix_tech_registries_run_id", table_name="tech_registries")
    op.drop_index("ix_tech_registries_project_id", table_name="tech_registries")
    op.drop_table("tech_registries")
