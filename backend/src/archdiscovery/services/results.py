from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.db.models import (
    AnalysisRun,
    ApiSpec,
    DeploymentModel,
    RunArtifact,
    TechRegistry,
)
from archdiscovery.services.errors import NotFoundError


def get_run_results(session: Session, run_id) -> dict:
    run = session.get(AnalysisRun, run_id)
    if run is None:
        raise NotFoundError(f"run {run_id} not found")

    technologies = session.scalars(
        select(TechRegistry).where(TechRegistry.run_id == run_id)
    ).first()
    api_specs = session.scalars(select(ApiSpec).where(ApiSpec.run_id == run_id)).all()
    deployment = session.scalars(
        select(DeploymentModel).where(DeploymentModel.run_id == run_id)
    ).first()
    artifacts = session.scalars(select(RunArtifact).where(RunArtifact.run_id == run_id)).all()

    return {
        "run": run,
        "technologies": technologies.technologies if technologies else [],
        "api_specs": [
            {"kind": spec.kind, "name": spec.name, "spec": spec.spec} for spec in api_specs
        ],
        "deployment": deployment.model if deployment else None,
        "artifacts": [
            {"kind": artifact.kind, "path": artifact.path, "content": artifact.content}
            for artifact in artifacts
        ],
    }
