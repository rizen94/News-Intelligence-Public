#!/bin/bash
# Phase 2: PostgreSQL configuration on Widow (secondary machine)
# Run from PRIMARY. Requires: postgresql-16 installed on Widow, passwordless sudo, passwordless SSH.
# After apt install completes on Widow, run: ./scripts/migration_phase2_widow.sh

set -e
WIDOW="${1:-widow}"

echo "Phase 2: Configuring PostgreSQL on $WIDOW..."
echo ""

# Get primary machine IP for pg_hba
PRIMARY_IP="${PRIMARY_IP:-$(hostname -I 2>/dev/null | awk '{print $1}')}"
echo "Primary IP (for pg_hba): $PRIMARY_IP"

# 2.1 — Sysctl tuning (HDD, 15GB RAM — reduced hugepages from migration plan)
ssh "$WIDOW" "sudo tee /etc/sysctl.d/99-newsplatform.conf << 'SYSCTL'
# PostgreSQL (15GB RAM, HDD)
vm.swappiness = 10
kernel.shmmax = 4294967296
kernel.shmall = 1048576
net.core.somaxconn = 1024
net.ipv4.tcp_keepalive_time = 600
fs.file-max = 262144
SYSCTL"
ssh "$WIDOW" "sudo sysctl --system" 2>/dev/null || true

# Limits
ssh "$WIDOW" "sudo tee /etc/security/limits.d/99-newsplatform.conf << 'LIMITS'
postgres     soft    nofile    65536
postgres     hard    nofile    65536
*            soft    nofile    65536
*            hard    nofile    65536
LIMITS"

# 2.2 — PostgreSQL config (HDD: random_page_cost=4.0, effective_io_concurrency=2)
PG_CONF="/etc/postgresql/16/main/postgresql.conf"
ssh "$WIDOW" "sudo systemctl stop postgresql" 2>/dev/null || true

ssh "$WIDOW" "sudo tee $PG_CONF << 'PGCONF'
data_directory = '/var/lib/postgresql/16/main'
listen_addresses = '*'
port = 5432
max_connections = 60
shared_buffers = 4GB
effective_cache_size = 10GB
work_mem = 64MB
maintenance_work_mem = 1GB
wal_buffers = 64MB
checkpoint_completion_target = 0.9
min_wal_size = 256MB
max_wal_size = 2GB
random_page_cost = 4.0
effective_io_concurrency = 2
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d.log'
datestyle = 'iso, mdy'
timezone = 'UTC'
dynamic_shared_memory_type = posix
PGCONF"

# 2.3 — pg_hba.conf (PRIMARY_IP inserted for remote access)
PG_HBA="/etc/postgresql/16/main/pg_hba.conf"
ssh "$WIDOW" "sudo tee $PG_HBA << PGHBA
local   all       postgres                         peer
local   all       all                              scram-sha-256
host    all       all         127.0.0.1/32         scram-sha-256
host    all       all         ::1/128               scram-sha-256
host    all       newsapp     ${PRIMARY_IP}/32      scram-sha-256
PGHBA"

# 2.4 — Create DB and user (generate password)
DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))" 2>/dev/null || openssl rand -base64 24)
echo ""
echo "Generated DB password. Save it: NEWS_PLATFORM_DB_PASSWORD=$DB_PASS"
echo "$DB_PASS" > "$(dirname "$0")/../.db_password_widow" 2>/dev/null && chmod 600 "$(dirname "$0")/../.db_password_widow" 2>/dev/null || true

ssh "$WIDOW" "sudo systemctl start postgresql"
ssh "$WIDOW" "sudo -u postgres psql -c \"
CREATE USER newsapp WITH PASSWORD '$DB_PASS';
CREATE DATABASE news_intel OWNER newsapp;
\\c news_intel
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS \\\"uuid-ossp\\\";
\""

# Verify
echo ""
echo "Verifying..."
ssh "$WIDOW" "PGPASSWORD='$DB_PASS' psql -h 127.0.0.1 -U newsapp -d news_intel -c 'SELECT 1 AS ok;'"
echo ""
echo "✅ Phase 2 complete. PostgreSQL ready on Widow."
echo "   Connection: host=192.168.93.101 port=5432 dbname=news_intel user=newsapp"
echo "   Password stored in .db_password_widow (add to .env as NEWS_PLATFORM_DB_PASSWORD)"
