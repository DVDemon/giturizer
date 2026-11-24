import uuid
from datetime import datetime

from sqlalchemy import func, nullslast, or_, select
from sqlalchemy.orm import Session

from archdiscovery.crypto import TokenCipher
from archdiscovery.db.models import AnalysisRun, Project
from archdiscovery.schemas.project import ProjectCreate
from archdiscovery.services.errors import NotFoundError
from archdiscovery.vcs.provider import detect_provider


class ProjectService:
    def __init__(self, session: Session, cipher: TokenCipher) -> None:
        self._session = session
        self._cipher = cipher

    def create(self, payload: ProjectCreate) -> Project:
        repo_url = str(payload.repo_url)
        project = Project(
            name=payload.name,
            repo_url=repo_url,
            provider=detect_provider(repo_url),
            default_branch=payload.default_branch or None,
            token_encrypted=(self._cipher.encrypt(payload.token) if payload.token else None),
        )
        self._session.add(project)
        self._session.commit()
        self._session.refresh(project)
        return project

    def list_page(
        self,
        *,
        search: str | None = None,
        provider: str | None = None,
        sort: str = "last_scan_at",
        order: str = "desc",
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[int, list[tuple[Project, datetime | None]]]:
        filters = []
        if search:
            pattern = f"%{search}%"
            filters.append(or_(Project.name.ilike(pattern), Project.repo_url.ilike(pattern)))
        if provider:
            filters.append(Project.provider == provider)

        total = self._session.scalar(select(func.count()).select_from(Project).where(*filters)) or 0

        latest = (
            select(
                AnalysisRun.project_id.label("project_id"),
                func.max(AnalysisRun.created_at).label("last_scan_at"),
            )
            .group_by(AnalysisRun.project_id)
            .subquery()
        )
        stmt = (
            select(Project, latest.c.last_scan_at)
            .outerjoin(latest, latest.c.project_id == Project.id)
            .where(*filters)
        )
        sort_columns = {
            "name": Project.name,
            "repo_url": Project.repo_url,
            "created_at": Project.created_at,
            "last_scan_at": latest.c.last_scan_at,
        }
        sort_column = sort_columns.get(sort, latest.c.last_scan_at)
        ordering = sort_column.asc() if order == "asc" else sort_column.desc()
        stmt = (
            stmt.order_by(nullslast(ordering), Project.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        rows = self._session.execute(stmt).all()
        return total, [(row[0], row[1]) for row in rows]

    def get(self, project_id: uuid.UUID) -> Project:
        project = self._session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        return project

    def delete(self, project_id: uuid.UUID) -> None:
        project = self.get(project_id)
        self._session.delete(project)
        self._session.commit()
