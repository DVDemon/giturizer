"""run progress: stage, progress, counters (with backfill)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-24

"""
import json

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("stage", sa.String(length=32), nullable=True))
    op.add_column(
        "analysis_runs",
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("technologies_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("services_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("api_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.execute(
        "UPDATE analysis_runs SET stage = 'done', progress = 100 WHERE status = 'done'"
    )
    op.execute("UPDATE analysis_runs SET stage = 'failed' WHERE status = 'failed'")
    op.execute(
        """
        UPDATE analysis_runs
        SET technologies_count = COALESCE(
                (SELECT json_array_length(t.technologies::json)
                 FROM tech_registries t WHERE t.run_id = analysis_runs.id), 0),
            api_count = COALESCE(
                (SELECT count(*) FROM api_specs a WHERE a.run_id = analysis_runs.id), 0)
        WHERE status = 'done'
        """
    )
    connection = op.get_bind()
    snapshots = connection.execute(
        sa.text("SELECT run_id, workspace FROM architecture_snapshots")
    ).fetchall()
    for run_id, workspace in snapshots:
        data = workspace if isinstance(workspace, dict) else json.loads(workspace)
        services = sum(
            len(system.get("containers", []))
            for system in data.get("model", {}).get("softwareSystems", [])
        )
        connection.execute(
            sa.text(
                "UPDATE analysis_runs SET services_count = :services WHERE id = :run_id"
            ),
            {"services": services, "run_id": run_id},
        )


def downgrade() -> None:
    op.drop_column("analysis_runs", "api_count")
    op.drop_column("analysis_runs", "services_count")
    op.drop_column("analysis_runs", "technologies_count")
    op.drop_column("analysis_runs", "progress")
    op.drop_column("analysis_runs", "stage")
