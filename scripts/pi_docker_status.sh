#!/usr/bin/env bash
# Check status of Docker containers on the Pi. Run from Pop OS (SSH to Pi).
# Usage: ./scripts/pi_docker_status.sh [user@host]
# Output can be redirected to a file for later review.

set -e
TARGET="${1:-petes@192.168.93.104}"

echo "=============================================="
echo "Pi Docker status — $(date -Iseconds)"
echo "Host: $TARGET"
echo "=============================================="
echo ""

ssh -o BatchMode=yes "$TARGET" bash -s << 'REMOTE'
D="docker"
# Use sudo if docker fails (e.g. user not in docker group)
docker --version &>/dev/null || D="sudo docker"

echo "--- Docker version ---"
$D --version 2>/dev/null || echo "Docker not installed or not in PATH"

echo ""
echo "--- All containers (ps -a) ---"
out=$($D ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null) || out=$($D ps -a 2>/dev/null)
if [ -z "$out" ]; then echo "(no containers)"; else echo "$out"; fi

echo ""
echo "--- Container resource usage (stats, one snapshot) ---"
$D stats --no-stream 2>/dev/null || echo "(no containers or stats unavailable)"

echo ""
echo "--- Docker Compose projects (if any) ---"
$D compose ls 2>/dev/null || $D compose ls 2>/dev/null || docker-compose ls 2>/dev/null || echo "No compose projects or compose not used"

echo ""
echo "--- Docker disk usage ---"
$D system df 2>/dev/null || sudo docker system df 2>/dev/null || echo "Could not get docker system df"
REMOTE

echo ""
echo "--- End Docker status ---"
