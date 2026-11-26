import re
from pathlib import Path
from typing import Any

import yaml

K8S_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Service", "Ingress", "ConfigMap"}
ARGOCD_KINDS = {"Application", "AppProject"}


def _load_yaml(path: Path):
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return None


def _load_yaml_all(path: Path) -> list[dict]:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            return [doc for doc in yaml.safe_load_all(handle) if isinstance(doc, dict)]
    except (OSError, yaml.YAMLError):
        return []


def _parse_dockerfile(path: Path, relative: str) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    base_images = re.findall(r"^\s*FROM\s+([^\s]+)", text, re.MULTILINE | re.IGNORECASE)
    exposed: list[str] = []
    for line in re.findall(r"^\s*EXPOSE\s+(.+)$", text, re.MULTILINE | re.IGNORECASE):
        exposed.extend(line.split())
    commands = re.findall(r"^\s*(?:CMD|ENTRYPOINT)\s+(.+)$", text, re.MULTILINE | re.IGNORECASE)
    return {
        "file": relative,
        "base_images": base_images,
        "exposed_ports": exposed,
        "commands": commands,
    }


def _normalize_build_source(
    repo_path: Path, relative: str, context: str | None, dockerfile: str | None
) -> tuple[str | None, str | None]:
    if context is None and dockerfile is None:
        return None, None
    compose_dir = (repo_path / relative).parent
    raw_context = context or "."
    context_path = (compose_dir / raw_context).resolve()
    try:
        context_rel = str(context_path.relative_to(repo_path.resolve()))
    except ValueError:
        context_rel = str(context_path)
    raw_dockerfile = dockerfile or "Dockerfile"
    dockerfile_path = (context_path / raw_dockerfile).resolve()
    try:
        dockerfile_rel = str(dockerfile_path.relative_to(repo_path.resolve()))
    except ValueError:
        dockerfile_rel = str(dockerfile_path)
    return context_rel, dockerfile_rel


def _parse_compose(document: dict, relative: str, repo_path: Path) -> dict:
    services = document.get("services") or {}
    nodes: list[dict] = []
    edges: list[dict] = []
    for name, config in services.items():
        if not isinstance(config, dict):
            continue
        build = config.get("build")
        if isinstance(build, dict):
            context = build.get("context")
            dockerfile = build.get("dockerfile")
        else:
            context = build
            dockerfile = None
        depends = config.get("depends_on") or []
        if isinstance(depends, dict):
            depends = list(depends.keys())
        context_rel, dockerfile_rel = _normalize_build_source(
            repo_path, relative, context, dockerfile
        )
        nodes.append(
            {
                "name": name,
                "image": config.get("image"),
                "build_context": context,
                "dockerfile": dockerfile,
                "build_context_normalized": context_rel,
                "dockerfile_normalized": dockerfile_rel,
                "build_source": (
                    f"{context_rel}:{dockerfile_rel}"
                    if context_rel is not None and dockerfile_rel is not None
                    else None
                ),
                "ports": [str(port) for port in config.get("ports", []) or []],
                "depends_on": list(depends),
            }
        )
        for dependency in depends:
            edges.append({"from": name, "to": dependency, "type": "depends_on"})
    return {"file": relative, "services": nodes, "edges": edges}


def _parse_k8s(document: dict, relative: str) -> dict:
    kind = str(document.get("kind"))
    metadata = document.get("metadata") or {}
    spec = document.get("spec") or {}
    item: dict = {
        "kind": kind,
        "name": metadata.get("name"),
        "namespace": metadata.get("namespace"),
        "file": relative,
    }
    if kind in {"Deployment", "StatefulSet", "DaemonSet"}:
        pod = (spec.get("template") or {}).get("spec") or {}
        item["containers"] = [
            {
                "name": container.get("name"),
                "image": container.get("image"),
                "ports": [port.get("containerPort") for port in (container.get("ports") or [])],
            }
            for container in (pod.get("containers") or [])
        ]
    elif kind == "Service":
        item["ports"] = [
            {"port": port.get("port"), "target_port": port.get("targetPort")}
            for port in (spec.get("ports") or [])
        ]
    elif kind == "Ingress":
        item["hosts"] = [
            rule.get("host") for rule in (spec.get("rules") or []) if isinstance(rule, dict)
        ]
    return item


def _parse_argocd(document: dict, relative: str) -> dict:
    spec = document.get("spec") or {}
    source = spec.get("source") or {}
    destination = spec.get("destination") or {}
    return {
        "kind": document.get("kind"),
        "name": (document.get("metadata") or {}).get("name"),
        "file": relative,
        "repo_url": source.get("repoURL"),
        "path": source.get("path"),
        "target_revision": source.get("targetRevision"),
        "server": destination.get("server"),
        "namespace": destination.get("namespace"),
    }


def _parse_helm(document: dict, relative: str, repo_path: Path) -> dict:
    chart_dir = (repo_path / relative).parent
    values = _load_yaml(chart_dir / "values.yaml")
    templates = (
        sorted(
            str(template.relative_to(repo_path))
            for template in (chart_dir / "templates").rglob("*.yaml")
        )
        if (chart_dir / "templates").is_dir()
        else []
    )
    return {
        "file": relative,
        "name": document.get("name"),
        "version": document.get("version"),
        "app_version": document.get("appVersion"),
        "values_keys": sorted(values.keys()) if isinstance(values, dict) else [],
        "templates": templates,
    }


def _parse_gitlab_ci(document: dict | None, relative: str) -> dict:
    if not isinstance(document, dict):
        return {"file": relative, "stages": [], "jobs": []}
    reserved = {
        "stages",
        "variables",
        "default",
        "include",
        "workflow",
        "image",
        "services",
        "cache",
        "before_script",
        "after_script",
    }
    jobs = [
        name
        for name, value in document.items()
        if name not in reserved and not name.startswith(".") and isinstance(value, dict)
    ]
    images = sorted(
        {
            value["image"]
            for value in document.values()
            if isinstance(value, dict) and isinstance(value.get("image"), str)
        }
    )
    return {
        "file": relative,
        "stages": document.get("stages") or [],
        "jobs": jobs,
        "images": images,
    }


def extract_deployment(repo_path: Path) -> dict:
    result: dict[str, Any] = {
        "compose": [],
        "dockerfiles": [],
        "kubernetes": [],
        "helm": [],
        "argocd": [],
        "gitlab_ci": [],
    }

    for path in repo_path.rglob("*"):
        if not path.is_file():
            continue
        relative = str(path.relative_to(repo_path))
        name = path.name.lower()

        if name in {"compose.yaml", "compose.yml", "docker-compose.yaml", "docker-compose.yml"}:
            document = _load_yaml(path)
            if isinstance(document, dict):
                result["compose"].append(_parse_compose(document, relative, repo_path))
        elif name == "dockerfile" or name.startswith("dockerfile.") or name == "containerfile":
            result["dockerfiles"].append(_parse_dockerfile(path, relative))
        elif name == "chart.yaml":
            document = _load_yaml(path)
            if isinstance(document, dict):
                result["helm"].append(_parse_helm(document, relative, repo_path))
        elif name == ".gitlab-ci.yml":
            result["gitlab_ci"].append(_parse_gitlab_ci(_load_yaml(path), relative))
        elif path.suffix.lower() in {".yaml", ".yml"}:
            for document in _load_yaml_all(path):
                kind = document.get("kind")
                if kind in ARGOCD_KINDS:
                    result["argocd"].append(_parse_argocd(document, relative))
                elif kind in K8S_KINDS:
                    result["kubernetes"].append(_parse_k8s(document, relative))

    result["summary"] = {
        "compose_files": len(result["compose"]),
        "compose_services": sum(len(item["services"]) for item in result["compose"]),
        "dockerfiles": len(result["dockerfiles"]),
        "kubernetes_resources": len(result["kubernetes"]),
        "helm_charts": len(result["helm"]),
        "argocd_apps": len(result["argocd"]),
        "gitlab_ci_files": len(result["gitlab_ci"]),
    }
    return result
