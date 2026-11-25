from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.db.models import (
    AnalysisRun,
    ApiSpec,
    ArchitectureSnapshot,
    DeploymentModel,
    TechRegistry,
)
from archdiscovery.pipeline.report import build_report
from archdiscovery.services.errors import NotFoundError


def get_run_report(session: Session, run_id: Any) -> dict[str, Any]:
    """Возвращает единый JSON-отчёт; для старых запусков собирает и кеширует его."""
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")

    snapshot = session.scalars(
        select(ArchitectureSnapshot).where(ArchitectureSnapshot.run_id == run_id)
    ).first()
    if snapshot is not None and snapshot.report:
        return snapshot.report

    tech_registry = session.scalars(
        select(TechRegistry)
        .where(TechRegistry.run_id == run_id)
        .order_by(TechRegistry.created_at.desc())
    ).first()
    api_specs = session.scalars(
        select(ApiSpec).where(ApiSpec.run_id == run_id).order_by(ApiSpec.id)
    ).all()
    deployment_model = session.scalars(
        select(DeploymentModel).where(DeploymentModel.run_id == run_id)
    ).first()

    report = build_report(
        technologies=tech_registry.technologies if tech_registry else [],
        api_specs=[{"kind": spec.kind, "name": spec.name, "spec": spec.spec} for spec in api_specs],
        deployment=deployment_model.model if deployment_model else {},
    )
    if snapshot is not None:
        snapshot.report = report
        session.commit()
    return report
