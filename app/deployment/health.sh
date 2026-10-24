#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/app/deployment/check.py" --data "${TEAMAI_DATA_ROOT:-$PROJECT_ROOT/data}" --url "http://127.0.0.1:${TEAMAI_PORT:-47821}" "$@"
