#!/usr/bin/env bash
# News Intelligence - Widow Migration Audit Script
# Run this on the Widow server to verify the migration

set -euo pipefail

echo "=============================================="
echo "News Intelligence - Widow Migration Audit"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS_COUNT=0
FAIL_COUNT=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS_COUNT++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL_COUNT++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# ==============================================
# 1. Python Environment Check
# ==============================================
echo "=== 1. Python Environment ==="

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    check_pass "Python installed: $PYTHON_VERSION"
else
    check_fail "Python not installed"
fi

if command -v uv &> /dev/null; then
    check_pass "UV package manager installed"
else
    check_warn "UV not found - using pip"
fi

# Check if venv exists
if [ -d "venv" ] || [ -d ".venv" ]; then
    check_pass "Virtual environment exists"
else
    check_warn "No virtual environment found - may need to create"
fi

echo ""

# ==============================================
# 2. Environment File Check
# ==============================================
echo "=== 2. Environment Configuration ==="

if [ -f ".env" ]; then
    check_pass ".env file exists"
    
    # Check for database configuration
    if grep -q "DATABASE_URL" .env; then
        DB_URL=$(grep "^DATABASE_URL=" .env | head -1)
        echo "   Database URL: $DB_URL"
        
        # Check if using localhost (correct for Widow) vs remote IP
        if echo "$DB_URL" | grep -q "localhost\|127\.0\.0\.1"; then
            check_pass "Database using local connection (correct for Widow)"
        elif echo "$DB_URL" | grep -q "192\.168"; then
            check_warn "Database using LAN IP - may need to change to localhost"
        else
            check_pass "Database URL format found"
        fi
    else
        check_fail "DATABASE_URL not found in .env"
    fi
    
    # Check data directory
    if grep -q "NEWS_INTEL_DATA_DIR" .env; then
        DATA_DIR=$(grep "^NEWS_INTEL_DATA_DIR=" .env | head -1)
        echo "   Data Directory: $DATA_DIR"
        check_pass "NEWS_INTEL_DATA_DIR configured"
    else
        check_warn "NEWS_INTEL_DATA_DIR not in .env"
    fi
    
else
    check_fail ".env file not found"
fi

echo ""

# ==============================================
# 3. Database Connection Test
# ==============================================
echo "=== 3. Database Connection ==="

if [ -f ".env" ]; then
    source .env 2>/dev/null || true
    
    if [ -n "${DATABASE_URL:-}" ]; then
        # Extract host and port from DATABASE_URL
        DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*\/\/\([^:]*\):.*/\1/p')
        DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*\/\/[^:]*:\([0-9]*\).*/\1/p')
        
        echo "   Attempting connection to: $DB_HOST:$DB_PORT"
        
        if command -v psql &> /dev/null; then
            if psql -h "$DB_HOST" -p "$DB_PORT" -U newsintel -d news_intel -c "SELECT 1;" &>/dev/null; then
                check_pass "Database connection successful"
                
                # Check table count
                TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U newsintel -d news_intel -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
                echo "   Tables in database: $TABLE_COUNT"
                
                if [ "$TABLE_COUNT" -gt "50" ]; then
                    check_pass "Database appears to have data migrated"
                else
                    check_warn "Low table count - verify migration completed"
                fi
            else
                check_fail "Database connection failed"
                echo "   Try: psql -h $DB_HOST -p $DB_PORT -U newsintel -d news_intel"
            fi
        else
            check_warn "psql not available for testing"
        fi
    else
        check_warn "DATABASE_URL not set in environment"
    fi
else
    check_warn "Cannot test database - .env not found"
fi

echo ""

# ==============================================
# 4. Docker Containers Check
# ==============================================
echo "=== 4. Docker Containers ==="

if command -v docker &> /dev/null; then
    check_pass "Docker is available"
    
    # Check for news_intelligence container
    NI_CONTAINERS=$(docker ps -a --format "{{.Names}}" | grep -iE "news|intelligence" || true)
    if [ -n "$NI_CONTAINERS" ]; then
        echo "   Found containers:"
        echo "$NI_CONTAINERS" | while read -r container; do
            STATUS=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null || echo "unknown")
            echo "   - $container: $STATUS"
        done
    else
        check_warn "No News Intelligence containers found"
    fi
    
    # Check for ChromaDB
    CHROMA_STATUS=$(docker ps --format "{{.Names}}: {{.Status}}" | grep -i chroma || echo "Not running")
    echo "   ChromaDB: $CHROMA_STATUS"
    
else
    check_warn "Docker not available"
fi

echo ""

# ==============================================
# 5. File Paths Verification
# ==============================================
echo "=== 5. File Paths & Data Directories ==="

# Check paths.py
if [ -f "api/config/paths.py" ]; then
    check_pass "paths.py exists"
    cat api/config/paths.py
else
    check_fail "paths.py not found"
fi

# Check data directories
DATA_DIRS=("data" "data/chroma" "reports" "backups" "configs")
for dir in "${DATA_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        SIZE=$(du -sh "$dir" 2>/dev/null | cut -f1)
        check_pass "$dir exists ($SIZE)"
    else
        check_warn "$dir not found"
    fi
done

echo ""

# ==============================================
# 6. API Import Test
# ==============================================
echo "=== 6. Python Import Test ==="

# Try importing main modules
python3 -c "
import sys
try:
    sys.path.insert(0, 'api')
    from config.settings import get_settings
    print('Settings import: OK')
except Exception as e:
    print(f'Settings import: FAILED - {e}')
    sys.exit(1)
" 2>&1 || check_fail "Settings import failed"

echo ""

# ==============================================
# 7. Summary
# ==============================================
echo "=============================================="
echo "AUDIT SUMMARY"
echo "=============================================="
echo -e "${GREEN}Passed:${NC} $PASS_COUNT"
echo -e "${RED}Failed:${NC} $FAIL_COUNT"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}All critical checks passed!${NC}"
    exit 0
else
    echo -e "${RED}Some checks failed. Please review above.${NC}"
    exit 1
fi