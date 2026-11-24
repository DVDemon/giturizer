import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.db.models import AnalysisRun, Project, RunStatus
from archdiscovery.schemas.run import RunCreate
from archdiscovery.services.errors import DispatchError, NotFoundError

Publisher = Callable[[uuid.UUID], None]


class RunService:
    def __init__(self, session: Session, publisher: Publisher) -> None:
        self._session = session
        self._publisher = publisher

    def create(self, project_id: uuid.UUID, payload: RunCreate) -> AnalysisRun:
        project = self._session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")

        run = AnalysisRun(
            project_id=project.id,
            commit_sha=payload.commit_sha,
            config=payload.config,
        )
        self._session.add(run)
        self._session.commit()
        self._session.refresh(run)

        try:
            self._publisher(run.id)
        except Exception as exc:  # noqa: BLE001 - любая ошибка брокера
            run.status = RunStatus.failed
            run.error = f"failed to enqueue: {exc}"
            self._session.commit()
            raise DispatchError(str(exc)) from exc

        return run

    def get(self, run_id: uuid.UUID) -> AnalysisRun:
        run = self._session.get(AnalysisRun, run_id)
        if run is None:
            raise NotFoundError(f"run {run_id} not found")
        return run

    def list_for_project(
        self, project_id: uuid.UUID, skip: int = 0, limit: int = 100
    ) -> list[AnalysisRun]:
        project = self._session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        stmt = (
            select(AnalysisRun)
            .where(AnalysisRun.project_id == project_id)
            .order_by(AnalysisRun.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(self._session.scalars(stmt))


def execute_stub(session: Session, run_id: uuid.UUID) -> AnalysisRun | None:
    """Заглушка P1: переводит запуск queued → running → done.

    В P2 здесь будет реальный пайплайн анализа.
    """
    run = session.get(AnalysisRun, run_id)
    if run is None:
        return None

    run.status = RunStatus.running
    run.started_at = datetime.now(UTC)
    session.commit()

    run.status = RunStatus.done
    run.finished_at = datetime.now(UTC)
    session.commit()
    session.refresh(run)
    return run
