"""Единый JSON-отчёт запуска: технологии, API, deployment."""

import re
from typing import Any

HTTP_METHODS = ("get", "post", "put", "delete", "patch", "head", "options")


def _service_from_source(source: str) -> str:
    match = re.search(r"services/([^/]+)/", source)
    if match:
        return match.group(1)
    parts = [part for part in source.split("/") if part]
    return parts[-2] if len(parts) > 1 else (parts[0] if parts else "unknown")


def _split_image(image: str | None) -> tuple[str | None, str | None]:
    if not image:
        return None, None
    if "@" in image:
        name, digest = image.split("@", 1)
        return name, digest
    last = image.rsplit("/", 1)[-1]
    if ":" in last:
        name, tag = image.rsplit(":", 1)
        return name, tag
    return image, None


def _technology_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": item.get("name"),
        "type": item.get("kind"),
        "version": item.get("version"),
        "description": item.get("evidence", ""),
    }


def _api_method(
    operation: str,
    description: str,
    technology: str,
) -> dict[str, Any]:
    return {
        "operation": operation,
        "description": description,
        "technology": technology,
    }


def _build_api(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    services: dict[str, dict[str, Any]] = {}

    def add(service: str, method: dict[str, Any]) -> None:
        key = service or "unknown"
        entry = services.setdefault(key, {"service": key, "methods": []})
        if method not in entry["methods"]:
            entry["methods"].append(method)

    for spec in specs:
        kind = spec.get("kind")
        name = str(spec.get("name") or "")
        raw = spec.get("spec") or {}
        if not isinstance(raw, dict):
            continue

        if kind == "openapi":
            paths = raw.get("paths") or {}
            for path, path_item in paths.items():
                if not isinstance(path_item, dict):
                    continue
                for http_method in HTTP_METHODS:
                    operation = path_item.get(http_method)
                    if not isinstance(operation, dict):
                        continue
                    tags = [tag for tag in operation.get("tags") or [] if isinstance(tag, str)]
                    service = tags[0] if tags else _service_from_source(name)
                    description = str(
                        operation.get("summary")
                        or operation.get("description")
                        or operation.get("operationId")
                        or ""
                    )
                    add(
                        service,
                        _api_method(
                            f"{http_method.upper()} {path}",
                            description,
                            "OpenAPI",
                        ),
                    )
        elif kind == "annotations":
            service = _service_from_source(name)
            framework = str(raw.get("framework") or "annotations")
            source = str(raw.get("file") or name)
            for endpoint in raw.get("endpoints") or []:
                if not isinstance(endpoint, dict) or not endpoint.get("path"):
                    continue
                method = str(endpoint.get("method") or "GET").upper()
                add(
                    service,
                    _api_method(
                        f"{method} {endpoint['path']}",
                        f"Найдено в {source} ({framework})",
                        framework,
                    ),
                )
        elif kind == "grpc":
            for service_item in raw.get("services") or []:
                if not isinstance(service_item, dict):
                    continue
                service = str(service_item.get("name") or "gRPC")
                for rpc in service_item.get("rpcs") or []:
                    if not isinstance(rpc, dict) or not rpc.get("name"):
                        continue
                    add(
                        service,
                        _api_method(
                            f"{service}/{rpc['name']}",
                            "gRPC method",
                            "gRPC",
                        ),
                    )
        elif kind == "graphql":
            service = _service_from_source(name)
            for operation in raw.get("operations") or []:
                if not isinstance(operation, dict) or not operation.get("operation"):
                    continue
                fields = [str(field) for field in operation.get("fields") or []]
                add(
                    service,
                    _api_method(
                        str(operation["operation"]),
                        f"GraphQL: {', '.join(fields)}" if fields else "GraphQL",
                        "GraphQL",
                    ),
                )

    result = []
    for entry in sorted(services.values(), key=lambda item: item["service"]):
        entry["methods"].sort(key=lambda item: item["operation"])
        result.append(entry)
    return result


def _deployment_service(
    name: str,
    image: str | None,
    ports: list[str],
    dependencies: list[str],
) -> dict[str, Any]:
    image_name, image_version = _split_image(image)
    return {
        "name": name,
        "image": image_name,
        "image_version": image_version,
        "ports": ports,
        "dependencies": dependencies,
    }


def _compose_services(deployment: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for compose_file in deployment.get("compose") or []:
        if not isinstance(compose_file, dict):
            continue
        for service in compose_file.get("services") or []:
            if not isinstance(service, dict):
                continue
            result.append(
                _deployment_service(
                    str(service.get("name") or "service"),
                    service.get("image"),
                    [str(port) for port in service.get("ports") or []],
                    [str(dep) for dep in service.get("depends_on") or []],
                )
            )
    return result


def _dockerfile_services(deployment: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for dockerfile in deployment.get("dockerfiles") or []:
        if not isinstance(dockerfile, dict):
            continue
        base_images = dockerfile.get("base_images") or []
        image = base_images[0] if base_images else None
        result.append(
            _deployment_service(
                str(dockerfile.get("file") or "Dockerfile"),
                image,
                [str(port) for port in dockerfile.get("exposed_ports") or []],
                [],
            )
        )
    return result


def _kubernetes_services(resources: list[Any]) -> list[dict[str, Any]]:
    result = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        metadata = resource.get("metadata") or {}
        resource_name = str(metadata.get("name") or resource.get("name") or "resource")
        spec = resource.get("spec") or {}
        template = spec.get("template") or {}
        pod_spec = template.get("spec") if isinstance(template, dict) else None
        if not isinstance(pod_spec, dict):
            pod_spec = spec if isinstance(spec, dict) else {}
        containers = pod_spec.get("containers") or []
        if containers:
            for container in containers:
                if not isinstance(container, dict):
                    continue
                name = str(container.get("name") or resource_name)
                ports = [
                    str(port.get("containerPort"))
                    for port in container.get("ports") or []
                    if isinstance(port, dict) and port.get("containerPort") is not None
                ]
                result.append(
                    _deployment_service(
                        name,
                        container.get("image"),
                        ports,
                        [],
                    )
                )
        elif resource.get("kind") == "Service":
            ports = [
                str(port.get("port"))
                for port in spec.get("ports") or []
                if isinstance(port, dict) and port.get("port") is not None
            ]
            result.append(_deployment_service(resource_name, None, ports, []))
    return result


def _argocd_services(apps: list[Any]) -> list[dict[str, Any]]:
    result = []
    for app in apps:
        if not isinstance(app, dict):
            continue
        metadata = app.get("metadata") or {}
        name = str(metadata.get("name") or app.get("name") or "application")
        result.append(_deployment_service(name, None, [], []))
    return result


def _gitlab_services(jobs: list[Any]) -> list[dict[str, Any]]:
    result = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        name = str(job.get("name") or job.get("job") or "job")
        result.append(
            _deployment_service(
                name,
                job.get("image"),
                [],
                [str(dep) for dep in job.get("needs") or []],
            )
        )
    return result


def _build_deployment(deployment: dict[str, Any]) -> list[dict[str, Any]]:
    result = [
        {"method": "Docker Compose", "services": _compose_services(deployment)},
        {"method": "Dockerfile", "services": _dockerfile_services(deployment)},
        {
            "method": "Kubernetes",
            "services": _kubernetes_services(deployment.get("kubernetes") or []),
        },
        {
            "method": "Helm",
            "services": _kubernetes_services(deployment.get("helm") or []),
        },
        {
            "method": "ArgoCD",
            "services": _argocd_services(deployment.get("argocd") or []),
        },
        {
            "method": "GitLab CI",
            "services": _gitlab_services(deployment.get("gitlab_ci") or []),
        },
    ]
    return [item for item in result if item["services"]]


def build_report(
    *,
    technologies: list[dict[str, Any]],
    api_specs: list[dict[str, Any]],
    deployment: dict[str, Any],
) -> dict[str, Any]:
    """Собирает единый JSON-отчёт из уже извлечённых артефактов."""
    return {
        "technologies": [_technology_item(item) for item in technologies],
        "api": _build_api(api_specs),
        "deployment": _build_deployment(deployment),
    }
