#!/bin/bash
# scripts/backup_project_for_widow_migration.sh
# Creates compressed backup of News Intelligence project for migration to Widow server

set -e

# ==============================
# CONFIGURATION
# ==============================

BACKUP_DIR="/mnt/nas/Data Lake Storage/news-intelligence/migration-2026-06"
PROJECT_ROOT="/home/pete/Documents/projects/News Intelligence"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LATEST_BACKUP_NAME="project-source-$TIMESTAMP.tar.gz"

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

# ==============================
# START
# ==============================

log "==============================================="
log "  News Intelligence — Project Backup Script"
log "==============================================="
log ""
log "Source:     $PROJECT_ROOT"
log "Destination: $BACKUP_DIR"
log "Backup file: $LATEST_BACKUP_NAME"
log ""

# Check if project root exists
if [ ! -d "$PROJECT_ROOT" ]; then
    error "Project root not found: $PROJECT_ROOT"
fi

# Check if NAS mount point exists
if [ ! -d "/mnt/nas" ]; then
    error "NAS mount point not found at /mnt/nas"
    log "Please mount NAS first:"
    log "  sudo mount -t cifs //192.168.93.100/public/Data\ Lake\ Storage /mnt/nas -o user=pete"
fi

# Create backup directory
log "📁 Creating backup directory..."
mkdir -p "$BACKUP_DIR"

# Create exclusion patterns file
EXCLUDE_FILE=$(mktemp)
cat > "$EXCLUDE_FILE" << 'EOF'
*.pyc
__pycache__
node_modules
.venv
logs/*
reports/output/*
reports/manifests/*
*.pid
repomix-*.json
repomix-*.md
repomix-*.txt
EOF

log "📋 Exclusion patterns created"

# Compress project folder (preserving structure, including .git)
log "📦 Compressing project files..."
log "   This may take a few minutes..."

# Navigate to parent directory for proper path handling
cd /home/pete/Documents/projects

# Create tarball - .git is included by default (not in exclusion list)
tar --exclude-from="$EXCLUDE_FILE" \
    -czf "$BACKUP_DIR/$LATEST_BACKUP_NAME" \
    "News Intelligence"

TARBALL_SIZE=$(du -h "$BACKUP_DIR/$LATEST_BACKUP_NAME" | cut -f1)
log "   ✅ Project compressed: ${TARBALL_SIZE}"

# Backup config files separately (with secrets)
log "⚙️  Backing up configuration files..."
CONFIG_BACKUP_DIR="$BACKUP_DIR/configs-$TIMESTAMP"
mkdir -p "$CONFIG_BACKUP_DIR"

# Copy main .env
if [ -f "$PROJECT_ROOT/.env" ]; then
    cp "$PROJECT_ROOT/.env" "$CONFIG_BACKUP_DIR/"
    log "   ✅ .env copied"
fi

# Copy Widow password file
if [ -f "$PROJECT_ROOT/.db_password_widow" ]; then
    cp "$PROJECT_ROOT/.db_password_widow" "$CONFIG_BACKUP_DIR/"
    log "   ✅ .db_password_widow copied"
fi

# Copy configs/.env
if [ -f "$PROJECT_ROOT/configs/.env" ]; then
    mkdir -p "$CONFIG_BACKUP_DIR/configs"
    cp "$PROJECT_ROOT/configs/.env" "$CONFIG_BACKUP_DIR/configs/"
    log "   ✅ configs/.env copied"
fi

# Copy .gitconfig if exists
if [ -f "$PROJECT_ROOT/.gitconfig" ]; then
    cp "$PROJECT_ROOT/.gitconfig" "$CONFIG_BACKUP_DIR/"
    log "   ✅ .gitconfig copied"
fi

# Create manifest
log "📄 Creating manifest..."
cat > "$BACKUP_DIR/MANIFEST-$TIMESTAMP.txt" << EOF
Migration Backup Manifest
========================
Timestamp: $TIMESTAMP
Date Created: $(date)
Source Host: 5090 (Primary / Main Machine)
Target Host: Widow (192.168.93.101)

Project Information:
  Source Path: $PROJECT_ROOT
  Git Remote: $(cd "$PROJECT_ROOT" && git remote get-url origin 2>/dev/null || echo "Not set")
  Latest Commit: $(cd "$PROJECT_ROOT" && git log -1 --format='%H %s' 2>/dev/null || echo "Not available")

Backup Files:
  1. project-source-$TIMESTAMP.tar.gz
     - Main project codebase
     - Includes .git for version history
     - Excludes: node_modules, .venv, logs, pid files, temp diagnostics

  2. configs-$TIMESTAMP/
     - .env (main environment)
     - .db_password_widow (Widow database credentials)
     - configs/.env (config directory environment)

Exclusions (will be regenerated on restore):
  - node_modules/ (npm install)
  - .venv/ (python venv)
  - uv.lock (uv lock)
  - package-lock.json (npm install)
  - logs/* (runtime logs)
  - reports/output/* (generated reports)
  - *.pid (process ID files)
  - repomix-*.json, repomix-*.md (diagnostic files)

Verification:
EOF

# Verify tarball integrity
if tar -tzf "$BACKUP_DIR/$LATEST_BACKUP_NAME" > /dev/null 2>&1; then
    echo "✅ Tarball integrity: PASSED" >> "$BACKUP_DIR/MANIFEST-$TIMESTAMP.txt"
    log "   ✅ Tarball integrity verified"
else
    echo "❌ Tarball integrity: FAILED" >> "$BACKUP_DIR/MANIFEST-$TIMESTAMP.txt"
    error "Tarball integrity check failed!"
fi

# Count files and directories
FILE_COUNT=$(tar -tzf "$BACKUP_DIR/$LATEST_BACKUP_NAME" | wc -l)
echo "📦 Total files/directories: $FILE_COUNT" >> "$BACKUP_DIR/MANIFEST-$TIMESTAMP.txt"
log "   📦 Total files/directories: $FILE_COUNT"

# Cleanup temp file
rm -f "$EXCLUDE_FILE"

# Summary
log ""
log "==============================================="
log "  ✅ Backup Complete!"
log "==============================================="
log ""
log "📍 Backup Location: $BACKUP_DIR"
log ""
log "📋 Files Created:"
ls -lh "$BACKUP_DIR"/*"$TIMESTAMP"* 2>/dev/null | awk '{print "   " $9 " (" $5 ")"}'
log ""
log "📄 Manifest: $BACKUP_DIR/MANIFEST-$TIMESTAMP.txt"
log ""
log "📝 Next Steps:"
log "   1. Run: backup_database_for_widow_migration.sh"
log "   2. Verify both backups exist on NAS"
log "   3. Prepare Widow server for restore"
log ""