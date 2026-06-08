#!/bin/bash
# Investigate Widow crash - run AFTER Widow comes back online
# Execute via: ssh 192.168.93.101 "bash -s" < scripts/investigate_widow_crash.sh

set -e

echo "=============================================="
echo "  WIDOW CRASH INVESTIGATION"
echo "  $(date)"
echo "=============================================="

# --- CONNECTION POOL INVESTIGATION ---
echo -e "\n[1] CONNECTION POOL SETTINGS"
echo "---"
sudo -u postgres psql -c "SHOW max_connections;" 2>/dev/null || echo "Could not query PostgreSQL"

echo -e "\nCurrent pool usage:"
sudo -u postgres psql -c "SELECT count(*) as active_connections FROM pg_stat_activity;" 2>/dev/null || echo "Could not query"

# --- PGBOUNCER SETTINGS (if configured) ---
echo -e "\n[2] PGBOUNCER SETTINGS"
echo "---"
if pgrep -x pgbouncer > /dev/null 2>&1; then
    echo "PgBouncer is running"
    # Check pgbouncer.ini location
    for loc in /etc/pgbouncer/pgbouncer.ini /opt/pgbouncer/pgbouncer.ini; do
        if [ -f "$loc" ]; then
            echo "Config found at: $loc"
            grep -E "(max_client_conn|default_pool_size|reserve_pool_size)" "$loc" 2>/dev/null || true
        fi
    done
else
    echo "PgBouncer NOT running"
fi

# --- CHECK FOR OOM / CONNECTION ISSUES IN LOGS ---
echo -e "\n[3] POSTGRESQL LOGS - ERROR SEARCH"
echo "---"
LOG_DIR="/var/log/postgresql"
if [ -d "$LOG_DIR" ]; then
    echo "Searching PostgreSQL logs for connection/OOM errors..."
    grep -riE "(too many connections|out of memory|cannot allocate memory|pgbouncer: pooling)" "$LOG_DIR" 2>/dev/null | tail -50 || echo "No matches found or logs not accessible"
else
    echo "PostgreSQL log directory not found at $LOG_DIR"
fi

# --- SYSTEM KERNEL LOGS FOR OOM ---
echo -e "\n[4] KERNEL LOGS - OOM KILLER"
echo "---"
grep -i "out of memory" /var/log/kern.log 2>/dev/null | tail -30 || \
grep -i "out of memory" /var/log/syslog 2>/dev/null | tail -30 || \
echo "No OOM messages found in kernel logs"

# --- HARD DRIVE HEALTH ---
echo -e "\n[5] HARD DRIVE SMART STATUS"
echo "---"
if command -v smartctl &> /dev/null; then
    for drive in /dev/sda /dev/sdb; do
        if [ -b "$drive" ]; then
            echo "Drive: $drive"
            smartctl -H "$drive" 2>/dev/null || echo "  Cannot read SMART data"
            smartctl -A "$drive" 2>/dev/null | grep -E "(Reallocated_Sector|Current_Pending_Sector|Offline_Uncorrectable|Raw_Read_Error)" || true
            echo ""
        fi
    done
else
    echo "smartctl not installed"
fi

# --- FILESYSTEM ERRORS ---
echo -e "\n[6] FILESYSTEM ERRORS (dmesg)"
echo "---"
dmesg 2>/dev/null | grep -iE "(error|warn|ext4|i/o)" | tail -30 || \
echo "Could not read dmesg"

# --- SYSTEM SHUTDOWN/RESTART LOGS ---
echo -e "\n[7] SYSTEM JOURNAL - LAST BOOT"
echo "---"
if command -v journalctl &> /dev/null; then
    echo "Last boot time:"
    journalctl -b -1 --no-pager 2>/dev/null | head -5 || echo "Could not access previous boot logs"
    echo ""
    echo "Errors/warnings from last boot:"
    journalctl -b -1 --no-pager 2>/dev/null | grep -iE "(error|fail|crash)" | tail -30 || true
else
    echo "journalctl not available"
fi

# --- CHECK IF SYSTEM WAS REBOOTED (not graceful shutdown) ---
echo -e "\n[8] UPTIME / REBOOT CHECK"
echo "---"
uptime
echo ""
echo "Last reboot timestamp:"
last reboot 2>/dev/null | head -5 || who -b 2>/dev/null || echo "Could not determine"

# --- POSTGRESQL PROCESS TERMINATION ---
echo -e "\n[9] POSTGRESQL PROCESS TERMINATION CHECKS"
echo "---"
grep -i "postgres" /var/log/syslog 2>/dev/null | grep -iE "(killed|segfault|term)" | tail -20 || \
grep -i "postgres" /var/log/kern.log 2>/dev/null | grep -iE "(killed|segfault|term)" | tail -20 || \
echo "No process termination found"

echo -e "\n=============================================="
echo "  INVESTIGATION COMPLETE"
echo "=============================================="
echo ""
echo "Review the output above for:"
echo "  - OOM killer messages (connection pool too high)"
echo "  - SMART drive errors (hard drive failing)"
echo "  - Filesystem I/O errors (storage issues)"
echo "  - PostgreSQL 'too many connections' errors"