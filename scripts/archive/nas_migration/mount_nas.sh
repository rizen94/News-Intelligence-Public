#!/bin/bash
# NAS Mount Script with Retry Logic

NAS_MOUNT="/mnt/nas"
MAX_RETRIES=5
RETRY_DELAY=5

for i in $(seq 1 $MAX_RETRIES); do
    if mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
        echo "NAS already mounted at $NAS_MOUNT"
        exit 0
    fi
    
    echo "Attempting to mount NAS (attempt $i/$MAX_RETRIES)..."
    mount "$NAS_MOUNT" 2>&1
    
    if mountpoint -q "$NAS_MOUNT" 2>/dev/null; then
        echo "NAS mounted successfully"
        exit 0
    fi
    
    if [ $i -lt $MAX_RETRIES ]; then
        echo "Mount failed, retrying in $RETRY_DELAY seconds..."
        sleep $RETRY_DELAY
    fi
done

echo "Failed to mount NAS after $MAX_RETRIES attempts"
exit 1
