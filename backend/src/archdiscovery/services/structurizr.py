from sqlalchemy import select
from sqlalchemy.orm import Session

from archdiscovery.db.models import ArchitectureSnapshot
from archdiscovery.services.errors import NotFoundError


def get_snapshot(session: Session, run_id) -> ArchitectureSnapshot:
    snapshot = session.scalars(
        select(ArchitectureSnapshot).where(ArchitectureSnapshot.run_id == run_id)
    ).first()
    if snapshot is None:
        raise NotFoundError(f"structurizr snapshot for run {run_id} not found")
    return snapshot
