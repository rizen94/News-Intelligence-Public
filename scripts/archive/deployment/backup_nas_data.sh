#!/bin/bash

# News Intelligence System - NAS Data Backup Script

set -e

BACKUP_DIR="/mnt/terramaster-nas/docker-postgres-data/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="news_system_backup_$TIMESTAMP"

echo "🔄 Creating backup: $BACKUP_NAME"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup PostgreSQL data
if docker ps | grep -q news-system-postgres-nas; then
    echo "📊 Backing up PostgreSQL database..."
    docker exec news-system-postgres-nas pg_dumpall -U newsapp > "$BACKUP_DIR/${BACKUP_NAME}_postgres.sql"
    echo "✅ PostgreSQL backup complete: ${BACKUP_NAME}_postgres.sql"
else
    echo "⚠️  PostgreSQL container not running, skipping database backup"
fi

# Backup application data
echo "📁 Backing up application data..."
tar -czf "$BACKUP_DIR/${BACKUP_NAME}_app_data.tar.gz" \
    -C /mnt/terramaster-nas/docker-postgres-data \
    logs data ml-models data-archives 2>/dev/null || true

echo "✅ Application data backup complete: ${BACKUP_NAME}_app_data.tar.gz"

# Clean up old backups (keep last 7 days)
echo "🧹 Cleaning up old backups..."
find "$BACKUP_DIR" -name "news_system_backup_*" -mtime +7 -delete

echo "🎉 Backup complete! Files saved to: $BACKUP_DIR"
echo "📊 Backup size: $(du -sh "$BACKUP_DIR" | cut -f1)"
