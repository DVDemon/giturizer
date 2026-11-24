import re
from pathlib import Path

TYPE_RE = re.compile(r"\b(type|input|interface|enum|union|scalar|directive)\s+(\w+)")
OPERATION_RE = re.compile(r"\btype\s+(Query|Mutation|Subscription)\s*\{")
FIELD_RE = re.compile(r"^\s*(\w+)\s*(?:\(|:|\s)")


def _strip_comments(text: str) -> str:
    text = re.sub(r'"""[\s\S]*?"""', "", text)
    return re.sub(r"#[^\n]*", "", text)


def _block(text: str, start: int) -> str:
    depth = 1
    index = start
    while index < len(text) and depth:
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
        index += 1
    return text[start : index - 1]


def _fields(body: str) -> list[str]:
    fields: list[str] = []
    for line in body.splitlines():
        line = line.strip()
        match = FIELD_RE.match(line)
        if match:
            fields.append(match.group(1))
    return fields


def extract_graphql_specs(repo_path: Path) -> list[dict]:
    specs: list[dict] = []
    for path in repo_path.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".graphql", ".gql"}:
            continue
        if ".git" in path.relative_to(repo_path).parts:
            continue
        try:
            text = _strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue

        types = [
            {"kind": match.group(1), "name": match.group(2)} for match in TYPE_RE.finditer(text)
        ]
        operations = [
            {"operation": match.group(1), "fields": _fields(_block(text, match.end()))}
            for match in OPERATION_RE.finditer(text)
        ]
        if not types and not operations:
            continue

        relative = str(path.relative_to(repo_path))
        specs.append(
            {
                "kind": "graphql",
                "name": relative,
                "spec": {"file": relative, "types": types, "operations": operations},
            }
        )
    return specs
