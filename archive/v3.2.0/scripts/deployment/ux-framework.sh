#!/bin/bash

# News Intelligence System v3.0 - UX Framework
# Reusable UX components for deployment scripts
# This framework can be applied to any deployment script

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
ESTIMATED_TIMES=()

# Function to initialize UX framework
init_ux_framework() {
    local script_name="$1"
    local default_times="$2"
    
    # Set default time estimates if provided
    if [ -n "$default_times" ]; then
        eval "ESTIMATED_TIMES=($default_times)"
    fi
    
    # Set up signal handlers
    trap cleanup_on_exit EXIT INT TERM
    
    print_header "Initializing UX Framework for $script_name"
}

# Print functions
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
    
    if [ -n "$estimated_seconds" ]; then
        local estimated_minutes=$((estimated_seconds / 60))
        local estimated_seconds_remainder=$((estimated_seconds % 60))
        
        if [ $estimated_minutes -gt 0 ]; then
            print_estimate "Estimated time for $operation: ${estimated_minutes}m ${estimated_seconds_remainder}s"
        else
            print_estimate "Estimated time for $operation: ${estimated_seconds}s"
        fi
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

# Function to execute command with error handling
execute_with_error_handling() {
    local command="$1"
    local context="$2"
    local show_progress="${3:-false}"
    
    print_activity "Executing: $context"
    
    if [ "$show_progress" = "true" ]; then
        eval "$command" &
        local pid=$!
        show_progress $pid "$context"
        wait $pid
        local exit_code=$?
    else
        eval "$command"
        local exit_code=$?
    fi
    
    if [ $exit_code -ne 0 ]; then
        show_error_details $exit_code "$context"
        return $exit_code
    fi
    
    print_success "Completed: $context"
    return 0
}

# Function to check prerequisites
check_prerequisites() {
    local requirements="$1"
    
    print_header "Checking Prerequisites..."
    show_time_estimate "prerequisites"
    
    local start_time=$(date +%s)
    
    # Check each requirement
    for requirement in $requirements; do
        print_progress "Checking $requirement..."
        
        case $requirement in
            docker)
                if ! docker info > /dev/null 2>&1; then
                    print_error "Docker is not running. Please start Docker first."
                    print_error "Try: sudo systemctl start docker"
                    return 1
                fi
                print_success "Docker is running"
                ;;
            docker-compose)
                if ! docker compose version > /dev/null 2>&1; then
                    print_error "Docker Compose not found or not working properly"
                    print_error "Please install Docker Compose v2.0+"
                    return 1
                fi
                print_success "Docker Compose is available"
                ;;
            nas-mount)
                if ! mountpoint -q /mnt/terramaster-nas; then
                    print_warning "NAS not mounted at /mnt/terramaster-nas"
                    print_warning "This will cause deployment to fail"
                    if ! confirm_action "Continue anyway? (This will likely fail)"; then
                        return 1
                    fi
                else
                    print_success "NAS is mounted"
                fi
                ;;
            disk-space)
                local available_space=$(df /mnt/terramaster-nas 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
                local available_gb=$((available_space / 1024 / 1024))
                
                if [ $available_gb -lt 10 ]; then
                    print_warning "Low disk space: ${available_gb}GB available"
                    print_warning "Recommended: At least 10GB free space"
                    if ! confirm_action "Continue with low disk space?"; then
                        return 1
                    fi
                else
                    print_success "Sufficient disk space: ${available_gb}GB available"
                fi
                ;;
        esac
    done
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    print_success "Prerequisites check completed in ${duration}s"
    return 0
}

# Function to show deployment summary
show_deployment_summary() {
    local build_flag="$1"
    local clean_flag="$2"
    local logs_flag="$3"
    local background_flag="$4"
    
    print_confirmation "Deployment Summary:"
    echo "  • Build containers: $build_flag"
    echo "  • Clean deployment: $clean_flag"
    echo "  • Show logs after: $logs_flag"
    echo "  • Background mode: $background_flag"
    echo ""
}

# Function to show access information
show_access_info() {
    local services="$1"
    
    echo ""
    print_header "Access Your System"
    
    for service in $services; do
        case $service in
            main-app)
                echo "  🌐 Main Application:     http://localhost:8000"
                ;;
            grafana)
                echo "  📊 Grafana Dashboards:   http://localhost:3001 (admin/Database@NEWSINT2025)"
                ;;
            prometheus)
                echo "  📈 Prometheus:           http://localhost:9090"
                ;;
            node-exporter)
                echo "  🔍 Node Exporter:        http://localhost:9100"
                ;;
        esac
    done
    echo ""
}

# Function to show background process status
show_background_status() {
    if [ ${#BACKGROUND_PROCESSES[@]} -gt 0 ]; then
        print_activity "Background processes are running:"
        for process_info in "${BACKGROUND_PROCESSES[@]}"; do
            IFS=':' read -r pid name log_file <<< "$process_info"
            print_status "  • $name (PID: $pid) - Log: $log_file"
        done
        print_status "These processes will continue running in the background"
    fi
}

# Export functions for use in other scripts
export -f init_ux_framework
export -f print_status print_success print_warning print_error print_header print_progress print_estimate print_confirmation print_activity
export -f show_time_estimate confirm_action show_progress
export -f start_background_process check_background_processes cleanup_on_exit
export -f show_error_details execute_with_error_handling
export -f check_prerequisites show_deployment_summary show_access_info show_background_status
