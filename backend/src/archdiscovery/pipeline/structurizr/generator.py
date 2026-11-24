import itertools
import re
from collections.abc import Callable

from archdiscovery.pipeline.model import ArchitectureModel, slug


def _tags(tags: list[str]) -> str:
    return ",".join(tags)


def _escape(value: str | None) -> str:
    return (value or "").replace("\\", "\\\\").replace('"', '\\"')


def _protocol_technology(relationship) -> str | None:
    if relationship.protocol == "include":
        return relationship.technology
    parts: list[str] = []
    if relationship.protocol:
        parts.append(relationship.protocol)
    if relationship.transport:
        transport = relationship.transport
        if relationship.port:
            transport = f"{transport}:{relationship.port}"
        parts.append(transport)
    return " · ".join(parts) or None


def _analyzed(model: ArchitectureModel) -> list:
    return [
        element
        for element in model.elements
        if element.type == "softwareSystem" and "analyzed" in element.tags
    ]


def _external(model: ArchitectureModel) -> list:
    return [
        element
        for element in model.elements
        if element.type == "softwareSystem" and "analyzed" not in element.tags
    ]


def generate_json(model: ArchitectureModel) -> dict:
    counter = itertools.count(1)

    def next_id() -> str:
        return str(next(counter))

    nodes: dict[str, dict] = {}
    containers = [element for element in model.elements if element.type == "container"]
    components = [element for element in model.elements if element.type == "component"]

    systems_json: list[dict] = []
    for system in [*_analyzed(model), *_external(model)]:
        node: dict = {
            "id": next_id(),
            "name": system.name,
            "description": system.description,
            "tags": _tags(system.tags),
        }
        if system.technology:
            node["technology"] = system.technology

        if "analyzed" in system.tags:
            node["containers"] = []
            for container in [item for item in containers if item.parent_id == system.id]:
                container_node: dict = {
                    "id": next_id(),
                    "name": container.name,
                    "description": container.description,
                    "tags": _tags(container.tags),
                    "components": [],
                }
                if container.technology:
                    container_node["technology"] = container.technology

                for component in [item for item in components if item.parent_id == container.id]:
                    component_node: dict = {
                        "id": next_id(),
                        "name": component.name,
                        "description": component.description,
                        "tags": _tags(component.tags),
                    }
                    if component.technology:
                        component_node["technology"] = component.technology
                    container_node["components"].append(component_node)
                    nodes[component.id] = component_node

                node["containers"].append(container_node)
                nodes[container.id] = container_node

        nodes[system.id] = node
        systems_json.append(node)

    relationships_json: list[dict] = []
    for relationship in model.relationships:
        source = nodes.get(relationship.source_id)
        destination = nodes.get(relationship.destination_id)
        if source is None or destination is None:
            continue
        item = {
            "id": next_id(),
            "description": relationship.description,
            "sourceId": source["id"],
            "destinationId": destination["id"],
            "tags": _tags(relationship.tags),
        }
        technology = relationship.technology or _protocol_technology(relationship)
        if technology:
            item["technology"] = technology
        properties: dict[str, str] = {}
        if relationship.transport:
            properties["transport"] = relationship.transport
        if relationship.protocol:
            properties["protocol"] = relationship.protocol
        if relationship.port:
            properties["port"] = relationship.port
        if properties:
            item["properties"] = properties
        relationships_json.append(item)

    deployment_json: list[dict] = []
    for deployment_node in model.deployment_nodes:
        instances = [
            {
                "id": next_id(),
                "containerId": nodes[instance.container_id]["id"],
                "name": instance.name,
            }
            for instance in deployment_node.instances
            if instance.container_id in nodes
        ]
        if not instances:
            continue
        deployment_json.append(
            {
                "id": next_id(),
                "name": deployment_node.name,
                "environment": deployment_node.environment,
                "description": deployment_node.description,
                "instances": instances,
                "children": [],
            }
        )

    analyzed = _analyzed(model)
    views: dict = {
        "systemLandscapeViews": [
            {
                "key": "systemLandscape",
                "description": "System landscape",
                "include": ["*"],
            }
        ],
        "systemContextViews": [],
        "containerViews": [],
    }
    if analyzed:
        system = analyzed[0]
        system_id = nodes[system.id]["id"]
        views["systemContextViews"].append(
            {
                "key": f"context-{slug(system.name)}",
                "description": f"Context of {system.name}",
                "softwareSystemId": system_id,
                "include": ["*"],
            }
        )
        views["containerViews"].append(
            {
                "key": f"containers-{slug(system.name)}",
                "description": f"Containers of {system.name}",
                "softwareSystemId": system_id,
                "include": ["*"],
            }
        )

    return {
        "id": 1,
        "name": model.name,
        "description": model.description,
        "model": {
            "softwareSystems": systems_json,
            "relationships": relationships_json,
            "deploymentNodes": deployment_json,
        },
        "views": views,
        "configuration": {},
    }


def _identifier_factory() -> Callable[[str], str]:
    used: set[str] = set()
    idents: dict[str, str] = {}

    def ident(logical_id: str) -> str:
        if logical_id in idents:
            return idents[logical_id]
        parts = re.findall(r"[A-Za-z0-9]+", logical_id)
        candidate = (
            parts[0] + "".join(part.capitalize() for part in parts[1:]) if parts else "element"
        )
        if candidate[0].isdigit():
            candidate = f"e{candidate}"
        base = candidate
        counter = 2
        while candidate in used:
            candidate = f"{base}{counter}"
            counter += 1
        used.add(candidate)
        idents[logical_id] = candidate
        return candidate

    return ident


def generate_dsl(model: ArchitectureModel) -> str:
    element_ids = {element.id for element in model.elements}
    ident = _identifier_factory()
    for element in model.elements:
        ident(element.id)

    lines = [
        f'workspace "{_escape(model.name)}" "{_escape(model.description)}" {{',
        "    model {",
    ]

    containers = [element for element in model.elements if element.type == "container"]
    components = [element for element in model.elements if element.type == "component"]

    for system in _analyzed(model):
        lines.append(
            f"        {ident(system.id)} = softwareSystem "
            f'"{_escape(system.name)}" "{_escape(system.description)}" {{'
        )
        for container in [item for item in containers if item.parent_id == system.id]:
            technology = f' "{_escape(container.technology)}"' if container.technology else ""
            lines.append(
                f"            {ident(container.id)} = container "
                f'"{_escape(container.name)}" "{_escape(container.description)}"{technology} {{'
            )
            for component in [item for item in components if item.parent_id == container.id]:
                component_technology = (
                    f' "{_escape(component.technology)}"' if component.technology else ""
                )
                lines.append(
                    f"                {ident(component.id)} = component "
                    f'"{_escape(component.name)}" "{_escape(component.description)}"'
                    f"{component_technology}"
                )
            lines.append("            }")
        lines.append("        }")

    for system in _external(model):
        lines.append(
            f"        {ident(system.id)} = softwareSystem "
            f'"{_escape(system.name)}" "{_escape(system.description)}" {{'
        )
        lines.append('            tags "external"')
        lines.append("        }")

    for relationship in model.relationships:
        if (
            relationship.source_id not in element_ids
            or relationship.destination_id not in element_ids
        ):
            continue
        technology_label = relationship.technology or _protocol_technology(relationship)
        technology = f' "{_escape(technology_label)}"' if technology_label else ""
        lines.append(
            f"        {ident(relationship.source_id)} -> {ident(relationship.destination_id)} "
            f'"{_escape(relationship.description)}"{technology}'
        )

    by_environment: dict[str, list] = {}
    for deployment_node in model.deployment_nodes:
        by_environment.setdefault(deployment_node.environment, []).append(deployment_node)
    for environment, deployment_nodes in by_environment.items():
        lines.append(f'        deploymentEnvironment "{_escape(environment)}" {{')
        for deployment_node in deployment_nodes:
            lines.append(
                f"            {ident(deployment_node.id)} = deploymentNode "
                f'"{_escape(deployment_node.name)}" "{_escape(deployment_node.description)}" {{'
            )
            for instance in deployment_node.instances:
                if instance.container_id in element_ids:
                    lines.append(
                        f"                containerInstance {ident(instance.container_id)}"
                    )
            lines.append("            }")
        lines.append("        }")

    lines.append("    }")

    lines.append("    views {")
    lines.append('        systemLandscape "landscape" {')
    lines.append("            include *")
    lines.append("        }")

    analyzed = _analyzed(model)
    if analyzed:
        system = analyzed[0]
        lines.append(f'        systemContext {ident(system.id)} "context" {{')
        lines.append("            include *")
        lines.append("        }")
        lines.append(f'        container {ident(system.id)} "containers" {{')
        lines.append("            include *")
        lines.append("        }")

    lines.append("    }")
    lines.append("}")
    return "\n".join(lines) + "\n"
