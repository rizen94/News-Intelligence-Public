#!/bin/bash

# News Intelligence System - NAS Storage Dashboard
# Real-time monitoring and status display for NAS storage

# Configuration
NAS_MOUNT_PATH="/mnt/nas/public"
LOG_FILE="/var/log/news-intelligence-nas.log"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# Clear screen and show header
clear
echo -e "${PURPLE}================================================${NC}"
echo -e "${PURPLE}    News Intelligence NAS Storage Dashboard    ${NC}"
echo -e "${PURPLE}================================================${NC}"
echo ""

# Function to get status with color
get_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ OK${NC}"
    else
        echo -e "${RED}✗ FAILED${NC}"
    fi
}

# Function to get usage color
get_usage_color() {
    local usage=$1
    if [ $usage -lt 70 ]; then
        echo -e "${GREEN}${usage}%${NC}"
    elif [ $usage -lt 85 ]; then
        echo -e "${YELLOW}${usage}%${NC}"
    else
        echo -e "${RED}${usage}%${NC}"
    fi
}

# 1. NAS Mount Status
echo -e "${BLUE}1. NAS Mount Status${NC}"
echo "=================="
if mountpoint -q "$NAS_MOUNT_PATH" 2>/dev/null; then
    echo -e "Mount Point: ${GREEN}$NAS_MOUNT_PATH${NC}"
    echo -e "Status: $(get_status 0)"
    
    # Get mount details
    MOUNT_INFO=$(mount | grep "$NAS_MOUNT_PATH")
    echo -e "Type: ${CYAN}$(echo $MOUNT_INFO | awk '{print $5}')${NC}"
    echo -e "Source: ${CYAN}$(echo $MOUNT_INFO | awk '{print $1}')${NC}"
else
    echo -e "Mount Point: ${RED}$NAS_MOUNT_PATH${NC}"
    echo -e "Status: $(get_status 1)"
fi
echo ""

# 2. Storage Usage
echo -e "${BLUE}2. Storage Usage${NC}"
echo "==============="
if [ -d "$NAS_MOUNT_PATH" ]; then
    USAGE_INFO=$(df -h "$NAS_MOUNT_PATH" | tail -1)
    TOTAL=$(echo $USAGE_INFO | awk '{print $2}')
    USED=$(echo $USAGE_INFO | awk '{print $3}')
    AVAIL=$(echo $USAGE_INFO | awk '{print $4}')
    USAGE_PCT=$(echo $USAGE_INFO | awk '{print $5}' | sed 's/%//')
    
    echo -e "Total Space: ${CYAN}$TOTAL${NC}"
    echo -e "Used Space:  ${CYAN}$USED${NC}"
    echo -e "Available:   ${CYAN}$AVAIL${NC}"
    echo -e "Usage:       $(get_usage_color $USAGE_PCT)"
else
    echo -e "${RED}Storage information unavailable${NC}"
fi
echo ""

# 3. Database Storage
echo -e "${BLUE}3. Database Storage${NC}"
echo "=================="
DB_PATH="$NAS_MOUNT_PATH/docker-postgres-data"
if [ -d "$DB_PATH" ]; then
    echo -e "PostgreSQL Data: ${GREEN}$DB_PATH${NC}"
    if [ -d "$DB_PATH/pgdata" ]; then
        PG_SIZE=$(du -sh "$DB_PATH/pgdata" 2>/dev/null | awk '{print $1}')
        echo -e "Database Size:   ${CYAN}$PG_SIZE${NC}"
        echo -e "Status:          $(get_status 0)"
    else
        echo -e "Database Size:   ${YELLOW}Not initialized${NC}"
        echo -e "Status:          $(get_status 1)"
    fi
    
    if [ -d "$DB_PATH/redis-data" ]; then
        REDIS_SIZE=$(du -sh "$DB_PATH/redis-data" 2>/dev/null | awk '{print $1}')
        echo -e "Redis Size:      ${CYAN}$REDIS_SIZE${NC}"
    fi
    
    if [ -d "$DB_PATH/prometheus-data" ]; then
        PROM_SIZE=$(du -sh "$DB_PATH/prometheus-data" 2>/dev/null | awk '{print $1}')
        echo -e "Prometheus Size: ${CYAN}$PROM_SIZE${NC}"
    fi
else
    echo -e "${RED}Database storage not found${NC}"
fi
echo ""

# 4. Service Health
echo -e "${BLUE}4. Service Health${NC}"
echo "================="
echo -e "PostgreSQL: $(get_status $(docker exec news-intelligence-postgres pg_isready -U newsapp -d news_intelligence >/dev/null 2>&1; echo $?))"
echo -e "Redis:      $(get_status $(docker exec news-intelligence-redis redis-cli ping >/dev/null 2>&1; echo $?))"
echo -e "API:        $(get_status $(curl -f http://localhost:8000/api/health/ >/dev/null 2>&1; echo $?))"
echo -e "Frontend:   $(get_status $(curl -f http://localhost/ >/dev/null 2>&1; echo $?))"
echo ""

# 5. Network Connectivity
echo -e "${BLUE}5. Network Connectivity${NC}"
echo "======================"
NAS_HOST="192.168.93.100"
if ping -c 1 "$NAS_HOST" >/dev/null 2>&1; then
    echo -e "NAS Host ($NAS_HOST): $(get_status 0)"
    PING_TIME=$(ping -c 1 "$NAS_HOST" | grep "time=" | awk -F'time=' '{print $2}' | awk '{print $1}')
    echo -e "Response Time: ${CYAN}$PING_TIME${NC}"
else
    echo -e "NAS Host ($NAS_HOST): $(get_status 1)"
fi
echo ""

# 6. Recent Activity
echo -e "${BLUE}6. Recent Activity${NC}"
echo "=================="
if [ -f "$LOG_FILE" ]; then
    echo -e "Last 5 log entries:"
    tail -5 "$LOG_FILE" | while read line; do
        echo -e "  ${CYAN}$line${NC}"
    done
else
    echo -e "${YELLOW}No log file found${NC}"
fi
echo ""

# 7. Backup Status
echo -e "${BLUE}7. Backup Status${NC}"
echo "==============="
BACKUP_DIR="$NAS_MOUNT_PATH/docker-postgres-data/backups"
if [ -d "$BACKUP_DIR" ]; then
    BACKUP_COUNT=$(find "$BACKUP_DIR" -name "*.sql.gz" -o -name "*.tar.gz" | wc -l)
    echo -e "Backup Directory: ${GREEN}$BACKUP_DIR${NC}"
    echo -e "Backup Count:     ${CYAN}$BACKUP_COUNT${NC}"
    
    if [ $BACKUP_COUNT -gt 0 ]; then
        LATEST_BACKUP=$(find "$BACKUP_DIR" -name "*.sql.gz" -o -name "*.tar.gz" -printf '%T@ %p\n' | sort -n | tail -1 | awk '{print $2}')
        if [ -n "$LATEST_BACKUP" ]; then
            BACKUP_DATE=$(stat -c %y "$LATEST_BACKUP" | awk '{print $1" "$2}' | cut -d. -f1)
            echo -e "Latest Backup:    ${CYAN}$(basename "$LATEST_BACKUP")${NC}"
            echo -e "Backup Date:      ${CYAN}$BACKUP_DATE${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Backup directory not found${NC}"
fi
echo ""

# 8. System Resources
echo -e "${BLUE}8. System Resources${NC}"
echo "==================="
echo -e "CPU Usage:  ${CYAN}$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')%${NC}"
echo -e "Memory:     ${CYAN}$(free | grep Mem | awk '{printf "%.1f%%", $3/$2 * 100.0}')${NC}"
echo -e "Load Avg:   ${CYAN}$(uptime | awk -F'load average:' '{print $2}')${NC}"
echo ""

# 9. Quick Actions
echo -e "${BLUE}9. Quick Actions${NC}"
echo "==============="
echo -e "1. ${CYAN}Mount NAS${NC}        - /usr/local/bin/mount-news-nas"
echo -e "2. ${CYAN}Health Check${NC}     - /usr/local/bin/monitor-nas"
echo -e "3. ${CYAN}Backup Database${NC}  - /usr/local/bin/backup-database"
echo -e "4. ${CYAN}Full Backup${NC}      - /usr/local/bin/backup-news-system"
echo -e "5. ${CYAN}View Logs${NC}        - tail -f $LOG_FILE"
echo ""

# 10. Footer
echo -e "${PURPLE}================================================${NC}"
echo -e "${PURPLE}Last Updated: $(date)${NC}"
echo -e "${PURPLE}================================================${NC}"

# Auto-refresh option
if [ "$1" = "--watch" ]; then
    echo -e "\n${YELLOW}Press Ctrl+C to exit watch mode${NC}"
    sleep 5
    exec "$0" --watch
fi
