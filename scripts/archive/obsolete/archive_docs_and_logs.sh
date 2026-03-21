#!/bin/bash
# Archive Documentation and Logs Script
# Safely archives historical documentation and logs

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ARCHIVE_DIR="$PROJECT_ROOT/archive"

echo "📦 Starting Documentation and Log Archive Process..."
echo "Project Root: $PROJECT_ROOT"
echo "Archive Directory: $ARCHIVE_DIR"
echo ""

# Create archive directory structure
echo "📁 Creating archive directory structure..."
mkdir -p "$ARCHIVE_DIR/logs/historical"
mkdir -p "$ARCHIVE_DIR/docs/historical-reports"
mkdir -p "$ARCHIVE_DIR/docs/production-reports"
mkdir -p "$ARCHIVE_DIR/docs/analysis-reports"
mkdir -p "$ARCHIVE_DIR/docs/phase-summaries"
mkdir -p "$ARCHIVE_DIR/docs/v4-analysis"
mkdir -p "$ARCHIVE_DIR/docs/root-docs"
echo "✅ Archive structure created"
echo ""

# Archive historical logs
echo "📝 Archiving historical logs..."
cd "$PROJECT_ROOT"

# Migration logs
if ls v4_migration*.log 1> /dev/null 2>&1; then
    echo "  Moving migration logs..."
    mv v4_migration*.log "$ARCHIVE_DIR/logs/historical/" 2>/dev/null || true
    echo "  ✅ Migration logs archived"
fi

# One-time logs
if [ -f "ollama_download.log" ]; then
    mv ollama_download.log "$ARCHIVE_DIR/logs/historical/" 2>/dev/null || true
    echo "  ✅ Ollama download log archived"
fi

if [ -f "ml_processor.log" ]; then
    # Check if log is actively being used (recent modification)
    if [ $(find ml_processor.log -mtime +7 2>/dev/null | wc -l) -gt 0 ]; then
        mv ml_processor.log "$ARCHIVE_DIR/logs/historical/" 2>/dev/null || true
        echo "  ✅ ML processor log archived (not recently modified)"
    else
        echo "  ⚠️  ML processor log kept (recently modified)"
    fi
fi

# Web build logs
if [ -d "web" ]; then
    cd web
    if ls *.log 1> /dev/null 2>&1; then
        mv *.log "$ARCHIVE_DIR/logs/historical/" 2>/dev/null || true
        echo "  ✅ Web build logs archived"
    fi
    cd "$PROJECT_ROOT"
fi

echo "✅ Log archiving complete"
echo ""

# Archive production reports
echo "📊 Archiving production reports..."
if [ -d "docs/production-reports" ]; then
    cd docs/production-reports
    for file in PRODUCTION_*.md; do
        if [ -f "$file" ]; then
            mv "$file" "$ARCHIVE_DIR/docs/production-reports/" 2>/dev/null || true
            echo "  ✅ Archived: $file"
        fi
    done
    cd "$PROJECT_ROOT"
fi
echo "✅ Production reports archived"
echo ""

# Archive analysis reports
echo "📈 Archiving analysis reports..."
if [ -d "docs/analysis-reports" ]; then
    cd docs/analysis-reports
    for file in *.md; do
        if [ -f "$file" ]; then
            mv "$file" "$ARCHIVE_DIR/docs/analysis-reports/" 2>/dev/null || true
            echo "  ✅ Archived: $file"
        fi
    done
    cd "$PROJECT_ROOT"
fi
echo "✅ Analysis reports archived"
echo ""

# Archive phase summaries
echo "📋 Archiving phase summaries..."
cd docs
for file in PHASE*_IMPLEMENTATION_SUMMARY.md; do
    if [ -f "$file" ]; then
        mv "$file" "$ARCHIVE_DIR/docs/phase-summaries/" 2>/dev/null || true
        echo "  ✅ Archived: $file"
    fi
done
cd "$PROJECT_ROOT"
echo "✅ Phase summaries archived"
echo ""

# Archive V4 analysis docs
echo "🔍 Archiving V4 analysis documentation..."
cd docs
for file in V4_CROSS_REFERENCE_ANALYSIS.md V4_DOCUMENTATION_FIXES_SUMMARY.md V4_CRITICAL_GAP_ANALYSIS.md; do
    if [ -f "$file" ]; then
        mv "$file" "$ARCHIVE_DIR/docs/v4-analysis/" 2>/dev/null || true
        echo "  ✅ Archived: $file"
    fi
done
cd "$PROJECT_ROOT"
echo "✅ V4 analysis docs archived"
echo ""

# Archive root directory documentation
echo "📄 Archiving root directory documentation..."
cd "$PROJECT_ROOT"

# Archive completion/summary/report files
for pattern in "*_COMPLETE.md" "*_SUMMARY.md" "*_REPORT.md" "*_FIX_REPORT.md"; do
    for file in $pattern; do
        if [ -f "$file" ] && [ "$file" != "README.md" ]; then
            # Skip if file is in archive or other directories
            if [[ "$file" != archive/* ]] && [[ "$file" != docs/* ]] && [[ "$file" != web/* ]] && [[ "$file" != api/* ]]; then
                mv "$file" "$ARCHIVE_DIR/docs/root-docs/" 2>/dev/null || true
                echo "  ✅ Archived: $file"
            fi
        fi
    done
done

echo "✅ Root documentation archived"
echo ""

# Consolidate issue reports
echo "🔧 Consolidating issue reports..."
if [ -f "docs/ISSUES_FIXED_REPORT.md" ] && [ -f "docs/PENDING_ISSUES_REPORT.md" ]; then
    echo "  Creating consolidated issue history..."
    cat > "$ARCHIVE_DIR/docs/historical-reports/ISSUE_RESOLUTION_HISTORY.md" << 'EOF'
# Issue Resolution History

This document consolidates historical issue reports from the News Intelligence System.

## Historical Issues Fixed

EOF
    cat docs/ISSUES_FIXED_REPORT.md >> "$ARCHIVE_DIR/docs/historical-reports/ISSUE_RESOLUTION_HISTORY.md" 2>/dev/null || true
    echo "" >> "$ARCHIVE_DIR/docs/historical-reports/ISSUE_RESOLUTION_HISTORY.md"
    echo "## Historical Pending Issues" >> "$ARCHIVE_DIR/docs/historical-reports/ISSUE_RESOLUTION_HISTORY.md"
    echo "" >> "$ARCHIVE_DIR/docs/historical-reports/ISSUE_RESOLUTION_HISTORY.md"
    cat docs/PENDING_ISSUES_REPORT.md >> "$ARCHIVE_DIR/docs/historical-reports/ISSUE_RESOLUTION_HISTORY.md" 2>/dev/null || true
    
    # Archive original (keep PENDING_ISSUES_REPORT.md active if it's current)
    if [ -f "docs/ISSUES_FIXED_REPORT.md" ]; then
        mv docs/ISSUES_FIXED_REPORT.md "$ARCHIVE_DIR/docs/historical-reports/" 2>/dev/null || true
        echo "  ✅ Consolidated issue reports"
    fi
fi
echo "✅ Issue reports consolidated"
echo ""

# Summary
echo "📊 Archive Summary:"
echo "=================="
echo "Logs archived: $(find "$ARCHIVE_DIR/logs" -type f 2>/dev/null | wc -l) files"
echo "Docs archived: $(find "$ARCHIVE_DIR/docs" -type f -name "*.md" 2>/dev/null | wc -l) files"
echo ""
echo "✅ Archive process complete!"
echo ""
echo "📁 Archive location: $ARCHIVE_DIR"
echo ""
echo "⚠️  Note: Active logs in api/logs/ were NOT archived"
echo "⚠️  Note: Current documentation in docs/ was preserved"
echo ""
echo "Next steps:"
echo "1. Review archived files in: $ARCHIVE_DIR"
echo "2. Update documentation indexes if needed"
echo "3. Verify no broken references"

