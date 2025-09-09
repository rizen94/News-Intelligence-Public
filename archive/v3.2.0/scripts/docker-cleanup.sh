#!/bin/bash

# Docker Resource Cleanup Script
# Runs every 6 hours to reclaim memory and disk space

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Log file
LOG_FILE="/var/log/docker-cleanup.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

log_message() {
    echo -e "${1}" | tee -a "$LOG_FILE"
}

log_message "${BLUE}[$DATE] Starting Docker cleanup...${NC}"

# Function to get memory usage before cleanup
get_memory_usage() {
    docker system df --format "table {{.Type}}\t{{.TotalCount}}\t{{.Size}}" 2>/dev/null || echo "Unable to get Docker system info"
}

# Function to get disk usage
get_disk_usage() {
    df -h /var/lib/docker 2>/dev/null || echo "Unable to get Docker disk usage"
}

log_message "${YELLOW}Before cleanup:${NC}"
log_message "$(get_memory_usage)"
log_message "$(get_disk_usage)"

# 1. Remove stopped containers
log_message "${BLUE}Removing stopped containers...${NC}"
STOPPED_CONTAINERS=$(docker container prune -f 2>/dev/null | grep -o '[0-9]*' | tail -1)
log_message "${GREEN}Removed $STOPPED_CONTAINERS stopped containers${NC}"

# 2. Remove unused images (keep images from last 24 hours)
log_message "${BLUE}Removing unused images older than 24 hours...${NC}"
UNUSED_IMAGES=$(docker image prune -a --filter "until=24h" -f 2>/dev/null | grep -o '[0-9]*' | tail -1)
log_message "${GREEN}Removed $UNUSED_IMAGES unused images${NC}"

# 3. Remove unused volumes (be careful with this)
log_message "${BLUE}Removing unused volumes...${NC}"
UNUSED_VOLUMES=$(docker volume prune -f 2>/dev/null | grep -o '[0-9]*' | tail -1)
log_message "${GREEN}Removed $UNUSED_VOLUMES unused volumes${NC}"

# 4. Remove unused networks
log_message "${BLUE}Removing unused networks...${NC}"
UNUSED_NETWORKS=$(docker network prune -f 2>/dev/null | grep -o '[0-9]*' | tail -1)
log_message "${GREEN}Removed $UNUSED_NETWORKS unused networks${NC}"

# 5. Remove build cache
log_message "${BLUE}Removing build cache...${NC}"
BUILD_CACHE=$(docker builder prune -f 2>/dev/null | grep -o '[0-9]*' | tail -1)
log_message "${GREEN}Removed $BUILD_CACHE MB of build cache${NC}"

# 6. System-wide cleanup (most aggressive)
log_message "${BLUE}Running system-wide cleanup...${NC}"
SYSTEM_CLEANUP=$(docker system prune -a --volumes -f 2>/dev/null | grep -o '[0-9]*' | tail -1)
log_message "${GREEN}System cleanup freed $SYSTEM_CLEANUP MB${NC}"

log_message "${YELLOW}After cleanup:${NC}"
log_message "$(get_memory_usage)"
log_message "$(get_disk_usage)"

# 7. Restart Docker daemon if memory usage is still high (>80%)
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
if [ "$MEMORY_USAGE" -gt 80 ]; then
    log_message "${RED}Memory usage is high ($MEMORY_USAGE%), restarting Docker daemon...${NC}"
    sudo systemctl restart docker
    log_message "${GREEN}Docker daemon restarted${NC}"
fi

# 8. Log final status
log_message "${GREEN}[$DATE] Docker cleanup completed successfully${NC}"
log_message "${BLUE}========================================${NC}"

# Optional: Send notification (if you have notify-send installed)
if command -v notify-send &> /dev/null; then
    notify-send "Docker Cleanup" "Cleanup completed. Freed resources and cleaned up unused containers/images."
fi







