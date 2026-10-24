#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export OCTOP_HOME="${TEAMAI_DATA_ROOT:-$PROJECT_ROOT/data}"
export OCTOP_TEAMSPACE=1
export TEAMSPACE_DATA_DIR="$OCTOP_HOME/teamspace"
export PYTHONPATH="$PROJECT_ROOT/app${PYTHONPATH:+:$PYTHONPATH}"
export OCTOP_DATABASE_DRIVER=sqlite
export OCTOP_DATABASE_SQLITE_PATH="$OCTOP_HOME/octop.db"
export OCTOP_REQUIRE_SETUP_PASSWORD=false
export OCTOP_LOG_MAX_BYTES=10485760
export OCTOP_LOG_RETENTION_DAYS=7
umask 077
mkdir -p "$OCTOP_HOME"
exec "$PROJECT_ROOT/.venv/bin/octop" run --host "${TEAMAI_BIND_HOST:-127.0.0.1}" --port "${TEAMAI_PORT:-47821}" --workers 1 --log-level warning
