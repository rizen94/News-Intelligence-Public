#!/bin/bash
# NAS Mount Health Monitor

NAS_MOUNT="/mnt/nas"
CHECK_INTERVAL=60

while true; do
    if ! mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
        echo "$(date): NAS mount lost, attempting to remount..."
        mount "$NAS_MOUNT" 2>&1 || echo "$(date): Remount failed"
    fi
    sleep $CHECK_INTERVAL
done
