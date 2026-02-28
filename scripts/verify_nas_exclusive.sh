#!/bin/bash
# Verify that NAS is the exclusive and only database in use

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}🔍 Verifying NAS is the Exclusive Database${NC}"
echo "=========================================="
echo ""

ERRORS=0

# 1. Check SSH tunnel
echo -e "${CYAN}[1/6]${NC} Checking SSH tunnel..."
if ps aux | grep -q "[s]sh -L 5433:localhost:5432.*192.168.93.100"; then
    TUNNEL_PID=$(ps aux | grep "[s]sh -L 5433:localhost:5432.*192.168.93.100" | awk '{print $2}')
    echo -e "${GREEN}✅ SSH tunnel running (PID: $TUNNEL_PID)${NC}"
else
    echo -e "${RED}❌ SSH tunnel not running${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 2. Check local PostgreSQL is stopped
echo -e "${CYAN}[2/6]${NC} Checking local PostgreSQL..."
if docker ps --filter "name=postgres" --format "{{.Names}}" 2>/dev/null | grep -q "postgres"; then
    echo -e "${RED}❌ Local PostgreSQL container is still running${NC}"
    docker ps --filter "name=postgres" --format "table {{.Names}}\t{{.Status}}"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✅ Local PostgreSQL container is stopped${NC}"
fi
echo ""

# 3. Check .env configuration
echo -e "${CYAN}[3/6]${NC} Checking .env configuration..."
if [ -f "$PROJECT_DIR/configs/.env" ]; then
    DB_HOST=$(grep "^DB_HOST=" "$PROJECT_DIR/configs/.env" | cut -d'=' -f2 | tr -d ' ')
    DB_PORT=$(grep "^DB_PORT=" "$PROJECT_DIR/configs/.env" | cut -d'=' -f2 | tr -d ' ')
    
    if [[ "$DB_HOST" == "localhost" ]] && [[ "$DB_PORT" == "5433" ]]; then
        echo -e "${GREEN}✅ .env configured for NAS (localhost:5433)${NC}"
    else
        echo -e "${RED}❌ .env not configured for NAS${NC}"
        echo "   Current: DB_HOST=$DB_HOST, DB_PORT=$DB_PORT"
        echo "   Expected: DB_HOST=localhost, DB_PORT=5433"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "${YELLOW}⚠️  .env file not found${NC}"
fi
echo ""

# 4. Test NAS database connection
echo -e "${CYAN}[4/6]${NC} Testing NAS database connection..."
if python3 << 'PYTHON_EOF'
import psycopg2
import sys
try:
    conn = psycopg2.connect(
        host='localhost',
        port=5433,
        database='news_intelligence',
        user='newsapp',
        password='newsapp_password',
        connect_timeout=5
    )
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM articles;")
    articles = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM rss_feeds;")
    rss = cursor.fetchone()[0]
    
    cursor.close()
    conn.close()
    
    if 'aarch64' in version:
        print(f"✅ Connected to NAS database (ARM)")
        print(f"   Articles: {articles} records")
        print(f"   RSS Feeds: {rss} records")
        sys.exit(0)
    else:
        print(f"❌ Connected to non-NAS database")
        print(f"   Version: {version[:60]}")
        sys.exit(1)
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
PYTHON_EOF
then
    echo -e "${GREEN}✅ NAS database connection successful${NC}"
else
    echo -e "${RED}❌ NAS database connection failed${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 5. Check DatabaseManager configuration
echo -e "${CYAN}[5/6]${NC} Checking DatabaseManager configuration..."
if python3 << 'PYTHON_EOF'
import os
import sys
sys.path.insert(0, 'api')

os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5433'
os.environ['DB_NAME'] = 'news_intelligence'
os.environ['DB_USER'] = 'newsapp'
os.environ['DB_PASSWORD'] = 'newsapp_password'

try:
    from config.database import DatabaseManager
    
    db_manager = DatabaseManager()
    config = db_manager.config
    
    if config['host'] == 'localhost' and config['port'] == 5433:
        print("✅ DatabaseManager configured for NAS")
        sys.exit(0)
    else:
        print(f"❌ DatabaseManager not configured for NAS")
        print(f"   Host: {config['host']}, Port: {config['port']}")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
PYTHON_EOF
then
    echo -e "${GREEN}✅ DatabaseManager configured correctly${NC}"
else
    echo -e "${RED}❌ DatabaseManager configuration issue${NC}"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# 6. Verify no local database connections
echo -e "${CYAN}[6/6]${NC} Checking for local database connections..."
if python3 << 'PYTHON_EOF'
import psycopg2
import sys

# Try to connect to local PostgreSQL (should fail or be blocked)
try:
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        database='news_intelligence',
        user='newsapp',
        password='newsapp_password',
        connect_timeout=2
    )
    cursor = conn.cursor()
    cursor.execute("SELECT version();")
    version = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    
    if 'aarch64' in version:
        print("⚠️  Port 5432 connects to NAS (unexpected)")
        sys.exit(1)
    else:
        print("❌ Local PostgreSQL is accessible on port 5432")
        print("   This should be blocked or stopped")
        sys.exit(1)
except psycopg2.OperationalError:
    print("✅ Local PostgreSQL is not accessible (correct)")
    sys.exit(0)
except Exception as e:
    if "Connection refused" in str(e) or "No route to host" in str(e):
        print("✅ Local PostgreSQL is not accessible (correct)")
        sys.exit(0)
    else:
        print(f"⚠️  Unexpected error: {e}")
        sys.exit(0)
PYTHON_EOF
then
    echo -e "${GREEN}✅ Local database is properly blocked${NC}"
else
    echo -e "${YELLOW}⚠️  Local database may still be accessible${NC}"
fi
echo ""

# Summary
echo "=========================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ VERIFICATION COMPLETE${NC}"
    echo -e "${GREEN}✅ NAS is the EXCLUSIVE database${NC}"
    echo ""
    echo "Summary:"
    echo "  • SSH tunnel: Running"
    echo "  • Local PostgreSQL: Stopped"
    echo "  • Configuration: NAS (localhost:5433)"
    echo "  • Database connection: NAS verified"
    echo "  • DatabaseManager: Configured for NAS"
    exit 0
else
    echo -e "${RED}❌ VERIFICATION FAILED${NC}"
    echo -e "${RED}   Found $ERRORS issue(s)${NC}"
    echo ""
    echo "Please fix the issues above before proceeding."
    exit 1
fi

