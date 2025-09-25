#!/bin/bash

# News Intelligence System - Methodology Enforcement Script
# Ensures development methodology is followed

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if we're on the correct branch
check_branch() {
    local current_branch=$(git branch --show-current)
    local expected_branch=$1
    
    if [ "$current_branch" != "$expected_branch" ]; then
        print_error "You are on branch '$current_branch', but expected '$expected_branch'"
        print_status "Please run: git checkout $expected_branch"
        exit 1
    fi
    
    print_success "On correct branch: $current_branch"
}

# Function to check for uncommitted changes
check_clean_working_directory() {
    if ! git diff-index --quiet HEAD --; then
        print_error "You have uncommitted changes"
        print_status "Please commit or stash your changes first"
        git status --short
        exit 1
    fi
    
    print_success "Working directory is clean"
}

# Function to check for port conflicts
check_port_conflicts() {
    local ports=("3000" "8000" "80" "5432" "6379" "9090")
    local conflicts=()
    
    for port in "${ports[@]}"; do
        if netstat -tlnp 2>/dev/null | grep -q ":$port "; then
            conflicts+=("$port")
        fi
    done
    
    if [ ${#conflicts[@]} -gt 0 ]; then
        print_warning "Port conflicts detected on: ${conflicts[*]}"
        print_status "Make sure you're not running development and production simultaneously"
    else
        print_success "No port conflicts detected"
    fi
}

# Function to check Docker container status
check_docker_status() {
    local containers=("news-intelligence-postgres" "news-intelligence-redis" "news-intelligence-api" "news-intelligence-frontend" "news-intelligence-monitoring")
    local unhealthy=()
    
    for container in "${containers[@]}"; do
        if ! docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "$container"; then
            unhealthy+=("$container")
        fi
    done
    
    if [ ${#unhealthy[@]} -gt 0 ]; then
        print_warning "Some containers are not running: ${unhealthy[*]}"
        print_status "Run: docker-compose up -d"
    else
        print_success "All Docker containers are running"
    fi
}

# Function to check API health
check_api_health() {
    if curl -s "http://localhost:8000/api/health/" | jq -e '.success' >/dev/null 2>&1; then
        print_success "API is healthy"
    else
        print_error "API health check failed"
        print_status "Check API container logs: docker logs news-intelligence-api"
        exit 1
    fi
}

# Function to check frontend accessibility
check_frontend_accessibility() {
    if curl -s "http://localhost:80" | grep -q "News Intelligence System"; then
        print_success "Frontend is accessible"
    else
        print_error "Frontend is not accessible"
        print_status "Check frontend container logs: docker logs news-intelligence-frontend"
        exit 1
    fi
}

# Function to run pre-commit checks
run_pre_commit_checks() {
    print_status "Running pre-commit checks..."
    
    # Check TypeScript compilation
    if [ -d "web" ]; then
        cd web
        if npm run build >/dev/null 2>&1; then
            print_success "TypeScript compilation passed"
        else
            print_error "TypeScript compilation failed"
            exit 1
        fi
        cd ..
    fi
    
    # Check ESLint
    if [ -d "web" ]; then
        cd web
        if npm run lint >/dev/null 2>&1; then
            print_success "ESLint checks passed"
        else
            print_warning "ESLint warnings detected (non-blocking)"
        fi
        cd ..
    fi
    
    print_success "Pre-commit checks completed"
}

# Function to promote to production
promote_to_production() {
    print_status "Promoting to production..."
    
    # Check we're on master
    check_branch "master"
    
    # Check working directory is clean
    check_clean_working_directory
    
    # Run pre-commit checks
    run_pre_commit_checks
    
    # Check for port conflicts
    check_port_conflicts
    
    # Check Docker status
    check_docker_status
    
    # Check API health
    check_api_health
    
    # Check frontend accessibility
    check_frontend_accessibility
    
    # Switch to production branch
    git checkout production
    
    # Merge master
    git merge master
    
    # Tag the release
    local version=$(date +"%Y%m%d_%H%M%S")
    git tag -a "v3.0.$version" -m "Production Release: $(date)"
    
    # Switch back to master
    git checkout master
    
    print_success "Successfully promoted to production with tag v3.0.$version"
}

# Function to rollback production
rollback_production() {
    print_status "Rolling back production..."
    
    # Check we're on production branch
    check_branch "production"
    
    # Show recent commits
    print_status "Recent production commits:"
    git log --oneline -5
    
    # Ask for confirmation
    read -p "Are you sure you want to rollback? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Rollback cancelled"
        exit 0
    fi
    
    # Rollback one commit
    git reset --hard HEAD~1
    
    print_success "Production rolled back successfully"
}

# Function to show status
show_status() {
    print_status "News Intelligence System Status"
    echo "=================================="
    
    # Git status
    echo "Current branch: $(git branch --show-current)"
    echo "Last commit: $(git log -1 --oneline)"
    
    # Docker status
    echo "Docker containers:"
    docker ps --format "table {{.Names}}\t{{.Status}}" | grep news-intelligence || echo "No containers running"
    
    # Port status
    echo "Port usage:"
    netstat -tlnp 2>/dev/null | grep -E ":(3000|8000|80|5432|6379|9090) " || echo "No relevant ports in use"
    
    # API health
    if curl -s "http://localhost:8000/api/health/" | jq -e '.success' >/dev/null 2>&1; then
        echo "API Status: ✅ Healthy"
    else
        echo "API Status: ❌ Unhealthy"
    fi
    
    # Frontend accessibility
    if curl -s "http://localhost:80" | grep -q "News Intelligence System"; then
        echo "Frontend Status: ✅ Accessible"
    else
        echo "Frontend Status: ❌ Not accessible"
    fi
}

# Main function
main() {
    case "$1" in
        "check")
            print_status "Running methodology checks..."
            check_branch "master"
            check_clean_working_directory
            check_port_conflicts
            check_docker_status
            check_api_health
            check_frontend_accessibility
            print_success "All checks passed!"
            ;;
        "promote")
            promote_to_production
            ;;
        "rollback")
            rollback_production
            ;;
        "status")
            show_status
            ;;
        "pre-commit")
            run_pre_commit_checks
            ;;
        *)
            echo "Usage: $0 {check|promote|rollback|status|pre-commit}"
            echo ""
            echo "Commands:"
            echo "  check      - Run all methodology checks"
            echo "  promote    - Promote master to production"
            echo "  rollback   - Rollback production one commit"
            echo "  status     - Show system status"
            echo "  pre-commit - Run pre-commit checks"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"
