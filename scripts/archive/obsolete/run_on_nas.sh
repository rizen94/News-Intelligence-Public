#!/bin/bash
# Commands to Run on NAS - Copy and paste these on NAS
# This file contains all commands needed to set up PostgreSQL on NAS

cat << 'NAS_COMMANDS'
# ============================================================================
# PostgreSQL Setup Commands for NAS
# Run these commands directly on the NAS (via SSH, web terminal, etc.)
# ============================================================================

# Step 1: Navigate to where files are
cd /mnt/nas
# Or if files are elsewhere, navigate there

# Step 2: Start PostgreSQL Container
echo "Starting PostgreSQL container..."
docker-compose -f docker-compose-postgres-nas.yml up -d

# Step 3: Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker exec news-intelligence-postgres-nas pg_isready -U newsapp -d news_intelligence > /dev/null 2>&1; then
        echo "✅ PostgreSQL is ready"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

# Step 4: Extract migrations
echo "Extracting migrations..."
tar -xzf migrations.tar.gz -C /tmp/
mkdir -p /tmp/news_intelligence_migrations
mv /tmp/api/database/migrations/* /tmp/news_intelligence_migrations/ 2>/dev/null || true

# Step 5: Install postgresql-client in container
echo "Installing postgresql-client..."
docker exec news-intelligence-postgres-nas apk add --no-cache postgresql-client > /dev/null 2>&1

# Step 6: Create migration tracking table
echo "Creating migration tracking table..."
docker exec news-intelligence-postgres-nas psql -U newsapp -d news_intelligence <<EOF
CREATE TABLE IF NOT EXISTS schema_migrations (
    id SERIAL PRIMARY KEY,
    migration_name VARCHAR(255) NOT NULL UNIQUE,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(64)
);
EOF

# Step 7: Apply migrations
echo "Applying schema migrations..."
export PGPASSWORD=newsapp_password
for migration in $(ls /tmp/news_intelligence_migrations/*.sql 2>/dev/null | sort); do
    migration_name=$(basename $migration .sql)
    echo "  Applying: $migration_name"
    
    # Check if already applied
    if docker exec news-intelligence-postgres-nas psql -U newsapp -d news_intelligence -t -c \
        "SELECT COUNT(*) FROM schema_migrations WHERE migration_name = '$migration_name';" | grep -q "1"; then
        echo "    Already applied, skipping"
        continue
    fi
    
    # Apply migration
    if docker exec -i news-intelligence-postgres-nas psql -U newsapp -d news_intelligence < "$migration" > /dev/null 2>&1; then
        docker exec news-intelligence-postgres-nas psql -U newsapp -d news_intelligence -c \
            "INSERT INTO schema_migrations (migration_name) VALUES ('$migration_name') ON CONFLICT DO NOTHING;" > /dev/null 2>&1
        echo "    ✅ Applied"
    else
        echo "    ❌ Failed"
    fi
done

# Step 8: Verify schema
echo ""
echo "Verifying schema..."
TABLE_COUNT=$(docker exec news-intelligence-postgres-nas psql -U newsapp -d news_intelligence -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null | tr -d ' ')
echo "✅ Database has $TABLE_COUNT tables"

# Step 9: List some tables
echo ""
echo "Sample tables:"
docker exec news-intelligence-postgres-nas psql -U newsapp -d news_intelligence -c \
    "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name LIMIT 10;"

echo ""
echo "✅ PostgreSQL setup complete on NAS!"
echo "Ready for data migration from local database."

NAS_COMMANDS

