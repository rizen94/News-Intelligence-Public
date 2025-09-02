#!/bin/bash

# News Intelligence System v3.0 - Deployment Script Template
# This template shows how to apply the UX framework to any deployment script
# Copy this template and customize for your specific deployment needs

set -e

# Source the UX framework
source "$(dirname "$0")/ux-framework.sh"

# Initialize the UX framework
init_ux_framework "Your Deployment Script" '(
    ["prerequisites"]=30
    ["cleanup"]=60
    ["build"]=300
    ["deploy"]=120
    ["health_check"]=30
)'

# Function to show usage
show_usage() {
    echo "🚀 Your Deployment Script - Enhanced with UX Framework"
    echo "====================================================="
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
}

# Function to check prerequisites
check_prerequisites() {
    # Use the UX framework's prerequisite checker
    check_prerequisites "docker docker-compose nas-mount disk-space"
}

# Function to deploy your system
deploy_system() {
    local build_flag="$1"
    local clean_flag="$2"
    
    print_header "Deploying Your System"
    print_status "Starting deployment process..."
    
    DEPLOYMENT_START_TIME=$(date +%s)
    
    # Set environment variables
    print_progress "Loading environment configuration..."
    if ! export $(cat env.unified | grep -v '^#' | xargs) 2>/dev/null; then
        print_error "Failed to load environment configuration"
        print_error "Check env.unified file for syntax errors"
        return 1
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
        
        # Use the UX framework's error handling
        execute_with_error_handling "docker compose -f docker-compose.unified.yml down -v" "Stopping and removing containers"
        execute_with_error_handling "docker system prune -f" "Cleaning up Docker system"
        
        print_success "Cleanup completed"
    fi
    
    # Build and start services
    print_progress "Preparing to start services..."
    
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
    
    # Start services
    print_activity "Starting services..."
    execute_with_error_handling "docker compose -f docker-compose.unified.yml up -d $build_cmd" "Starting core services"
    
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
        print_success "Deployment completed successfully!"
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
    
    if docker compose -f docker-compose.unified.yml ps | grep -q "Up"; then
        print_success "Services are running"
        docker compose -f docker-compose.unified.yml ps
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
    print_status "Stopping all services..."
    
    if ! confirm_action "This will stop all running services. Continue?"; then
        print_status "Stop operation cancelled by user"
        return 0
    fi
    
    execute_with_error_handling "docker compose -f docker-compose.unified.yml down" "Stopping containers"
    print_success "All services stopped successfully"
}

# Function to restart services
restart_services() {
    print_header "Restarting Services"
    print_status "Restarting all services..."
    
    if ! confirm_action "This will restart all services. Continue?"; then
        print_status "Restart operation cancelled by user"
        return 0
    fi
    
    execute_with_error_handling "docker compose -f docker-compose.unified.yml restart" "Restarting containers"
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
}

# Main execution
main() {
    local build_flag="false"
    local clean_flag="false"
    local logs_flag="false"
    local status_flag="false"
    local stop_flag="false"
    local restart_flag="false"
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
    
    # Default action: deploy
    print_header "Your Deployment Script - Enhanced with UX Framework"
    print_status "Starting deployment process..."
    
    # Check if running in background mode
    if [[ "$background_flag" == "true" ]]; then
        print_activity "Running in background mode"
        print_status "Deployment will continue even if terminal is closed"
    fi
    
    # Show deployment summary
    show_deployment_summary "$build_flag" "$clean_flag" "$logs_flag" "$background_flag"
    
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
    
    if ! deploy_system "$build_flag" "$clean_flag"; then
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
    
    print_success "Deployment complete!"
    print_success "Total deployment time: ${total_minutes}m ${total_seconds}s"
    print_status "Use '$0 --status' to check service status"
    print_status "Use '$0 --logs' to view logs"
    print_status "Use '$0 --help' for more options"
    
    # Show access information
    show_access_info "main-app grafana prometheus node-exporter"
    
    # Show background process status
    show_background_status
}

# Run main function
main "$@"
