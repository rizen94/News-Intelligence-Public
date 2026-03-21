#!/bin/bash

# News Intelligence System - Pre-Deployment Verification Script
# Comprehensive checklist before test deployment

set -e

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="/tmp/news-intelligence-pre-deployment.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Counters
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0
WARNING_CHECKS=0

# Logging functions
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
    ((FAILED_CHECKS++))
}

warn() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
    ((WARNING_CHECKS++))
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
    ((PASSED_CHECKS++))
}

header() {
    echo -e "${PURPLE}================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}================================${NC}"
}

check() {
    local check_name="$1"
    local command="$2"
    local expected_result="$3"
    
    ((TOTAL_CHECKS++))
    info "Checking: $check_name"
    
    if eval "$command" >/dev/null 2>&1; then
        if [ -n "$expected_result" ]; then
            if [[ "$(eval "$command" 2>/dev/null)" == *"$expected_result"* ]]; then
                success "$check_name"
            else
                error "$check_name - Unexpected result"
            fi
        else
            success "$check_name"
        fi
    else
        error "$check_name"
    fi
}

# Create log file
touch "$LOG_FILE"

header "News Intelligence Pre-Deployment Verification"
log "Starting comprehensive pre-deployment checks"

cd "$PROJECT_DIR"

# 1. Infrastructure Verification
header "1. Infrastructure Verification"

# Docker and Docker Compose
check "Docker Installation" "docker --version"
check "Docker Compose Installation" "docker-compose --version"
check "Docker Daemon Running" "docker info"

# System Resources
check "Available Memory" "free -m | awk 'NR==2{print \$7}' | awk '\$1 > 1000'"
check "Available Disk Space" "df -h . | awk 'NR==2{print \$4}' | grep -E '[0-9]+G'"
check "CPU Cores" "nproc | awk '\$1 >= 2'"

# Network Connectivity
check "Internet Connectivity" "ping -c 1 8.8.8.8"
check "DNS Resolution" "nslookup google.com"

# 2. Service Health Checks
header "2. Service Health Checks"

# Check if services are running
check "PostgreSQL Container" "docker ps | grep news-intelligence-postgres"
check "Redis Container" "docker ps | grep news-intelligence-redis"
check "API Container" "docker ps | grep news-intelligence-api"
check "Frontend Container" "docker ps | grep news-intelligence-frontend"

# Check service health
check "PostgreSQL Health" "docker exec news-intelligence-postgres pg_isready -U newsapp -d news_intelligence"
check "Redis Health" "docker exec news-intelligence-redis redis-cli ping"
check "API Health" "curl -f http://localhost:8000/api/health/"
check "Frontend Health" "curl -f http://localhost/"

# 3. Database Verification
header "3. Database Verification"

# Database connectivity
check "Database Connection" "docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c 'SELECT 1;'"

# Schema verification
check "Core Tables Exist" "docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c '\dt' | grep -E '(articles|storylines|rss_feeds)'"
check "Database Indexes" "docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c '\di' | wc -l | awk '\$1 > 10'"
check "Database Views" "docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c '\dv' | wc -l | awk '\$1 > 0'"

# Data integrity
check "Articles Table Structure" "docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c '\d articles' | grep -q 'id.*integer'"
check "Storylines Table Structure" "docker exec news-intelligence-postgres psql -U newsapp -d news_intelligence -c '\d storylines' | grep -q 'id.*uuid'"

# 4. API Functionality
header "4. API Functionality"

# API endpoints
check "Health Endpoint" "curl -s http://localhost:8000/api/health/ | jq -r '.success' | grep -q 'true'"
check "Articles Endpoint" "curl -s http://localhost:8000/api/articles/ | jq -r '.success' | grep -q 'true'"
check "Storylines Endpoint" "curl -s http://localhost:8000/api/storylines/ | jq -r '.success' | grep -q 'true'"
check "RSS Feeds Endpoint" "curl -s http://localhost:8000/api/rss-feeds/ | jq -r '.success' | grep -q 'true'"

# API response times
API_RESPONSE_TIME=$(curl -o /dev/null -s -w '%{time_total}' http://localhost:8000/api/health/)
if (( $(echo "$API_RESPONSE_TIME < 2.0" | bc -l) )); then
    success "API Response Time (< 2s)"
    ((PASSED_CHECKS++))
else
    warn "API Response Time (${API_RESPONSE_TIME}s) - Consider optimization"
    ((WARNING_CHECKS++))
fi
((TOTAL_CHECKS++))

# 5. Frontend Verification
header "5. Frontend Verification"

# Frontend files
check "Frontend Build Directory" "test -d web/build"
check "Frontend Index File" "test -f web/build/index.html"

# Frontend serving
check "Frontend Nginx" "curl -s http://localhost/ | grep -q 'News Intelligence'"

# 6. Configuration Verification
header "6. Configuration Verification"

# Environment files
check "Environment File" "test -f .env"
check "Docker Compose File" "test -f docker-compose.yml"

# Configuration validation
check "Database Configuration" "grep -q 'DB_HOST.*news-intelligence-postgres' .env"
check "Redis Configuration" "grep -q 'REDIS_URL.*redis://' .env"
check "API Configuration" "grep -q 'API_V1_STR.*/api' .env"

# 7. Security Verification
header "7. Security Verification"

# Port accessibility
check "Database Port Security" "! netstat -tlnp | grep ':5432.*0.0.0.0'"
check "Redis Port Security" "! netstat -tlnp | grep ':6379.*0.0.0.0'"

# File permissions
check "Environment File Permissions" "test $(stat -c %a .env) -le 644"
check "Docker Compose Permissions" "test $(stat -c %a docker-compose.yml) -le 644"

# 8. Performance Verification
header "8. Performance Verification"

# Memory usage
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.1f", $3*100/$2}')
if (( $(echo "$MEMORY_USAGE < 80" | bc -l) )); then
    success "Memory Usage (${MEMORY_USAGE}%)"
    ((PASSED_CHECKS++))
else
    warn "Memory Usage (${MEMORY_USAGE}%) - High usage detected"
    ((WARNING_CHECKS++))
fi
((TOTAL_CHECKS++))

# Disk usage
DISK_USAGE=$(df . | awk 'NR==2{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    success "Disk Usage (${DISK_USAGE}%)"
    ((PASSED_CHECKS++))
else
    warn "Disk Usage (${DISK_USAGE}%) - High usage detected"
    ((WARNING_CHECKS++))
fi
((TOTAL_CHECKS++))

# 9. Backup and Recovery
header "9. Backup and Recovery"

# Backup scripts
check "Backup Scripts" "test -f /usr/local/bin/backup-news-system"
check "Database Backup Script" "test -f /usr/local/bin/backup-database"
check "Restore Script" "test -f /usr/local/bin/restore-news-system"

# Backup functionality
if [ -f "/usr/local/bin/backup-database" ]; then
    check "Database Backup Test" "/usr/local/bin/backup-database >/dev/null 2>&1"
fi

# 10. Monitoring and Logging
header "10. Monitoring and Logging"

# Log files
check "System Logs" "test -d /var/log/news-intelligence* || test -d /tmp/news-intelligence*"
check "Application Logs" "docker logs news-intelligence-api >/dev/null 2>&1"

# Monitoring tools
check "NAS Monitoring" "test -f /usr/local/bin/monitor-nas"
check "NAS Dashboard" "test -f scripts/nas_dashboard.sh"

# 11. Network Configuration
header "11. Network Configuration"

# Docker network
check "Docker Network" "docker network ls | grep news-network"
check "Container Networking" "docker exec news-intelligence-api ping -c 1 news-intelligence-postgres"

# Port availability
check "API Port Available" "! netstat -tlnp | grep ':8000.*LISTEN' || netstat -tlnp | grep ':8000.*news-intelligence'"
check "Frontend Port Available" "! netstat -tlnp | grep ':80.*LISTEN' || netstat -tlnp | grep ':80.*news-intelligence'"

# 12. Dependencies and Packages
header "12. Dependencies and Packages"

# Python dependencies
check "Python API Dependencies" "docker exec news-intelligence-api python -c 'import fastapi, sqlalchemy, redis'"

# Node.js dependencies (if applicable)
if [ -d "web/node_modules" ]; then
    check "Node.js Dependencies" "test -d web/node_modules"
fi

# 13. Data Pipeline Verification
header "13. Data Pipeline Verification"

# ML components
check "ML Worker Scripts" "test -f api/scripts/ml_worker.py"
check "Optimized ML Worker" "test -f api/scripts/optimized_ml_worker.py"

# RSS processing
check "RSS Processing" "docker exec news-intelligence-api python -c 'import feedparser'"

# 14. Final System Test
header "14. Final System Test"

# End-to-end test
log "Running end-to-end system test..."

# Test data flow
if curl -s http://localhost:8000/api/health/ | jq -r '.data.services.database' | grep -q 'healthy'; then
    success "End-to-End Database Test"
    ((PASSED_CHECKS++))
else
    error "End-to-End Database Test"
    ((FAILED_CHECKS++))
fi
((TOTAL_CHECKS++))

if curl -s http://localhost:8000/api/health/ | jq -r '.data.services.redis' | grep -q 'healthy'; then
    success "End-to-End Redis Test"
    ((PASSED_CHECKS++))
else
    error "End-to-End Redis Test"
    ((FAILED_CHECKS++))
fi
((TOTAL_CHECKS++))

# 15. Summary Report
header "Pre-Deployment Verification Summary"

echo -e "${CYAN}Total Checks: $TOTAL_CHECKS${NC}"
echo -e "${GREEN}Passed: $PASSED_CHECKS${NC}"
echo -e "${YELLOW}Warnings: $WARNING_CHECKS${NC}"
echo -e "${RED}Failed: $FAILED_CHECKS${NC}"

# Calculate success rate
SUCCESS_RATE=$((PASSED_CHECKS * 100 / TOTAL_CHECKS))
echo -e "${BLUE}Success Rate: ${SUCCESS_RATE}%${NC}"

# Deployment readiness
if [ $FAILED_CHECKS -eq 0 ]; then
    if [ $WARNING_CHECKS -eq 0 ]; then
        echo -e "${GREEN}✅ DEPLOYMENT READY - All checks passed!${NC}"
        log "System is ready for test deployment"
    else
        echo -e "${YELLOW}⚠️  DEPLOYMENT READY WITH WARNINGS - Review warnings before deployment${NC}"
        log "System is ready for test deployment with warnings"
    fi
else
    echo -e "${RED}❌ DEPLOYMENT NOT READY - Fix failed checks before deployment${NC}"
    log "System is NOT ready for test deployment"
    exit 1
fi

# Additional recommendations
header "Pre-Deployment Recommendations"

if [ $WARNING_CHECKS -gt 0 ]; then
    echo -e "${YELLOW}Recommendations:${NC}"
    echo "1. Review warning messages above"
    echo "2. Consider optimizing performance if needed"
    echo "3. Monitor system resources during deployment"
fi

echo -e "${BLUE}Next Steps:${NC}"
echo "1. Run test deployment in staging environment"
echo "2. Monitor system performance and logs"
echo "3. Test all functionality thoroughly"
echo "4. Prepare rollback plan if needed"

log "Pre-deployment verification completed"
log "Log file: $LOG_FILE"
