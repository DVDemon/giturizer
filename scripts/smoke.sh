#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://localhost:8000}"
PROJECT_ID="${PROJECT_ID:-}"
GITLAB_URL="${GITLAB_URL:-}"
GITLAB_BRANCH="${GITLAB_BRANCH:-main}"
GITLAB_TOKEN="${GITLAB_TOKEN:-}"
PROJECT_NAME="${PROJECT_NAME:-smoke-$(date +%s)}"
TIMEOUT="${TIMEOUT:-180}"

fail() {
  echo "SMOKE FAILED: $*" >&2
  exit 1
}

log() {
  echo "== $*"
}

log "health: $API_URL/health"
curl -fsS "$API_URL/health" >/dev/null || fail "health endpoint"

if [ -z "$PROJECT_ID" ]; then
  [ -n "$GITLAB_URL" ] || fail "set PROJECT_ID or GITLAB_URL"
  payload=$(python3 - "$PROJECT_NAME" "$GITLAB_URL" "$GITLAB_BRANCH" "$GITLAB_TOKEN" <<'PY'
import json
import sys

name, url, branch, token = sys.argv[1:5]
data = {"name": name, "gitlab_url": url, "default_branch": branch}
if token:
    data["token"] = token
print(json.dumps(data))
PY
)
  project=$(curl -fsS -X POST "$API_URL/api/projects" \
    -H 'Content-Type: application/json' -d "$payload") || fail "create project"
  PROJECT_ID=$(echo "$project" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
  log "project created: $PROJECT_ID"
fi

run=$(curl -fsS -X POST "$API_URL/api/projects/$PROJECT_ID/runs" \
  -H 'Content-Type: application/json' -d '{}') || fail "start run"
RUN_ID=$(echo "$run" | python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])')
log "run started: $RUN_ID"

deadline=$(( $(date +%s) + TIMEOUT ))
while :; do
  status=$(curl -fsS "$API_URL/api/runs/$RUN_ID" \
    | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
  echo "status: $status"
  [ "$status" = "done" ] && break
  [ "$status" = "failed" ] && fail "run failed: $(curl -fsS "$API_URL/api/runs/$RUN_ID")"
  [ "$(date +%s)" -ge "$deadline" ] && fail "timeout waiting for run (${TIMEOUT}s)"
  sleep 2
done

log "report"
curl -fsS "$API_URL/api/runs/$RUN_ID/report" -o /tmp/smoke-report.json \
  || fail "report endpoint"
python3 - <<'PY'
import json

data = json.load(open("/tmp/smoke-report.json"))
assert set(data) == {"technologies", "api", "deployment"}, data.keys()
assert isinstance(data["technologies"], list)
assert isinstance(data["api"], list)
assert isinstance(data["deployment"], list)
print("technologies:", len(data["technologies"]),
      "| api services:", len(data["api"]),
      "| deployment methods:", [item["method"] for item in data["deployment"]])
PY

log "results"
curl -fsS "$API_URL/api/runs/$RUN_ID/results" -o /tmp/smoke-results.json \
  || fail "results endpoint"
python3 - <<'PY'
import json

data = json.load(open("/tmp/smoke-results.json"))
print("technologies:", len(data["technologies"]),
      "| api specs:", len(data["api_specs"]),
      "| artifacts:", [item["kind"] for item in data["artifacts"]])
PY

log "handlers"
curl -fsS "$API_URL/api/runs/$RUN_ID/handlers" -o /tmp/smoke-handlers.json \
  || fail "handlers endpoint"
python3 - <<'PY'
import json

data = json.load(open("/tmp/smoke-handlers.json"))
assert "handlers" in data
print("available:", data.get("available"), "| handlers:", len(data["handlers"]))
PY

log "c4"
curl -fsS "$API_URL/api/runs/$RUN_ID/c4.model" >/dev/null || fail "c4 model"
curl -fsS "$API_URL/api/runs/$RUN_ID/c4.svg" -o /tmp/smoke-c4.svg || fail "c4 svg"
grep -q '<svg' /tmp/smoke-c4.svg || fail "c4 svg is empty"

log "SMOKE OK (run $RUN_ID)"
