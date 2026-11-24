import jsonschema

WORKSPACE_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["name", "model"],
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "model": {
            "type": "object",
            "required": ["softwareSystems", "relationships"],
            "properties": {
                "softwareSystems": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/element"},
                },
                "relationships": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/relationship"},
                },
                "deploymentNodes": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/deploymentNode"},
                },
            },
        },
        "views": {"type": "object"},
        "configuration": {"type": "object"},
    },
    "definitions": {
        "element": {
            "type": "object",
            "required": ["id", "name", "description", "tags"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "tags": {"type": "string"},
                "technology": {"type": "string"},
                "containers": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/element"},
                },
                "components": {
                    "type": "array",
                    "items": {"$ref": "#/definitions/element"},
                },
            },
        },
        "relationship": {
            "type": "object",
            "required": ["id", "description", "sourceId", "destinationId", "tags"],
            "properties": {
                "id": {"type": "string"},
                "description": {"type": "string"},
                "sourceId": {"type": "string"},
                "destinationId": {"type": "string"},
                "tags": {"type": "string"},
                "technology": {"type": "string"},
            },
        },
        "deploymentNode": {
            "type": "object",
            "required": ["id", "name", "environment", "instances"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "environment": {"type": "string"},
                "description": {"type": "string"},
                "instances": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id", "containerId"],
                        "properties": {
                            "id": {"type": "string"},
                            "containerId": {"type": "string"},
                            "name": {"type": "string"},
                        },
                    },
                },
                "children": {"type": "array"},
            },
        },
    },
}


def validate_workspace(workspace: dict) -> None:
    jsonschema.validate(workspace, WORKSPACE_SCHEMA)
