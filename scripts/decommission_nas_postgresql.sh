#!/bin/bash
# News Intelligence — Phase 7.5: Decommission PostgreSQL on NAS
# Run from primary. Stops and disables PostgreSQL on NAS (192.168.93.100).
# NAS becomes storage-only. Rollback: see docs/MIGRATION_TODO.md

set -e

NAS_HOST="${NAS_HOST:-192.168.93.100}"
NAS_SSH_PORT="${NAS_SSH_PORT:-9222}"
NAS_USER="${NAS_USER:-Admin}"

echo "=== Decommissioning PostgreSQL on NAS ($NAS_HOST) ==="
echo "Ensure News Intelligence is fully migrated to Widow before continuing."
if [[ "${1:-}" != "-y" ]] && [[ "${1:-}" != "--yes" ]]; then
    read -p "Proceed? (yes/no): " confirm
    [[ "$confirm" != "yes" ]] && echo "Aborted." && exit 0
fi

echo "Killing any NAS SSH tunnel on primary..."
pkill -f "ssh -L 5433:localhost:5432.*${NAS_HOST}" 2>/dev/null || true
sleep 1
echo "Tunnel stopped."

echo "Stopping PostgreSQL on NAS..."
if ssh -o ConnectTimeout=5 -p "$NAS_SSH_PORT" "${NAS_USER}@${NAS_HOST}" "
    if command -v docker &>/dev/null; then
        docker stop news-system-postgres 2>/dev/null || docker stop postgres 2>/dev/null || true
        docker ps -a | grep -i postgres || true
    fi
    sudo systemctl stop postgresql 2>/dev/null || true
    sudo systemctl disable postgresql 2>/dev/null || true
    echo 'PostgreSQL stopped on NAS.'
" 2>/dev/null; then
    echo "✅ NAS PostgreSQL decommissioned."
else
    echo "⚠️  Could not SSH to NAS. Stop PostgreSQL manually via NAS admin interface:"
    echo "   - Synology: Package Center → PostgreSQL → Stop"
    echo "   - QNAP: App Center → PostgreSQL → Stop"
    echo "   - Or SSH: ssh -p $NAS_SSH_PORT ${NAS_USER}@${NAS_HOST}"
fi
