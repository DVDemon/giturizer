import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from archdiscovery.analyzer.syntax.analyze import analyze_syntax
from archdiscovery.db.models import AnalysisRun, Project, RunArtifact


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_detects_routes_for_java_nest_and_fastapi(tmp_path: Path) -> None:
    write(
        tmp_path / "api" / "OrderController.java",
        '@RestController\n@RequestMapping("/orders")\n'
        "public class OrderController {\n"
        '  @PostMapping("/{id}/pay")\n  public void pay() {}\n}\n'
        '@FeignClient(name = "billing")\ninterface BillingClient {\n'
        '  @PostMapping("/api/v1/invoices")\n  void createInvoice(String body);\n}\n',
    )
    write(
        tmp_path / "web" / "orders.controller.ts",
        'import { Controller, Post } from "@nestjs/common";\n'
        '@Controller("orders")\nexport class OrdersController {\n'
        '  @Post(":id/pay")\n  async pay() {}\n}\n',
    )
    write(
        tmp_path / "py" / "orders.py",
        "from fastapi import APIRouter\n"
        'router = APIRouter(prefix="/orders")\n'
        '@router.post("/{order_id}/pay")\n'
        "async def pay(order_id: str):\n    ...\n",
    )
    write(
        tmp_path / "tests" / "TestOrders.java",
        '@RestController\npublic class TestOrders {\n  @GetMapping("/test")\n  void t() {}\n}\n',
    )

    result = analyze_syntax(tmp_path, tmp_path / "syntax.json")
    handlers = {
        (item["method"], item["path"], item["handler"]["language"]) for item in result["handlers"]
    }
    assert ("POST", "/orders/{}/pay", "java") in handlers
    assert ("POST", "/orders/{}/pay", "typescript") in handlers
    assert ("POST", "/orders/{}/pay", "python") in handlers
    assert not any(path == "/test" for _, path, _ in handlers)
    assert not any(path == "/api/v1/invoices" for _, path, _ in handlers)
    assert result["stats"]["handlers"] == 3


def test_excludes_disabled_languages(tmp_path: Path) -> None:
    write(
        tmp_path / "Main.java",
        '@RestController\nclass Main {\n  @GetMapping("/main")\n  void main() {}\n}\n',
    )
    write(
        tmp_path / "main.py",
        '@router.get("/py")\ndef py():\n    ...\n',
    )

    result = analyze_syntax(tmp_path, tmp_path / "syntax.json", ["python"])
    assert {item["handler"]["language"] for item in result["handlers"]} == {"python"}


def test_handlers_endpoint(client: TestClient, session: Session) -> None:
    project = Project(name="syntax", repo_url="https://github.com/o/r", provider="github")
    session.add(project)
    session.commit()
    session.refresh(project)
    run = AnalysisRun(project_id=project.id)
    session.add(run)
    session.commit()
    session.refresh(run)
    session.add(
        RunArtifact(
            run_id=run.id,
            kind="syntax",
            path="",
            content={
                "handlers": [{"method": "GET", "path": "/x"}],
                "stats": {"files": 1, "handlers": 1},
                "errors": [],
            },
        )
    )
    session.commit()

    response = client.get(f"/api/runs/{run.id}/handlers")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["handlers"] == [{"method": "GET", "path": "/x"}]


def test_handlers_endpoint_requires_run(client: TestClient) -> None:
    response = client.get(f"/api/runs/{uuid.uuid4()}/handlers")
    assert response.status_code == 404
