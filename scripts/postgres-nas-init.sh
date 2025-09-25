#!/bin/sh
set -e

# Custom entrypoint for PostgreSQL on NAS storage
# This script handles the CIFS permission limitations

echo "Starting PostgreSQL NAS initialization..."

# Check if data directory exists and has content
if [ -d "/var/lib/postgresql/data" ] && [ "$(ls -A /var/lib/postgresql/data)" ]; then
    echo "PostgreSQL data directory exists on NAS storage"
    
    # Fix ownership for CIFS-mounted data
    echo "Fixing ownership for CIFS-mounted data..."
    chown -R postgres:postgres /var/lib/postgresql/data
    
    # Start PostgreSQL
    echo "Starting PostgreSQL server with existing data..."
    exec su-exec postgres postgres
else
    echo "Initializing PostgreSQL database on NAS storage..."
    
    # Create a temporary local directory for initialization
    TEMP_DIR="/tmp/postgres_init_$$"
    mkdir -p "$TEMP_DIR"
    chown postgres:postgres "$TEMP_DIR"
    
    # Initialize PostgreSQL in the temporary directory
    echo "Running initdb in temporary directory..."
    su-exec postgres initdb \
        --pgdata="$TEMP_DIR" \
        --username=postgres \
        --auth-local=trust \
        --auth-host=md5 \
        --encoding=UTF-8 \
        --lc-collate=C \
        --lc-ctype=C
    
    # Copy the initialized data to the NAS mount
    echo "Copying initialized data to NAS storage..."
    cp -r "$TEMP_DIR"/* /var/lib/postgresql/data/
    chown -R postgres:postgres /var/lib/postgresql/data
    
    # Clean up temporary directory
    rm -rf "$TEMP_DIR"
    
    echo "PostgreSQL initialization complete on NAS storage"
    
    # Start PostgreSQL
    echo "Starting PostgreSQL server..."
    exec su-exec postgres postgres
fi
