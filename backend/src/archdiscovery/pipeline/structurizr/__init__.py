"""Генерация Structurizr (DSL + JSON workspace)."""

from archdiscovery.pipeline.structurizr.generator import generate_dsl, generate_json
from archdiscovery.pipeline.structurizr.schema import (
    WORKSPACE_SCHEMA,
    validate_workspace,
)

__all__ = ["generate_dsl", "generate_json", "WORKSPACE_SCHEMA", "validate_workspace"]
