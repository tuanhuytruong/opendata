#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
api_pid=''
vite_pid=''
cleanup() {
  [[ -n "$api_pid" ]] && kill "$api_pid" 2>/dev/null || true
  [[ -n "$vite_pid" ]] && kill "$vite_pid" 2>/dev/null || true
}
trap cleanup EXIT

cd "$root"
e2e_port="${E2E_PORT:-$((20000 + RANDOM % 20000))}"
env -u OPENDATA_BASIC_AUTH_USER -u OPENDATA_BASIC_AUTH_PASSWORD \
  .venv/bin/uvicorn main:app --app-dir services/api --host 127.0.0.1 --port 8021 &
api_pid=$!
E2E_PORT="$e2e_port" npx vite --config scripts/vite.e2e.config.ts --host 127.0.0.1 &
vite_pid=$!

for _ in $(seq 1 40); do
  if ! kill -0 "$api_pid" 2>/dev/null || ! kill -0 "$vite_pid" 2>/dev/null; then
    printf 'E2E API or Vite process exited before readiness.\n' >&2
    exit 1
  fi
  if curl -fsS http://127.0.0.1:8021/api/health >/dev/null && curl -fsS "http://127.0.0.1:${e2e_port}/" >/dev/null; then
    E2E_BASE_URL="http://127.0.0.1:${e2e_port}" npx playwright test
    exit 0
  fi
  sleep 0.25
done
printf 'E2E services did not become ready.\n' >&2
exit 1
