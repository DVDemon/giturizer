import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.crypto import TokenCipher
from archdiscovery.db.models import Project
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

    def list(self, skip: int = 0, limit: int = 100) -> list[Project]:
        stmt = select(Project).order_by(Project.created_at.desc()).offset(skip).limit(limit)
        return list(self._session.scalars(stmt))

    def get(self, project_id: uuid.UUID) -> Project:
        project = self._session.get(Project, project_id)
        if project is None:
            raise NotFoundError(f"project {project_id} not found")
        return project

    def delete(self, project_id: uuid.UUID) -> None:
        project = self.get(project_id)
        self._session.delete(project)
        self._session.commit()
