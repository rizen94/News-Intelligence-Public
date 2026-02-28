#!/bin/bash
# Pre-Testing Readiness Checklist
# Verifies all systems are ready before running tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${CYAN}🧪 Pre-Testing Readiness Checklist${NC}"
echo "=========================================="
echo ""

ISSUES=0
WARNINGS=0

# 1. Database Configuration
echo -e "${CYAN}[1/7]${NC} Database Configuration"
if [ -f "$PROJECT_DIR/configs/.env" ]; then
    DB_HOST=$(grep "^DB_HOST=" "$PROJECT_DIR/configs/.env" | cut -d'=' -f2 | tr -d ' ')
    DB_PORT=$(grep "^DB_PORT=" "$PROJECT_DIR/configs/.env" | cut -d'=' -f2 | tr -d ' ')
    if [[ "$DB_HOST" == "localhost" ]] && [[ "$DB_PORT" == "5433" ]]; then
        echo -e "${GREEN}✅ .env configured for NAS (localhost:5433)${NC}"
    else
        echo -e "${RED}❌ .env not configured for NAS${NC}"
        echo "   Current: DB_HOST=$DB_HOST, DB_PORT=$DB_PORT"
        ISSUES=$((ISSUES + 1))
    fi
else
    echo -e "${RED}❌ .env file missing${NC}"
    ISSUES=$((ISSUES + 1))
fi
echo ""

# 2. SSH Tunnel
echo -e "${CYAN}[2/7]${NC} SSH Tunnel to NAS"
if ps aux | grep -q "[s]sh -L 5433:localhost:5432.*192.168.93.100"; then
    TUNNEL_PID=$(ps aux | grep "[s]sh -L 5433:localhost:5432.*192.168.93.100" | awk '{print $2}')
    echo -e "${GREEN}✅ SSH tunnel running (PID: $TUNNEL_PID)${NC}"
else
    echo -e "${RED}❌ SSH tunnel not running${NC}"
    echo "   Run: ./scripts/setup_nas_ssh_tunnel.sh"
    ISSUES=$((ISSUES + 1))
fi
echo ""

# 3. Local PostgreSQL
echo -e "${CYAN}[3/7]${NC} Local PostgreSQL Status"
if docker ps --filter "name=postgres" --format "{{.Names}}" 2>/dev/null | grep -q .; then
    echo -e "${YELLOW}⚠️  Local PostgreSQL still running${NC}"
    echo "   Consider stopping: docker stop news-intelligence-postgres"
    WARNINGS=$((WARNINGS + 1))
else
    echo -e "${GREEN}✅ Local PostgreSQL stopped${NC}"
fi
echo ""

# 4. Database Connection
echo -e "${CYAN}[4/7]${NC} Database Connection Test"
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
    
    import psycopg2
    conn = psycopg2.connect(**config)
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
        print(f"✅ Connected to NAS database")
        print(f"   Articles: {articles} records")
        print(f"   RSS Feeds: {rss} records")
        sys.exit(0)
    else:
        print(f"❌ Not connected to NAS")
        sys.exit(1)
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)
PYTHON_EOF
then
    echo -e "${GREEN}✅ Database connection successful${NC}"
else
    echo -e "${RED}❌ Database connection failed${NC}"
    ISSUES=$((ISSUES + 1))
fi
echo ""

# 5. Redis
echo -e "${CYAN}[5/7]${NC} Redis Service"
if docker ps --filter "name=redis" --format "{{.Names}}" 2>/dev/null | grep -q .; then
    echo -e "${GREEN}✅ Redis container running${NC}"
else
    echo -e "${YELLOW}⚠️  Redis not running (may be needed for caching)${NC}"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# 6. Application Dependencies
echo -e "${CYAN}[6/7]${NC} Application Dependencies"
if [ -d "$PROJECT_DIR/api" ] && [ -f "$PROJECT_DIR/api/requirements.txt" ]; then
    echo -e "${GREEN}✅ API directory and requirements.txt found${NC}"
else
    echo -e "${RED}❌ API directory or requirements.txt missing${NC}"
    ISSUES=$((ISSUES + 1))
fi

if [ -d "$PROJECT_DIR/web" ] && [ -f "$PROJECT_DIR/web/package.json" ]; then
    echo -e "${GREEN}✅ Web directory and package.json found${NC}"
else
    echo -e "${RED}❌ Web directory or package.json missing${NC}"
    ISSUES=$((ISSUES + 1))
fi
echo ""

# 7. SSH Tunnel Persistence
echo -e "${CYAN}[7/7]${NC} SSH Tunnel Persistence"
if systemctl list-unit-files 2>/dev/null | grep -q "nas.*tunnel\|ssh.*tunnel"; then
    echo -e "${GREEN}✅ Systemd service configured${NC}"
else
    echo -e "${YELLOW}⚠️  No systemd service (tunnel may not survive reboot)${NC}"
    echo "   Consider setting up: ./scripts/setup_persistent_nas_connection.sh"
    WARNINGS=$((WARNINGS + 1))
fi
echo ""

# Summary
echo "=========================================="
if [ $ISSUES -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ READY FOR TESTING${NC}"
    echo ""
    echo "All checks passed. You can proceed with testing."
    echo ""
    echo "To start the system:"
    echo "  ./start_system.sh"
    exit 0
elif [ $ISSUES -eq 0 ]; then
    echo -e "${YELLOW}⚠️  READY WITH WARNINGS${NC}"
    echo ""
    echo "Found $WARNINGS warning(s) but no critical issues."
    echo "You can proceed with testing, but consider addressing warnings."
    echo ""
    echo "To start the system:"
    echo "  ./start_system.sh"
    exit 0
else
    echo -e "${RED}❌ NOT READY FOR TESTING${NC}"
    echo ""
    echo "Found $ISSUES critical issue(s) and $WARNINGS warning(s)."
    echo "Please fix the issues above before testing."
    exit 1
fi

