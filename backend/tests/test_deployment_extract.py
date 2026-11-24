from pathlib import Path

from archdiscovery.pipeline.deployment_extract import extract_deployment


def test_extracts_compose(tmp_path: Path) -> None:
    (tmp_path / "compose.yaml").write_text(
        "services:\n"
        "  api:\n"
        "    build: ./api\n"
        "    ports:\n"
        "      - 8000:8000\n"
        "    depends_on:\n"
        "      - db\n"
        "  db:\n"
        "    image: postgres:16\n",
        encoding="utf-8",
    )

    model = extract_deployment(tmp_path)

    assert model["compose"]
    services = model["compose"][0]["services"]
    names = {service["name"] for service in services}
    assert names == {"api", "db"}
    api = next(service for service in services if service["name"] == "api")
    assert api["build_context"] == "./api"
    assert api["ports"] == ["8000:8000"]
    assert {"from": "api", "to": "db", "type": "depends_on"} in model["compose"][0]["edges"]


def test_extracts_dockerfile(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text(
        'FROM python:3.12-slim\nEXPOSE 8000\nCMD ["uvicorn"]\n', encoding="utf-8"
    )

    model = extract_deployment(tmp_path)

    assert model["dockerfiles"][0]["base_images"] == ["python:3.12-slim"]
    assert model["dockerfiles"][0]["exposed_ports"] == ["8000"]


def test_extracts_kubernetes_and_argocd(tmp_path: Path) -> None:
    (tmp_path / "k8s.yaml").write_text(
        "apiVersion: apps/v1\n"
        "kind: Deployment\n"
        "metadata:\n"
        "  name: api\n"
        "spec:\n"
        "  template:\n"
        "    spec:\n"
        "      containers:\n"
        "        - name: api\n"
        "          image: registry/api:1\n"
        "          ports:\n"
        "            - containerPort: 8080\n"
        "---\n"
        "apiVersion: v1\n"
        "kind: Service\n"
        "metadata:\n"
        "  name: api\n"
        "spec:\n"
        "  ports:\n"
        "    - port: 80\n"
        "      targetPort: 8080\n",
        encoding="utf-8",
    )
    (tmp_path / "argo.yaml").write_text(
        "apiVersion: argoproj.io/v1alpha1\n"
        "kind: Application\n"
        "metadata:\n"
        "  name: app\n"
        "spec:\n"
        "  source:\n"
        "    repoURL: https://gitlab.com/g/r.git\n"
        "    path: deploy\n"
        "  destination:\n"
        "    namespace: prod\n"
        "    server: https://k8s\n",
        encoding="utf-8",
    )

    model = extract_deployment(tmp_path)

    assert {item["kind"] for item in model["kubernetes"]} == {"Deployment", "Service"}
    assert model["argocd"][0]["name"] == "app"
    assert model["argocd"][0]["namespace"] == "prod"


def test_extracts_helm_and_gitlab_ci(tmp_path: Path) -> None:
    chart = tmp_path / "chart"
    (chart / "templates").mkdir(parents=True)
    (chart / "Chart.yaml").write_text(
        "name: demo\nversion: 1.2.3\nappVersion: '4.5'\n", encoding="utf-8"
    )
    (chart / "values.yaml").write_text("replicaCount: 1\nimage: nginx\n", encoding="utf-8")
    (chart / "templates" / "deployment.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\n", encoding="utf-8"
    )
    (tmp_path / ".gitlab-ci.yml").write_text(
        "stages: [build, deploy]\n"
        "build:\n"
        "  stage: build\n"
        "  image: python:3.12\n"
        "deploy:\n"
        "  stage: deploy\n",
        encoding="utf-8",
    )

    model = extract_deployment(tmp_path)

    helm = model["helm"][0]
    assert helm["name"] == "demo"
    assert helm["version"] == "1.2.3"
    assert helm["values_keys"] == ["image", "replicaCount"]
    assert helm["templates"] == ["chart/templates/deployment.yaml"]

    ci = model["gitlab_ci"][0]
    assert ci["stages"] == ["build", "deploy"]
    assert set(ci["jobs"]) == {"build", "deploy"}
    assert ci["images"] == ["python:3.12"]
    assert model["summary"]["helm_charts"] == 1
