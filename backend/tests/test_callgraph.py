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
