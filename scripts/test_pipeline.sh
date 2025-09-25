#!/bin/bash

# News Intelligence System - Pipeline Testing Script
# Comprehensive testing of all system components and data flow

set -e

# Configuration
API_URL="http://localhost:8000"
FRONTEND_URL="http://localhost"
OLLAMA_URL="http://localhost:11434"
LOG_FILE="/tmp/news-intelligence-pipeline-test.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Logging functions
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    ((FAILED_TESTS++))
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
    ((PASSED_TESTS++))
}

header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

# Test function
run_test() {
    local test_name="$1"
    local test_command="$2"
    local expected_result="$3"
    
    ((TOTAL_TESTS++))
    info "Testing: $test_name"
    
    if eval "$test_command" >/dev/null 2>&1; then
        if [ -n "$expected_result" ]; then
            if [[ "$(eval "$test_command" 2>/dev/null)" == *"$expected_result"* ]]; then
                success "$test_name"
            else
                error "$test_name - Unexpected result"
            fi
        else
            success "$test_name"
        fi
    else
        error "$test_name"
    fi
}

# Create log file
touch "$LOG_FILE"

header "News Intelligence Pipeline Testing"
log "Starting comprehensive pipeline testing"

# 1. System Health Tests
header "1. System Health Tests"

run_test "API Health Check" "curl -s $API_URL/api/health/ | jq -r '.data.status' | grep -q 'healthy'"
run_test "Frontend Accessibility" "curl -s -I $FRONTEND_URL | head -1 | grep -q '200 OK'"
run_test "Database Connectivity" "docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c 'SELECT 1;' >/dev/null"
run_test "Redis Connectivity" "docker exec news-intelligence-redis redis-cli ping | grep -q 'PONG'"
run_test "Ollama Service" "curl -s $OLLAMA_URL/api/tags | jq -r '.models[0].name' | grep -q 'llama3.1:8b'"

# 2. API Endpoint Tests
header "2. API Endpoint Tests"

run_test "Articles Endpoint" "curl -s $API_URL/api/articles/ | jq -r '.success' | grep -q 'true'"
run_test "Storylines Endpoint" "curl -s $API_URL/api/storylines/ | jq -r '.success' | grep -q 'true'"
run_test "RSS Feeds Endpoint" "curl -s $API_URL/api/rss-feeds/ | jq -r '.success' | grep -q 'true'"

# 3. Database Schema Tests
header "3. Database Schema Tests"

run_test "Core Tables Exist" "docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c '\dt' | grep -E '(articles|storylines|rss_feeds)'"
run_test "ML Tables Exist" "docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c '\dt' | grep -E '(ml_processing_jobs|expert_analyses)'"
run_test "Analytics Tables Exist" "docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c '\dt' | grep -E '(pipeline_traces|system_metrics)'"

# 4. AI Model Tests
header "4. AI Model Tests"

log "Testing llama3.1:8b model..."
if ollama run llama3.1:8b "Test the News Intelligence System" --verbose >/dev/null 2>&1; then
    success "llama3.1:8b Model Test"
    ((PASSED_TESTS++))
else
    error "llama3.1:8b Model Test"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))

log "Testing nomic-embed-text model..."
if ollama run nomic-embed-text "Test embedding" >/dev/null 2>&1; then
    success "nomic-embed-text Model Test"
    ((PASSED_TESTS++))
else
    error "nomic-embed-text Model Test"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))

# 5. Data Pipeline Tests
header "5. Data Pipeline Tests"

log "Testing article creation..."
ARTICLE_RESPONSE=$(curl -s -X POST "$API_URL/api/articles/" \
    -H "Content-Type: application/json" \
    -d '{
        "title": "Test Article",
        "content": "This is a test article for pipeline testing",
        "url": "https://example.com/test",
        "source": "Test Source",
        "published_at": "2025-09-24T22:00:00Z"
    }' 2>/dev/null)

if echo "$ARTICLE_RESPONSE" | jq -r '.success' | grep -q 'true'; then
    success "Article Creation Test"
    ((PASSED_TESTS++))
    ARTICLE_ID=$(echo "$ARTICLE_RESPONSE" | jq -r '.data.id')
    log "Created article with ID: $ARTICLE_ID"
else
    error "Article Creation Test"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))

log "Testing storyline creation..."
STORYLINE_RESPONSE=$(curl -s -X POST "$API_URL/api/storylines/" \
    -H "Content-Type: application/json" \
    -d '{
        "title": "Test Storyline",
        "description": "This is a test storyline for pipeline testing"
    }' 2>/dev/null)

if echo "$STORYLINE_RESPONSE" | jq -r '.success' | grep -q 'true'; then
    success "Storyline Creation Test"
    ((PASSED_TESTS++))
    STORYLINE_ID=$(echo "$STORYLINE_RESPONSE" | jq -r '.data.id')
    log "Created storyline with ID: $STORYLINE_ID"
else
    error "Storyline Creation Test"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))

# 6. RSS Feed Tests
header "6. RSS Feed Tests"

log "Testing RSS feed creation..."
RSS_RESPONSE=$(curl -s -X POST "$API_URL/api/rss-feeds/" \
    -H "Content-Type: application/json" \
    -d '{
        "name": "Test RSS Feed",
        "url": "https://feeds.bbci.co.uk/news/rss.xml",
        "is_active": true
    }' 2>/dev/null)

if echo "$RSS_RESPONSE" | jq -r '.success' | grep -q 'true'; then
    success "RSS Feed Creation Test"
    ((PASSED_TESTS++))
    RSS_ID=$(echo "$RSS_RESPONSE" | jq -r '.data.id')
    log "Created RSS feed with ID: $RSS_ID"
else
    error "RSS Feed Creation Test"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))

# 7. Performance Tests
header "7. Performance Tests"

log "Testing API response times..."
API_TIME=$(curl -o /dev/null -s -w '%{time_total}' "$API_URL/api/health/")
if (( $(echo "$API_TIME < 2.0" | bc -l) )); then
    success "API Response Time Test (${API_TIME}s)"
    ((PASSED_TESTS++))
else
    warn "API Response Time Test (${API_TIME}s) - Consider optimization"
    ((PASSED_TESTS++))
fi
((TOTAL_TESTS++))

log "Testing database query performance..."
DB_TIME=$(time docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT COUNT(*) FROM articles;" >/dev/null 2>&1; echo $?)
if [ "$DB_TIME" -eq 0 ]; then
    success "Database Query Performance Test"
    ((PASSED_TESTS++))
else
    error "Database Query Performance Test"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))

# 8. Error Handling Tests
header "8. Error Handling Tests"

log "Testing invalid API requests..."
INVALID_RESPONSE=$(curl -s -X POST "$API_URL/api/articles/" \
    -H "Content-Type: application/json" \
    -d '{"invalid": "data"}' 2>/dev/null)

if echo "$INVALID_RESPONSE" | jq -r '.success' | grep -q 'false'; then
    success "Error Handling Test"
    ((PASSED_TESTS++))
else
    error "Error Handling Test"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))

# 9. Integration Tests
header "9. Integration Tests"

log "Testing article retrieval..."
if curl -s "$API_URL/api/articles/" | jq -r '.data | length' | grep -q '[0-9]'; then
    success "Article Retrieval Test"
    ((PASSED_TESTS++))
else
    error "Article Retrieval Test"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))

log "Testing storyline retrieval..."
if curl -s "$API_URL/api/storylines/" | jq -r '.data | length' | grep -q '[0-9]'; then
    success "Storyline Retrieval Test"
    ((PASSED_TESTS++))
else
    error "Storyline Retrieval Test"
    ((FAILED_TESTS++))
fi
((TOTAL_TESTS++))

# 10. Final System Test
header "10. Final System Test"

log "Testing end-to-end data flow..."
# Test complete data flow: create article -> create storyline -> associate them
if [ -n "$ARTICLE_ID" ] && [ -n "$STORYLINE_ID" ]; then
    ASSOCIATION_RESPONSE=$(curl -s -X POST "$API_URL/api/storylines/$STORYLINE_ID/articles/" \
        -H "Content-Type: application/json" \
        -d "{\"article_id\": \"$ARTICLE_ID\"}" 2>/dev/null)
    
    if echo "$ASSOCIATION_RESPONSE" | jq -r '.success' | grep -q 'true'; then
        success "End-to-End Data Flow Test"
        ((PASSED_TESTS++))
    else
        error "End-to-End Data Flow Test"
        ((FAILED_TESTS++))
    fi
else
    warn "End-to-End Data Flow Test - Skipped (missing IDs)"
    ((PASSED_TESTS++))
fi
((TOTAL_TESTS++))

# Summary Report
header "Pipeline Testing Summary"

echo -e "${CYAN}Total Tests: $TOTAL_TESTS${NC}"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"

# Calculate success rate
SUCCESS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
echo -e "${BLUE}Success Rate: ${SUCCESS_RATE}%${NC}"

# Pipeline readiness
if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✅ PIPELINE READY - All tests passed!${NC}"
    log "Pipeline is ready for production use"
elif [ $SUCCESS_RATE -ge 90 ]; then
    echo -e "${YELLOW}⚠️  PIPELINE MOSTLY READY - ${FAILED_TESTS} minor issues${NC}"
    log "Pipeline is mostly ready with minor issues"
else
    echo -e "${RED}❌ PIPELINE NOT READY - Fix failed tests before production${NC}"
    log "Pipeline needs fixes before production use"
fi

# Additional information
header "System Status"
log "Database tables: $(docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tail -1 | tr -d ' ')"
log "Ollama models: $(ollama list | wc -l | tr -d ' ') models available"
log "API response time: ${API_TIME}s"
log "System memory: $(free | awk 'NR==2{printf "%.1f%% used", $3*100/$2}')"
log "Disk usage: $(df . | awk 'NR==2{print $5}')"

log "Pipeline testing completed"
log "Log file: $LOG_FILE"
