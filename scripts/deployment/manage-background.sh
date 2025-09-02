#!/bin/bash

# News Intelligence System v3.0 - Background Process Manager
# Manages background processes and provides status information

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
    echo "🔧 News Intelligence System v3.0 - Background Process Manager"
    echo "============================================================="
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "COMMANDS:"
    echo "  status     - Show status of all background processes"
    echo "  logs       - Show logs from background processes"
    echo "  stop       - Stop all background processes"
    echo "  cleanup    - Clean up old log files"
    echo "  monitor    - Monitor processes in real-time"
    echo "  help       - Show this help message"
    echo ""
    echo "EXAMPLES:"
    echo "  $0 status      # Show process status"
    echo "  $0 logs        # Show recent logs"
    echo "  $0 monitor     # Monitor in real-time"
    echo "  $0 stop        # Stop all processes"
    echo ""
}

# Function to find background processes
find_background_processes() {
    local processes=()
    
    # Find processes by name pattern
    while IFS= read -r line; do
        if [[ $line =~ news-system ]]; then
            processes+=("$line")
        fi
    done < <(ps aux | grep -E "(docker|news-system)" | grep -v grep)
    
    echo "${processes[@]}"
}

# Function to show process status
show_status() {
    print_header "Background Process Status"
    echo ""
    
    local processes=($(find_background_processes))
    
    if [ ${#processes[@]} -eq 0 ]; then
        print_status "No background processes found"
        return 0
    fi
    
    print_status "Found ${#processes[@]} background processes:"
    echo ""
    
    for process in "${processes[@]}"; do
        local pid=$(echo "$process" | awk '{print $2}')
        local command=$(echo "$process" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
        local cpu=$(echo "$process" | awk '{print $3}')
        local mem=$(echo "$process" | awk '{print $4}')
        local time=$(echo "$process" | awk '{print $10}')
        
        print_activity "PID: $pid"
        print_status "  Command: $command"
        print_status "  CPU: ${cpu}% | Memory: ${mem}% | Time: $time"
        echo ""
    done
    
    # Check log files
    print_status "Log files:"
    for log_file in /tmp/news-system-*.log; do
        if [ -f "$log_file" ]; then
            local size=$(du -h "$log_file" | cut -f1)
            local modified=$(stat -c %y "$log_file" | cut -d' ' -f1,2 | cut -d'.' -f1)
            print_status "  • $(basename "$log_file") - Size: $size - Modified: $modified"
        fi
    done
}

# Function to show logs
show_logs() {
    print_header "Background Process Logs"
    echo ""
    
    local log_files=($(ls /tmp/news-system-*.log 2>/dev/null || true))
    
    if [ ${#log_files[@]} -eq 0 ]; then
        print_status "No log files found"
        return 0
    fi
    
    for log_file in "${log_files[@]}"; do
        print_activity "Log file: $(basename "$log_file")"
        echo "----------------------------------------"
        tail -20 "$log_file" 2>/dev/null || print_warning "Could not read log file"
        echo ""
    done
}

# Function to stop background processes
stop_processes() {
    print_header "Stopping Background Processes"
    echo ""
    
    local processes=($(find_background_processes))
    
    if [ ${#processes[@]} -eq 0 ]; then
        print_status "No background processes to stop"
        return 0
    fi
    
    print_warning "This will stop all background processes"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Operation cancelled"
        return 0
    fi
    
    for process in "${processes[@]}"; do
        local pid=$(echo "$process" | awk '{print $2}')
        local command=$(echo "$process" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
        
        print_activity "Stopping process $pid: $command"
        if kill $pid 2>/dev/null; then
            print_success "Process $pid stopped"
        else
            print_warning "Could not stop process $pid"
        fi
    done
    
    print_success "Background process cleanup completed"
}

# Function to cleanup log files
cleanup_logs() {
    print_header "Cleaning Up Log Files"
    echo ""
    
    local log_files=($(ls /tmp/news-system-*.log 2>/dev/null || true))
    
    if [ ${#log_files[@]} -eq 0 ]; then
        print_status "No log files to clean up"
        return 0
    fi
    
    print_warning "This will remove all log files"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Operation cancelled"
        return 0
    fi
    
    for log_file in "${log_files[@]}"; do
        print_activity "Removing $(basename "$log_file")"
        rm -f "$log_file"
    done
    
    print_success "Log cleanup completed"
}

# Function to monitor processes in real-time
monitor_processes() {
    print_header "Real-time Process Monitoring"
    print_status "Press Ctrl+C to exit"
    echo ""
    
    while true; do
        clear
        print_header "News Intelligence System - Process Monitor"
        echo "Last updated: $(date)"
        echo ""
        
        local processes=($(find_background_processes))
        
        if [ ${#processes[@]} -eq 0 ]; then
            print_status "No background processes running"
        else
            print_status "Active processes:"
            for process in "${processes[@]}"; do
                local pid=$(echo "$process" | awk '{print $2}')
                local command=$(echo "$process" | awk '{for(i=11;i<=NF;i++) printf "%s ", $i; print ""}')
                local cpu=$(echo "$process" | awk '{print $3}')
                local mem=$(echo "$process" | awk '{print $4}')
                local time=$(echo "$process" | awk '{print $10}')
                
                print_activity "PID: $pid | CPU: ${cpu}% | Memory: ${mem}% | Time: $time"
                print_status "  $command"
                echo ""
            done
        fi
        
        # Show system resources
        print_status "System Resources:"
        print_status "  CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)%"
        print_status "  Memory: $(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')"
        print_status "  Disk: $(df -h / | awk 'NR==2{printf "%s", $5}')"
        echo ""
        
        sleep 5
    done
}

# Main execution
main() {
    local command="${1:-status}"
    
    case $command in
        status)
            show_status
            ;;
        logs)
            show_logs
            ;;
        stop)
            stop_processes
            ;;
        cleanup)
            cleanup_logs
            ;;
        monitor)
            monitor_processes
            ;;
        help|--help|-h)
            show_usage
            ;;
        *)
            print_error "Unknown command: $command"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
