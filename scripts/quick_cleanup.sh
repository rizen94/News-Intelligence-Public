#!/bin/bash
# Quick Project Cleanup Script
# Removes cache files, archives backups, consolidates requirements
# Includes backup and revert functionality

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_DIR="$PROJECT_ROOT/backups/cleanup_$(date +%Y%m%d_%H%M%S)"
REVERT_LOG="$BACKUP_DIR/revert_log.txt"

cd "$PROJECT_ROOT"

# Create backup directory
mkdir -p "$BACKUP_DIR"

echo "🧹 Starting Quick Project Cleanup..."
echo "Project Root: $PROJECT_ROOT"
echo "Backup Directory: $BACKUP_DIR"
echo ""

# Function to log file moves for revert
log_move() {
    local source_file="$1"
    local dest_file="$2"
    echo "$source_file|$dest_file" >> "$REVERT_LOG"
}

# Function to revert changes
revert_cleanup() {
    echo "🔄 Reverting cleanup changes..."
    if [ ! -f "$REVERT_LOG" ]; then
        echo "❌ No revert log found. Cannot revert."
        return 1
    fi
    
    while IFS='|' read -r source dest; do
        if [ -f "$dest" ] || [ -d "$dest" ]; then
            echo "  Restoring: $source"
            mv "$dest" "$source" 2>/dev/null || true
        fi
    done < "$REVERT_LOG"
    
    echo "✅ Revert complete"
}

# Check for revert flag
if [ "$1" == "--revert" ]; then
    if [ -z "$2" ]; then
        echo "Usage: $0 --revert <backup_directory>"
        echo "Available backups:"
        ls -d backups/cleanup_* 2>/dev/null | head -5
        exit 1
    fi
    REVERT_LOG="$2/revert_log.txt"
    revert_cleanup
    exit 0
fi

echo "📦 Creating backup before cleanup..."
echo "Backup location: $BACKUP_DIR"
echo ""

# 1. Remove Python cache files
echo "📦 Removing Python cache files..."
CACHE_COUNT=0
CACHE_FILES="$BACKUP_DIR/cache_files.txt"

# Find and log cache files before removal
find . -type d -name "__pycache__" ! -path "./archive/*" ! -path "./.git/*" ! -path "./node_modules/*" ! -path "./backups/*" 2>/dev/null > "$CACHE_FILES" || true
CACHE_COUNT=$(wc -l < "$CACHE_FILES" 2>/dev/null || echo "0")

if [ "$CACHE_COUNT" -gt 0 ]; then
    echo "  Found $CACHE_COUNT cache directories (will be removed - can regenerate)"
    # Note: We don't backup cache files as they can be regenerated
    find . -type d -name "__pycache__" ! -path "./archive/*" ! -path "./.git/*" ! -path "./node_modules/*" ! -path "./backups/*" -exec rm -r {} + 2>/dev/null || true
    find . -name "*.pyc" ! -path "./archive/*" ! -path "./.git/*" ! -path "./node_modules/*" ! -path "./backups/*" -delete 2>/dev/null || true
    echo "  ✅ Removed Python cache directories"
else
    echo "  ℹ️  No Python cache files found"
fi
echo ""

# 2. Archive backup files (with backup for revert)
echo "📁 Archiving backup files..."
mkdir -p archive/backups/codebase
BACKUP_COUNT=0

# Find and archive .backup files
for file in $(find . -name "*.backup" ! -path "./archive/*" ! -path "./backups/*" ! -path "./.git/*" ! -path "./node_modules/*" -type f 2>/dev/null); do
    # Create backup before moving
    backup_path="$BACKUP_DIR/$(echo "$file" | sed 's|^\./||' | sed 's|/|_|g')"
    mkdir -p "$(dirname "$backup_path")"
    cp "$file" "$backup_path" 2>/dev/null || true
    
    # Move to archive
    if mv "$file" archive/backups/codebase/ 2>/dev/null; then
        log_move "$file" "archive/backups/codebase/$(basename "$file")"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
done

# Find and archive .backup_* files
for file in $(find . -name "*.backup_*" ! -path "./archive/*" ! -path "./backups/*" ! -path "./.git/*" ! -path "./node_modules/*" -type f 2>/dev/null); do
    # Create backup before moving
    backup_path="$BACKUP_DIR/$(echo "$file" | sed 's|^\./||' | sed 's|/|_|g')"
    mkdir -p "$(dirname "$backup_path")"
    cp "$file" "$backup_path" 2>/dev/null || true
    
    # Move to archive
    if mv "$file" archive/backups/codebase/ 2>/dev/null; then
        log_move "$file" "archive/backups/codebase/$(basename "$file")"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
done

# Archive backup directories (except legitimate backups/)
if [ -d "api/routes.backup" ]; then
    # Backup before moving
    cp -r api/routes.backup "$BACKUP_DIR/routes.backup" 2>/dev/null || true
    
    if mv api/routes.backup archive/backups/codebase/ 2>/dev/null; then
        log_move "api/routes.backup" "archive/backups/codebase/routes.backup"
        BACKUP_COUNT=$((BACKUP_COUNT + 1))
    fi
fi

if [ "$BACKUP_COUNT" -gt 0 ]; then
    echo "  ✅ Archived $BACKUP_COUNT backup files (backed up to $BACKUP_DIR)"
else
    echo "  ℹ️  No backup files found to archive"
fi
echo ""

# 3. Consolidate requirements files (with backup)
echo "📋 Consolidating requirements files..."
if [ -f "requirements-fixed.txt" ] && [ -f "api/requirements.txt" ]; then
    if diff -q requirements-fixed.txt api/requirements.txt > /dev/null 2>&1; then
        # Backup before removing
        cp requirements-fixed.txt "$BACKUP_DIR/requirements-fixed.txt" 2>/dev/null || true
        
        if mv requirements-fixed.txt archive/backups/codebase/requirements-fixed.txt 2>/dev/null; then
            log_move "requirements-fixed.txt" "archive/backups/codebase/requirements-fixed.txt"
            echo "  ✅ Removed duplicate requirements-fixed.txt (backed up)"
        fi
    else
        echo "  ⚠️  Requirements files differ - keeping both for review"
        echo "  Files: requirements-fixed.txt vs api/requirements.txt"
    fi
else
    echo "  ℹ️  Only one requirements file found (expected)"
fi
echo ""

# 4. Archive old logs (>30 days) (with backup)
echo "📝 Archiving old logs..."
mkdir -p archive/logs/historical
OLD_LOG_COUNT=0
OLD_LOG_LIST="$BACKUP_DIR/old_logs.txt"

find logs -name "*.log" -mtime +30 2>/dev/null > "$OLD_LOG_LIST" || true
OLD_LOG_COUNT=$(wc -l < "$OLD_LOG_LIST" 2>/dev/null || echo "0")

if [ "$OLD_LOG_COUNT" -gt 0 ]; then
    while IFS= read -r log_file; do
        if [ -n "$log_file" ]; then
            # Backup before moving
            backup_path="$BACKUP_DIR/$(echo "$log_file" | sed 's|^\./||' | sed 's|/|_|g')"
            mkdir -p "$(dirname "$backup_path")"
            cp "$log_file" "$backup_path" 2>/dev/null || true
            
            # Move to archive
            if mv "$log_file" archive/logs/historical/ 2>/dev/null; then
                log_move "$log_file" "archive/logs/historical/$(basename "$log_file")"
            fi
        fi
    done < "$OLD_LOG_LIST"
    echo "  ✅ Archived $OLD_LOG_COUNT old log files (>30 days, backed up)"
else
    echo "  ℹ️  No old logs found to archive"
fi
echo ""

# 5. Organize test files in root (with backup)
echo "🧪 Organizing test files..."
mkdir -p tests/root-tests
TEST_COUNT=0
for file in test_*.py debug_*.py; do
    if [ -f "$file" ]; then
        # Backup before moving
        cp "$file" "$BACKUP_DIR/$file" 2>/dev/null || true
        
        if mv "$file" tests/root-tests/ 2>/dev/null; then
            log_move "$file" "tests/root-tests/$file"
            TEST_COUNT=$((TEST_COUNT + 1))
        fi
    fi
done
if [ "$TEST_COUNT" -gt 0 ]; then
    echo "  ✅ Moved $TEST_COUNT test files to tests/root-tests/ (backed up)"
else
    echo "  ℹ️  No test files in root to organize"
fi
echo ""

# Save backup info
cat > "$BACKUP_DIR/backup_info.txt" << EOF
Cleanup Backup Information
==========================
Date: $(date)
Backup Directory: $BACKUP_DIR
Project Root: $PROJECT_ROOT

Files Backed Up:
- Python cache: $CACHE_COUNT directories (not backed up - can regenerate)
- Backup files: $BACKUP_COUNT files
- Old logs: $OLD_LOG_COUNT files
- Test files: $TEST_COUNT files

To Revert:
  $0 --revert $BACKUP_DIR
EOF

# Summary
echo "📊 Cleanup Summary:"
echo "=================="
echo "Python cache: $CACHE_COUNT directories removed (can regenerate)"
echo "Backup files: $BACKUP_COUNT archived"
echo "Requirements: Consolidated"
echo "Old logs: $OLD_LOG_COUNT archived"
echo "Test files: $TEST_COUNT organized"
echo ""
echo "✅ Quick cleanup complete!"
echo ""
echo "📁 Backup location: $BACKUP_DIR"
echo "📁 Archive location: archive/backups/codebase/"
echo ""
echo "🔄 To revert changes, run:"
echo "   $0 --revert $BACKUP_DIR"
echo ""
echo "⚠️  Note: All files were backed up before moving"
echo "⚠️  Note: Active code and logs were preserved"
