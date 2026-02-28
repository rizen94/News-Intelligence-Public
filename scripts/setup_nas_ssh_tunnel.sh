#!/bin/bash
# News Intelligence - NAS SSH Tunnel Connection Script
# Establishes localhost:5433 -> NAS:5432 tunnel for database access.
# Run this whenever the PC is on and News Intelligence is in use.
# start_system.sh calls this automatically if the tunnel is not running.

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configuration (matches connection.py and main_v4.py)
NAS_HOST="${NAS_HOST:-192.168.93.100}"
NAS_SSH_PORT="${NAS_SSH_PORT:-9222}"
NAS_USER="${NAS_USER:-Admin}"
LOCAL_PORT="${LOCAL_PORT:-5433}"
NAS_DB_PORT="${NAS_DB_PORT:-5432}"

# Non-interactive by default (for start_system.sh)
INTERACTIVE=0
FORCE_RECREATE=0
for arg in "$@"; do
    case $arg in
        -i|--interactive) INTERACTIVE=1 ;;
        -k|--kill) FORCE_RECREATE=1 ;;
        -h|--help)
            echo "Usage: $0 [-i|--interactive] [-k|--kill]"
            echo "  -i  Interactive: prompt before killing existing tunnel"
            echo "  -k  Force: kill existing tunnel and recreate"
            echo "  No args: non-interactive, exit 0 if tunnel already running"
            exit 0
            ;;
    esac
done

tunnel_running() {
    pgrep -f "ssh -L ${LOCAL_PORT}:localhost:${NAS_DB_PORT}.*${NAS_HOST}" > /dev/null 2>&1
}

echo -e "${CYAN}[News Intelligence]${NC} Checking NAS SSH tunnel (localhost:${LOCAL_PORT} -> ${NAS_HOST}:${NAS_DB_PORT})"

# Already running?
if tunnel_running; then
    echo -e "${GREEN}✅ SSH tunnel already running${NC}"
    exit 0
fi

# Force kill existing (for -k)
if [[ $FORCE_RECREATE -eq 1 ]]; then
    pkill -f "ssh -L ${LOCAL_PORT}:localhost:${NAS_DB_PORT}.*${NAS_HOST}" 2>/dev/null || true
    sleep 2
fi

# Interactive: ask about any stale tunnel (detect by port)
if [[ $INTERACTIVE -eq 1 ]] && lsof -i ":${LOCAL_PORT}" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port ${LOCAL_PORT} in use. Kill and recreate tunnel? (y/N):${NC} "
    read -n 1 -r; echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "ssh -L ${LOCAL_PORT}:localhost:${NAS_DB_PORT}" 2>/dev/null || true
        sleep 2
    else
        echo "Leaving existing connection."
        exit 0
    fi
fi

# Create tunnel
echo -e "${CYAN}🔌 Creating SSH tunnel...${NC}"
ssh -L "${LOCAL_PORT}:localhost:${NAS_DB_PORT}" -N -f -p "${NAS_SSH_PORT}" \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    "${NAS_USER}@${NAS_HOST}" 2>&1 || {
    echo -e "${RED}❌ Failed to create SSH tunnel${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  • NAS reachable?  ping ${NAS_HOST}"
    echo "  • SSH port open?  nc -zv ${NAS_HOST} ${NAS_SSH_PORT}"
    echo "  • SSH key setup:  ssh-copy-id -p ${NAS_SSH_PORT} ${NAS_USER}@${NAS_HOST}"
    echo "  • Manual tunnel:  ssh -L ${LOCAL_PORT}:localhost:${NAS_DB_PORT} -N -f -p ${NAS_SSH_PORT} ${NAS_USER}@${NAS_HOST}"
    exit 1
}

sleep 1
if tunnel_running; then
    echo -e "${GREEN}✅ SSH tunnel established (localhost:${LOCAL_PORT} -> ${NAS_HOST}:${NAS_DB_PORT})${NC}"
    exit 0
else
    echo -e "${RED}❌ Tunnel process did not stay up${NC}"
    exit 1
fi
