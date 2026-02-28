#!/bin/bash
# NAS Database Requirement Validator
# Ensures system is configured to use NAS database, not local storage

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🔍 Validating NAS Database Requirement"
echo "======================================"
echo ""

ERRORS=0
WARNINGS=0

# Check DB_HOST environment variable
if [[ -z "${DB_HOST}" ]]; then
    echo -e "${RED}❌ ERROR:${NC} DB_HOST not set"
    echo "   System requires NAS database (192.168.93.100)"
    ERRORS=$((ERRORS + 1))
else
    echo -e "${GREEN}✅ DB_HOST:${NC} ${DB_HOST}"
fi

# Check if using localhost
if [[ "${DB_HOST}" == "localhost" ]] || [[ "${DB_HOST}" == "127.0.0.1" ]]; then
    if [[ "${ALLOW_LOCAL_DB}" != "true" ]]; then
        echo -e "${RED}❌ ERROR:${NC} Local database connection detected"
        echo "   Local storage is BLOCKED (insufficient space)"
        echo "   Set ALLOW_LOCAL_DB=true to override (NOT RECOMMENDED)"
        ERRORS=$((ERRORS + 1))
    else
        echo -e "${YELLOW}⚠️  WARNING:${NC} Using local database (ALLOW_LOCAL_DB=true)"
        echo "   This is NOT RECOMMENDED - local storage has insufficient space"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

# Check if using NAS
if [[ "${DB_HOST}" == "192.168.93.100" ]]; then
    echo -e "${GREEN}✅ Using NAS database${NC}"
    
    # Test NAS connectivity
    echo "   Testing NAS connectivity..."
    if nc -zv -w 3 "${DB_HOST}" 5432 > /dev/null 2>&1; then
        echo -e "   ${GREEN}✅ NAS database is accessible${NC}"
    else
        echo -e "   ${RED}❌ Cannot connect to NAS database${NC}"
        echo "   Please ensure NAS is accessible and PostgreSQL is running"
        ERRORS=$((ERRORS + 1))
    fi
fi

# Check database configuration file
echo ""
echo "Checking database configuration..."
if grep -q "localhost" api/config/database.py 2>/dev/null; then
    if ! grep -q "ALLOW_LOCAL_DB" api/config/database.py 2>/dev/null; then
        echo -e "${YELLOW}⚠️  WARNING:${NC} database.py may have localhost fallback"
        WARNINGS=$((WARNINGS + 1))
    fi
fi

# Summary
echo ""
echo "======================================"
if [[ $ERRORS -eq 0 ]]; then
    if [[ $WARNINGS -eq 0 ]]; then
        echo -e "${GREEN}✅ Validation PASSED${NC}"
        echo "   System is correctly configured for NAS database"
        exit 0
    else
        echo -e "${YELLOW}⚠️  Validation PASSED with warnings${NC}"
        echo "   $WARNINGS warning(s) found"
        exit 0
    fi
else
    echo -e "${RED}❌ Validation FAILED${NC}"
    echo "   $ERRORS error(s) found"
    echo ""
    echo "Fix the errors above before starting the system."
    exit 1
fi

