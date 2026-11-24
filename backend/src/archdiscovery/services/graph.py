import uuid
from typing import Any

from archdiscovery.config import settings
from archdiscovery.pipeline.model import ArchitectureModel


class Neo4jGraphStore:
    """Запись и чтение архитектурного графа в Neo4j (ADR-0010)."""

    def __init__(self, url: str, user: str, password: str) -> None:
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(url, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def replace_run(self, run_id: str, model: ArchitectureModel) -> None:
        elements = [
            {
                "id": element.id,
                "name": element.name,
                "type": element.type,
                "technology": element.technology or "",
                "parent_id": element.parent_id or "",
            }
            for element in model.elements
        ]
        relationships = [
            {
                "id": relationship.id,
                "source": relationship.source_id,
                "target": relationship.destination_id,
                "description": relationship.description,
                "technology": relationship.technology or "",
            }
            for relationship in model.relationships
        ]
        with self._driver.session() as session:
            session.run(
                "MATCH (n:ArchElement {run_id:$run_id}) DETACH DELETE n",
                run_id=run_id,
            )
            session.run(
                "UNWIND $elements AS e "
                "MERGE (n:ArchElement {run_id:$run_id, element_id:e.id}) "
                "SET n.name=e.name, n.type=e.type, n.technology=e.technology, "
                "n.parent_id=e.parent_id",
                run_id=run_id,
                elements=elements,
            )
            session.run(
                "UNWIND $relationships AS r "
                "MATCH (a:ArchElement {run_id:$run_id, element_id:r.source}), "
                "(b:ArchElement {run_id:$run_id, element_id:r.target}) "
                "MERGE (a)-[rel:RELATES {run_id:$run_id, rel_id:r.id}]->(b) "
                "SET rel.description=r.description, rel.technology=r.technology",
                run_id=run_id,
                relationships=relationships,
            )

    def elements(self, run_id: str) -> list[dict[str, Any]]:
        with self._driver.session() as session:
            result = session.run(
                "MATCH (n:ArchElement {run_id:$run_id}) "
                "RETURN n.element_id AS id, n.name AS name, n.type AS type, "
                "n.technology AS technology ORDER BY n.type, n.name",
                run_id=run_id,
            )
            return [record.data() for record in result]

    def downstream(self, run_id: str, element_id: str, depth: int = 3) -> list[dict[str, Any]]:
        depth = max(1, min(int(depth), 10))
        query = (
            "MATCH path=(a:ArchElement {run_id:$run_id, element_id:$element_id})"
            f"-[:RELATES*1..{depth}]->(b) "
            "RETURN b.element_id AS id, b.name AS name, b.type AS type, "
            "length(path) AS distance ORDER BY distance, name"
        )
        with self._driver.session() as session:
            result = session.run(query, run_id=run_id, element_id=element_id)
            return [record.data() for record in result]


def write_graph(run_id: uuid.UUID, model: ArchitectureModel) -> None:
    store = Neo4jGraphStore(settings.neo4j_url, settings.neo4j_user, settings.neo4j_password)
    try:
        store.replace_run(str(run_id), model)
    finally:
        store.close()
