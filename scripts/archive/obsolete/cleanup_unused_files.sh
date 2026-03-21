#!/bin/bash
# Cleanup Script for Unused Files
# This script identifies and optionally archives unused test scripts and outdated documentation
# Run with --dry-run first to see what would be cleaned up

set -e

DRY_RUN=true
ARCHIVE_DIR="archive/cleanup_$(date +%Y%m%d_%H%M%S)"

# Parse arguments
if [[ "$1" == "--execute" ]]; then
    DRY_RUN=false
    mkdir -p "$ARCHIVE_DIR"
    echo "⚠️  EXECUTE MODE: Files will be moved to $ARCHIVE_DIR"
else
    echo "🔍 DRY RUN MODE: No files will be moved (use --execute to actually move files)"
fi

echo "=========================================="
echo "Cleanup Analysis"
echo "=========================================="
echo ""

# 1. Find test scripts
echo "📋 Test Scripts:"
echo "---"
find . -type f \( -name "*test*.py" -o -name "*test*.sh" \) \
    ! -path "*/node_modules/*" \
    ! -path "*/.git/*" \
    ! -path "*/.venv/*" \
    ! -path "*/venv/*" \
    ! -path "*/__pycache__/*" \
    ! -path "*/archive/*" \
    ! -path "*/tests/*" \
    2>/dev/null | while read file; do
    echo "  $file"
    if [[ "$DRY_RUN" == "false" ]]; then
        rel_path=$(echo "$file" | sed 's|^\./||')
        target_dir="$ARCHIVE_DIR/$(dirname "$rel_path")"
        mkdir -p "$target_dir"
        mv "$file" "$ARCHIVE_DIR/$rel_path" 2>/dev/null || true
    fi
done

echo ""

# 2. Find potentially outdated documentation
echo "📄 Potentially Outdated Documentation:"
echo "---"
find docs -name "*.md" -type f \
    ! -path "*/archive/*" \
    ! -path "*/consolidated/*" \
    2>/dev/null | grep -iE "(v3|completion|summary|backup|old|legacy)" | while read file; do
    echo "  $file"
    if [[ "$DRY_RUN" == "false" ]]; then
        rel_path=$(echo "$file" | sed 's|^\./||')
        target_dir="$ARCHIVE_DIR/$(dirname "$rel_path")"
        mkdir -p "$target_dir"
        mv "$file" "$ARCHIVE_DIR/$rel_path" 2>/dev/null || true
    fi
done

echo ""

# 3. Find temporary/backup files
echo "🗑️  Temporary/Backup Files:"
echo "---"
find . -type f \( -name "*.bak" -o -name "*.tmp" -o -name "*.swp" -o -name "*.py~" -o -name "*_backup.*" \) \
    ! -path "*/.git/*" \
    ! -path "*/node_modules/*" \
    ! -path "*/venv/*" \
    ! -path "*/archive/*" \
    2>/dev/null | while read file; do
    echo "  $file"
    if [[ "$DRY_RUN" == "false" ]]; then
        rm "$file" 2>/dev/null || true
    fi
done

echo ""

if [[ "$DRY_RUN" == "false" ]]; then
    echo "✅ Cleanup complete! Files moved to: $ARCHIVE_DIR"
    echo "📋 Review the archive and delete if everything looks good"
else
    echo "💡 Run with --execute to actually perform the cleanup"
fi

