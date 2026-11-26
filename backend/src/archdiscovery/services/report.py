from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.db.models import (
    AnalysisRun,
    ApiSpec,
    ArchitectureSnapshot,
    DeploymentModel,
    Project,
    RunArtifact,
    TechRegistry,
)
from archdiscovery.pipeline.report import build_report
from archdiscovery.services.errors import NotFoundError
from archdiscovery.services.syntax_api import (
    load_syntax_handlers,
    merge_into_report,
    syntax_specs,
)


def get_run_report(session: Session, run_id: Any) -> dict[str, Any]:
    """Единый JSON-отчёт; api_flows добавляются из syntax artifact, старые снапшоты обновляются."""
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")

    snapshot = session.scalars(
        select(ArchitectureSnapshot).where(ArchitectureSnapshot.run_id == run_id)
    ).first()
    syntax_artifact = session.scalars(
        select(RunArtifact).where(
            RunArtifact.run_id == run_id,
            RunArtifact.kind == "syntax",
        )
    ).first()
    api_flows = (
        syntax_artifact.content.get("outbound_calls", [])
        if syntax_artifact is not None and isinstance(syntax_artifact.content, dict)
        else []
    )
    project = session.get(Project, run.project_id)
    service_name = project.name if project else "application"
    handlers = load_syntax_handlers(session, run_id)
    if snapshot is not None and snapshot.report:
        report = dict(snapshot.report)
        report["api_flows"] = api_flows
        merged = merge_into_report(report, handlers, service_name)
        if merged != snapshot.report:
            snapshot.report = merged
            session.commit()
        return merged

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

    existing_specs = [
        {"kind": spec.kind, "name": spec.name, "spec": spec.spec} for spec in api_specs
    ]
    syntax_specs_from_handlers = syntax_specs(
        handlers,
        service_name,
        existing_specs,
    )
    report = build_report(
        technologies=tech_registry.technologies if tech_registry else [],
        api_specs=[*existing_specs, *syntax_specs_from_handlers],
        deployment=deployment_model.model if deployment_model else {},
        api_flows=api_flows,
    )
    if snapshot is not None:
        snapshot.report = report
        session.commit()
    return report
