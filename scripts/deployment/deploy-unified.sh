#!/bin/bash

# News Intelligence System v3.0 - Unified Deployment Script
# All-in-one package with NAS storage and full feature set
# No profiles needed - everything is included by default

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Global variables for tracking
DEPLOYMENT_START_TIME=""
BACKGROUND_PROCESSES=()
ESTIMATED_TIMES=(
    ["prerequisites"]=30
    ["cleanup"]=60
    ["build"]=300
    ["deploy"]=120
    ["health_check"]=30
)

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

print_header() {
    echo -e "${PURPLE}[HEADER]${NC} $1"
}

print_progress() {
    echo -e "${CYAN}[PROGRESS]${NC} $1"
}

print_estimate() {
    echo -e "${BOLD}[ESTIMATE]${NC} $1"
}

print_confirmation() {
    echo -e "${BOLD}${YELLOW}[CONFIRM]${NC} $1"
}

print_activity() {
    echo -e "${BOLD}${BLUE}[ACTIVITY]${NC} $1"
}

# Function to show time estimate
show_time_estimate() {
    local operation="$1"
    local estimated_seconds="${ESTIMATED_TIMES[$operation]}"
    local estimated_minutes=$((estimated_seconds / 60))
    local estimated_seconds_remainder=$((estimated_seconds % 60))
    
    if [ $estimated_minutes -gt 0 ]; then
        print_estimate "Estimated time for $operation: ${estimated_minutes}m ${estimated_seconds_remainder}s"
    else
        print_estimate "Estimated time for $operation: ${estimated_seconds}s"
    fi
}

# Function to confirm user action
confirm_action() {
    local message="$1"
    local default="${2:-n}"
    
    print_confirmation "$message"
    if [ "$default" = "y" ]; then
        read -p "Continue? (Y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Nn]$ ]]; then
            return 1
        fi
    else
        read -p "Continue? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            return 1
        fi
    fi
    return 0
}

# Function to show progress with spinner
show_progress() {
    local pid=$1
    local message="$2"
    local spinner="⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    local i=0
    
    while kill -0 $pid 2>/dev/null; do
        printf "\r${CYAN}[PROGRESS]${NC} $message ${spinner:$((i % 10)):1}"
        sleep 0.1
        ((i++))
    done
    printf "\r${GREEN}[COMPLETE]${NC} $message ✓\n"
}

# Function to handle background processes
start_background_process() {
    local command="$1"
    local name="$2"
    local log_file="/tmp/news-system-${name}.log"
    
    print_activity "Starting background process: $name"
    eval "$command" > "$log_file" 2>&1 &
    local pid=$!
    BACKGROUND_PROCESSES+=("$pid:$name:$log_file")
    echo $pid
}

# Function to check background processes
check_background_processes() {
    local all_complete=true
    
    for process_info in "${BACKGROUND_PROCESSES[@]}"; do
        IFS=':' read -r pid name log_file <<< "$process_info"
        if kill -0 $pid 2>/dev/null; then
            all_complete=false
            print_activity "Background process '$name' (PID: $pid) is still running"
        else
            local exit_code=$(wait $pid 2>/dev/null; echo $?)
            if [ $exit_code -eq 0 ]; then
                print_success "Background process '$name' completed successfully"
            else
                print_error "Background process '$name' failed with exit code $exit_code"
                print_error "Check log file: $log_file"
            fi
        fi
    done
    
    if [ "$all_complete" = true ]; then
        print_success "All background processes completed"
        BACKGROUND_PROCESSES=()
    fi
}

# Function to cleanup background processes on exit
cleanup_on_exit() {
    if [ ${#BACKGROUND_PROCESSES[@]} -gt 0 ]; then
        print_warning "Cleaning up background processes..."
        for process_info in "${BACKGROUND_PROCESSES[@]}"; do
            IFS=':' read -r pid name log_file <<< "$process_info"
            if kill -0 $pid 2>/dev/null; then
                print_activity "Stopping background process '$name' (PID: $pid)"
                kill $pid 2>/dev/null || true
            fi
        done
        BACKGROUND_PROCESSES=()
    fi
}

# Set up signal handlers
trap cleanup_on_exit EXIT INT TERM

# Function to show detailed error information
show_error_details() {
    local error_code="$1"
    local context="$2"
    
    print_error "Operation failed: $context"
    print_error "Exit code: $error_code"
    
    case $error_code in
        1)
            print_error "General error - check logs and configuration"
            ;;
        2)
            print_error "Misuse of shell builtins - check script syntax"
            ;;
        126)
            print_error "Command invoked cannot execute - check permissions"
            ;;
        127)
            print_error "Command not found - check if required tools are installed"
            ;;
        128)
            print_error "Invalid argument to exit - script error"
            ;;
        130)
            print_error "Script terminated by Ctrl+C"
            ;;
        255)
            print_error "Exit status out of range - check system resources"
            ;;
        *)
            print_error "Unknown error - check system logs"
            ;;
    esac
}

# Function to show usage
show_usage() {
    echo "🚀 News Intelligence System v3.0 - Unified Deployment"
    echo "====================================================="
    echo ""
    echo "All-in-one package with NAS storage and full feature set"
    echo "No profiles needed - everything is included by default"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  --build      - Force rebuild of containers (5-10 min)"
    echo "  --clean      - Remove old containers and volumes"
    echo "  --logs       - Show logs after deployment"
    echo "  --status     - Show service status"
    echo "  --stop       - Stop all services"
    echo "  --restart    - Restart all services"
    echo "  --background - Run in background mode (continues if terminal closed)"
    echo "  --help       - Show this help message"
    echo ""
    echo "EXAMPLES:"
    echo "  $0                     # Deploy with default settings"
    echo "  $0 --build            # Deploy with rebuild (5-10 min)"
    echo "  $0 --clean --build    # Clean deployment with rebuild"
    echo "  $0 --logs             # Deploy and show logs"
    echo "  $0 --status           # Show current status"
    echo "  $0 --background       # Deploy in background mode"
    echo ""
    echo "SERVICES INCLUDED:"
    echo "  ✅ News System Application (Port 8000)"
    echo "  ✅ PostgreSQL Database (Port 5432)"
    echo "  ✅ Redis Cache (Port 6379)"
    echo "  ✅ Prometheus Monitoring (Port 9090)"
    echo "  ✅ Grafana Dashboards (Port 3001)"
    echo "  ✅ Node Exporter (Port 9100)"
    echo "  ✅ PostgreSQL Exporter (Port 9187)"
    echo "  ✅ NVIDIA GPU Exporter (Port 9445) - if GPU available"
    echo "  ✅ Nginx Reverse Proxy (Ports 80/443) - optional"
    echo ""
}

# Function to check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites..."
    show_time_estimate "prerequisites"
    
    local start_time=$(date +%s)
    
    # Check if Docker is running
    print_progress "Checking Docker status..."
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        print_error "Try: sudo systemctl start docker"
        exit 1
    fi
    print_success "Docker is running"
    
    # Check Docker Compose version
    print_progress "Checking Docker Compose version..."
    if ! docker compose version > /dev/null 2>&1; then
        print_error "Docker Compose not found or not working properly"
        print_error "Please install Docker Compose v2.0+"
        exit 1
    fi
    print_success "Docker Compose is available"
    
    # Check if unified files exist
    print_progress "Checking deployment files..."
    if [[ ! -f "docker-compose.unified.yml" ]]; then
        print_error "docker-compose.unified.yml not found!"
        print_error "Make sure you're running this script from the project root directory"
        exit 1
    fi
    
    if [[ ! -f "env.unified" ]]; then
        print_error "env.unified not found!"
        print_error "Make sure you're running this script from the project root directory"
        exit 1
    fi
    print_success "Deployment files found"
    
    # Check NAS mount
    print_progress "Checking NAS mount..."
    if ! mountpoint -q /mnt/terramaster-nas; then
        print_warning "NAS not mounted at /mnt/terramaster-nas"
        print_warning "This will cause deployment to fail"
        print_warning "Please mount your NAS first or update the paths in env.unified"
        
        if ! confirm_action "Continue anyway? (This will likely fail)"; then
            print_status "Deployment cancelled by user"
            exit 0
        fi
    else
        print_success "NAS is mounted"
    fi
    
    # Check available disk space
    print_progress "Checking available disk space..."
    local available_space=$(df /mnt/terramaster-nas 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
    local available_gb=$((available_space / 1024 / 1024))
    
    if [ $available_gb -lt 10 ]; then
        print_warning "Low disk space: ${available_gb}GB available"
        print_warning "Recommended: At least 10GB free space"
        if ! confirm_action "Continue with low disk space?"; then
            print_status "Deployment cancelled by user"
            exit 0
        fi
    else
        print_success "Sufficient disk space: ${available_gb}GB available"
    fi
    
    # Create NAS directories if they don't exist
    print_progress "Creating NAS directories..."
    if ! sudo mkdir -p /mnt/terramaster-nas/docker-postgres-data/{pgdata,data,logs,backups,temp,ml-models,cache,uploads,prometheus-data,grafana-data,redis-data,nginx-logs} 2>/dev/null; then
        print_error "Failed to create NAS directories"
        print_error "Check NAS permissions and mount status"
        exit 1
    fi
    
    if ! sudo chown -R 1000:1000 /mnt/terramaster-nas/docker-postgres-data/ 2>/dev/null; then
        print_warning "Failed to set NAS directory permissions"
        print_warning "This may cause issues with container access"
    fi
    print_success "NAS directories created and configured"
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    print_success "Prerequisites check completed in ${duration}s"
}

# Function to deploy unified system
deploy_unified() {
    local build_flag="$1"
    local clean_flag="$2"
    
    print_header "Deploying News Intelligence System v3.0"
    print_status "All-in-one package with NAS storage and full feature set"
    
    DEPLOYMENT_START_TIME=$(date +%s)
    
    # Set environment variables
    print_progress "Loading environment configuration..."
    if ! export $(cat env.unified | grep -v '^#' | xargs) 2>/dev/null; then
        print_error "Failed to load environment configuration"
        print_error "Check env.unified file for syntax errors"
        exit 1
    fi
    print_success "Environment configuration loaded"
    
    # Clean up if requested
    if [[ "$clean_flag" == "true" ]]; then
        show_time_estimate "cleanup"
        print_progress "Cleaning up old containers and volumes..."
        
        if ! confirm_action "This will remove all existing containers and volumes. Continue?"; then
            print_status "Cleanup cancelled by user"
            return 0
        fi
        
        print_activity "Stopping and removing containers..."
        if ! docker compose -f docker-compose.unified.yml down -v 2>/dev/null; then
            print_warning "Some containers may not have been stopped properly"
        fi
        
        print_activity "Cleaning up Docker system..."
        if ! docker system prune -f 2>/dev/null; then
            print_warning "Docker system cleanup had issues"
        fi
        
        print_success "Cleanup completed"
    fi
    
    # Build and start services
    print_progress "Preparing to start unified services..."
    
    local build_cmd=""
    if [[ "$build_flag" == "true" ]]; then
        build_cmd="--build"
        show_time_estimate "build"
        print_status "Forcing rebuild of containers"
        print_warning "Container rebuild may take 5-10 minutes depending on your system"
        
        if ! confirm_action "Continue with container rebuild?"; then
            print_status "Deployment cancelled by user"
            return 0
        fi
    fi
    
    show_time_estimate "deploy"
    
    # Start core services
    print_activity "Starting core services..."
    if ! docker compose -f docker-compose.unified.yml up -d $build_cmd; then
        print_error "Failed to start core services"
        print_error "Check Docker logs: docker compose -f docker-compose.unified.yml logs"
        exit 1
    fi
    print_success "Core services started"
    
    # Check if GPU is available and start GPU exporter
    print_progress "Checking for GPU availability..."
    if command -v nvidia-smi &> /dev/null; then
        print_activity "GPU detected, starting GPU monitoring..."
        if docker compose -f docker-compose.unified.yml --profile gpu up -d nvidia-gpu-exporter 2>/dev/null; then
            print_success "GPU monitoring started"
        else
            print_warning "Failed to start GPU monitoring (this is optional)"
        fi
    else
        print_status "No GPU detected, skipping GPU monitoring"
    fi
    
    # Wait for services to be ready
    print_progress "Waiting for services to initialize..."
    sleep 10
    
    # Check service health
    show_time_estimate "health_check"
    print_progress "Checking service health..."
    
    local healthy_services=0
    local total_services=0
    
    # Check each service
    for service in postgres news-system redis prometheus grafana; do
        total_services=$((total_services + 1))
        if docker compose -f docker-compose.unified.yml ps $service | grep -q "Up"; then
            healthy_services=$((healthy_services + 1))
            print_success "Service $service is running"
        else
            print_warning "Service $service may not be running properly"
        fi
    done
    
    local end_time=$(date +%s)
    local duration=$((end_time - DEPLOYMENT_START_TIME))
    local duration_minutes=$((duration / 60))
    local duration_seconds=$((duration % 60))
    
    if [ $healthy_services -eq $total_services ]; then
        print_success "Unified deployment completed successfully!"
        print_success "All $total_services services are running"
        print_success "Deployment took ${duration_minutes}m ${duration_seconds}s"
    else
        print_warning "Deployment completed with issues"
        print_warning "$healthy_services out of $total_services services are running"
        print_warning "Check logs: docker compose -f docker-compose.unified.yml logs"
    fi
}

# Function to show service status
show_status() {
    print_header "Service Status"
    echo ""
    
    docker compose -f docker-compose.unified.yml ps
    
    echo ""
    print_header "Service URLs"
    echo "  🌐 News System:     http://localhost:8000"
    echo "  📊 Grafana:         http://localhost:3001 (admin/Database@NEWSINT2025)"
    echo "  📈 Prometheus:      http://localhost:9090"
    echo "  🔍 Node Exporter:   http://localhost:9100"
    echo "  🗄️  PostgreSQL:      localhost:5432"
    echo "  ⚡ Redis:           localhost:6379"
    echo "  📊 PostgreSQL Exp:  http://localhost:9187"
    echo "  🎮 GPU Exporter:    http://localhost:9445 (if GPU available)"
    echo ""
    
    # Check service health
    print_status "Checking service health..."
    if docker compose -f docker-compose.unified.yml ps | grep -q "Up"; then
        print_success "Services are running"
    else
        print_warning "Some services may not be running properly"
    fi
}

# Function to show logs
show_logs() {
    print_header "Service Logs"
    print_status "Showing recent logs (press Ctrl+C to exit)..."
    print_warning "Logs will continue in background if you exit"
    echo ""
    
    # Start log monitoring in background
    local log_pid=$(start_background_process "docker compose -f docker-compose.unified.yml logs -f" "logs")
    
    print_activity "Log monitoring started (PID: $log_pid)"
    print_status "Logs are being written to: /tmp/news-system-logs.log"
    print_status "You can safely close this terminal - logs will continue in background"
    
    # Show initial logs
    docker compose -f docker-compose.unified.yml logs --tail=50
    
    print_confirmation "Press Enter to continue monitoring, or Ctrl+C to exit (logs continue in background)"
    read -r
    
    # Continue showing logs
    docker compose -f docker-compose.unified.yml logs -f
}

# Function to stop services
stop_services() {
    print_header "Stopping Services"
    print_status "Stopping all News Intelligence System services..."
    
    if ! confirm_action "This will stop all running services. Continue?"; then
        print_status "Stop operation cancelled by user"
        return 0
    fi
    
    print_activity "Stopping containers..."
    if docker compose -f docker-compose.unified.yml down; then
        print_success "All services stopped successfully"
    else
        print_error "Some services may not have stopped properly"
        print_error "Check logs: docker compose -f docker-compose.unified.yml logs"
    fi
}

# Function to restart services
restart_services() {
    print_header "Restarting Services"
    print_status "Restarting all News Intelligence System services..."
    
    if ! confirm_action "This will restart all services. Continue?"; then
        print_status "Restart operation cancelled by user"
        return 0
    fi
    
    print_activity "Restarting containers..."
    if docker compose -f docker-compose.unified.yml restart; then
        print_success "All services restarted successfully"
        
        # Wait for services to be ready
        print_progress "Waiting for services to initialize..."
        sleep 10
        
        # Check service health
        print_progress "Checking service health..."
        local healthy_services=0
        local total_services=0
        
        for service in postgres news-system redis prometheus grafana; do
            total_services=$((total_services + 1))
            if docker compose -f docker-compose.unified.yml ps $service | grep -q "Up"; then
                healthy_services=$((healthy_services + 1))
                print_success "Service $service is running"
            else
                print_warning "Service $service may not be running properly"
            fi
        done
        
        if [ $healthy_services -eq $total_services ]; then
            print_success "All $total_services services are running"
        else
            print_warning "$healthy_services out of $total_services services are running"
        fi
    else
        print_error "Some services may not have restarted properly"
        print_error "Check logs: docker compose -f docker-compose.unified.yml logs"
    fi
}

# Function to show system information
show_system_info() {
    print_header "System Information"
    echo ""
    echo "📋 Deployment Type: Unified (All-in-one)"
    echo "💾 Storage: NAS (/mnt/terramaster-nas/docker-postgres-data/)"
    echo "🐳 Docker Compose: docker-compose.unified.yml"
    echo "⚙️  Environment: env.unified"
    echo "🔧 Features: All enabled by default"
    echo ""
    echo "📦 Included Services:"
    echo "  • News System Application"
    echo "  • PostgreSQL Database"
    echo "  • Redis Cache"
    echo "  • Prometheus Monitoring"
    echo "  • Grafana Dashboards"
    echo "  • Node Exporter"
    echo "  • PostgreSQL Exporter"
    echo "  • NVIDIA GPU Exporter (if available)"
    echo "  • Nginx Reverse Proxy (optional)"
    echo ""
}

# Main execution
main() {
    local build_flag="false"
    local clean_flag="false"
    local logs_flag="false"
    local status_flag="false"
    local stop_flag="false"
    local restart_flag="false"
    local info_flag="false"
    local background_flag="false"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
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
            --status)
                status_flag="true"
                shift
                ;;
            --stop)
                stop_flag="true"
                shift
                ;;
            --restart)
                restart_flag="true"
                shift
                ;;
            --info)
                info_flag="true"
                shift
                ;;
            --background)
                background_flag="true"
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
    
    # Handle different commands
    if [[ "$status_flag" == "true" ]]; then
        show_status
        exit 0
    fi
    
    if [[ "$stop_flag" == "true" ]]; then
        stop_services
        exit 0
    fi
    
    if [[ "$restart_flag" == "true" ]]; then
        restart_services
        exit 0
    fi
    
    if [[ "$info_flag" == "true" ]]; then
        show_system_info
        exit 0
    fi
    
    # Default action: deploy
    print_header "News Intelligence System v3.0 - Unified Deployment"
    print_status "Starting deployment process..."
    
    # Check if running in background mode
    if [[ "$background_flag" == "true" ]]; then
        print_activity "Running in background mode"
        print_status "Deployment will continue even if terminal is closed"
    fi
    
    # Show deployment summary
    print_confirmation "Deployment Summary:"
    echo "  • Build containers: $build_flag"
    echo "  • Clean deployment: $clean_flag"
    echo "  • Show logs after: $logs_flag"
    echo "  • Background mode: $background_flag"
    echo ""
    
    if ! confirm_action "Proceed with deployment?"; then
        print_status "Deployment cancelled by user"
        exit 0
    fi
    
    # Start deployment
    local deployment_start=$(date +%s)
    
    if ! check_prerequisites; then
        print_error "Prerequisites check failed"
        exit 1
    fi
    
    if ! deploy_unified "$build_flag" "$clean_flag"; then
        print_error "Deployment failed"
        exit 1
    fi
    
    show_status
    
    # Show logs if requested
    if [[ "$logs_flag" == "true" ]]; then
        show_logs
    fi
    
    local deployment_end=$(date +%s)
    local total_duration=$((deployment_end - deployment_start))
    local total_minutes=$((total_duration / 60))
    local total_seconds=$((total_duration % 60))
    
    print_success "Unified deployment complete!"
    print_success "Total deployment time: ${total_minutes}m ${total_seconds}s"
    print_status "Use '$0 --status' to check service status"
    print_status "Use '$0 --logs' to view logs"
    print_status "Use '$0 --help' for more options"
    
    # Show access information
    echo ""
    print_header "Access Your System"
    echo "  🌐 Main Application:     http://localhost:8000"
    echo "  📊 Grafana Dashboards:   http://localhost:3001 (admin/Database@NEWSINT2025)"
    echo "  📈 Prometheus:           http://localhost:9090"
    echo "  🔍 Node Exporter:        http://localhost:9100"
    echo ""
    
    # Check for background processes
    if [ ${#BACKGROUND_PROCESSES[@]} -gt 0 ]; then
        print_activity "Background processes are running:"
        for process_info in "${BACKGROUND_PROCESSES[@]}"; do
            IFS=':' read -r pid name log_file <<< "$process_info"
            print_status "  • $name (PID: $pid) - Log: $log_file"
        done
        print_status "These processes will continue running in the background"
    fi
}

# Run main function
main "$@"
