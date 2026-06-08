#!/bin/bash
# scripts/restore_news_intelligence_on_widow.sh
# Restores News Intelligence from backup to Widow server

set -e

# ==============================
# CONFIGURATION
# ==============================

# Backup location (NAS)
BACKUP_NAS_PATH="/mnt/nas/Data Lake Storage/news-intelligence/migration-2026-06"

# Target installation paths on Widow
TARGET_PROJECT_ROOT="/home/pete/Documents/projects/News Intelligence"
TARGET_DB_HOST="localhost"
TARGET_DB_PORT="5432"
TARGET_DB_NAME="news_intel"
TARGET_DB_USER="newsintel_user"

# Main/5090 server (for Ollama GPU calls)
MAIN_SERVER_HOST="192.168.93.100"  # Update with actual IP

# ==============================
# FUNCTIONS
# ==============================

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

error() {
    log "❌ ERROR: $*"
    exit 1
}

confirm() {
    read -p "$* (y/N): " reply
    if [ "$reply" != "y" ] && [ "$reply" != "Y" ]; then
        log "Cancelled by user."
        exit 0
    fi
}

# ==============================
# START
# ==============================

log "============================================="
log "  News Intelligence — Restore to Widow"
log "============================================="
log ""
log "This script will:"
log "   1. Extract project files to: $TARGET_PROJECT_ROOT"
log "   2. Restore database to: $TARGET_DB_HOST:$TARGET_DB_PORT"
log "   3. Update environment configuration for Widow"
log "   4. Install dependencies (Python + Node)"
log "   5. Pull required Ollama models"
log "   6. Configure systemd service"
log ""
log "⚠️  WARNING: This will overwrite any existing installation!"
log ""

# Check NAS mount
if [ ! -d "/mnt/nas" ]; then
    log "Checking if NAS needs to be mounted..."
    if ! mountpoint -q /mnt/nas; then
        log "Mounting NAS..."
        sudo mount -t cifs //192.168.93.100/public/Data\ Lake\ Storage /mnt/nas -o user=pete
        if [ $? -ne 0 ]; then
            error "Failed to mount NAS. Please mount manually:"
            log "  sudo mount -t cifs //192.168.93.100/public/Data\ Lake\ Storage /mnt/nas -o user=pete"
        fi
    fi
fi

# Find latest backup
log "📁 Finding latest backup..."
PROJECT_BACKUP=$(ls -t "$BACKUP_NAS_PATH"/project-source-*.tar.gz 2>/dev/null | head -1)
DB_BACKUP=$(ls -t "$BACKUP_NAS_PATH"/db-backups/news-intel-database-*.sql.gz 2>/dev/null | head -1)

if [ -z "$PROJECT_BACKUP" ]; then
    error "No project backup found in $BACKUP_NAS_PATH"
fi

if [ -z "$DB_BACKUP" ]; then
    error "No database backup found in $BACKUP_NAS_PATH/db-backups"
fi

log "   Project backup: $PROJECT_BACKUP"
log "   Database backup: $DB_BACKUP"
log ""

confirm "Proceed with restore?"

# ==============================
# PHASE 1: Extract Project Files
# ==============================

log ""
log "============================================="
log "  PHASE 1: Extracting Project Files"
log "============================================="
log ""

# Backup existing installation if any
if [ -d "$TARGET_PROJECT_ROOT" ]; then
    log "⚠️  Existing installation found!"
    CONFIRM_BACKUP=$(echo -n "Create backup of existing? (y/N): " && read reply && [ "$reply" = "y" ] || [ "$reply" = "Y" ])
    if [ "$CONFIRM_BACKUP" = true ]; then
        BACKUP_EXISTING="$TARGET_PROJECT_ROOT.backup-$(date +%Y%m%d-%H%M%S)"
        log "   Moving existing to: $BACKUP_EXISTING"
        mv "$TARGET_PROJECT_ROOT" "$BACKUP_EXISTING"
    else
        log "   Removing existing installation..."
        rm -rf "$TARGET_PROJECT_ROOT"
    fi
fi

# Create target directory
mkdir -p "$TARGET_PROJECT_ROOT"

# Extract project
log "📦 Extracting project files..."
tar -xzf "$PROJECT_BACKUP" -C /home/pete/Documents/projects/
log "   ✅ Project extracted"

# ==============================
# PHASE 2: Restore Database
# ==============================

log ""
log "============================================="
log "  PHASE 2: Restoring Database"
log "============================================="
log ""

log "📊 Checking PostgreSQL..."
if ! pg_isready -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT"; then
    error "PostgreSQL is not running on $TARGET_DB_HOST:$TARGET_DB_PORT"
    log "Please start PostgreSQL first:"
    log "  sudo systemctl start postgresql"
fi

log "✅ PostgreSQL is ready"

# Check if database exists
DB_EXISTS=$(psql -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -t -c \
    "SELECT 1 WHERE pg_database_exists('$TARGET_DB_NAME');" 2>/dev/null | tr -d ' ')

if [ "$DB_EXISTS" = "1" ]; then
    log "⚠️  Database '$TARGET_DB_NAME' already exists!"
    confirm "Drop and recreate database? (This will delete all existing data!)"
    log "   Dropping existing database..."
    dropdb -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" "$TARGET_DB_NAME"
fi

log "📄 Creating fresh database..."
createdb -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" "$TARGET_DB_NAME"
log "   ✅ Database created"

log "📥 Restoring database from backup..."
log "   This may take several minutes..."
gunzip -c "$DB_BACKUP" | psql -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" -d "$TARGET_DB_NAME" --verbose
log "   ✅ Database restored"

# Verify restoration
TABLE_COUNT=$(psql -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" -d "$TARGET_DB_NAME" -t -c \
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema NOT LIKE 'pg_%';" 2>/dev/null | tr -d ' ')
log "   📊 Tables restored: $TABLE_COUNT"

# ==============================
# PHASE 3: Configure Environment
# ==============================

log ""
log "============================================="
log "  PHASE 3: Configuring Environment"
log "============================================="
log ""

log "⚙️  Updating environment variables for Widow..."

# Create/update main .env
cat > "$TARGET_PROJECT_ROOT/.env" << EOF
# News Intelligence — Widow Server Configuration
# Generated: $(date)

# ============= Server Identity =============
SERVER_ROLE="widow"
SERVER_HOSTNAME="widow"

# ============= Database Configuration =============
DB_HOST="localhost"
DB_PORT="5432"
DB_NAME="news_intel"
DB_USER="newsintel_user"
DB_POOL_WORKER_MIN="2"
DB_POOL_WORKER_MAX="20"
DB_POOL_UI_MIN="5"
DB_POOL_UI_MAX="30"
DB_POOL_HEALTH_MIN="1"
DB_POOL_HEALTH_MAX="5"

# ============= Ollama Configuration =============
# Widow runs its own Ollama (8B, 7B models)
# But calls main server for 70B narrative finisher
OLLAMA_HOST="http://localhost:11434"
OLLAMA_MODEL_PRIMARY="llama3.1:8b"
OLLAMA_MODEL_SECONDARY="mistral-nemo"

# Dual-host routing for 70B finisher
OLLAMA_DUAL_HOST_ROUTING_ENABLED="true"
OLLAMA_CPU_HOST="http://localhost:11434"       # Widow local
OLLAMA_GPU_HOST="http://$MAIN_SERVER_HOST:11434"  # Main server (5090)
OLLAMA_CPU_CONCURRENCY="4"
OLLAMA_GPU_CONCURRENCY="8"

# ============= Server Configuration =============
UVICORN_HOST="0.0.0.0"
UVICORN_PORT="8000"
UVICORN_WORKERS="4"

# ============= Feature Flags =============
AUTOMATION_ENABLED="true"
STRICT_ARTICLE_ENRICHMENT_GATES_SINCE=""

# ============= Logging =============
LOG_LEVEL="INFO"
EOF

log "   ✅ Main .env configured"

# Create Widow password file
cat > "$TARGET_PROJECT_ROOT/.db_password_widow" << EOF
$TARGET_DB_USER:$NEWS_INTEL_DB_PASSWORD
EOF
chmod 600 "$TARGET_PROJECT_ROOT/.db_password_widow"
log "   ✅ Database password file created"

# ==============================
# PHASE 4: Install Dependencies
# ==============================

log ""
log "============================================="
log "  PHASE 4: Installing Dependencies"
log "============================================="
log ""

cd "$TARGET_PROJECT_ROOT"

# Python dependencies
log "🐍 Installing Python dependencies..."
uv sync
log "   ✅ Python dependencies installed"

# Node dependencies (if needed)
if [ -f "package.json" ]; then
    log "📦 Installing Node.js dependencies..."
    npm install
    log "   ✅ Node.js dependencies installed"
fi

# ==============================
# PHASE 5: Pull Ollama Models
# ==============================

log ""
log "============================================="
log "  PHASE 5: Pulling Ollama Models"
log "============================================="
log ""

log "📥 Checking Ollama connection..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    log "⚠️  Ollama is not running locally"
    log "   Please install and start Ollama first:"
    log "   curl -fsSL https://ollama.com/install.sh | sh"
    log "   ollama serve"
    log ""
    log "   Skipping model pull. Run manually after Ollama is installed."
else
    log "✅ Ollama is running"
    log ""
    log "📥 Pulling models for Widow (this may take a while)..."
    
    log "   Pulling llama3.1:8b (primary, ~5GB)..."
    ollama pull llama3.1:8b
    
    log "   Pulling qwen2.5:7b (extraction, ~4GB)..."
    ollama pull qwen2.5:7b
    
    log "   Pulling phi3.5 (fast/simple, ~2GB)..."
    ollama pull phi3.5
    
    log "   Pulling mistral-nemo (secondary, ~8GB)..."
    ollama pull mistral-nemo
    
    log "   ✅ All models pulled"
fi

# ==============================
# PHASE 6: Systemd Service
# ==============================

log ""
log "============================================="
log "  PHASE 6: Configuring Systemd Service"
log "============================================="
log ""

log "📝 Creating systemd service file..."
cat > /tmp/news-intelligence-widow.service << EOF
[Unit]
Description=News Intelligence API (Widow Server)
After=network.target postgresql.service

[Service]
Type=simple
User=pete
Group=pete
WorkingDirectory=$TARGET_PROJECT_ROOT
Environment="PATH=$TARGET_PROJECT_ROOT/.venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$TARGET_PROJECT_ROOT/.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=news-intelligence-widow

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo cp /tmp/news-intelligence-widow.service /etc/systemd/system/
sudo systemctl daemon-reload
log "   ✅ Service file installed"

# ==============================
# SUMMARY
# ==============================

log ""
log "============================================="
log "  ✅ Restore Complete!"
log "============================================="
log ""
log "📍 Installation Path: $TARGET_PROJECT_ROOT"
log ""
log "📝 Configuration Summary:"
log "   Database:     localhost:5432/$TARGET_DB_NAME"
log "   Ollama Local: localhost:11434 (8B, 7B models)"
log "   Ollama Main:  $MAIN_SERVER_HOST:11434 (70B finisher)"
log "   API Port:     8000"
log ""
log "🚀 To Start the System:"
log "   Option 1 — Systemd (recommended):"
log "     sudo systemctl enable news-intelligence-widow"
log "     sudo systemctl start news-intelligence-widow"
log ""
log "   Option 2 — Manual:"
log "     cd $TARGET_PROJECT_ROOT"
log "     source .venv/bin/activate"
log "     uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4"
log ""
log "📊 To Verify:"
log "     curl http://localhost:8000/api/system_monitoring/health"
log ""
log "⚙️  To Check Logs (systemd):"
log "     sudo journalctl -u news-intelligence-widow -f"
log ""
log "🔗 Next Steps:"
log "   1. Update DNS or /etc/hosts to point to Widow"
log "   2. Configure reverse proxy (Caddy/Nginx) if needed"
log "   3. Test all endpoints"
log ""