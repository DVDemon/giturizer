from pathlib import Path

from archdiscovery.pipeline.annotations_extract import extract_annotation_specs


def test_extracts_spring_endpoints(tmp_path: Path) -> None:
    source = (
        "@RestController\n"
        '@RequestMapping("/api")\n'
        "public class UserController {\n"
        '  @GetMapping("/users")\n'
        '  public String list() { return ""; }\n'
        '  @PostMapping("/users")\n'
        '  public String create() { return ""; }\n'
        "}\n"
    )
    (tmp_path / "UserController.java").write_text(source, encoding="utf-8")

    specs = extract_annotation_specs(tmp_path)

    endpoints = specs[0]["spec"]["endpoints"]
    assert {"method": "GET", "path": "/api/users"} in endpoints
    assert {"method": "POST", "path": "/api/users"} in endpoints


def test_extracts_fastapi_endpoints(tmp_path: Path) -> None:
    source = (
        "from fastapi import FastAPI\n"
        "app = FastAPI()\n\n"
        '@app.get("/health")\n'
        "def health():\n"
        "    return {}\n"
    )
    (tmp_path / "main.py").write_text(source, encoding="utf-8")

    specs = extract_annotation_specs(tmp_path)

    assert specs[0]["spec"]["framework"] == "fastapi"
    assert {"method": "GET", "path": "/health"} in specs[0]["spec"]["endpoints"]


def test_extracts_express_routes(tmp_path: Path) -> None:
    source = (
        "const express = require('express');\n"
        "const app = express();\n"
        'app.get("/users", handler);\n'
        'router.post("/users", handler);\n'
    )
    (tmp_path / "server.js").write_text(source, encoding="utf-8")

    specs = extract_annotation_specs(tmp_path)

    assert specs[0]["spec"]["framework"] == "express"
    assert {"method": "POST", "path": "/users"} in specs[0]["spec"]["endpoints"]


def test_extracts_aspnet_attributes(tmp_path: Path) -> None:
    source = (
        "[ApiController]\n"
        '[Route("/api/items")]\n'
        "public class ItemsController {\n"
        '  [HttpGet("/list")]\n'
        "  public IActionResult List() => Ok();\n"
        "}\n"
    )
    (tmp_path / "ItemsController.cs").write_text(source, encoding="utf-8")

    specs = extract_annotation_specs(tmp_path)

    assert {"method": "GET", "path": "/list"} in specs[0]["spec"]["endpoints"]


def test_extracts_spring_path_attribute(tmp_path: Path) -> None:
    source = (
        "@RestController\n"
        '@RequestMapping(path = "/api")\n'
        "public class NfrController {\n"
        '  @GetMapping(path = "/v1/nfr/{id}", produces = "application/json")\n'
        '  public String get() { return ""; }\n'
        '  @PostMapping(path = "/import/{entityType}")\n'
        '  public String upload() { return ""; }\n'
        '  @GetMapping(produces = "application/json")\n'
        '  public String list() { return ""; }\n'
        "}\n"
    )
    (tmp_path / "NfrController.java").write_text(source, encoding="utf-8")

    endpoints = extract_annotation_specs(tmp_path)[0]["spec"]["endpoints"]

    assert {"method": "GET", "path": "/api/v1/nfr/{id}"} in endpoints
    assert {"method": "POST", "path": "/api/import/{entityType}"} in endpoints
    assert {"method": "GET", "path": "/api"} in endpoints
