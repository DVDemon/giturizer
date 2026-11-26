"""Внутренняя архитектурная модель (C4-ориентированная)."""

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Element:
    id: str
    name: str
    type: str  # softwareSystem | container | component
    description: str = ""
    technology: str | None = None
    tags: list[str] = field(default_factory=list)
    parent_id: str | None = None


@dataclass
class Relationship:
    id: str
    source_id: str
    destination_id: str
    description: str
    technology: str | None = None
    transport: str | None = None
    protocol: str | None = None
    port: str | None = None
    tags: list[str] = field(default_factory=lambda: ["Relationship"])


@dataclass
class ContainerInstance:
    id: str
    container_id: str
    name: str


@dataclass
class DeploymentNode:
    id: str
    name: str
    environment: str
    description: str = ""
    instances: list[ContainerInstance] = field(default_factory=list)


@dataclass
class ArchitectureModel:
    name: str
    description: str
    elements: list[Element] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    deployment_nodes: list[DeploymentNode] = field(default_factory=list)


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "element"


def _cpp_groups(cpp_artifact: dict | None) -> dict[str, int]:
    groups: dict[str, int] = {}
    if not cpp_artifact:
        return groups
    for entry in cpp_artifact.get("files", []):
        path = entry.get("path", "")
        group = path.split("/")[0] if "/" in path else "."
        groups[group] = groups.get(group, 0) + 1
    return groups


def _external_kind(image: str) -> str:
    lowered = image.lower()
    if any(marker in lowered for marker in ("postgres", "mongo")):
        return "database"
    if any(marker in lowered for marker in ("redis", "valkey")):
        return "cache"
    if "swagger" in lowered:
        return "tool"
    return "external"


PROTOCOL_BY_IMAGE = [
    ("postgres", ("PostgreSQL", "TCP", "5432")),
    ("mongo", ("MongoDB", "TCP", "27017")),
    ("redis", ("RESP", "TCP", "6379")),
    ("valkey", ("RESP", "TCP", "6379")),
    ("nginx", ("HTTP", "TCP", "80")),
    ("swagger-ui", ("HTTP", "TCP", "80")),
]


def _container_port(service: dict) -> str | None:
    for entry in service.get("ports", []) or []:
        text = str(entry)
        if ":" in text:
            return text.rsplit(":", 1)[-1].split("/")[0]
        if text.isdigit():
            return text
    return None


def _endpoint_protocol(service: dict) -> tuple[str | None, str | None, str | None]:
    """Возвращает (protocol, transport, port) для связи к сервису."""
    image = str(service.get("image") or "").lower()
    image_name = image.rsplit("/", 1)[-1]
    for marker, (protocol, transport, default_port) in PROTOCOL_BY_IMAGE:
        if image_name.startswith(marker):
            return protocol, transport, _container_port(service) or default_port
    # собираемый сервис без образа: считаем HTTP-микросервисом
    return "HTTP", "TCP", _container_port(service)


def _service_source_key(service: dict, compose_file: str) -> str:
    """Ключ идентичности контейнера: build source или image."""
    if service.get("build_source"):
        return f"build:{service['build_source']}"
    context = service.get("build_context")
    dockerfile = service.get("dockerfile")
    if context is not None or dockerfile is not None:
        compose_dir = Path(compose_file).parent if compose_file else Path(".")
        context_path = compose_dir / (context or ".")
        dockerfile_path = context_path / (dockerfile or "Dockerfile")
        return f"build:{context_path}:{dockerfile_path}"
    image = service.get("image")
    if image:
        return f"image:{image}"
    return f"service:{service.get('name')}"


BASE_IMAGE_TECHNOLOGIES = (
    ("python", "Python"),
    ("node", "JavaScript/TypeScript"),
    ("openjdk", "Java"),
    ("temurin", "Java"),
    ("golang", "Go"),
    ("dotnet", "C#"),
    ("gcc", "C++"),
    ("clang", "C++"),
    ("rust", "Rust"),
)


def _dockerfile_entry(
    service: dict,
    compose_file: str,
    deployment: dict,
) -> dict | None:
    source = service.get("build_source")
    if source:
        for item in deployment.get("dockerfiles", []):
            if item.get("file") == source:
                return item
    context = service.get("build_context")
    if context is None and service.get("dockerfile") is None:
        return None
    compose_dir = Path(compose_file).parent if compose_file else Path(".")
    candidate = str(compose_dir / (context or ".") / (service.get("dockerfile") or "Dockerfile"))
    return next(
        (item for item in deployment.get("dockerfiles", []) if item.get("file") == candidate),
        None,
    )


def _container_technology(
    service: dict,
    compose_file: str,
    deployment: dict,
    language_names: list[str],
) -> str:
    entry = _dockerfile_entry(service, compose_file, deployment)
    if entry:
        for base_image in entry.get("base_images", []):
            lowered = str(base_image).lower()
            for marker, technology in BASE_IMAGE_TECHNOLOGIES:
                if marker in lowered:
                    return technology
    context = str(service.get("build_context") or service.get("name") or "").lower()
    if any(marker in context for marker in ("web", "frontend", "ui")):
        return "JavaScript/TypeScript"
    if len(language_names) == 1:
        return language_names[0]
    return "Docker"


def build_model(
    *,
    project_name: str,
    technologies: list[dict],
    api_specs: list[dict],
    deployment: dict,
    cpp_artifact: dict | None,
) -> ArchitectureModel:
    system_id = f"sys-{slug(project_name)}"
    language_names = sorted(
        {
            str(item.get("name"))
            for item in technologies
            if item.get("kind") == "language" and item.get("name")
        }
    )
    default_technology = language_names[0] if len(language_names) == 1 else None

    model = ArchitectureModel(
        name=project_name,
        description=f"Architecture recovered from source code; API specs: {len(api_specs)}",
    )
    model.elements.append(
        Element(
            id=system_id,
            name=project_name,
            type="softwareSystem",
            description=model.description,
            tags=["Element", "Software System", "analyzed"],
        )
    )

    compose_services: list[dict] = []
    built_entries: list[tuple[dict, str]] = []
    external: list[dict] = []
    for compose in deployment.get("compose", []) or []:
        compose_file = str(compose.get("file") or "")
        for service in compose.get("services", []):
            compose_services.append(service)
            if service.get("build_context") or service.get("dockerfile"):
                built_entries.append((service, compose_file))
            elif service.get("image"):
                external.append(service)

    containers: list[Element] = []
    service_element: dict[str, str] = {}
    seen_sources: dict[str, Element] = {}
    for service, compose_file in built_entries:
        source_key = _service_source_key(service, compose_file)
        container = seen_sources.get(source_key)
        if container is None:
            base_id = f"container-{slug(service['name'])}"
            container_id = base_id
            index = 2
            while any(item.id == container_id for item in containers):
                container_id = f"{base_id}-{index}"
                index += 1
            container = Element(
                id=container_id,
                name=service["name"],
                type="container",
                description="Deployed via docker-compose",
                technology=_container_technology(service, compose_file, deployment, language_names),
                tags=["Element", "Container"],
                parent_id=system_id,
            )
            containers.append(container)
            seen_sources[source_key] = container
        service_element[slug(service["name"])] = container.id

    if not containers and deployment.get("dockerfiles"):
        seen: set[str] = set()
        for dockerfile in deployment["dockerfiles"]:
            directory = dockerfile["file"].rsplit("/", 1)[0] if "/" in dockerfile["file"] else "."
            name = project_name if directory == "." else directory
            if slug(name) in seen:
                continue
            seen.add(slug(name))
            containers.append(
                Element(
                    id=f"container-{slug(name)}",
                    name=name,
                    type="container",
                    description="Built from Dockerfile",
                    technology=", ".join(dockerfile.get("base_images", [])) or "Docker",
                    tags=["Element", "Container"],
                    parent_id=system_id,
                )
            )
    if not containers:
        containers.append(
            Element(
                id="container-app",
                name="Application",
                type="container",
                description="Application",
                technology=default_technology,
                tags=["Element", "Container"],
                parent_id=system_id,
            )
        )
    model.elements.extend(containers)

    seen_external: dict[str, Element] = {}
    for service in external:
        image = service.get("image") or ""
        name = service["name"]
        key = slug(name) or image
        element = seen_external.get(key)
        if element is None:
            element = Element(
                id=f"external-{slug(name)}",
                name=name,
                type="softwareSystem",
                description=image,
                technology=image,
                tags=["Element", "Software System", "external", _external_kind(image)],
            )
            model.elements.append(element)
            seen_external[key] = element
        service_element[slug(name)] = element.id

    container_by_slug = {
        container.id.removeprefix("container-"): container.id for container in containers
    }
    group_element: dict[str, str] = {}
    shared_container: Element | None = None

    for group in sorted(_cpp_groups(cpp_artifact)):
        name = "root" if group == "." else group
        group_slug = slug(name)
        if group_slug in container_by_slug:
            group_element[group] = container_by_slug[group_slug]
            continue
        if shared_container is None:
            shared_container = Element(
                id="container-shared",
                name="shared",
                type="container",
                description="Shared code and libraries",
                technology="C++",
                tags=["Element", "Container"],
                parent_id=system_id,
            )
            model.elements.append(shared_container)
        component_id = f"component-shared-{group_slug}"
        model.elements.append(
            Element(
                id=component_id,
                name=name,
                type="component",
                description="C++ module",
                technology="C++",
                tags=["Element", "Component"],
                parent_id=shared_container.id,
            )
        )
        group_element[group] = component_id

    relation_counter = 0

    def add_relationship(
        source: str,
        target: str,
        description: str,
        technology: str | None,
        *,
        transport: str | None = None,
        protocol: str | None = None,
        port: str | None = None,
    ) -> None:
        nonlocal relation_counter
        if source == target:
            return
        relation_counter += 1
        model.relationships.append(
            Relationship(
                id=f"rel-{relation_counter}",
                source_id=source,
                destination_id=target,
                description=description,
                technology=technology,
                transport=transport,
                protocol=protocol,
                port=port,
            )
        )

    service_by_slug = {slug(service["name"]): service for service in compose_services}
    for service in compose_services:
        source = service_element.get(slug(service["name"]))
        if source is None:
            continue
        for dependency in service.get("depends_on", []):
            target = service_element.get(slug(dependency))
            if target is None:
                continue
            target_service = service_by_slug.get(slug(dependency), {})
            protocol, transport, port = _endpoint_protocol(target_service)
            add_relationship(
                source,
                target,
                "depends on",
                None,
                transport=transport,
                protocol=protocol,
                port=port,
            )

    seen_pairs: set[tuple[str, str]] = set()
    if cpp_artifact:
        for edge in cpp_artifact.get("dependencies", []):
            source_group = edge["from"].split("/")[0]
            target_group = edge["to"].split("/")[0]
            if source_group == target_group:
                continue
            source = group_element.get(source_group)
            target = group_element.get(target_group)
            if source is None or target is None or (source, target) in seen_pairs:
                continue
            seen_pairs.add((source, target))
            add_relationship(source, target, "includes", "C++ include", protocol="include")

    if built_entries:
        node = DeploymentNode(
            id="dep-docker-compose",
            name="Docker Compose",
            environment="Production",
            description="docker-compose services",
        )
        seen_instances: set[str] = set()
        for service, _compose_file in built_entries:
            instance_container_id = service_element.get(slug(service["name"]))
            if instance_container_id is None or instance_container_id in seen_instances:
                continue
            seen_instances.add(instance_container_id)
            node.instances.append(
                ContainerInstance(
                    id=f"dc-instance-{len(seen_instances)}",
                    container_id=instance_container_id,
                    name=service["name"],
                )
            )
        if node.instances:
            model.deployment_nodes.append(node)

    kubernetes = [
        resource
        for resource in deployment.get("kubernetes", [])
        if resource.get("kind") in {"Deployment", "StatefulSet", "DaemonSet"}
    ]
    if kubernetes:
        node = DeploymentNode(
            id="dep-kubernetes",
            name="Kubernetes",
            environment="Production",
            description="Kubernetes workloads",
        )
        for index, resource in enumerate(kubernetes, start=1):
            name = resource.get("name") or f"workload-{index}"
            element = next(
                (container for container in containers if slug(container.name) == slug(name)),
                None,
            )
            if element is not None:
                node.instances.append(
                    ContainerInstance(
                        id=f"k8s-instance-{index}",
                        container_id=element.id,
                        name=name,
                    )
                )
        if node.instances:
            model.deployment_nodes.append(node)

    return model
