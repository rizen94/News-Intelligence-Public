#!/usr/bin/env bash
# Run from Pop OS (or API host): SSH into the Pi and report what's using disk space.
# Usage: ./scripts/pi_disk_scan.sh [user@host]
# Default: petes@192.168.93.104

set -e
TARGET="${1:-petes@192.168.93.104}"

echo "=== Disk usage (Pi) ==="
ssh -o BatchMode=yes "$TARGET" "df -h /"

echo ""
echo "=== Top-level directories (/) ==="
ssh -o BatchMode=yes "$TARGET" "sudo du -sh /* 2>/dev/null | sort -hr | head -25"

echo ""
echo "=== Under /var (logs, cache, lib) ==="
ssh -o BatchMode=yes "$TARGET" "sudo du -sh /var/* 2>/dev/null | sort -hr | head -20"

echo ""
echo "=== Under /etc (configs; Pi-hole lives here) ==="
ssh -o BatchMode=yes "$TARGET" "sudo du -sh /etc/* 2>/dev/null | sort -hr | head -20"

echo ""
echo "=== Pi-hole breakdown (/etc/pihole) ==="
ssh -o BatchMode=yes "$TARGET" "sudo du -sh /etc/pihole/* 2>/dev/null | sort -hr"

echo ""
echo "=== Home directory ==="
ssh -o BatchMode=yes "$TARGET" "du -sh /home/*/* 2>/dev/null | sort -hr | head -15"

echo ""
echo "=== Contents of /var/backups (often the biggest) ==="
ssh -o BatchMode=yes "$TARGET" "sudo du -sh /var/backups/* 2>/dev/null | sort -hr | head -20"

echo ""
echo "Done."
