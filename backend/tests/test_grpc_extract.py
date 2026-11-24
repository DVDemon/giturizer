from pathlib import Path

from archdiscovery.pipeline.grpc_extract import extract_grpc_specs

PROTO = """
syntax = "proto3";
package shop.v1;

service ShopService {
  rpc GetShop (GetShopRequest) returns (GetShopResponse);
  rpc WatchOrders (WatchRequest) returns (stream Order);
}

message GetShopRequest { string id = 1; }
"""


def test_extracts_services_and_rpcs(tmp_path: Path) -> None:
    (tmp_path / "shop.proto").write_text(PROTO, encoding="utf-8")

    specs = extract_grpc_specs(tmp_path)

    assert len(specs) == 1
    spec = specs[0]["spec"]
    assert spec["package"] == "shop.v1"
    service = spec["services"][0]
    assert service["name"] == "ShopService"
    rpcs = {rpc["name"]: rpc for rpc in service["rpcs"]}
    assert rpcs["GetShop"]["request"] == "GetShopRequest"
    assert rpcs["GetShop"]["server_streaming"] is False
    assert rpcs["WatchOrders"]["server_streaming"] is True


def test_ignores_proto_without_services(tmp_path: Path) -> None:
    (tmp_path / "types.proto").write_text("message A { string x = 1; }\n", encoding="utf-8")
    assert extract_grpc_specs(tmp_path) == []
