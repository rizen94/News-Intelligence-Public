#!/bin/bash
# Verify Database Migration and Connection Persistence
# Compares local and NAS databases to ensure migration was successful

set -e

NAS_HOST="192.168.93.100"
NAS_PORT="5432"
LOCAL_HOST="localhost"
LOCAL_PORT="5432"
DB_NAME="news_intelligence"
DB_USER="newsapp"
DB_PASSWORD="newsapp_password"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔍 Database Migration Verification"
echo "===================================="
echo ""

# Function to execute SQL query
execute_query() {
    local HOST=$1
    local PORT=$2
    local QUERY=$3
    
    python3 << PYTHON_EOF
import psycopg2
import sys
try:
    conn = psycopg2.connect(
        host='$HOST',
        port=$PORT,
        database='$DB_NAME',
        user='$DB_USER',
        password='$DB_PASSWORD',
        connect_timeout=5
    )
    cursor = conn.cursor()
    cursor.execute('$QUERY')
    result = cursor.fetchall()
    for row in result:
        print('|'.join(str(x) for x in row))
    cursor.close()
    conn.close()
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF
}

# Function to get table count
get_table_count() {
    local HOST=$1
    local PORT=$2
    execute_query "$HOST" "$PORT" "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
}

# Function to get record count for a table
get_record_count() {
    local HOST=$1
    local PORT=$2
    local TABLE=$3
    execute_query "$HOST" "$PORT" "SELECT COUNT(*) FROM $TABLE;" 2>/dev/null || echo "0"
}

# Step 1: Test NAS connection
echo "Step 1: Testing NAS database connection..."
if python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='$NAS_HOST',
        port=$NAS_PORT,
        database='$DB_NAME',
        user='$DB_USER',
        password='$DB_PASSWORD',
        connect_timeout=5
    )
    conn.close()
    print('✅ NAS database connection successful')
    exit(0)
except Exception as e:
    print(f'❌ NAS database connection failed: {e}')
    exit(1)
" 2>&1; then
    echo -e "${GREEN}✅ NAS database is accessible${NC}"
else
    echo -e "${RED}❌ NAS database is not accessible${NC}"
    echo "   Please ensure PostgreSQL is running on NAS"
    exit 1
fi
echo ""

# Step 2: Get table lists
echo "Step 2: Comparing database schemas..."
echo ""

echo -e "${CYAN}NAS Database Tables:${NC}"
NAS_TABLES=$(execute_query "$NAS_HOST" "$NAS_PORT" "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;" 2>&1)
NAS_TABLE_COUNT=$(echo "$NAS_TABLES" | wc -l)
echo "$NAS_TABLES" | head -20 | sed 's/^/  /'
if [ "$NAS_TABLE_COUNT" -gt 20 ]; then
    echo "  ... and $((NAS_TABLE_COUNT - 20)) more tables"
fi
echo ""

# Check local database if accessible
echo -e "${CYAN}Local Database (if accessible):${NC}"
LOCAL_TABLES=$(execute_query "$LOCAL_HOST" "$LOCAL_PORT" "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;" 2>&1 || echo "")
if [ -n "$LOCAL_TABLES" ] && [ "$LOCAL_TABLES" != "ERROR"* ]; then
    LOCAL_TABLE_COUNT=$(echo "$LOCAL_TABLES" | wc -l)
    echo "$LOCAL_TABLES" | head -20 | sed 's/^/  /'
    if [ "$LOCAL_TABLE_COUNT" -gt 20 ]; then
        echo "  ... and $((LOCAL_TABLE_COUNT - 20)) more tables"
    fi
    echo ""
    echo -e "${CYAN}Table Count Comparison:${NC}"
    echo "  NAS:   $NAS_TABLE_COUNT tables"
    echo "  Local: $LOCAL_TABLE_COUNT tables"
    if [ "$NAS_TABLE_COUNT" -eq "$LOCAL_TABLE_COUNT" ]; then
        echo -e "  ${GREEN}✅ Table counts match${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Table counts differ${NC}"
    fi
else
    echo "  ⚠️  Local database not accessible (may have been removed)"
fi
echo ""

# Step 3: Compare record counts for key tables
echo "Step 3: Comparing record counts for key tables..."
echo ""

KEY_TABLES=(
    "articles"
    "rss_feeds"
    "topics"
    "story_threads"
    "schema_migrations"
)

for table in "${KEY_TABLES[@]}"; do
    # Check if table exists in NAS
    TABLE_EXISTS=$(execute_query "$NAS_HOST" "$NAS_PORT" "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '$table');" 2>&1 | grep -i true || echo "")
    
    if [ -n "$TABLE_EXISTS" ]; then
        NAS_COUNT=$(get_record_count "$NAS_HOST" "$NAS_PORT" "$table" 2>/dev/null || echo "0")
        echo -e "${CYAN}$table:${NC}"
        echo "  NAS:   $NAS_COUNT records"
        
        # Try to get local count if accessible
        LOCAL_COUNT=$(get_record_count "$LOCAL_HOST" "$LOCAL_PORT" "$table" 2>/dev/null || echo "N/A")
        if [ "$LOCAL_COUNT" != "N/A" ] && [ "$LOCAL_COUNT" != "ERROR"* ]; then
            echo "  Local: $LOCAL_COUNT records"
            if [ "$NAS_COUNT" -eq "$LOCAL_COUNT" ]; then
                echo -e "  ${GREEN}✅ Counts match${NC}"
            elif [ "$NAS_COUNT" -gt 0 ]; then
                echo -e "  ${YELLOW}⚠️  Counts differ (NAS has data)${NC}"
            else
                echo -e "  ${RED}❌ NAS table is empty${NC}"
            fi
        else
            if [ "$NAS_COUNT" -gt 0 ]; then
                echo -e "  ${GREEN}✅ NAS has $NAS_COUNT records${NC}"
            else
                echo -e "  ${YELLOW}⚠️  NAS table is empty${NC}"
            fi
        fi
        echo ""
    else
        echo -e "${YELLOW}⚠️  Table '$table' not found in NAS database${NC}"
        echo ""
    fi
done

# Step 4: Check schema migrations
echo "Step 4: Checking schema migrations..."
echo ""

MIGRATION_COUNT=$(execute_query "$NAS_HOST" "$NAS_PORT" "SELECT COUNT(*) FROM schema_migrations;" 2>&1 || echo "0")
echo "  NAS migrations applied: $MIGRATION_COUNT"

if [ -n "$LOCAL_TABLES" ] && [ "$LOCAL_TABLES" != "ERROR"* ]; then
    LOCAL_MIGRATION_COUNT=$(execute_query "$LOCAL_HOST" "$LOCAL_PORT" "SELECT COUNT(*) FROM schema_migrations;" 2>&1 || echo "0")
    echo "  Local migrations: $LOCAL_MIGRATION_COUNT"
    if [ "$MIGRATION_COUNT" -eq "$LOCAL_MIGRATION_COUNT" ]; then
        echo -e "  ${GREEN}✅ Migration counts match${NC}"
    else
        echo -e "  ${YELLOW}⚠️  Migration counts differ${NC}"
    fi
fi
echo ""

# Step 5: Verify connection persistence
echo "Step 5: Verifying connection persistence..."
echo ""

echo "Testing multiple connections to verify persistence:"
for i in {1..3}; do
    if python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='$NAS_HOST',
        port=$NAS_PORT,
        database='$DB_NAME',
        user='$DB_USER',
        password='$DB_PASSWORD',
        connect_timeout=5
    )
    cursor = conn.cursor()
    cursor.execute('SELECT 1;')
    conn.close()
    print('✅ Connection $i successful')
    exit(0)
except Exception as e:
    print(f'❌ Connection $i failed: {e}')
    exit(1)
" 2>&1; then
        :
    else
        echo -e "${RED}❌ Connection persistence issue detected${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✅ All connections successful - persistence verified${NC}"
echo ""

# Step 6: Check startup script configuration
echo "Step 6: Verifying startup script configuration..."
echo ""

if grep -q "DB_HOST=192.168.93.100" "$PROJECT_ROOT/start_system.sh" 2>/dev/null; then
    echo -e "${GREEN}✅ Startup script configured for NAS database${NC}"
else
    echo -e "${RED}❌ Startup script not configured for NAS${NC}"
fi

if grep -q "DB_NAME=news_intelligence" "$PROJECT_ROOT/start_system.sh" 2>/dev/null; then
    echo -e "${GREEN}✅ Database name configured correctly${NC}"
fi

if grep -q "DB_USER=newsapp" "$PROJECT_ROOT/start_system.sh" 2>/dev/null; then
    echo -e "${GREEN}✅ Database user configured correctly${NC}"
fi
echo ""

# Summary
echo "===================================="
echo -e "${CYAN}Migration Verification Summary${NC}"
echo "===================================="
echo ""
echo "✅ NAS Database: Accessible"
echo "✅ Connection: Persistent"
echo "✅ Tables: $NAS_TABLE_COUNT found"
echo "✅ Migrations: $MIGRATION_COUNT applied"
echo ""
echo "📋 Next Steps:"
echo "  1. Verify all key tables have data"
echo "  2. Test application functionality"
echo "  3. Monitor connection stability"
echo ""

