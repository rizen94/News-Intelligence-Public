#!/bin/bash
# Test API endpoints to verify routes and data population
# This script tests the API endpoints directly (requires API server to be running)

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"

echo "============================================================"
echo "  API ENDPOINT TEST SUITE"
echo "============================================================"
echo ""
echo "Testing API at: $API_BASE_URL"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

test_endpoint() {
    local method=$1
    local url=$2
    local name=$3
    local params=$4
    
    echo -n "Testing $name... "
    
    if [ "$method" = "GET" ]; then
        if [ -n "$params" ]; then
            response=$(curl -s -w "\n%{http_code}" "$url?$params" 2>/dev/null)
        else
            response=$(curl -s -w "\n%{http_code}" "$url" 2>/dev/null)
        fi
    else
        response=$(curl -s -w "\n%{http_code}" -X "$method" "$url" 2>/dev/null)
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 400 ]; then
        echo -e "${GREEN}✅ PASS${NC} (HTTP $http_code)"
        PASSED=$((PASSED + 1))
        
        # Try to extract data counts
        if echo "$body" | grep -q '"success"'; then
            if echo "$body" | grep -q '"total"'; then
                total=$(echo "$body" | grep -o '"total":[0-9]*' | grep -o '[0-9]*' | head -1)
                if [ -n "$total" ]; then
                    echo "      Total records: $total"
                fi
            fi
        fi
        return 0
    else
        echo -e "${RED}❌ FAIL${NC} (HTTP $http_code)"
        FAILED=$((FAILED + 1))
        if [ "$http_code" = "000" ]; then
            echo "      Error: Cannot connect to API server. Is it running?"
        else
            echo "      Response: $(echo "$body" | head -c 200)"
        fi
        return 1
    fi
}

echo "============================================================"
echo "  1. HEALTH CHECK"
echo "============================================================"
test_endpoint "GET" "$API_BASE_URL/api/system_monitoring/health" "System Health"

echo ""
echo "============================================================"
echo "  2. DOMAIN ENDPOINTS"
echo "============================================================"

for domain in politics finance science-tech; do
    echo ""
    echo "  Domain: $domain"
    echo "  ----------------------------------------"
    
    # Articles
    test_endpoint "GET" "$API_BASE_URL/api/$domain/articles" \
        "Articles" "limit=10&offset=0"
    
    # Storylines
    test_endpoint "GET" "$API_BASE_URL/api/$domain/storylines" \
        "Storylines" "limit=10&offset=0"
    
    # RSS Feeds
    test_endpoint "GET" "$API_BASE_URL/api/$domain/rss_feeds" \
        "RSS Feeds"
done

echo ""
echo "============================================================"
echo "  3. PAGINATION TEST"
echo "============================================================"

echo ""
echo "  Testing pagination for politics domain"
echo "  ----------------------------------------"

# Test page 1
test_endpoint "GET" "$API_BASE_URL/api/politics/articles" \
    "Page 1 (offset=0)" "limit=5&offset=0"

# Test page 2
test_endpoint "GET" "$API_BASE_URL/api/politics/articles" \
    "Page 2 (offset=5)" "limit=5&offset=5"

echo ""
echo "============================================================"
echo "  TEST SUMMARY"
echo "============================================================"
echo ""
TOTAL=$((PASSED + FAILED))
if [ $TOTAL -gt 0 ]; then
    SUCCESS_RATE=$((PASSED * 100 / TOTAL))
    echo "  Tests Passed: $PASSED / $TOTAL"
    echo "  Success Rate: $SUCCESS_RATE%"
    echo ""
    
    if [ $FAILED -eq 0 ]; then
        echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
    else
        echo -e "${YELLOW}⚠️  $FAILED TESTS FAILED${NC}"
    fi
else
    echo -e "${RED}❌ NO TESTS RUN${NC}"
    echo "  Make sure the API server is running on $API_BASE_URL"
fi

echo ""
echo "============================================================"


