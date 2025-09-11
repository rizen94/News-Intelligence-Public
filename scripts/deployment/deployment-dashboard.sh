#!/bin/bash

# News Intelligence System v3.0 - Deployment Dashboard
# Real-time status monitoring and management interface

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

# Global variables
REFRESH_INTERVAL=5
DASHBOARD_RUNNING=true

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

print_activity() {
    echo -e "${BOLD}${BLUE}[ACTIVITY]${NC} $1"
}

# Function to show usage
show_usage() {
    echo "📊 News Intelligence System v3.0 - Deployment Dashboard"
    echo "======================================================"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  --interval N    - Set refresh interval in seconds (default: 5)"
    echo "  --help          - Show this help message"
    echo ""
    echo "CONTROLS:"
    echo "  q, Q, Ctrl+C    - Quit dashboard"
    echo "  r, R            - Refresh now"
    echo "  s, S            - Show service status"
    echo "  l, L            - Show recent logs"
    echo "  h, H            - Show help"
    echo ""
}

# Function to get service status
get_service_status() {
    local service="$1"
    local status=$(docker compose -f docker-compose.yml ps $service 2>/dev/null | grep -E "Up|Down|Exited" | awk '{print $3}' || echo "Unknown")
    echo "$status"
}

# Function to get service health
get_service_health() {
    local service="$1"
    local status=$(get_service_status "$service")
    
    case $status in
        "Up")
            echo "🟢"
            ;;
        "Down"|"Exited")
            echo "🔴"
            ;;
        *)
            echo "🟡"
            ;;
    esac
}

# Function to get system resources
get_system_resources() {
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    local memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    local disk_usage=$(df -h / | awk 'NR==2{print $5}' | cut -d'%' -f1)
    
    echo "$cpu_usage|$memory_usage|$disk_usage"
}

# Function to get container stats
get_container_stats() {
    local service="$1"
    local stats=$(docker stats --no-stream --format "table {{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $service 2>/dev/null | tail -n +2 || echo "N/A")
    echo "$stats"
}

# Function to show service status
show_service_status() {
    local services=("postgres" "news-system" "redis" "prometheus" "grafana" "node-exporter")
    
    echo ""
    print_header "Service Status"
    echo "┌─────────────────┬─────────┬─────────────────────────────────┐"
    echo "│ Service         │ Status  │ Details                         │"
    echo "├─────────────────┼─────────┼─────────────────────────────────┤"
    
    for service in "${services[@]}"; do
        local health=$(get_service_health "$service")
        local status=$(get_service_status "$service")
        local stats=$(get_container_stats "$service")
        
        printf "│ %-15s │ %s %-6s │ %-31s │\n" "$service" "$health" "$status" "$stats"
    done
    
    echo "└─────────────────┴─────────┴─────────────────────────────────┘"
    echo ""
}

# Function to show system overview
show_system_overview() {
    local resources=$(get_system_resources)
    IFS='|' read -r cpu memory disk <<< "$resources"
    
    echo ""
    print_header "System Overview"
    echo "┌─────────────────┬─────────────────────────────────────────┐"
    echo "│ Resource        │ Usage                                   │"
    echo "├─────────────────┼─────────────────────────────────────────┤"
    printf "│ CPU Usage       │ %-39s │\n" "${cpu}%"
    printf "│ Memory Usage    │ %-39s │\n" "${memory}%"
    printf "│ Disk Usage      │ %-39s │\n" "${disk}%"
    echo "└─────────────────┴─────────────────────────────────────────┘"
    echo ""
}

# Function to show recent logs
show_recent_logs() {
    echo ""
    print_header "Recent Logs (Last 10 lines)"
    echo "┌─────────────────────────────────────────────────────────────┐"
    
    local log_output=$(docker compose -f docker-compose.yml logs --tail=10 2>/dev/null || echo "No logs available")
    
    while IFS= read -r line; do
        # Truncate long lines
        if [ ${#line} -gt 60 ]; then
            line="${line:0:57}..."
        fi
        printf "│ %-59s │\n" "$line"
    done <<< "$log_output"
    
    echo "└─────────────────────────────────────────────────────────────┘"
    echo ""
}

# Function to show access information
show_access_info() {
    echo ""
    print_header "Access Information"
    echo "┌─────────────────┬─────────────────────────────────────────┐"
    echo "│ Service         │ URL                                     │"
    echo "├─────────────────┼─────────────────────────────────────────┤"
    echo "│ Main App        │ http://localhost:8000                   │"
    echo "│ Grafana         │ http://localhost:3002                   │"
    echo "│ Prometheus      │ http://localhost:9090                   │"
    echo "│ Node Exporter   │ http://localhost:9100                   │"
    echo "└─────────────────┴─────────────────────────────────────────┘"
    echo ""
}

# Function to show deployment info
show_deployment_info() {
    echo ""
    print_header "Deployment Information"
    echo "┌─────────────────┬─────────────────────────────────────────┐"
    echo "│ Property        │ Value                                   │"
    echo "├─────────────────┼─────────────────────────────────────────┤"
    
    local deployment_time=$(stat -c %y docker-compose.yml 2>/dev/null | cut -d' ' -f1,2 | cut -d'.' -f1 || echo "Unknown")
    local docker_version=$(docker --version 2>/dev/null | cut -d' ' -f3 | cut -d',' -f1 || echo "Unknown")
    local compose_version=$(docker compose version 2>/dev/null | cut -d' ' -f4 || echo "Unknown")
    
    printf "│ Deployment Time │ %-39s │\n" "$deployment_time"
    printf "│ Docker Version  │ %-39s │\n" "$docker_version"
    printf "│ Compose Version │ %-39s │\n" "$compose_version"
    echo "└─────────────────┴─────────────────────────────────────────┘"
    echo ""
}

# Function to show main dashboard
show_dashboard() {
    clear
    echo "📊 News Intelligence System v3.0 - Deployment Dashboard"
    echo "======================================================"
    echo "Last updated: $(date)"
    echo "Refresh interval: ${REFRESH_INTERVAL}s"
    echo ""
    
    show_system_overview
    show_service_status
    show_access_info
    show_deployment_info
    
    echo "Controls: [q]uit [r]efresh [s]tatus [l]ogs [h]elp"
    echo ""
}

# Function to handle user input
handle_input() {
    local input="$1"
    
    case $input in
        q|Q)
            print_status "Exiting dashboard..."
            DASHBOARD_RUNNING=false
            ;;
        r|R)
            show_dashboard
            ;;
        s|S)
            show_service_status
            ;;
        l|L)
            show_recent_logs
            ;;
        h|H)
            show_usage
            ;;
        *)
            # Unknown input, ignore
            ;;
    esac
}

# Function to run dashboard
run_dashboard() {
    print_status "Starting deployment dashboard..."
    print_status "Press 'h' for help, 'q' to quit"
    
    # Set up signal handler
    trap 'DASHBOARD_RUNNING=false' INT TERM
    
    # Initial display
    show_dashboard
    
    # Main loop
    while $DASHBOARD_RUNNING; do
        # Check for user input (non-blocking)
        if read -t 0.1 -n 1 input 2>/dev/null; then
            handle_input "$input"
        fi
        
        # Refresh dashboard
        if $DASHBOARD_RUNNING; then
            sleep $REFRESH_INTERVAL
            show_dashboard
        fi
    done
    
    print_success "Dashboard stopped"
}

# Main execution
main() {
    local refresh_interval=5
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --interval)
                refresh_interval="$2"
                shift 2
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
    
    REFRESH_INTERVAL=$refresh_interval
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    
    # Check if unified files exist
    if [[ ! -f "docker-compose.yml" ]]; then
        print_error "docker-compose.yml not found!"
        print_error "Make sure you're running this script from the project root directory"
        exit 1
    fi
    
    # Run dashboard
    run_dashboard
}

# Run main function
main "$@"
