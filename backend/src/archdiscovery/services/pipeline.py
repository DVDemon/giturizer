import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from archdiscovery.config import settings
from archdiscovery.crypto import TokenCipher
from archdiscovery.db.models import (
    AnalysisRun,
    ApiSpec,
    ArchitectureSnapshot,
    DeploymentModel,
    Project,
    RunArtifact,
    RunStatus,
    TechRegistry,
)
from archdiscovery.gitlab.clone import clone_repository
from archdiscovery.pipeline.annotations_extract import extract_annotation_specs
from archdiscovery.pipeline.deployment_extract import extract_deployment
from archdiscovery.pipeline.dispatch import dispatch_cpp_analyzer
from archdiscovery.pipeline.graphql_extract import extract_graphql_specs
from archdiscovery.pipeline.grpc_extract import extract_grpc_specs
from archdiscovery.pipeline.model import ArchitectureModel, build_model
from archdiscovery.pipeline.openapi_extract import extract_openapi_specs
from archdiscovery.pipeline.structurizr import (
    generate_dsl,
    generate_json,
    validate_workspace,
)
from archdiscovery.pipeline.tech_detect import detect_technologies
from archdiscovery.services.graph import write_graph

CloneFn = Callable[[str, str, str | None, Path], str]
DispatchFn = Callable[[Path, Path], dict]
GraphWriter = Callable[[uuid.UUID, ArchitectureModel], None]


def _decrypt_token(project: Project) -> str | None:
    if not project.gitlab_token_encrypted:
        return None
    return TokenCipher(settings.token_encryption_key).decrypt(project.gitlab_token_encrypted)


def execute_run(
    session: Session,
    run_id,
    *,
    data_dir: Path | None = None,
    clone: CloneFn = clone_repository,
    dispatch: DispatchFn = dispatch_cpp_analyzer,
    graph_writer: GraphWriter | None = write_graph,
) -> AnalysisRun | None:
    """Клон → детект → анализаторы → API/deployment → Structurizr → Neo4j."""
    run = session.get(AnalysisRun, run_id)
    if run is None:
        return None
    project = session.get(Project, run.project_id)
    if project is None:
        return None

    run.status = RunStatus.running
    run.started_at = datetime.now(UTC)
    session.commit()

    base = Path(data_dir or settings.data_dir)
    repo_path = base / "repos" / str(run.id)
    artifacts_dir = base / "artifacts" / str(run.id)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    try:
        token = _decrypt_token(project)
        run.commit_sha = clone(project.gitlab_url, project.default_branch, token, repo_path)
        session.commit()

        technologies = detect_technologies(repo_path)
        tech_payload = [technology.as_dict() for technology in technologies]
        session.add(
            TechRegistry(
                project_id=project.id,
                run_id=run.id,
                technologies=tech_payload,
            )
        )
        session.commit()

        cpp_artifact: dict | None = None
        if any(technology.name == "C++" for technology in technologies):
            try:
                cpp_artifact = dispatch(repo_path, artifacts_dir)
                session.add(
                    RunArtifact(
                        run_id=run.id,
                        kind="cpp",
                        path=str(artifacts_dir / "cpp.json"),
                        content=cpp_artifact,
                    )
                )
                session.commit()
            except Exception as exc:  # noqa: BLE001 - сбой инструмента не валит пайплайн
                warnings.append(f"cpp analyzer: {exc}")

        specs = [
            *extract_openapi_specs(repo_path),
            *extract_grpc_specs(repo_path),
            *extract_graphql_specs(repo_path),
            *extract_annotation_specs(repo_path),
        ]
        for spec in specs:
            session.add(
                ApiSpec(
                    project_id=project.id,
                    run_id=run.id,
                    kind=spec["kind"],
                    name=spec["name"],
                    spec=spec["spec"],
                )
            )
        session.commit()

        deployment = extract_deployment(repo_path)
        session.add(DeploymentModel(project_id=project.id, run_id=run.id, model=deployment))
        session.commit()

        model = build_model(
            project_name=project.name,
            technologies=tech_payload,
            api_specs=specs,
            deployment=deployment,
            cpp_artifact=cpp_artifact,
        )
        workspace = generate_json(model)
        validate_workspace(workspace)
        dsl = generate_dsl(model)
        session.add(
            ArchitectureSnapshot(
                project_id=project.id,
                run_id=run.id,
                dsl=dsl,
                workspace=workspace,
            )
        )
        session.commit()

        if graph_writer is not None:
            try:
                graph_writer(run.id, model)
            except Exception as exc:  # noqa: BLE001 - Neo4j не должен валить пайплайн
                warnings.append(f"neo4j: {exc}")

        if warnings:
            session.add(
                RunArtifact(
                    run_id=run.id,
                    kind="pipeline_warnings",
                    path="",
                    content={"warnings": warnings},
                )
            )
            session.commit()

        run.status = RunStatus.done
    except Exception as exc:  # noqa: BLE001 - причину фиксируем в запуске
        session.rollback()
        failed_run = session.get(AnalysisRun, run_id) or run
        failed_run.status = RunStatus.failed
        failed_run.error = str(exc)[:2000]
        run = failed_run
    finally:
        run.finished_at = datetime.now(UTC)
        session.commit()
        session.refresh(run)

    return run
