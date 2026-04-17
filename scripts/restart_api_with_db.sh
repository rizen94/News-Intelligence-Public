#!/bin/bash
#
# Restart API Server with Database Environment Variables
#
# Primary: PostgreSQL on Widow (or PgBouncer on Widow) — same host the app connection pools use
#   (see api/shared/database/connection.py — DB_HOST / DB_PORT from .env).
# Backup / rollback only: NAS Postgres via SSH tunnel to localhost:5433 — set DB_HOST=localhost
#   and DB_PORT=5433 in .env and run scripts/setup_nas_ssh_tunnel.sh yourself; do not use for normal ops.
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$PROJECT_ROOT/api"
PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
[ -x "$PYTHON_BIN" ] || PYTHON_BIN="python3"

echo "🔄 Restarting API Server with Database Configuration"
echo "===================================================="
echo ""

# Load .env first — DB_* and API_PORT / NI_API_PORT for stop/start
echo "Step 1: Loading environment (.env)..."
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$PROJECT_ROOT/.env"
    set +a
    echo "   ✅ Loaded .env"
else
    echo "   ⚠️  No .env — using defaults aligned with api/shared/database/connection.py"
fi

# Listen port for this API (must match uvicorn --port below).
# Do not use a loose pkill on "main:app" — that matches other apps (e.g. open_webui.main:app) and can hit EPERM.
NI_API_PORT="${NI_API_PORT:-${API_PORT:-8000}}"

echo ""
echo "Step 2: Stopping News Intelligence API (port ${NI_API_PORT})..."
if command -v fuser >/dev/null 2>&1; then
    fuser -k "${NI_API_PORT}/tcp" 2>/dev/null || true
elif command -v lsof >/dev/null 2>&1; then
    pids=$(lsof -ti:"${NI_API_PORT}" -sTCP:LISTEN 2>/dev/null || true)
    if [ -n "${pids}" ]; then
        # shellcheck disable=SC2086
        kill ${pids} 2>/dev/null || true
    fi
else
    # No fuser/lsof: match NI uvicorn only — literal "uvicorn main:app" / "main_v4:app", not "open_webui.main:app"
    pkill -f 'uvicorn main:app --host' 2>/dev/null || pkill -f 'uvicorn main_v4:app --host' 2>/dev/null || true
fi
sleep 2

# Defaults only when unset (Widow LAN Postgres — not NAS)
export DB_HOST="${DB_HOST:-192.168.93.101}"
export DB_PORT="${DB_PORT:-5432}"
export DB_NAME="${DB_NAME:-news_intel}"
export DB_USER="${DB_USER:-newsapp}"
export DB_PASSWORD="${DB_PASSWORD:-}"

# Optional: NAS backup DB via SSH tunnel — only when explicitly configured
if [[ "$DB_HOST" == "localhost" || "$DB_HOST" == "127.0.0.1" ]] && [[ "$DB_PORT" == "5433" ]]; then
    echo ""
    echo "Step 2b: NAS tunnel mode (localhost:5433) — checking SSH tunnel..."
    if pgrep -f "ssh.*5433.*5432" >/dev/null 2>&1; then
        echo "   ✅ SSH tunnel is running on port 5433"
    else
        echo "   💡 Starting SSH tunnel (scripts/setup_nas_ssh_tunnel.sh)..."
        if [ -f "$PROJECT_ROOT/scripts/setup_nas_ssh_tunnel.sh" ]; then
            bash "$PROJECT_ROOT/scripts/setup_nas_ssh_tunnel.sh" || echo "   ❌ Failed to start SSH tunnel"
        else
            echo "   ❌ setup_nas_ssh_tunnel.sh not found"
        fi
    fi
else
    echo "   Using direct DB target (pooled connections): ${DB_HOST}:${DB_PORT} (no NAS tunnel)"
fi

echo ""
echo "   DB_HOST=$DB_HOST"
echo "   DB_PORT=$DB_PORT"
echo "   DB_NAME=$DB_NAME"
echo "   DB_USER=$DB_USER"
echo "   DB_PASSWORD=***"

# Step 3: Test database connection
echo ""
echo "Step 3: Testing database connection (Widow / pool config)..."
cd "$API_DIR"
"$PYTHON_BIN" << 'PYTHON_EOF'
import os
import sys
sys.path.insert(0, '.')

try:
    from shared.database.connection import get_db_connection
    from shared.services.domain_aware_service import validate_domain

    conn = get_db_connection()
    if conn:
        print("   ✅ Database connection successful")

        for domain in ("politics", "finance"):
            is_valid = validate_domain(domain)
            status = "✅" if is_valid else "❌"
            print(f"   {status} Domain '{domain}': {'valid' if is_valid else 'invalid'}")

        conn.close()
    else:
        print("   ❌ Database connection failed")
        sys.exit(1)
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Database connection test failed"
    echo "   Set DB_HOST / DB_PORT / DB_NAME in .env to your Widow Postgres (or PgBouncer)."
    echo "   NAS tunnel (localhost:5433) is backup-only — do not use for normal API operation."
    exit 1
fi

# Step 4: Start API server
echo ""
echo "Step 4: Starting API server..."
cd "$PROJECT_ROOT/api"

export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
[ -n "$FRED_API_KEY" ] && export FRED_API_KEY

mkdir -p "$PROJECT_ROOT/logs"
nohup "$PYTHON_BIN" -m uvicorn main:app --host 0.0.0.0 --port "${NI_API_PORT}" --reload > "$PROJECT_ROOT/logs/api_server.log" 2>&1 &
API_PID=$!

echo "   ✅ API server started (PID: $API_PID)"
echo "   📝 Logs: $PROJECT_ROOT/logs/api_server.log"
echo ""

# Step 5: Wait and test
echo "Step 5: Waiting for API to start..."
sleep 5

echo ""
echo "Testing API endpoints..."
for domain in politics finance; do
    echo -n "   Testing /api/$domain/articles... "
    response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:${NI_API_PORT}/api/$domain/articles?limit=1" || echo "000")
    if [ "$response" = "200" ]; then
        echo "✅ OK"
    else
        echo "❌ Failed (HTTP $response)"
    fi
done

echo ""
echo "===================================================="
echo "✅ API Server Restarted Successfully"
echo ""
echo "API is running at: http://localhost:${NI_API_PORT}"
echo "API Docs: http://localhost:${NI_API_PORT}/docs"
echo ""
echo "To stop the server: kill $API_PID"
echo ""
