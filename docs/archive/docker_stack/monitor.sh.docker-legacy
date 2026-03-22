#!/bin/bash

# News Intelligence System v3.0 - Unified Monitoring Script
# System health, performance, and metrics monitoring

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="news-intelligence"
LOG_FILE="logs/monitor.log"
METRICS_FILE="logs/metrics.json"

# Create logs directory
mkdir -p logs

# Logging function
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"
}

# Show usage
show_usage() {
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  health          Check system health"
    echo "  metrics         Show system metrics"
    echo "  performance     Show performance data"
    echo "  logs            Show system logs"
    echo "  alerts          Check for alerts"
    echo "  dashboard       Open monitoring dashboard"
    echo "  watch           Continuous monitoring"
    echo "  report          Generate monitoring report"
    echo ""
    echo "Options:"
    echo "  --service NAME  Target specific service"
    echo "  --format JSON   Output in JSON format"
    echo "  --interval N    Monitoring interval in seconds (for watch)"
    echo "  --duration N    Monitoring duration in minutes (for watch)"
    echo ""
    echo "Examples:"
    echo "  $0 health                    # Check system health"
    echo "  $0 metrics --format json     # Show metrics in JSON"
    echo "  $0 watch --interval 5        # Monitor every 5 seconds"
    echo "  $0 report                    # Generate monitoring report"
}

# Check system health
check_health() {
    log "Checking system health..."
    
    local healthy_count=0
    local total_count=0
    local health_status=""
    
    # Check Docker
    if docker info > /dev/null 2>&1; then
        success "Docker: Running"
        ((healthy_count++))
    else
        error "Docker: Not running"
    fi
    ((total_count++))
    
    # Check PostgreSQL
    if docker-compose -f docker-compose.yml -p "$PROJECT_NAME" exec -T postgres pg_isready -U newsapp -d news_intelligence > /dev/null 2>&1; then
        success "PostgreSQL: Healthy"
        ((healthy_count++))
    else
        error "PostgreSQL: Unhealthy"
    fi
    ((total_count++))
    
    # Check Redis
    if docker-compose -f docker-compose.yml -p "$PROJECT_NAME" exec -T redis redis-cli ping > /dev/null 2>&1; then
        success "Redis: Healthy"
        ((healthy_count++))
    else
        error "Redis: Unhealthy"
    fi
    ((total_count++))
    
    # Check API
    if curl -s http://localhost:8000/api/health/ > /dev/null 2>&1; then
        success "API: Healthy"
        ((healthy_count++))
    else
        error "API: Unhealthy"
    fi
    ((total_count++))
    
    # Check Frontend
    if curl -s http://localhost/ > /dev/null 2>&1; then
        success "Frontend: Healthy"
        ((healthy_count++))
    else
        error "Frontend: Unhealthy"
    fi
    ((total_count++))
    
    # Check Pipeline Monitoring
    if curl -s http://localhost:8000/api/pipeline-monitoring/health > /dev/null 2>&1; then
        success "Pipeline Monitoring: Healthy"
        ((healthy_count++))
    else
        error "Pipeline Monitoring: Unhealthy"
    fi
    ((total_count++))
    
    # Overall health status
    if [ $healthy_count -eq $total_count ]; then
        health_status="HEALTHY"
        success "System Status: $health_status ($healthy_count/$total_count services)"
    else
        health_status="UNHEALTHY"
        warning "System Status: $health_status ($healthy_count/$total_count services)"
    fi
    
    # Return health status for JSON output
    if [ "${2:-}" = "json" ]; then
        echo "{\"status\":\"$health_status\",\"healthy\":$healthy_count,\"total\":$total_count,\"timestamp\":\"$(date -Iseconds)\"}"
    fi
}

# Show system metrics
show_metrics() {
    log "Collecting system metrics..."
    
    local metrics=""
    
    # System metrics
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    local memory_usage=$(free | grep Mem | awk '{printf "%.2f", $3/$2 * 100.0}')
    local disk_usage=$(df -h / | awk 'NR==2{print $5}' | sed 's/%//')
    
    # Docker metrics
    local container_count=$(docker ps -q | wc -l)
    local image_count=$(docker images -q | wc -l)
    
    # Database metrics
    local db_size=""
    if docker-compose -f docker-compose.yml -p "$PROJECT_NAME" exec -T postgres psql -U newsapp -d news_intelligence -c "SELECT pg_size_pretty(pg_database_size('news_intelligence'));" 2>/dev/null | grep -v "pg_size_pretty" | grep -v "^-" | grep -v "^(" | head -1; then
        db_size=$(docker-compose -f docker-compose.yml -p "$PROJECT_NAME" exec -T postgres psql -U newsapp -d news_intelligence -c "SELECT pg_size_pretty(pg_database_size('news_intelligence'));" 2>/dev/null | grep -v "pg_size_pretty" | grep -v "^-" | grep -v "^(" | head -1 | xargs)
    fi
    
    # API metrics
    local api_response_time=""
    if command -v curl > /dev/null 2>&1; then
        api_response_time=$(curl -o /dev/null -s -w '%{time_total}' http://localhost:8000/api/health/ 2>/dev/null || echo "N/A")
    fi
    
    # Display metrics
    echo "System Metrics:"
    echo "==============="
    echo "CPU Usage: ${cpu_usage}%"
    echo "Memory Usage: ${memory_usage}%"
    echo "Disk Usage: ${disk_usage}%"
    echo "Containers: $container_count"
    echo "Images: $image_count"
    echo "Database Size: ${db_size:-N/A}"
    echo "API Response Time: ${api_response_time}s"
    
    # JSON output
    if [ "${2:-}" = "json" ]; then
        metrics="{\"cpu_usage\":\"$cpu_usage\",\"memory_usage\":\"$memory_usage\",\"disk_usage\":\"$disk_usage\",\"containers\":$container_count,\"images\":$image_count,\"database_size\":\"$db_size\",\"api_response_time\":\"$api_response_time\",\"timestamp\":\"$(date -Iseconds)\"}"
        echo "$metrics" > "$METRICS_FILE"
        echo "$metrics"
    fi
}

# Show performance data
show_performance() {
    log "Collecting performance data..."
    
    # Container resource usage
    echo "Container Performance:"
    echo "======================"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
    
    echo ""
    echo "System Load:"
    echo "============"
    uptime
    
    echo ""
    echo "Memory Usage:"
    echo "============="
    free -h
    
    echo ""
    echo "Disk Usage:"
    echo "==========="
    df -h
}

# Show system logs
show_logs() {
    local service="${1:-}"
    log "Showing system logs${service:+ for $service}..."
    
    if [ -n "$service" ]; then
        docker-compose -f docker-compose.yml -p "$PROJECT_NAME" logs --tail=100 "$service"
    else
        echo "Application Logs:"
        echo "================="
        if [ -f "logs/production-startup.log" ]; then
            tail -20 logs/production-startup.log
        fi
        
        echo ""
        echo "Pipeline Logs:"
        echo "=============="
        if [ -f "logs/pipeline_trace.log" ]; then
            tail -20 logs/pipeline_trace.log
        fi
        
        echo ""
        echo "Docker Logs:"
        echo "============"
        docker-compose -f docker-compose.yml -p "$PROJECT_NAME" logs --tail=20
    fi
}

# Check for alerts
check_alerts() {
    log "Checking for alerts..."
    
    local alerts=0
    
    # High CPU usage
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        warning "High CPU usage: ${cpu_usage}%"
        ((alerts++))
    fi
    
    # High memory usage
    local memory_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    if [ "$memory_usage" -gt 80 ]; then
        warning "High memory usage: ${memory_usage}%"
        ((alerts++))
    fi
    
    # High disk usage
    local disk_usage=$(df -h / | awk 'NR==2{print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 80 ]; then
        warning "High disk usage: ${disk_usage}%"
        ((alerts++))
    fi
    
    # Service health
    if ! curl -s http://localhost:8000/api/health/ > /dev/null 2>&1; then
        warning "API service is down"
        ((alerts++))
    fi
    
    if [ $alerts -eq 0 ]; then
        success "No alerts detected"
    else
        warning "$alerts alert(s) detected"
    fi
}

# Open monitoring dashboard
open_dashboard() {
    log "Opening monitoring dashboard..."
    
    # Check if Grafana is running
    if curl -s http://localhost:9090 > /dev/null 2>&1; then
        success "Grafana dashboard: http://localhost:9090"
        if command -v xdg-open > /dev/null 2>&1; then
            xdg-open http://localhost:9090
        elif command -v open > /dev/null 2>&1; then
            open http://localhost:9090
        else
            log "Please open http://localhost:9090 in your browser"
        fi
    else
        warning "Grafana dashboard not available. Please start monitoring services."
    fi
    
    # Show other available dashboards
    echo ""
    log "Available dashboards:"
    echo "  - API Documentation: http://localhost:8000/docs"
    echo "  - Pipeline Monitoring: http://localhost:8000/api/pipeline-monitoring"
    echo "  - Frontend: http://localhost"
}

# Continuous monitoring
watch_monitoring() {
    local interval="${1:-5}"
    local duration="${2:-0}"
    
    log "Starting continuous monitoring (interval: ${interval}s${duration:+, duration: ${duration}m})"
    
    local start_time=$(date +%s)
    local end_time=0
    
    if [ "$duration" -gt 0 ]; then
        end_time=$((start_time + duration * 60))
    fi
    
    while true; do
        clear
        echo "News Intelligence System v3.0 - Live Monitoring"
        echo "==============================================="
        echo "Time: $(date)"
        echo ""
        
        check_health
        echo ""
        show_metrics
        echo ""
        check_alerts
        
        # Check if duration limit reached
        if [ "$duration" -gt 0 ] && [ $(date +%s) -ge $end_time ]; then
            break
        fi
        
        sleep "$interval"
    done
}

# Generate monitoring report
generate_report() {
    local report_file="logs/monitoring_report_$(date +%Y%m%d_%H%M%S).txt"
    
    log "Generating monitoring report: $report_file"
    
    {
        echo "News Intelligence System v3.0 - Monitoring Report"
        echo "================================================="
        echo "Generated: $(date)"
        echo ""
        
        echo "System Health:"
        echo "=============="
        check_health
        echo ""
        
        echo "System Metrics:"
        echo "==============="
        show_metrics
        echo ""
        
        echo "Performance Data:"
        echo "================="
        show_performance
        echo ""
        
        echo "Alerts:"
        echo "======"
        check_alerts
        echo ""
        
        echo "Recent Logs:"
        echo "============"
        show_logs
        
    } > "$report_file"
    
    success "Monitoring report generated: $report_file"
}

# Main execution
main() {
    case "${1:-}" in
        health)
            check_health "${2:-}"
            ;;
        metrics)
            show_metrics "${2:-}"
            ;;
        performance)
            show_performance
            ;;
        logs)
            show_logs "${2:-}"
            ;;
        alerts)
            check_alerts
            ;;
        dashboard)
            open_dashboard
            ;;
        watch)
            local interval="5"
            local duration="0"
            
            # Parse options
            shift
            while [[ $# -gt 0 ]]; do
                case $1 in
                    --interval)
                        interval="$2"
                        shift 2
                        ;;
                    --duration)
                        duration="$2"
                        shift 2
                        ;;
                    *)
                        error "Unknown option: $1"
                        exit 1
                        ;;
                esac
            done
            
            watch_monitoring "$interval" "$duration"
            ;;
        report)
            generate_report
            ;;
        --help)
            show_usage
            ;;
        *)
            error "Invalid command: ${1:-}"
            show_usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"
