#!/bin/bash
#
# Restart API Server with Database Environment Variables
# This ensures the API can connect to the database and validate domains
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

# Step 1: Stop existing API server
echo "Step 1: Stopping existing API server..."
pkill -f 'uvicorn.*(main|main_v4):app' || echo "   (No API server running)"
sleep 2

# Step 2: Check SSH tunnel
echo ""
echo "Step 2: Checking SSH tunnel..."
if ps aux | grep -q "ssh.*5433.*5432" | grep -v grep; then
    echo "   ✅ SSH tunnel is running on port 5433"
    export DB_HOST=localhost
    export DB_PORT=5433
else
    echo "   ⚠️  SSH tunnel not running"
    echo "   💡 Starting SSH tunnel..."
    if [ -f "$PROJECT_ROOT/scripts/setup_nas_ssh_tunnel.sh" ]; then
        bash "$PROJECT_ROOT/scripts/setup_nas_ssh_tunnel.sh" || echo "   ❌ Failed to start SSH tunnel"
    fi
    export DB_HOST=localhost
    export DB_PORT=5433
fi

# Step 3: Load .env and set database environment variables
echo ""
echo "Step 3: Loading environment..."
if [ -f "$PROJECT_ROOT/.env" ]; then
    set -a
    source "$PROJECT_ROOT/.env"
    set +a
    echo "   ✅ Loaded .env"
fi
export DB_NAME=${DB_NAME:-news_intelligence}
export DB_USER=${DB_USER:-newsapp}
export DB_PASSWORD=${DB_PASSWORD:-newsapp_password}

echo "   DB_HOST=$DB_HOST"
echo "   DB_PORT=$DB_PORT"
echo "   DB_NAME=$DB_NAME"
echo "   DB_USER=$DB_USER"
echo "   DB_PASSWORD=***"

# Step 4: Test database connection
echo ""
echo "Step 4: Testing database connection..."
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
        
        # Test domain validation
        for domain in ['politics', 'finance', 'science-tech']:
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
    echo "   Please check your database configuration"
    exit 1
fi

# Step 5: Start API server
echo ""
echo "Step 5: Starting API server..."
cd "$PROJECT_ROOT/api"

# Export environment variables for the API process (including FRED_API_KEY from .env)
export DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD
[ -n "$FRED_API_KEY" ] && export FRED_API_KEY

# Start API server in background
nohup "$PYTHON_BIN" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload > "$PROJECT_ROOT/logs/api_server.log" 2>&1 &
API_PID=$!

echo "   ✅ API server started (PID: $API_PID)"
echo "   📝 Logs: $PROJECT_ROOT/logs/api_server.log"
echo ""

# Step 6: Wait and test
echo "Step 6: Waiting for API to start..."
sleep 5

echo ""
echo "Testing API endpoints..."
for domain in politics finance; do
    echo -n "   Testing /api/$domain/articles... "
    response=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/api/$domain/articles?limit=1" || echo "000")
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
echo "API is running at: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
echo "To stop the server: kill $API_PID"
echo ""

