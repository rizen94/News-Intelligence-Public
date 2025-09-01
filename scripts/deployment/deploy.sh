#!/bin/bash

# News Intelligence System - Consolidated Deployment Script
# Uses the new consolidated Docker Compose file with profiles

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

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

# Function to show usage
show_usage() {
    echo "🚀 News Intelligence System - Consolidated Deployment"
    echo "====================================================="
    echo ""
    echo "Usage: $0 [PROFILE] [OPTIONS]"
    echo ""
    echo "PROFILES:"
    echo "  local       - Local storage, basic functionality"
    echo "  nas         - NAS storage, full monitoring"
    echo "  production  - NAS storage, production settings, full monitoring"
    echo ""
    echo "OPTIONS:"
    echo "  --build     - Force rebuild of containers"
    echo "  --clean     - Remove old containers and volumes"
    echo "  --logs      - Show logs after deployment"
    echo "  --help      - Show this help message"
    echo ""
    echo "EXAMPLES:"
    echo "  $0 nas                    # Deploy with NAS storage and monitoring"
    echo "  $0 local --build         # Deploy locally with rebuild"
    echo "  $0 production --clean    # Deploy production with cleanup"
    echo ""
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    # Check if consolidated files exist
            if [[ ! -f "docker-compose.yml" ]]; then
            print_error "docker-compose.yml not found!"
            exit 1
        fi
        
        if [[ ! -f ".env" ]]; then
            print_error ".env not found!"
            exit 1
        fi
    
    # Check NAS mount for NAS/production profiles
    if [[ "$1" == "nas" || "$1" == "production" ]]; then
        if ! mountpoint -q /mnt/terramaster-nas; then
            print_error "NAS not mounted. Please mount NAS first."
            exit 1
        fi
    fi
    
    print_success "Prerequisites check passed"
}

# Function to deploy with profile
deploy_profile() {
    local profile="$1"
    local build_flag="$2"
    local clean_flag="$3"
    
    print_status "Deploying with profile: $profile"
    
    # Set environment variables
    export $(cat env.consolidated | grep -v '^#' | xargs)
    
    # Determine profiles to use
    local compose_profiles=""
    case "$profile" in
        "local")
            compose_profiles="--profile local"
            print_status "Using local storage profile"
            ;;
        "nas")
            compose_profiles="--profile nas --profile monitoring"
            print_status "Using NAS storage with monitoring profile"
            ;;
        "production")
            compose_profiles="--profile production --profile monitoring"
            print_status "Using production with monitoring profile"
            ;;
        *)
            print_error "Unknown profile: $profile"
            exit 1
            ;;
    esac
    
    # Clean up if requested
    if [[ "$clean_flag" == "true" ]]; then
        print_status "Cleaning up old containers and volumes..."
        docker compose -f docker-compose.yml $compose_profiles down -v
        docker system prune -f
    fi
    
    # Build and start services
    print_status "Starting services with profile: $profile"
    
    local build_cmd=""
    if [[ "$build_flag" == "true" ]]; then
        build_cmd="--build"
        print_status "Forcing rebuild of containers"
    fi
    
            docker compose -f docker-compose.yml $compose_profiles up -d $build_cmd
    
    print_success "Deployment completed successfully!"
}

# Function to show service status
show_status() {
    local profile="$1"
    
    print_status "Service status:"
    echo ""
    
    case "$profile" in
        "local")
            docker compose -f docker-compose.yml --profile local ps
            ;;
        "nas"|"production")
            docker compose -f docker-compose.yml --profile nas --profile monitoring ps
            ;;
    esac
    
    echo ""
    print_status "Service URLs:"
    echo "  - News System: http://localhost:8000"
    echo "  - Grafana: http://localhost:3001 (admin/admin123)"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Node Exporter: http://localhost:9100"
    echo "  - PostgreSQL Exporter: http://localhost:9187"
    echo "  - NVIDIA GPU Exporter: http://localhost:9445"
}

# Function to show logs
show_logs() {
    local profile="$1"
    
    print_status "Showing recent logs (press Ctrl+C to exit)..."
    echo ""
    
    case "$profile" in
        "local")
            docker compose -f docker-compose.yml --profile local logs -f
            ;;
        "nas"|"production")
            docker compose -f docker-compose.yml --profile nas --profile monitoring logs -f
            ;;
    esac
}

# Main execution
main() {
    local profile=""
    local build_flag="false"
    local clean_flag="false"
    local logs_flag="false"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            local|nas|production)
                profile="$1"
                shift
                ;;
            --build)
                build_flag="true"
                shift
                ;;
            --clean)
                clean_flag="true"
                shift
                ;;
            --logs)
                logs_flag="true"
                shift
                ;;
            --help|-h)
                show_usage
                exit 0
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done
    
    # Check if profile was specified
    if [[ -z "$profile" ]]; then
        print_error "No profile specified!"
        show_usage
        exit 1
    fi
    
    # Check prerequisites
    check_prerequisites "$profile"
    
    # Deploy
    deploy_profile "$profile" "$build_flag" "$clean_flag"
    
    # Show status
    show_status "$profile"
    
    # Show logs if requested
    if [[ "$logs_flag" == "true" ]]; then
        show_logs "$profile"
    fi
    
    print_success "Deployment complete! Use '$0 $profile --logs' to view logs."
}

# Run main function
main "$@"
