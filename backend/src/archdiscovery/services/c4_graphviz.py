"""C4 container diagram: DOT из Structurizr JSON и рендер Graphviz."""

import re
import subprocess
from typing import Any

DATABASE_TECHNOLOGIES = (
    "postgres",
    "postgresql",
    "mysql",
    "mongo",
    "mongodb",
    "clickhouse",
    "neo4j",
)
CACHE_TECHNOLOGIES = ("redis", "valkey", "memcached", "rabbitmq", "kafka")
PALETTE = {
    "container": "#538efb",
    "database": "#00c2ab",
    "cache": "#1e8e4e",
    "external": "#ffc800",
}


class GraphvizError(RuntimeError):
    """Graphviz недоступен или вернул ошибку."""


def _escape(value: Any) -> str:
    text = str(value or "")
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    text = text.replace("\r", "").replace("\n", "\\n")
    return text


def _dot_id(value: Any, prefix: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9_]", "_", str(value))
    return f"{prefix}_{raw}" if raw else f"{prefix}_unknown"


def _container_color(technology: str) -> str:
    lowered = technology.lower()
    if any(name in lowered for name in DATABASE_TECHNOLOGIES):
        return PALETTE["database"]
    if any(name in lowered for name in CACHE_TECHNOLOGIES):
        return PALETTE["cache"]
    return PALETTE["container"]


def _container_label(container: dict[str, Any]) -> str:
    name = _escape(container.get("name") or container.get("id"))
    technology = _escape(container.get("technology") or "")
    return f"{name}\\n[{technology}]" if technology else name


def build_c4_dot(workspace: dict[str, Any]) -> str:
    """Строит DOT container view: systems — кластеры, containers — узлы."""
    model = workspace.get("model") or {}
    systems = [item for item in model.get("softwareSystems") or [] if isinstance(item, dict)]
    relationships = [item for item in model.get("relationships") or [] if isinstance(item, dict)]

    lines = [
        "digraph c4 {",
        "  compound=true",
        "  graph [rankdir=LR, splines=polyline, nodesep=0.5, ranksep=1.1, "
        'pad=0.35, bgcolor="white", fontname="DejaVu Sans", fontsize=12]',
        '  node [shape=box, style="rounded,filled", color="#141414", penwidth=1.2, '
        'fontname="DejaVu Sans", fontsize=11, margin="0.14,0.07"]',
        '  edge [color="#7a7f87", arrowsize=0.7, fontname="DejaVu Sans", fontsize=9, '
        'fontcolor="#4e535b"]',
    ]

    node_ids: dict[str, str] = {}
    anchor_clusters: dict[str, str] = {}
    internal_ids: set[str] = set()
    system_by_id: dict[str, dict[str, Any]] = {}

    for system_index, system in enumerate(systems):
        system_id = str(system.get("id") or f"system-{system_index}")
        system_by_id[system_id] = system
        containers = [item for item in system.get("containers") or [] if isinstance(item, dict)]
        if containers:
            internal_ids.add(system_id)
            internal_ids.update(str(container.get("id")) for container in containers)

    touched_external: set[str] = set()
    for relationship in relationships:
        source_id = str(relationship.get("sourceId") or "")
        target_id = str(relationship.get("destinationId") or "")
        if source_id in internal_ids or target_id in internal_ids:
            for endpoint in (source_id, target_id):
                if endpoint in system_by_id and endpoint not in internal_ids:
                    touched_external.add(endpoint)

    external_nodes: dict[str, str] = {}
    for system_index, system in enumerate(systems):
        system_id = str(system.get("id") or f"system-{system_index}")
        containers = [item for item in system.get("containers") or [] if isinstance(item, dict)]
        system_name = _escape(system.get("name") or system_id)
        if not containers:
            if system_id not in touched_external:
                continue
            # Одинаковые внешние системы (postgres, rabbitmq...) схлопываем в один узел.
            name_key = str(system.get("name") or system_id)
            existing = external_nodes.get(name_key)
            if existing is not None:
                node_ids[system_id] = existing
                continue
            node_id = _dot_id(name_key, "ext")
            external_nodes[name_key] = node_id
            node_ids[system_id] = node_id
            technology = _escape(system.get("technology") or "")
            label = f"{system_name}\\n[{technology}]" if technology else system_name
            lines.append(
                f'  {node_id} [label="{label}", fillcolor="{PALETTE["external"]}", '
                f'fontcolor="#141414", tooltip="{system_name}"]'
            )
            continue

        cluster_id = _dot_id(system_id, "cluster")
        anchor_clusters[system_id] = cluster_id
        lines.append(f"  subgraph {cluster_id} {{")
        lines.append('    style="rounded,dashed"; color="#8a8f96"; fontsize=12; margin=16;')
        lines.append(f'    label="{system_name}";')
        anchor_id = _dot_id(system_id, "anchor")
        node_ids[system_id] = anchor_id
        lines.append(
            f"    {anchor_id} [style=invis, shape=point, width=0.01, height=0.01, fixedsize=true]"
        )
        for container_index, container in enumerate(containers):
            container_id = str(container.get("id") or f"{system_id}-container-{container_index}")
            node_id = _dot_id(container_id, "ctr")
            node_ids[container_id] = node_id
            technology = str(container.get("technology") or "")
            label = _container_label(container)
            tooltip = _escape(container.get("name") or container_id)
            lines.append(
                f'    {node_id} [label="{label}", fillcolor="{_container_color(technology)}", '
                f'fontcolor="#ffffff", tooltip="{tooltip}"]'
            )
        lines.append("  }")

    for relationship in relationships:
        source_id = str(relationship.get("sourceId") or "")
        target_id = str(relationship.get("destinationId") or "")
        if source_id not in internal_ids and target_id not in internal_ids:
            continue
        source = node_ids.get(source_id)
        target = node_ids.get(target_id)
        if source is None or target is None or source == target:
            continue
        attributes = []
        description = _escape(relationship.get("description") or "")
        if description:
            attributes.append(f'label="{description}"')
        properties = relationship.get("properties") or {}
        protocol = _escape(properties.get("protocol") or "")
        if protocol:
            attributes.append(f'tooltip="{protocol}"')
        if source_id in anchor_clusters:
            attributes.append(f"ltail={anchor_clusters[source_id]}")
        if target_id in anchor_clusters:
            attributes.append(f"lhead={anchor_clusters[target_id]}")
        suffix = f" [{', '.join(attributes)}]" if attributes else ""
        lines.append(f"  {source} -> {target}{suffix};")

    lines.append("}")
    return "\n".join(lines) + "\n"


def render_c4_svg(workspace: dict[str, Any], timeout: int = 20) -> str:
    """Рендерит C4 container view через Graphviz `fdp -Tsvg`.

    fdp выбран вместо dot: для десятков контейнеров и внешних систем он даёт
    компактную раскладку без вытянутого на несколько экранов холста.
    """
    dot = build_c4_dot(workspace)
    try:
        result = subprocess.run(
            ["fdp", "-Tsvg"],
            input=dot,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise GraphvizError("graphviz не установлен в образе API") from exc
    except subprocess.TimeoutExpired as exc:
        raise GraphvizError(f"graphviz timeout {timeout}s") from exc

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "dot failed").strip()
        raise GraphvizError(detail[:500])
    return result.stdout
