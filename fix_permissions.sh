#!/bin/bash

# Comprehensive Permission Fix for News Intelligence System
# This script ensures consistent permissions across all project components

set -e

echo "🔧 Fixing permissions for News Intelligence System..."

# Define user and group IDs
USER_ID=1000
GROUP_ID=1000
POSTGRES_USER_ID=999
POSTGRES_GROUP_ID=999

# Create a shared group for the project (if it doesn't exist)
SHARED_GROUP="newsint"
SHARED_GROUP_ID=1001

echo "📋 Setting up shared group..."

# Check if group exists, create if not
if ! getent group $SHARED_GROUP_ID > /dev/null 2>&1; then
    echo "Creating shared group $SHARED_GROUP with ID $SHARED_GROUP_ID..."
    sudo groupadd -g $SHARED_GROUP_ID $SHARED_GROUP
else
    echo "Shared group $SHARED_GROUP already exists"
fi

# Add current user to the shared group
echo "Adding current user to shared group..."
sudo usermod -a -G $SHARED_GROUP $USER

echo "📁 Fixing directory permissions..."

# Create necessary directories if they don't exist
mkdir -p api/docker/postgres/data
mkdir -p api/docker/postgres/init
mkdir -p api/docker/postgres/backups
mkdir -p api/docker/postgres/logs
mkdir -p api/logs
mkdir -p api/data
mkdir -p api/config
mkdir -p temp
mkdir -p web/build

# Set ownership for PostgreSQL data directory
echo "Setting PostgreSQL data directory permissions..."
sudo chown -R $POSTGRES_USER_ID:$POSTGRES_GROUP_ID api/docker/postgres/data
sudo chmod -R 755 api/docker/postgres/data

# Set ownership for other project directories
echo "Setting project directory permissions..."
sudo chown -R $USER_ID:$GROUP_ID api/docker/postgres/init
sudo chown -R $USER_ID:$GROUP_ID api/docker/postgres/backups
sudo chown -R $USER_ID:$GROUP_ID api/docker/postgres/logs
sudo chown -R $USER_ID:$GROUP_ID api/logs
sudo chown -R $USER_ID:$GROUP_ID api/data
sudo chown -R $USER_ID:$GROUP_ID api/config
sudo chown -R $USER_ID:$GROUP_ID temp
sudo chown -R $USER_ID:$GROUP_ID web/build

# Set proper permissions
sudo chmod -R 755 api/docker/postgres/init
sudo chmod -R 755 api/docker/postgres/backups
sudo chmod -R 755 api/docker/postgres/logs
sudo chmod -R 755 api/logs
sudo chmod -R 755 api/data
sudo chmod -R 755 api/config
sudo chmod -R 755 temp
sudo chmod -R 755 web/build

# Special permissions for PostgreSQL data
sudo chmod 700 api/docker/postgres/data

echo "🔍 Verifying permissions..."
echo "PostgreSQL data directory:"
ls -la api/docker/postgres/data/ | head -5

echo "Project directories:"
ls -la api/ | grep -E "(logs|data|config)"

echo "✅ Permission fix completed!"
echo ""
echo "📋 Summary:"
echo "  - PostgreSQL data: owned by postgres user ($POSTGRES_USER_ID:$POSTGRES_GROUP_ID)"
echo "  - Project files: owned by current user ($USER_ID:$GROUP_ID)"
echo "  - Shared group: $SHARED_GROUP ($SHARED_GROUP_ID) created"
echo "  - All directories have proper permissions"
echo ""
echo "🚀 You can now start the system with: docker compose --profile local up -d"
