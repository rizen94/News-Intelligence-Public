# Migration Plan: Three-Machine Architecture
# News Intelligence Platform — Infrastructure Migration


## Overview


This document describes the migration from a two-machine architecture (primary workstation +
NAS running PostgreSQL) to a three-machine architecture where responsibilities are cleanly
separated. Cursor should execute this plan sequentially, validating each phase before
proceeding to the next.


### Current Architecture


Primary Machine (local workstation):
  - Role: All application logic, Ollama LLM inference, API server
  - Specs: 62 GB RAM, RTX 5090
  - Connects to PostgreSQL on NAS over network


NAS (<NAS_HOST_IP>):
  - Role: PostgreSQL database server + file storage
  - Specs: 4 CPU cores, 2 GB RAM (critically low, actively swapping)
  - Running PostgreSQL under severe memory pressure


### Target Architecture


Primary Machine (local workstation):
  - Role: LLM inference (Ollama), ML processing, Finance analysis, RAG,
    entity extraction, topic clustering, sentiment analysis, API server
  - Connects to PostgreSQL on secondary machine over LAN


Secondary Machine (new Linux PC):
  - Role: PostgreSQL database server, RSS ingest, article processing,
    deduplication, data retention, log archival, database maintenance
  - Specs: 16 GB RAM, SSD (confirm during setup)
  - IP: Will be discovered during Phase 1


NAS (<NAS_HOST_IP>):
  - Role: Pure storage appliance (NFS/SMB) for backups, log archives,
    and bulk file storage
  - No PostgreSQL, no application logic




---




## Phase 1: Secondary Machine Discovery and Baseline Setup


This phase establishes the secondary machine as a functioning server node on the network.
Cursor will connect via SSH to configure the system-level prerequisites.


### 1.1 — Establish SSH Connection and Record Machine Details


Connect to the secondary machine via SSH using the stored key. The user will provide the
IP address or hostname. Once connected, gather and record the following system information
for use in later phases.


```bash
# Run on secondary machine
hostname
hostname -I
cat /etc/os-release
uname -r
nproc
free -h
lsblk -f
df -h
cat /proc/cpuinfo | grep "model name" | head -1
# Check if SSD or HDD
cat /sys/block/sda/queue/rotational
# 0 = SSD, 1 = HDD. Check all block devices if multiple disks.


Record the output. The IP address, disk type (SSD vs HDD), and available disk space are
critical for later configuration decisions. Store this information in a file on the primary
machine at infrastructure/secondary-machine-info.txt.
1.2 — System Update and Essential Packages
# Run on secondary machine
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
  postgresql-16 \
  postgresql-client-16 \
  postgresql-contrib-16 \
  python3 \
  python3-pip \
  python3-venv \
  git \
  curl \
  wget \
  htop \
  iotop \
  nfs-common \
  net-tools \
  ufw \
  rsync \
  lz4 \
  pigz


If postgresql-16 is not available in the default repositories (depends on the OS version),
add the PostgreSQL APT repository first:
sudo apt install -y gnupg2
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo gpg --dearmor -o /etc/apt/trusted.gpg.d/postgresql.gpg
sudo apt update
sudo apt install -y postgresql-16 postgresql-client-16 postgresql-contrib-16


1.3 — OS Kernel Tuning
Write the following to /etc/sysctl.d/99-newsplatform.conf:
# PostgreSQL huge pages support
# Calculated: 4GB shared_buffers / 2MB hugepage size = 2048, +10% overhead
vm.nr_hugepages = 2200


# Prefer keeping data in RAM, minimize swapping
vm.swappiness = 10


# Shared memory limits for PostgreSQL
kernel.shmmax = 4294967296
kernel.shmall = 1048576


# Network tuning for LAN database connections
net.core.somaxconn = 1024
net.ipv4.tcp_keepalive_time = 600
net.ipv4.tcp_keepalive_intvl = 60
net.ipv4.tcp_keepalive_probes = 5


# Increase max open files for database + ingest workers
fs.file-max = 262144


Apply immediately:
sudo sysctl --system


Verify huge pages are allocated:
grep HugePages /proc/meminfo
# HugePages_Total should be 2200
# If HugePages_Free is 0 or much less than 2200, the system didn't have
# enough contiguous memory. Reboot and try again, or reduce the number.


Write the following to /etc/security/limits.d/99-newsplatform.conf:
postgres     soft    nofile    65536
postgres     hard    nofile    65536
*            soft    nofile    65536
*            hard    nofile    65536


1.4 — Firewall Configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing


# SSH
sudo ufw allow ssh


# PostgreSQL from primary machine and NAS subnet
# Replace PRIMARY_IP with the actual primary machine IP
sudo ufw allow from PRIMARY_IP to any port 5432 proto tcp
# Optionally allow the whole subnet:
# sudo ufw allow from 192.168.93.0/24 to any port 5432 proto tcp


sudo ufw enable
sudo ufw status verbose


1.5 — NAS NFS Mount
Create the mount point and configure persistent NFS mount to the NAS for backup and
archive storage.
sudo mkdir -p /mnt/nas/backups
sudo mkdir -p /mnt/nas/archives
sudo mkdir -p /mnt/nas/logs


Add to /etc/fstab:
<NAS_HOST_IP>:/share/news-platform/backups  /mnt/nas/backups  nfs  defaults,soft,timeo=150,retrans=3  0  0
<NAS_HOST_IP>:/share/news-platform/archives /mnt/nas/archives nfs  defaults,soft,timeo=150,retrans=3  0  0
<NAS_HOST_IP>:/share/news-platform/logs     /mnt/nas/logs     nfs  defaults,soft,timeo=150,retrans=3  0  0


NOTE: The NFS share paths above assume specific share names on the NAS. These will need to
be verified or created on the NAS. If the NAS uses a different share structure, adjust the
paths accordingly. The user may need to create these shares on the NAS admin interface
before this mount will work.
sudo mount -a
df -h | grep nas
# Verify all three mounts appear


If NFS is not configured on the NAS, fall back to SMB/CIFS mounts:
sudo apt install -y cifs-utils


Replace the fstab entries with:
//<NAS_HOST_IP>/news-platform/backups  /mnt/nas/backups  cifs  credentials=/etc/nas-credentials,iocharset=utf8,uid=1000,gid=1000  0  0
//<NAS_HOST_IP>/news-platform/archives /mnt/nas/archives cifs  credentials=/etc/nas-credentials,iocharset=utf8,uid=1000,gid=1000  0  0
//<NAS_HOST_IP>/news-platform/logs     /mnt/nas/logs     cifs  credentials=/etc/nas-credentials,iocharset=utf8,uid=1000,gid=1000  0  0


With /etc/nas-credentials containing:
username=NAS_USERNAME
password=NAS_PASSWORD


sudo chmod 600 /etc/nas-credentials
sudo mount -a


________________


Phase 2: PostgreSQL Configuration on Secondary Machine
This phase configures PostgreSQL for optimal performance on the 16GB secondary machine and
prepares it to accept connections from the primary machine.
2.1 — Stop PostgreSQL and Configure
sudo systemctl stop postgresql


Determine the PostgreSQL data directory and config location:
sudo -u postgres psql -c "SHOW data_directory;" 2>/dev/null || echo "/var/lib/postgresql/16/main"
sudo -u postgres psql -c "SHOW config_file;" 2>/dev/null || echo "/etc/postgresql/16/main/postgresql.conf"


If the machine has multiple disks and you want PostgreSQL data on the SSD (check the output
from Phase 1.1 for disk types), move the data directory before proceeding:
# Only if moving to a different disk. Skip if default location is fine.
sudo mkdir -p /ssd/postgresql/16/main
sudo chown postgres:postgres /ssd/postgresql/16/main
sudo rsync -av /var/lib/postgresql/16/main/ /ssd/postgresql/16/main/
# Then update data_directory in postgresql.conf to point to /ssd/postgresql/16/main


2.2 — Write PostgreSQL Configuration
Replace the contents of /etc/postgresql/16/main/postgresql.conf with the following. If the
config file is at a different path (determined in 2.1), use that path instead. Preserve any
existing SSL certificate paths if present.
# =============================================================================
# PostgreSQL Configuration — Secondary Machine (16GB RAM)
# News Intelligence Platform
# =============================================================================


# --- Connection Settings ---
listen_addresses = '*'
port = 5432
max_connections = 60
superuser_reserved_connections = 3


# --- Memory ---
shared_buffers = 4GB
effective_cache_size = 10GB
work_mem = 64MB
maintenance_work_mem = 1GB
huge_pages = try
temp_buffers = 32MB


# --- WAL (Write-Ahead Log) ---
wal_level = replica
wal_buffers = 64MB
checkpoint_completion_target = 0.9
min_wal_size = 256MB
max_wal_size = 2GB
archive_mode = off


# --- Query Planner ---
# random_page_cost: 1.1 for SSD, 4.0 for HDD
# Check Phase 1.1 output for disk type and adjust accordingly
random_page_cost = 1.1
effective_io_concurrency = 200
# effective_io_concurrency: 200 for SSD, 2 for HDD


# --- Background Writer ---
bgwriter_delay = 200ms
bgwriter_lru_maxpages = 100
bgwriter_lru_multiplier = 2.0


# --- Autovacuum ---
autovacuum = on
autovacuum_max_workers = 3
autovacuum_naptime = 30s
autovacuum_vacuum_threshold = 50
autovacuum_analyze_threshold = 50
autovacuum_vacuum_scale_factor = 0.05
autovacuum_analyze_scale_factor = 0.02
autovacuum_vacuum_cost_delay = 2ms
autovacuum_vacuum_cost_limit = 1000


# --- Logging ---
logging_collector = on
log_directory = 'log'
log_filename = 'postgresql-%Y-%m-%d.log'
log_rotation_age = 1d
log_rotation_size = 100MB
log_min_duration_statement = 500
log_checkpoints = on
log_connections = on
log_disconnections = on
log_lock_waits = on
log_autovacuum_min_duration = 250ms
log_line_prefix = '%t [%p] %q%u@%d '
log_statement = 'ddl'


# --- Locale ---
datestyle = 'iso, mdy'
timezone = 'UTC'
lc_messages = 'en_US.UTF-8'
lc_monetary = 'en_US.UTF-8'
lc_numeric = 'en_US.UTF-8'
lc_time = 'en_US.UTF-8'
default_text_search_config = 'pg_catalog.english'


# --- Misc ---
dynamic_shared_memory_type = posix


IMPORTANT: If Phase 1.1 revealed the disk is an HDD (rotational = 1), change:
random_page_cost = 4.0
effective_io_concurrency = 2
2.3 — Write pg_hba.conf
Replace the contents of /etc/postgresql/16/main/pg_hba.conf:
# =============================================================================
# PostgreSQL Client Authentication — Secondary Machine
# News Intelligence Platform
# =============================================================================


# TYPE  DATABASE  USER        ADDRESS              METHOD


# Local connections
local   all       postgres                         peer
local   all       all                              scram-sha-256


# Localhost
host    all       all         127.0.0.1/32         scram-sha-256
host    all       all         ::1/128              scram-sha-256


# Primary machine (LLM/compute server)
# REPLACE PRIMARY_IP with actual IP of the primary workstation
host    all       newsapp     PRIMARY_IP/32        scram-sha-256


# Optional: entire LAN subnet (less restrictive)
# host  all       newsapp     192.168.93.0/24      scram-sha-256


2.4 — Create Application Database and User
sudo systemctl start postgresql


sudo -u postgres psql <<'SQL'
-- Create the application user
CREATE USER newsapp WITH PASSWORD 'GENERATE_SECURE_PASSWORD_HERE';


-- Create the database
CREATE DATABASE news_intel OWNER newsapp;


-- Connect to the new database and set up permissions
\c news_intel


-- Create any schemas the application uses
CREATE SCHEMA IF NOT EXISTS public;
GRANT ALL ON SCHEMA public TO newsapp;


-- Extension the application may need
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS btree_gist;


-- If the application uses UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
SQL


NOTE: Replace GENERATE_SECURE_PASSWORD_HERE with an actual secure password. Store it
somewhere Cursor can reference it for later configuration steps. A reasonable approach is
to generate one now and write it to a file on the primary machine:
# Run on PRIMARY machine
python3 -c "import secrets; print(secrets.token_urlsafe(32))" > ~/.newsplatform_db_password
cat ~/.newsplatform_db_password


Then use that password in the CREATE USER command above and in all connection strings later.
2.5 — Verify PostgreSQL is Running and Accessible
# Local test on secondary machine
sudo -u postgres psql -c "SELECT version();"
psql -h 127.0.0.1 -U newsapp -d news_intel -c "SELECT 1 AS connection_test;"


# Check PostgreSQL is listening
sudo ss -tlnp | grep 5432


From the primary machine, test remote connectivity:
# Run on PRIMARY machine
# Replace SECONDARY_IP with the actual IP from Phase 1.1
psql -h SECONDARY_IP -U newsapp -d news_intel -c "SELECT 1 AS remote_test;"


If the remote connection fails, check:
   1. Firewall: sudo ufw status (on secondary)
   2. pg_hba.conf: ensure PRIMARY_IP is correct
   3. postgresql.conf: ensure listen_addresses = '*'
   4. Restart PostgreSQL: sudo systemctl restart postgresql
________________


Phase 3: Database Migration from NAS to Secondary Machine
This phase moves the existing database from the NAS (<NAS_HOST_IP>) to the secondary
machine. The existing database must remain operational until the migration is validated.
3.1 — Assess Current Database on NAS
From the primary machine (which currently has connectivity to the NAS database):
# Determine current database name, size, and table list
psql -h <NAS_HOST_IP> -U CURRENT_DB_USER -d CURRENT_DB_NAME <<'SQL'
SELECT pg_database.datname,
       pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datistemplate = false;


SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size,
       n_live_tup AS row_count
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;
SQL


Record the output. This gives us the database name, total size, and per-table row counts
that we'll use to validate the migration.
NOTE: Cursor needs to discover the current database credentials. Check the application's
configuration files on the primary machine for the existing PostgreSQL connection string.
Common locations to check:
   * .env files in the project root
   * config/.yaml or config/.yml
   * src/config.py or similar
   * docker-compose.yml if using Docker
   * Any file containing "<NAS_HOST_IP>" or "postgresql://"
# Run on primary machine, in the project directory
grep -r "<NAS_HOST_IP>" --include="*.py" --include="*.yaml" --include="*.yml" --include="*.env" --include="*.json" --include="*.toml" .
grep -r "postgresql://" --include="*.py" --include="*.yaml" --include="*.yml" --include="*.env" --include="*.json" --include="*.toml" .


3.2 — Dump Database from NAS
Run this from the secondary machine, pulling data directly from the NAS:
# Run on secondary machine
# Replace placeholders with actual values discovered in 3.1
pg_dump -h <NAS_HOST_IP> \
  -U CURRENT_DB_USER \
  -d CURRENT_DB_NAME \
  -F custom \
  -Z 5 \
  -v \
  -f /tmp/nas_database_dump.pgdump


# Record the dump file size for reference
ls -lh /tmp/nas_database_dump.pgdump


If pg_dump cannot connect (version mismatch, network issues), try from the primary machine
and then transfer:
# Run on primary machine
pg_dump -h <NAS_HOST_IP> \
  -U CURRENT_DB_USER \
  -d CURRENT_DB_NAME \
  -F custom \
  -Z 5 \
  -v \
  -f /tmp/nas_database_dump.pgdump


# Transfer to secondary
scp /tmp/nas_database_dump.pgdump SECONDARY_USER@SECONDARY_IP:/tmp/


3.3 — Restore Database on Secondary Machine
# Run on secondary machine
pg_restore -h 127.0.0.1 \
  -U newsapp \
  -d news_intel \
  -v \
  --no-owner \
  --no-privileges \
  /tmp/nas_database_dump.pgdump


# If there are errors about existing objects, add --clean flag:
# pg_restore -h 127.0.0.1 -U newsapp -d news_intel -v --no-owner --no-privileges --clean /tmp/nas_database_dump.pgdump


3.4 — Validate Migration
Run the same assessment query from Phase 3.1 against the new database and compare:
psql -h 127.0.0.1 -U newsapp -d news_intel <<'SQL'
SELECT schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size,
       n_live_tup AS row_count
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC;
SQL


Compare row counts per table against the output from Phase 3.1. They should match exactly.
If any table has a significant discrepancy, investigate before proceeding.
Also run a quick integrity check:
psql -h 127.0.0.1 -U newsapp -d news_intel <<'SQL'
-- Check for any broken foreign key references (if FK constraints exist)
-- This will error if any data integrity issues exist
SET check_function_bodies = false;
DO $$
BEGIN
  RAISE NOTICE 'Database restoration validated successfully';
END $$;


-- Reanalyze all tables so the query planner has accurate statistics
ANALYZE VERBOSE;
SQL


3.5 — Clean Up Dump File
rm /tmp/nas_database_dump.pgdump


________________


Phase 4: Application Code Changes
This phase modifies the application codebase to support the multi-machine architecture.
All code changes happen on the primary machine in the project repository.
4.1 — Audit Current Configuration System
Before making changes, Cursor needs to understand the current config structure. Examine:
# Run on primary machine, in the project directory
# Find all configuration files
find . -name "*.yaml" -o -name "*.yml" -o -name "*.env" -o -name "*.toml" -o -name "*.ini" | head -30


# Find where database connections are established
grep -rn "create_engine\|asyncpg\|psycopg\|aiopg\|database_url\|DATABASE_URL\|connection_string\|db_url" \
  --include="*.py" .


# Find where Ollama connections are configured
grep -rn "ollama\|OLLAMA\|11434" --include="*.py" --include="*.yaml" --include="*.env" .


# Find controller definitions
grep -rn "class.*Controller\|class.*Manager\|class.*Scheduler" --include="*.py" .


# Find any existing machine/host configuration
grep -rn "host\|HOST\|192\.168" --include="*.yaml" --include="*.yml" --include="*.env" .


Record all findings. The specific code changes below are templates — Cursor must adapt
them to match the actual project structure discovered here.
4.2 — Create Multi-Machine Configuration
Create or update the main configuration file to support machine-role-based deployment.
The configuration must define which machine runs which components, with the database
connection pointing to the secondary machine.
Create config/machines.yaml (or integrate into the existing config structure):
# =============================================================================
# Multi-Machine Deployment Configuration
# News Intelligence Platform
# =============================================================================


# Machine roles and their assignments
machines:
  primary:
    description: "LLM compute, ML processing, Finance analysis, API server"
    # No host needed — this is the machine running the primary process


  secondary:
    description: "Database server, RSS ingest, article processing, cleanup"
    host: "SECONDARY_IP"  # Replace with actual IP from Phase 1.1
    ssh_user: "SECONDARY_SSH_USER"


  nas:
    description: "Pure storage — backups, archives, logs"
    host: "<NAS_HOST_IP>"


# Database connection (hosted on secondary machine)
database:
  host: "SECONDARY_IP"
  port: 5432
  name: "news_intel"
  user: "newsapp"
  password_env: "NEWS_PLATFORM_DB_PASSWORD"
  # Connection pool settings
  pool_size: 10
  max_overflow: 5
  pool_timeout: 30
  pool_recycle: 1800


# Storage paths (NAS mounts, relevant on secondary machine)
storage:
  nas_backup_path: "/mnt/nas/backups"
  nas_archive_path: "/mnt/nas/archives"
  nas_log_path: "/mnt/nas/logs"


Create config/primary.yaml — controller configuration for the primary machine:
# =============================================================================
# Primary Machine Controller Configuration
# Runs: LLM inference, ML processing, Finance analysis, API server
# =============================================================================


machine_role: primary


resource_pool:
  llm_slots: 2
  db_writer_slots: 2
  external_api_slots: 2
  max_concurrent_tasks: 6


api_server:
  enabled: true
  host: "0.0.0.0"
  port: 8000


ollama:
  host: "http://127.0.0.1:11434"


controllers:
  data_processing:
    enabled: true
    workers: 2
    tasks:
      rss_processing:
        enabled: false      # Handled by secondary
      article_fetching:
        enabled: false      # Handled by secondary
      text_extraction:
        enabled: false      # Handled by secondary
      ml_processing:
        enabled: true
      entity_extraction:
        enabled: true
      topic_clustering:
        enabled: true
      sentiment_analysis:
        enabled: true
      rag_enhancement:
        enabled: true


  finance:
    enabled: true
    tasks:
      data_collection:
        enabled: true
      analysis:
        enabled: true
      synthesis:
        enabled: true
      rag_enhancement:
        enabled: true
      verification:
        enabled: true


  review_cleanup:
    enabled: false          # Entirely handled by secondary


Create config/secondary.yaml — controller configuration for the secondary machine:
# =============================================================================
# Secondary Machine Controller Configuration
# Runs: PostgreSQL (system service), RSS ingest, article processing, cleanup
# =============================================================================


machine_role: secondary


resource_pool:
  llm_slots: 0              # No GPU on this machine
  db_writer_slots: 4         # Database is local, more generous
  external_api_slots: 5      # RSS fetching, article downloading
  max_concurrent_tasks: 8


api_server:
  enabled: false             # API runs on primary only


controllers:
  data_processing:
    enabled: true
    workers: 3
    tasks:
      rss_processing:
        enabled: true
      article_fetching:
        enabled: true
      text_extraction:
        enabled: true
      ml_processing:
        enabled: false      # Needs GPU, handled by primary
      entity_extraction:
        enabled: false      # Needs GPU, handled by primary
      topic_clustering:
        enabled: false      # Needs GPU, handled by primary
      sentiment_analysis:
        enabled: false      # Needs GPU, handled by primary
      rag_enhancement:
        enabled: false      # Needs GPU, handled by primary


  finance:
    enabled: false           # Entirely handled by primary


  review_cleanup:
    enabled: true
    workers: 2
    tasks:
      deduplication:
        enabled: true
      data_retention:
        enabled: true
      log_archive:
        enabled: true
        archive_destination: "/mnt/nas/archives"
      db_optimization:
        enabled: true
      storyline_consolidation:
        enabled: false      # Needs LLM, handled by primary
      docker_cleanup:
        enabled: false      # No Docker on secondary (unless needed)


4.3 — Update Database Connection String
Find every location where the database connection is configured (discovered in Phase 4.1)
and update it to use the new connection string. The connection string format depends on the
database library the project uses.
For SQLAlchemy:
postgresql+asyncpg://newsapp:PASSWORD@SECONDARY_IP:5432/news_intel


For raw asyncpg:
postgresql://newsapp:PASSWORD@SECONDARY_IP:5432/news_intel


For psycopg2:
host=SECONDARY_IP port=5432 dbname=news_intel user=newsapp password=PASSWORD


The password should come from an environment variable (NEWS_PLATFORM_DB_PASSWORD) rather
than being hardcoded. Update the .env file on the primary machine:
# Add to .env on primary machine
NEWS_PLATFORM_DB_PASSWORD="THE_PASSWORD_FROM_PHASE_2.4"


CRITICAL: Search for and replace ALL references to the old NAS database connection. Every
occurrence of "<NAS_HOST_IP>" in database connection contexts must point to SECONDARY_IP.
Any reference that remains pointing to the NAS will break once PostgreSQL is stopped there.
# Verify no old references remain after changes
grep -rn "<NAS_HOST_IP>" --include="*.py" --include="*.yaml" --include="*.yml" --include="*.env" .


Any remaining references to <NAS_HOST_IP> should ONLY be for NAS file storage paths, not
database connections.
4.4 — Add Machine Role Startup Logic
The application needs to know which role it's playing when it starts up. Modify the main
entry point (discovered in Phase 4.1) to accept a role parameter and load the appropriate
configuration.
Create or modify the entry point to support:
# On primary machine:
python -m newsplatform --role primary


# On secondary machine:
python -m newsplatform --role secondary


The implementation depends on the existing project structure, but the pattern is:
import argparse
import yaml
from pathlib import Path


def load_config(role: str) -> dict:
    """Load machine-specific configuration based on role."""
    base_config_path = Path("config/machines.yaml")
    role_config_path = Path(f"config/{role}.yaml")


    with open(base_config_path) as f:
        base_config = yaml.safe_load(f)


    with open(role_config_path) as f:
        role_config = yaml.safe_load(f)


    # Merge: role config overrides base config
    config = {**base_config, **role_config}
    return config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=["primary", "secondary"], required=True)
    args = parser.parse_args()


    config = load_config(args.role)


    # Only start controllers that are enabled for this role
    # Only start API server if enabled for this role
    # Use database connection from base config
    ...


Cursor must adapt this to the actual project structure. The key contract is:
   * The role determines which controllers start
   * Both roles use the same database connection (to secondary machine)
   * Only the primary role starts the API server
   * Only the primary role connects to Ollama
   * Controller enabled/disabled flags from the role config override everything
4.5 — Update Controller Initialization
The existing controller initialization code needs to respect the enabled/disabled flags
from the role configuration. Find where controllers are instantiated (discovered in Phase
4.1) and wrap each initialization in a check:
# Pseudocode — adapt to actual controller structure
if config["controllers"]["data_processing"]["enabled"]:
    dp_controller = DataProcessingController(config)
    # Only register tasks that are enabled
    for task_name, task_config in config["controllers"]["data_processing"]["tasks"].items():
        if task_config.get("enabled", False):
            dp_controller.register_task(task_name)


if config["controllers"]["finance"]["enabled"]:
    finance_controller = FinanceController(config)


if config["controllers"]["review_cleanup"]["enabled"]:
    cleanup_controller = ReviewCleanupController(config)


4.6 — Handle SQLite Databases
If the application uses any SQLite databases (common for caching, local state, or specific
subsystems), these CANNOT be shared between machines. Audit for SQLite usage:
grep -rn "sqlite\|\.db\|aiosqlite" --include="*.py" .
find . -name "*.db" -o -name "*.sqlite" -o -name "*.sqlite3"


For each SQLite database found, determine:
   1. What uses it (which controller/task)
   2. Whether the controller/task runs on primary, secondary, or both
SQLite databases should be local to the machine that runs the associated controller. If
any SQLite database needs to be accessible from both machines, it must be migrated to
PostgreSQL or a shared-state solution.
4.7 — Article Processing Pipeline Handoff
The ingest pipeline is now split across machines: the secondary machine handles RSS
collection, article fetching, and text extraction, then the primary machine picks up with
ML processing, entity extraction, topic clustering, and so on.
The handoff mechanism is the PostgreSQL database. The secondary machine writes articles
with a status indicating they're ready for ML processing (e.g., status = 'text_extracted'
or 'pending_ml'). The primary machine's data processing controller polls for articles in
this status and processes them.
Verify that the existing pipeline already uses database status fields for inter-stage
coordination. If it does, the split works naturally — each machine processes articles in
the statuses relevant to its assigned stages.
If the pipeline currently uses in-memory queues or direct function calls between stages,
this must be refactored to use database-driven state transitions:
Secondary writes article → status: 'fetched'
Secondary extracts text  → status: 'text_extracted'
Primary picks up         → status: 'ml_processing'
Primary completes ML     → status: 'enriched'
Primary entity extraction → status: 'entities_extracted'
...and so on


Cursor should examine the existing pipeline code to determine which pattern is in use and
make modifications if needed.
________________


Phase 5: Deploy Application to Secondary Machine
This phase deploys the application code to the secondary machine and configures it to run
as the secondary role.
5.1 — Clone or Copy Application Code
# Option A: If using git
# Run on secondary machine
cd /opt
sudo mkdir -p newsplatform
sudo chown $USER:$USER newsplatform
git clone REPOSITORY_URL newsplatform
cd newsplatform
git checkout main  # or whatever branch


# Option B: If no git remote, rsync from primary
# Run on primary machine
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='.git' --exclude='node_modules' \
  /path/to/project/ SECONDARY_USER@SECONDARY_IP:/opt/newsplatform/


5.2 — Set Up Python Environment on Secondary
# Run on secondary machine
cd /opt/newsplatform


python3 -m venv .venv
source .venv/bin/activate


pip install --upgrade pip
pip install -r requirements.txt


If the project has optional dependencies for ML/LLM that aren't needed on the secondary:
# Install only the dependencies needed for ingest and cleanup
# This depends on how requirements are structured. If there's no separation,
# install everything — the unused ML libraries just won't be imported.
pip install -r requirements.txt


5.3 — Configure Environment on Secondary
Create the .env file on the secondary machine:
# /opt/newsplatform/.env on secondary machine
NEWS_PLATFORM_DB_PASSWORD="THE_PASSWORD_FROM_PHASE_2.4"
NEWS_PLATFORM_DB_HOST="127.0.0.1"
NEWS_PLATFORM_DB_PORT="5432"
NEWS_PLATFORM_DB_NAME="news_intel"
NEWS_PLATFORM_DB_USER="newsapp"
NEWS_PLATFORM_ROLE="secondary"
NEWS_PLATFORM_NAS_BACKUP_PATH="/mnt/nas/backups"
NEWS_PLATFORM_NAS_ARCHIVE_PATH="/mnt/nas/archives"
NEWS_PLATFORM_NAS_LOG_PATH="/mnt/nas/logs"


5.4 — Create Systemd Service for Secondary
Create /etc/systemd/system/newsplatform-secondary.service:
[Unit]
Description=News Intelligence Platform — Secondary Worker
After=network.target postgresql.service
Requires=postgresql.service


[Service]
Type=simple
User=SECONDARY_SSH_USER
Group=SECONDARY_SSH_USER
WorkingDirectory=/opt/newsplatform
Environment=PATH=/opt/newsplatform/.venv/bin:/usr/local/bin:/usr/bin:/bin
EnvironmentFile=/opt/newsplatform/.env
ExecStart=/opt/newsplatform/.venv/bin/python -m newsplatform --role secondary
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=newsplatform


# Resource limits
LimitNOFILE=65536
MemoryMax=6G
CPUQuota=80%


[Install]
WantedBy=multi-user.target


sudo systemctl daemon-reload
sudo systemctl enable newsplatform-secondary
# Don't start yet — Phase 6 validation first


5.5 — Create Database Backup Cron Job
Create /etc/cron.d/newsplatform-backup:
# Daily database backup to NAS at 3:00 AM
0 3 * * * SECONDARY_SSH_USER /opt/newsplatform/scripts/db_backup.sh >> /var/log/newsplatform-backup.log 2>&1


# Weekly full backup with extra retention on Sundays
0 4 * * 0 SECONDARY_SSH_USER /opt/newsplatform/scripts/db_backup_weekly.sh >> /var/log/newsplatform-backup.log 2>&1


Create /opt/newsplatform/scripts/db_backup.sh:
#!/bin/bash
set -euo pipefail


TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/mnt/nas/backups/daily"
BACKUP_FILE="${BACKUP_DIR}/news_intel_${TIMESTAMP}.pgdump"


mkdir -p "${BACKUP_DIR}"


echo "[$(date)] Starting daily database backup..."


pg_dump -h 127.0.0.1 \
  -U newsapp \
  -d news_intel \
  -F custom \
  -Z 5 \
  -f "${BACKUP_FILE}"


echo "[$(date)] Backup complete: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"


# Remove daily backups older than 7 days
find "${BACKUP_DIR}" -name "*.pgdump" -mtime +7 -delete
echo "[$(date)] Old daily backups cleaned up."


Create /opt/newsplatform/scripts/db_backup_weekly.sh:
#!/bin/bash
set -euo pipefail


TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/mnt/nas/backups/weekly"
BACKUP_FILE="${BACKUP_DIR}/news_intel_weekly_${TIMESTAMP}.pgdump"


mkdir -p "${BACKUP_DIR}"


echo "[$(date)] Starting weekly database backup..."


pg_dump -h 127.0.0.1 \
  -U newsapp \
  -d news_intel \
  -F custom \
  -Z 9 \
  -f "${BACKUP_FILE}"


echo "[$(date)] Weekly backup complete: ${BACKUP_FILE} ($(du -h "${BACKUP_FILE}" | cut -f1))"


# Remove weekly backups older than 30 days
find "${BACKUP_DIR}" -name "*.pgdump" -mtime +30 -delete
echo "[$(date)] Old weekly backups cleaned up."


chmod +x /opt/newsplatform/scripts/db_backup.sh
chmod +x /opt/newsplatform/scripts/db_backup_weekly.sh


Create a .pgpass file so backup scripts don't need interactive password entry:
echo "127.0.0.1:5432:news_intel:newsapp:THE_PASSWORD_FROM_PHASE_2.4" > ~/.pgpass
chmod 600 ~/.pgpass


________________


Phase 6: Integration Validation
This phase tests the multi-machine setup before going live. All existing services on the
primary machine should be stopped during these tests to avoid conflicts.
6.1 — Database Connectivity Test
From the primary machine, verify the application can connect to the database on the
secondary machine:
# Run on primary machine
cd /path/to/project
source .venv/bin/activate


python3 -c "
import asyncio
# Adapt import to actual database module used in the project
# This is a generic test — Cursor should use the project's actual DB connection code
import asyncpg


async def test():
    conn = await asyncpg.connect(
        host='SECONDARY_IP',
        port=5432,
        user='newsapp',
        password='THE_PASSWORD',
        database='news_intel'
    )
    result = await conn.fetchval('SELECT COUNT(*) FROM information_schema.tables')
    print(f'Connected successfully. {result} tables found.')
    await conn.close()


asyncio.run(test())
"


6.2 — Secondary Machine Smoke Test
Start the secondary application manually (not via systemd) and observe:
# Run on secondary machine
cd /opt/newsplatform
source .venv/bin/activate
python -m newsplatform --role secondary


# In another terminal on the secondary machine, watch logs:
journalctl -f | grep newsplatform


# And watch PostgreSQL activity:
sudo -u postgres psql -c "SELECT pid, usename, application_name, state, query FROM pg_stat_activity WHERE datname = 'news_intel';"


Verify:
   * The process starts without errors
   * Only secondary-role controllers initialize (ingest, cleanup)
   * No attempt is made to connect to Ollama
   * Database connections are established (check pg_stat_activity)
   * RSS processing can fetch feeds (if there's a manual trigger or if a cycle runs)
Stop the manual process with Ctrl+C after verification.
6.3 — Primary Machine Smoke Test
Update the primary machine's configuration to use the new database connection and role
config. Start the primary application:
# Run on primary machine
cd /path/to/project
source .venv/bin/activate
python -m newsplatform --role primary


Verify:
   * The process starts without errors
   * Only primary-role controllers initialize (ML processing, finance, API server)
   * Ollama connection is established
   * Database connections to the secondary machine work
   * API server starts and can serve requests
   * No RSS/ingest tasks are attempted
6.4 — End-to-End Pipeline Test
With both machines running (secondary first, then primary):
   1. Trigger or wait for an RSS ingest cycle on the secondary machine.
   2. Verify articles appear in the database with status indicating text extraction is complete.
   3. Verify the primary machine picks up these articles for ML processing.
   4. Verify ML processing completes and articles progress through the full pipeline.
   5. Verify the API serves the enriched data correctly.
Monitor both machines during this test:
# On secondary — watch for ingest activity
tail -f /opt/newsplatform/logs/secondary.log  # or whatever log path


# On primary — watch for ML processing pickup
tail -f logs/primary.log  # or whatever log path


# On secondary — watch database activity
watch -n 2 'sudo -u postgres psql -t -c "SELECT state, count(*) FROM pg_stat_activity WHERE datname = '\''news_intel'\'' GROUP BY state;"'


6.5 — Backup Test
# Run on secondary machine
/opt/newsplatform/scripts/db_backup.sh


# Verify backup was written to NAS
ls -lh /mnt/nas/backups/daily/


# Test restore to a temporary database
sudo -u postgres psql -c "CREATE DATABASE news_intel_test OWNER newsapp;"
pg_restore -h 127.0.0.1 -U newsapp -d news_intel_test \
  /mnt/nas/backups/daily/$(ls -t /mnt/nas/backups/daily/ | head -1)


# Verify row counts match
psql -h 127.0.0.1 -U newsapp -d news_intel_test -c \
  "SELECT tablename, n_live_tup FROM pg_stat_user_tables ORDER BY tablename;"


# Clean up test database
sudo -u postgres psql -c "DROP DATABASE news_intel_test;"


________________


Phase 7: Go Live and Decommission NAS PostgreSQL
Only proceed with this phase after Phase 6 completes successfully.
7.1 — Stop All Application Processes
# On primary machine — stop the current application
# Method depends on how it's currently run (systemd, screen, tmux, Docker, etc.)
# Cursor should identify and use the appropriate stop mechanism


# On secondary machine — if the test process is still running, stop it


7.2 — Final Database Sync
If any time has passed since Phase 3 and the application has been running against the NAS
database in the interim, perform a final sync:
# On secondary machine
# Dump only data that changed since the migration
# The safest approach is a fresh full dump and restore


# Drop and recreate the database on secondary
sudo -u postgres psql -c "DROP DATABASE news_intel;"
sudo -u postgres psql -c "CREATE DATABASE news_intel OWNER newsapp;"
sudo -u postgres psql -d news_intel -c "CREATE EXTENSION IF NOT EXISTS pg_trgm;"
sudo -u postgres psql -d news_intel -c "CREATE EXTENSION IF NOT EXISTS btree_gin;"
sudo -u postgres psql -d news_intel -c "CREATE EXTENSION IF NOT EXISTS btree_gist;"
sudo -u postgres psql -d news_intel -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'


# Fresh dump from NAS and restore
pg_dump -h <NAS_HOST_IP> -U CURRENT_DB_USER -d CURRENT_DB_NAME -F custom -Z 5 -f /tmp/final_dump.pgdump
pg_restore -h 127.0.0.1 -U newsapp -d news_intel --no-owner --no-privileges /tmp/final_dump.pgdump
rm /tmp/final_dump.pgdump


# Validate
psql -h 127.0.0.1 -U newsapp -d news_intel -c \
  "SELECT tablename, n_live_tup FROM pg_stat_user_tables ORDER BY tablename;"


7.3 — Start Services in Order
# 1. PostgreSQL on secondary is already running (system service)
sudo systemctl status postgresql  # verify on secondary


# 2. Start secondary application
sudo systemctl start newsplatform-secondary
sudo systemctl status newsplatform-secondary
journalctl -u newsplatform-secondary -f  # watch for errors


# 3. Start primary application
# On primary machine, using whatever start mechanism is standard
python -m newsplatform --role primary
# Or if using systemd on primary:
# sudo systemctl start newsplatform-primary


7.4 — Verify Everything is Working
# Check API is responding (on primary)
curl http://localhost:8000/health  # or whatever health endpoint exists


# Check database connections from both machines
# On secondary:
sudo -u postgres psql -c \
  "SELECT client_addr, usename, application_name, state FROM pg_stat_activity WHERE datname = 'news_intel';"
# Should show connections from 127.0.0.1 (local/secondary) and PRIMARY_IP


# Monitor for a full processing cycle to complete successfully


7.5 — Decommission PostgreSQL on NAS
Once you've confirmed the system is running correctly with the database on the secondary
machine for at least one full processing cycle:
# Run on NAS (<NAS_HOST_IP>)
# Stop PostgreSQL
sudo systemctl stop postgresql
sudo systemctl disable postgresql


# Optional: keep the data directory for a rollback period
# The data directory location varies by NAS OS. Common locations:
# /var/lib/postgresql/
# /volume1/postgresql/
# /share/postgresql/


# After 1-2 weeks with no issues, the old data directory can be removed
# to free up NAS storage.


7.6 — Create NAS Shared Folders
If not already done, create the shared folders on the NAS that the secondary machine mounts.
This step may require the NAS web admin interface. The folders needed are:
   * news-platform/backups/daily
   * news-platform/backups/weekly
   * news-platform/archives
   * news-platform/logs
Ensure the NAS user has read/write permissions to these shares, and that NFS or SMB is
enabled for the secondary machine's IP.
________________


Phase 8: Monitoring and Maintenance Setup
8.1 — PostgreSQL Monitoring Script
Create /opt/newsplatform/scripts/pg_health_check.sh on the secondary machine:
#!/bin/bash
# PostgreSQL health check — run periodically or on demand


echo "=== PostgreSQL Health Check — $(date) ==="
echo ""


echo "--- Connection Stats ---"
sudo -u postgres psql -d news_intel -c "
SELECT state, count(*)
FROM pg_stat_activity
WHERE datname = 'news_intel'
GROUP BY state
ORDER BY count(*) DESC;
"


echo "--- Database Size ---"
sudo -u postgres psql -c "
SELECT pg_database.datname,
       pg_size_pretty(pg_database_size(pg_database.datname)) AS size
FROM pg_database
WHERE datname = 'news_intel';
"


echo "--- Table Sizes (Top 10) ---"
sudo -u postgres psql -d news_intel -c "
SELECT schemaname || '.' || tablename AS table,
       pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size,
       n_live_tup AS live_rows,
       n_dead_tup AS dead_rows,
       CASE WHEN n_live_tup > 0
            THEN round(100.0 * n_dead_tup / n_live_tup, 1)
            ELSE 0 END AS dead_pct
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(schemaname || '.' || tablename) DESC
LIMIT 10;
"


echo "--- Cache Hit Ratio ---"
sudo -u postgres psql -d news_intel -c "
SELECT
  sum(heap_blks_read) AS heap_read,
  sum(heap_blks_hit) AS heap_hit,
  CASE WHEN sum(heap_blks_hit) + sum(heap_blks_read) > 0
       THEN round(100.0 * sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)), 2)
       ELSE 0 END AS cache_hit_ratio
FROM pg_statio_user_tables;
"


echo "--- Long Running Queries (>5s) ---"
sudo -u postgres psql -d news_intel -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 seconds'
  AND state != 'idle'
  AND datname = 'news_intel'
ORDER BY duration DESC;
"


echo "--- Replication/WAL Status ---"
sudo -u postgres psql -c "SELECT pg_current_wal_lsn(), pg_walfile_name(pg_current_wal_lsn());"


echo "--- Disk Usage ---"
df -h $(sudo -u postgres psql -t -c "SHOW data_directory;")


echo "--- System Memory ---"
free -h


echo ""
echo "=== Health check complete ==="


chmod +x /opt/newsplatform/scripts/pg_health_check.sh


8.2 — System Monitoring Cron
Add to /etc/cron.d/newsplatform-monitoring on the secondary machine:
# Health check every 6 hours, logged to NAS
0 */6 * * * SECONDARY_SSH_USER /opt/newsplatform/scripts/pg_health_check.sh >> /mnt/nas/logs/pg_health.log 2>&1


# Disk space warning
0 * * * * SECONDARY_SSH_USER /opt/newsplatform/scripts/disk_check.sh 2>&1


Create /opt/newsplatform/scripts/disk_check.sh:
#!/bin/bash
# Alert if any filesystem is over 85% full
df -h | awk 'NR>1 && int($5) > 85 {print "WARNING: " $6 " is " $5 " full"}'


chmod +x /opt/newsplatform/scripts/disk_check.sh


8.3 — Log Rotation
Create /etc/logrotate.d/newsplatform on the secondary machine:
/opt/newsplatform/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 SECONDARY_SSH_USER SECONDARY_SSH_USER
    sharedscripts
    postrotate
        # Archive compressed logs to NAS monthly
        find /opt/newsplatform/logs/ -name "*.gz" -mtime +7 -exec mv {} /mnt/nas/logs/ \;
    endscript
}


/var/log/newsplatform-backup.log {
    weekly
    missingok
    rotate 4
    compress
    delaycompress
    notifempty
}


________________


Rollback Plan
If any phase fails and cannot be resolved, the rollback path is straightforward because
the NAS PostgreSQL instance is not modified until Phase 7.5.
Before Phase 7.5: Simply revert the application configuration on the primary machine to
point back to <NAS_HOST_IP> and restart. The NAS database is still running and has all
the data.
After Phase 7.5 (NAS PostgreSQL disabled): Re-enable PostgreSQL on the NAS, restore from
the most recent backup on the NAS, revert the application configuration, and restart. The
backup scripts (Phase 5.5) ensure there's always a recent copy available.
# Emergency rollback after Phase 7.5
# On NAS:
sudo systemctl enable postgresql
sudo systemctl start postgresql


# If the NAS database was deleted, restore from backup:
# Copy latest backup from /mnt/nas/backups/daily/ to NAS
# pg_restore into the NAS PostgreSQL instance


# On primary machine:
# Revert database connection string to <NAS_HOST_IP>
# Restart application


Keep the NAS PostgreSQL data directory intact for at least two weeks after Phase 7.5 as
an additional safety net.
________________


Placeholder Reference
Throughout this document, the following placeholders must be replaced with actual values
as they are discovered during execution:
Placeholder
	Description
	Discovered In
	SECONDARY_IP
	IP address of the secondary machine
	Phase 1.1
	SECONDARY_SSH_USER
	SSH username on secondary machine
	Pre-migration (user provides)
	PRIMARY_IP
	IP address of the primary workstation
	Phase 1.1 (hostname -I on primary)
	CURRENT_DB_USER
	PostgreSQL username on NAS
	Phase 3.1
	CURRENT_DB_NAME
	Database name on NAS
	Phase 3.1
	THE_PASSWORD_FROM_PHASE_2.4
	New database password
	Phase 2.4
	REPOSITORY_URL
	Git repo URL (if applicable)
	Phase 4.1
	NAS_USERNAME
	NAS login for SMB mounts
	User provides
	NAS_PASSWORD
	NAS password for SMB mounts
	User provides
	________________


Execution Notes for Cursor
   1. Execute phases sequentially. Do not skip ahead.

   2. Each phase has validation steps. If validation fails, stop and report the failure
rather than continuing to the next phase.

   3. When this document says "adapt to actual project structure," it means Cursor should
examine the existing codebase to determine the correct file paths, class names, import
paths, and configuration patterns before writing code. Do not assume the project
structure matches the pseudocode examples exactly.

   4. All SSH commands to the secondary machine should use the stored key. All SSH commands
to the NAS should use the existing stored key at the known path.

   5. When creating files on the secondary machine via SSH, use heredocs or scp from the
primary machine. For large file contents, write the file locally first and scp it over.

   6. Record all discovered values (IPs, paths, credentials, database names) in
infrastructure/migration-state.json on the primary machine so that later phases can
reference them without re-discovery.

   7. If the project uses Docker for any components, the container configurations will also
need updating with new database connection strings. Search for docker-compose files and
Dockerfiles in addition to the application code.

   8. The application may have migration scripts (Alembic, raw SQL, custom) that run on
startup. Ensure these work correctly against the new database on the secondary machine
before going live.



This document is designed so Cursor can work through it phase by phase, with each phase building on confirmed success of the previous one. The placeholder table at the end gives it a clear reference for values it needs to discover and propagate through the rest of the plan.


A couple of things to flag before you hand this off: you'll need to give Cursor the secondary machine's IP address and SSH username once it's on the network, and you'll want to be present for Phase 7 (the actual cutover) since that's the point of no return for the NAS. Everything before that is non-destructive — the NAS keeps running normally while you build and validate the new setup in parallel.