from pathlib import Path

from archdiscovery.pipeline.graphql_extract import extract_graphql_specs

SCHEMA = """
type Query {
  shop(id: ID!): Shop
  orders: [Order!]!
}

type Mutation {
  addToCart(shopId: ID!, item: String!): Cart
}

type Shop {
  id: ID!
  name: String
}

enum Status {
  ACTIVE
  CLOSED
}
"""


def test_extracts_types_and_operations(tmp_path: Path) -> None:
    (tmp_path / "schema.graphql").write_text(SCHEMA, encoding="utf-8")

    specs = extract_graphql_specs(tmp_path)

    assert len(specs) == 1
    spec = specs[0]["spec"]
    type_names = {item["name"] for item in spec["types"]}
    assert {"Query", "Mutation", "Shop", "Status"} <= type_names
    operations = {item["operation"]: item["fields"] for item in spec["operations"]}
    assert "shop" in operations["Query"]
    assert "addToCart" in operations["Mutation"]


def test_ignores_empty_graphql(tmp_path: Path) -> None:
    (tmp_path / "empty.graphql").write_text("# just a comment\n", encoding="utf-8")
    assert extract_graphql_specs(tmp_path) == []
