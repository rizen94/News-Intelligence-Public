#!/bin/bash
#
# Manual API restart (dev / pre-systemd). Production Widow should use systemd instead.
# Called from restart_api_with_db.sh when news-intelligence-api-public is not enabled.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$PROJECT_ROOT/api"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

echo "🔄 Manual API restart (no systemd unit enabled)"
echo "===================================================="
echo ""

if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_ROOT/.env"
    set +a
    echo "   ✅ Loaded .env"
fi

NI_API_PORT="${NI_API_PORT:-${API_PORT:-8000}}"

echo "Stopping API on port ${NI_API_PORT}..."
if command -v fuser >/dev/null 2>&1; then
    fuser -k "${NI_API_PORT}/tcp" 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti:"${NI_API_PORT}" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "${pids}" ]; then
        kill ${pids} 2>/dev/null || true
    fi
else
    pkill -f 'uvicorn main:app --host' 2>/dev/null || true
fi
sleep 2

export DB_HOST="${DB_HOST:-127.0.0.1}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-news_intel}"
export DB_USER="${DB_USER:-newsapp}"
export DB_PASSWORD="${DB_PASSWORD:-}"

echo "Testing database..."
cd "$API_DIR"
"$PYTHON_BIN" << 'PYTHON_EOF'
import sys
sys.path.insert(0, '.')
from shared.database.connection import get_db_connection
conn = get_db_connection()
if not conn:
    sys.exit(1)
with conn.cursor() as cur:
    cur.execute("SELECT 1")
conn.close()
print("   ✅ Database OK")
PYTHON_EOF

mkdir -p "$PROJECT_ROOT/logs"
cd "$API_DIR"
export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
nohup "$PYTHON_BIN" -m uvicorn main:app --host 127.0.0.1 --port "${NI_API_PORT}" \
  > "$PROJECT_ROOT/logs/api_server.log" 2>&1 &
echo "✅ API started (PID $!) — no --reload (single AutomationManager)"
echo "   Prefer: sudo systemctl enable --now news-intelligence-api-public"
