"""P0 acceptance: фиксирует ключевые результаты PoC."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from syntax_index import build_index

ROOT = Path(__file__).parent
REPO = ROOT / "fixtures"
SCHEMA = json.loads((ROOT / "api_flow_edge.schema.json").read_text(encoding="utf-8"))


def main() -> int:
    index = build_index(REPO)
    files = {item["file"]: item for item in index["files"]}
    routes = index["routes"]
    flows = index["api_flow_candidates"]

    assert len(routes) == 3, routes
    assert {route["path"] for route in routes} == {"/orders/{}/pay"}
    assert files["java/OrderController.java"]["routes"][0]["handler"] == "pay"
    assert files["java/OrderController.java"]["annotations"][3]["owner"] == "BillingClient"
    assert files["cpp/order.cpp"]["routes"] == []
    assert files["cpp/order.cpp"]["calls"][0]["urls"] == [
        "http://billing/api/v1/invoices"
    ]
    assert len(flows) == 3, flows
    for flow in flows:
        jsonschema.validate(flow, SCHEMA)
        assert flow["input"]["operation"] == "POST /orders/{}/pay"
        assert flow["output"]["url_template"] == "http://billing/api/v1/invoices"

    print(
        json.dumps(
            {
                "files": len(files),
                "routes": len(routes),
                "flows": len(flows),
                "languages": sorted({item["language"] for item in index["files"]}),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
