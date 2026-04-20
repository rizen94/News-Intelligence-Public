#!/bin/bash
# Run last-24h activity report using a minimal venv (no system pip / uv sync needed).
# Usage: from project root:  ./scripts/run_last_24h_report.sh

set -e
cd "$(dirname "$0")/.."
REPORT_VENV="${REPORT_VENV:-.venv-report}"

if [ ! -d "$REPORT_VENV" ]; then
  echo "Creating minimal venv at $REPORT_VENV for the report script..."
  python3 -m venv "$REPORT_VENV"
  "$REPORT_VENV/bin/pip" install --quiet psycopg2-binary
  echo "Done. Next runs will reuse this venv."
fi

[ -f .env ] && source .env
exec "$REPORT_VENV/bin/python3" scripts/last_24h_activity_report.py "$@"
