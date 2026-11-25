import shutil
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
from archdiscovery.pipeline.annotations_extract import extract_annotation_specs
from archdiscovery.pipeline.deployment_extract import extract_deployment
from archdiscovery.pipeline.dispatch import (
    dispatch_archguard_analyzer,
    dispatch_cpp_analyzer,
    dispatch_syntax_analyzer,
)
from archdiscovery.pipeline.graphql_extract import extract_graphql_specs
from archdiscovery.pipeline.grpc_extract import extract_grpc_specs
from archdiscovery.pipeline.model import build_model
from archdiscovery.pipeline.openapi_extract import extract_openapi_specs
from archdiscovery.pipeline.report import build_report
from archdiscovery.pipeline.structurizr import (
    generate_dsl,
    generate_json,
    validate_workspace,
)
from archdiscovery.pipeline.tech_detect import detect_technologies
from archdiscovery.vcs.clone import clone_repository, detect_default_branch

CloneFn = Callable[[str, str, str | None, Path], str]
DispatchFn = Callable[[Path, Path], dict]
ArchguardDispatchFn = Callable[[Path, Path, list[str]], dict]
SyntaxDispatchFn = Callable[[Path, Path, list[str]], dict]

SYNTAX_LANGUAGES = {
    "Java": "java",
    "JavaScript/TypeScript": "typescript",
    "Python": "python",
}

ARCHGUARD_LANGUAGES = {
    "Java": "Java",
    "Kotlin": "Kotlin",
    "C#": "CSharp",
    "JavaScript/TypeScript": "TypeScript",
    "Python": "Python",
    "Go": "Golang",
}


def _advance(
    session: Session,
    run: AnalysisRun,
    *,
    stage: str | None = None,
    progress: int | None = None,
    **counters: int,
) -> None:
    """Фиксирует стадию/прогресс/счётчики запуска для UI."""
    if stage is not None:
        run.stage = stage
    if progress is not None:
        run.progress = progress
    for name, value in counters.items():
        setattr(run, name, value)
    session.commit()


def _decrypt_token(project: Project) -> str | None:
    if not project.token_encrypted:
        return None
    return TokenCipher(settings.token_encryption_key).decrypt(project.token_encrypted)


def execute_run(
    session: Session,
    run_id,
    *,
    data_dir: Path | None = None,
    clone: CloneFn = clone_repository,
    dispatch: DispatchFn = dispatch_cpp_analyzer,
    archguard_dispatch: ArchguardDispatchFn | None = None,
    syntax_dispatch: SyntaxDispatchFn | None = None,
    keep_repos: bool | None = None,
) -> AnalysisRun | None:
    """Клон → детект → анализаторы → API/deployment → JSON-отчёт/C4."""
    run = session.get(AnalysisRun, run_id)
    if run is None:
        return None
    project = session.get(Project, run.project_id)
    if project is None:
        return None

    run.status = RunStatus.running
    run.started_at = datetime.now(UTC)
    session.commit()
    _advance(session, run, stage="clone", progress=3)

    cleanup_repo = not (settings.keep_repos if keep_repos is None else keep_repos)

    base = Path(data_dir or settings.data_dir)
    repo_path = base / "repos" / str(run.id)
    artifacts_dir = base / "artifacts" / str(run.id)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []

    try:
        token = _decrypt_token(project)
        branch = project.default_branch or detect_default_branch(project.repo_url, token)
        if project.default_branch is None:
            project.default_branch = branch
            session.commit()
        run.commit_sha = clone(project.repo_url, branch, token, repo_path)
        session.commit()
        _advance(session, run, stage="detect", progress=15)

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
        _advance(
            session,
            run,
            stage="analyzers",
            progress=30,
            technologies_count=len(technologies),
        )

        syntax_languages = sorted(
            {
                SYNTAX_LANGUAGES[name]
                for name in {technology.name for technology in technologies}
                if name in SYNTAX_LANGUAGES
            }
        )
        api_flows: list[dict] = []
        if syntax_languages:
            try:
                dispatcher = syntax_dispatch or dispatch_syntax_analyzer
                syntax_artifact = dispatcher(repo_path, artifacts_dir, syntax_languages)
                session.add(
                    RunArtifact(
                        run_id=run.id,
                        kind="syntax",
                        path=str(artifacts_dir / "syntax.json"),
                        content=syntax_artifact,
                    )
                )
                session.commit()
                if isinstance(syntax_artifact, dict):
                    api_flows = syntax_artifact.get("outbound_calls", [])
            except Exception as exc:  # noqa: BLE001 - сбой инструмента не валит пайплайн
                warnings.append(f"syntax analyzer: {exc}")

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
        _advance(session, run, progress=45)

        detected_names = {technology.name for technology in technologies}
        if "Go" in detected_names and not (repo_path / "go.mod").exists():
            detected_names.discard("Go")
        archguard_languages = sorted(
            {ARCHGUARD_LANGUAGES[name] for name in detected_names if name in ARCHGUARD_LANGUAGES}
        )
        if archguard_languages:
            try:
                dispatcher = archguard_dispatch or dispatch_archguard_analyzer
                archguard_artifact = dispatcher(repo_path, artifacts_dir, archguard_languages)
                session.add(
                    RunArtifact(
                        run_id=run.id,
                        kind="archguard",
                        path=str(artifacts_dir / "archguard.json"),
                        content=archguard_artifact,
                    )
                )
                session.commit()
            except Exception as exc:  # noqa: BLE001 - сбой инструмента не валит пайплайн
                warnings.append(f"archguard: {exc}")
        _advance(session, run, progress=55)

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
        _advance(
            session,
            run,
            stage="deployment",
            progress=70,
            api_count=len(specs),
        )

        deployment = extract_deployment(repo_path)
        session.add(DeploymentModel(project_id=project.id, run_id=run.id, model=deployment))
        session.commit()
        _advance(session, run, stage="model", progress=80)

        model = build_model(
            project_name=project.name,
            technologies=tech_payload,
            api_specs=specs,
            deployment=deployment,
            cpp_artifact=cpp_artifact,
        )
        services_count = len([element for element in model.elements if element.type == "container"])
        _advance(
            session,
            run,
            stage="report",
            progress=90,
            services_count=services_count,
        )
        workspace = generate_json(model)
        validate_workspace(workspace)
        dsl = generate_dsl(model)
        report = build_report(
            technologies=tech_payload,
            api_specs=specs,
            deployment=deployment,
            api_flows=api_flows,
        )
        session.add(
            ArchitectureSnapshot(
                project_id=project.id,
                run_id=run.id,
                dsl=dsl,
                workspace=workspace,
                report=report,
            )
        )
        session.commit()
        _advance(session, run, stage="finalize", progress=95)

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

        _advance(session, run, stage="done", progress=100)
        run.status = RunStatus.done
    except Exception as exc:  # noqa: BLE001 - причину фиксируем в запуске
        run.stage = "failed"
        session.rollback()
        failed_run = session.get(AnalysisRun, run_id) or run
        failed_run.status = RunStatus.failed
        failed_run.error = str(exc)[:2000]
        run = failed_run
    finally:
        run.finished_at = datetime.now(UTC)
        session.commit()
        session.refresh(run)
        if cleanup_repo:
            shutil.rmtree(repo_path, ignore_errors=True)

    return run
