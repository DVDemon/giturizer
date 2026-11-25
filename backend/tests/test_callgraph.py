import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from archdiscovery.analyzer.syntax.analyze import analyze_syntax
from archdiscovery.db.models import AnalysisRun, Project, RunArtifact


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_java_call_graph_reaches_feign_client(tmp_path: Path) -> None:
    write(
        tmp_path / "java" / "OrderController.java",
        '@RestController\n@RequestMapping("/orders")\nclass OrderController {\n'
        "  private final BillingService service;\n"
        '  @PostMapping("/{id}/pay")\n  public void pay() { service.charge(); }\n}\n'
        "class BillingService {\n  private final BillingClient client;\n"
        '  void charge() { client.createInvoice("http://billing/api/v1/invoices"); }\n}\n'
        '@FeignClient(name = "billing")\ninterface BillingClient {\n'
        '  @PostMapping("/api/v1/invoices")\n  void createInvoice(String body);\n}\n',
    )
    result = analyze_syntax(tmp_path, tmp_path / "syntax.json")
    calls = result["outbound_calls"]
    assert len(calls) == 1
    call = calls[0]
    assert call["input"]["operation"] == "POST /orders/{}/pay"
    assert call["output"]["callee"] == "client.createInvoice"
    assert [item["symbol"] for item in call["path"]] == ["pay", "charge"]
    assert call["status"] == "partial"


def test_typescript_call_graph_reaches_axios(tmp_path: Path) -> None:
    write(
        tmp_path / "src" / "orders.controller.ts",
        'import { Controller, Post } from "@nestjs/common";\n'
        'import axios from "axios";\n'
        '@Controller("orders")\nexport class OrdersController {\n'
        "  constructor(private billing: BillingService) {}\n"
        '  @Post(":id/pay")\n  async pay() { return this.billing.charge(); }\n}\n'
        'class BillingService {\n  async charge() { return axios.post("http://billing/api/v1/invoices"); }\n}\n',
    )
    result = analyze_syntax(tmp_path, tmp_path / "syntax.json")
    calls = result["outbound_calls"]
    assert len(calls) == 1
    assert calls[0]["output"]["callee"] == "axios.post"
    assert "http://billing/api/v1/invoices" in calls[0]["output"]["urls"]


def test_python_call_graph_reaches_httpx(tmp_path: Path) -> None:
    write(
        tmp_path / "app" / "orders.py",
        "from fastapi import APIRouter\nimport httpx\n"
        'router = APIRouter(prefix="/orders")\n'
        '@router.post("/{order_id}/pay")\n'
        "async def pay(order_id: str):\n"
        "    return await billing.charge()\n"
        "async def charge():\n"
        '    await httpx.AsyncClient().post("http://billing/api/v1/invoices")\n',
    )
    result = analyze_syntax(tmp_path, tmp_path / "syntax.json")
    calls = result["outbound_calls"]
    assert len(calls) == 1
    assert calls[0]["output"]["callee"] == "httpx.AsyncClient().post"


def test_outbound_calls_endpoint(client: TestClient, session: Session) -> None:
    project = Project(name="p2", repo_url="https://github.com/o/r", provider="github")
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
                "handlers": [],
                "outbound_calls": [{"input": {"operation": "GET /x"}, "output": {}}],
                "stats": {"handlers": 0, "outbound_calls": 1},
                "errors": [],
            },
        )
    )
    session.commit()

    response = client.get(f"/api/runs/{run.id}/outbound-calls")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["calls"][0]["input"]["operation"] == "GET /x"


def test_outbound_calls_endpoint_requires_run(client: TestClient) -> None:
    assert client.get(f"/api/runs/{uuid.uuid4()}/outbound-calls").status_code == 404


def test_report_includes_api_flows(client: TestClient, session: Session) -> None:
    project = Project(name="flows", repo_url="https://github.com/o/r", provider="github")
    session.add(project)
    session.commit()
    session.refresh(project)
    run = AnalysisRun(project_id=project.id)
    session.add(run)
    session.commit()
    session.refresh(run)
    flow = {
        "input": {
            "operation": "GET /orders",
            "handler": {"file": "Orders.java", "line": 1, "symbol": "orders"},
        },
        "path": [{"symbol": "orders", "file": "Orders.java", "line": 1}],
        "output": {
            "callee": "restTemplate.exchange",
            "file": "Orders.java",
            "line": 4,
            "urls": ["/api/v1/billing"],
            "kind": "http",
        },
        "confidence": 0.75,
        "status": "partial",
    }
    session.add(
        RunArtifact(
            run_id=run.id,
            kind="syntax",
            path="",
            content={"outbound_calls": [flow]},
        )
    )
    session.commit()

    response = client.get(f"/api/runs/{run.id}/report")
    assert response.status_code == 200
    assert response.json()["api_flows"] == [flow]


def test_resolves_typed_python_dependency_to_create(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(
        "import sqlalchemy\n"
        "from fastapi import APIRouter, Depends\n"
        'router = APIRouter(prefix="/api")\n'
        "class ProjectService:\n"
        "    def __init__(self, session):\n"
        "        self._session = session\n"
        "    def create(self):\n"
        "        self._session.add(object())\n"
        "        self._session.commit()\n"
        "class OtherService:\n"
        "    def create(self):\n"
        "        pass\n"
        "def get_service():\n"
        "    return ProjectService(None)\n"
        '@router.post("/projects")\n'
        "def create_project(service: ProjectService = Depends(get_service)):\n"
        "    return service.create()\n",
        encoding="utf-8",
    )
    result = analyze_syntax(tmp_path, tmp_path / "syntax.json")
    post = [
        item
        for item in result["outbound_calls"]
        if item["input"]["operation"] == "POST /api/projects"
    ]
    assert post
    assert {item["output"]["kind"] for item in post} == {"database"}
    assert all(
        [step["symbol"] for step in item["path"]] == ["create_project", "create"] for item in post
    )
