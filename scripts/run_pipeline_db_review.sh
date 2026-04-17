#!/usr/bin/env bash
# Run pipeline_db_review.py with a Python that has psycopg2 (project venv, uv, or minimal .venv-review).
# Usage from anywhere:
#   ./scripts/run_pipeline_db_review.sh
#   ./scripts/run_pipeline_db_review.sh --days 7

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [ -x "$ROOT/.venv/bin/python3" ]; then
  exec "$ROOT/.venv/bin/python3" "$ROOT/scripts/pipeline_db_review.py" "$@"
fi

if command -v uv >/dev/null 2>&1; then
  exec uv run python "$ROOT/scripts/pipeline_db_review.py" "$@"
fi

REVIEW_VENV="${REVIEW_VENV:-$ROOT/.venv-review}"
if [ ! -d "$REVIEW_VENV" ]; then
  echo "Creating minimal venv at $REVIEW_VENV (psycopg2-binary only)..."
  python3 -m venv "$REVIEW_VENV"
  "$REVIEW_VENV/bin/pip" install --quiet psycopg2-binary python-dotenv
  echo "Done. Re-run this script or sync the main project venv: uv sync"
fi

exec "$REVIEW_VENV/bin/python3" "$ROOT/scripts/pipeline_db_review.py" "$@"
