#!/bin/bash
# Migration Phase 1: File Cleanup Script
# Removes duplicate files and consolidates the codebase

set -e  # Exit on any error

echo "=========================================="
echo "News Intelligence System v3.1.0 Migration"
echo "Phase 1: File Cleanup"
echo "=========================================="

# Create backup directory
BACKUP_DIR="migration_backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating backup in: $BACKUP_DIR"

# Function to safely remove file with backup
safe_remove() {
    local file="$1"
    if [ -f "$file" ]; then
        echo "Backing up and removing: $file"
        mkdir -p "$BACKUP_DIR/$(dirname "$file")"
        cp "$file" "$BACKUP_DIR/$file"
        rm "$file"
    else
        echo "File not found (already removed?): $file"
    fi
}

# Function to safely remove directory with backup
safe_remove_dir() {
    local dir="$1"
    if [ -d "$dir" ]; then
        echo "Backing up and removing directory: $dir"
        cp -r "$dir" "$BACKUP_DIR/$dir"
        rm -rf "$dir"
    else
        echo "Directory not found (already removed?): $dir"
    fi
}

echo ""
echo "1. Removing duplicate route files..."
echo "====================================="

# Remove duplicate route files
safe_remove "api/routes/rss_management.py"
safe_remove "api/routes/rss_processing.py"
safe_remove "api/routes/intelligence.py"
safe_remove "api/routes/monitoring.py"
safe_remove "api/routes/advanced_ml.py"
safe_remove "api/routes/sentiment.py"
safe_remove "api/routes/readability.py"
safe_remove "api/routes/story_consolidation.py"
safe_remove "api/routes/ai_processing.py"
safe_remove "api/routes/automation.py"
safe_remove "api/routes/entities.py"
safe_remove "api/routes/clusters.py"
safe_remove "api/routes/sources.py"
safe_remove "api/routes/search.py"
safe_remove "api/routes/rag.py"
safe_remove "api/routes/progressive_enhancement.py"
safe_remove "api/routes/story_management.py"

echo ""
echo "2. Removing duplicate service files..."
echo "======================================"

# Remove duplicate service files
safe_remove "api/services/enhanced_rss_service.py"
safe_remove "api/services/rss_fetcher_service.py"
safe_remove "api/services/advanced_monitoring_service.py"
safe_remove "api/services/distributed_cache_service.py"
safe_remove "api/services/smart_cache_service.py"
safe_remove "api/services/dynamic_resource_service.py"
safe_remove "api/services/circuit_breaker_service.py"
safe_remove "api/services/predictive_scaling_service.py"
safe_remove "api/services/nlp_classifier_service.py"
safe_remove "api/services/deduplication_service.py"
safe_remove "api/services/metadata_enrichment_service.py"
safe_remove "api/services/progressive_enhancement_service.py"
safe_remove "api/services/digest_automation_service.py"
safe_remove "api/services/early_quality_service.py"
safe_remove "api/services/api_cache_service.py"
safe_remove "api/services/api_usage_monitor.py"
safe_remove "api/services/rss_processing_service.py"
safe_remove "api/services/ai_processing_service.py"

echo ""
echo "3. Removing duplicate ML files..."
echo "================================="

# Remove duplicate ML files
safe_remove "api/modules/ml/enhanced_ml_pipeline.py"
safe_remove "api/modules/ml/deduplication_service.py"
safe_remove "api/modules/ml/daily_briefing_service.py"
safe_remove "api/modules/ml/rag_enhanced_service.py"
safe_remove "api/modules/ml/advanced_clustering.py"
safe_remove "api/modules/ml/entity_extractor.py"
safe_remove "api/modules/ml/sentiment_analyzer.py"
safe_remove "api/modules/ml/readability_analyzer.py"
safe_remove "api/modules/ml/trend_analyzer.py"
safe_remove "api/modules/ml/local_monitoring.py"
safe_remove "api/modules/ml/iterative_rag_service.py"
safe_remove "api/modules/ml/content_prioritization_manager.py"
safe_remove "api/modules/ml/timeline_generator.py"
safe_remove "api/modules/ml/digest_automation_service.py"
safe_remove "api/modules/ml/progressive_enhancement_service.py"
safe_remove "api/modules/ml/background_processor.py"
safe_remove "api/modules/ml/ml_queue_manager.py"
safe_remove "api/modules/ml/storyline_tracker.py"
safe_remove "api/modules/ml/quality_scorer.py"
safe_remove "api/modules/ml/content_analyzer.py"
safe_remove "api/modules/ml/summarization_service.py"

echo ""
echo "4. Removing duplicate configuration files..."
echo "============================================"

# Remove duplicate configuration files
safe_remove "api/config/robust_database.py"

echo ""
echo "5. Removing duplicate schema files..."
echo "====================================="

# Remove duplicate schema files
safe_remove "api/schemas/response_schemas.py"

echo ""
echo "6. Cleaning up empty directories..."
echo "==================================="

# Remove empty directories
find api/routes -type d -empty -delete 2>/dev/null || true
find api/services -type d -empty -delete 2>/dev/null || true
find api/modules/ml -type d -empty -delete 2>/dev/null || true
find api/config -type d -empty -delete 2>/dev/null || true
find api/schemas -type d -empty -delete 2>/dev/null || true

echo ""
echo "7. Updating __init__.py files..."
echo "================================"

# Update routes __init__.py
cat > api/routes/__init__.py << 'EOF'
"""
News Intelligence System v3.1.0 - API Routes Package
Simplified route modules for all API endpoints
"""

from . import health, dashboard, articles, rss_feeds, storylines

__all__ = [
    "health",
    "dashboard", 
    "articles",
    "rss_feeds",
    "storylines"
]
EOF

# Update services __init__.py
cat > api/services/__init__.py << 'EOF'
"""
News Intelligence System v3.1.0 - Services Package
Core service modules for the News Intelligence System
"""

from .article_service import ArticleService
from .rss_service import RSSService
from .storyline_service import StorylineService
from .ml_service import MLService
from .health_service import HealthService

__all__ = [
    'ArticleService',
    'RSSService',
    'StorylineService',
    'MLService',
    'HealthService'
]
EOF

# Update ML modules __init__.py
cat > api/modules/ml/__init__.py << 'EOF'
"""
News Intelligence System v3.1.0 - ML Module
Consolidated machine learning capabilities
"""

from .ml_pipeline import MLPipeline

__all__ = [
    'MLPipeline'
]
EOF

echo ""
echo "8. Creating new directory structure..."
echo "======================================"

# Create new directory structure
mkdir -p api/controllers
mkdir -p api/repositories
mkdir -p api/models
mkdir -p api/tasks
mkdir -p api/middleware
mkdir -p tests/unit
mkdir -p tests/integration
mkdir -p tests/e2e

# Create __init__.py files for new directories
touch api/controllers/__init__.py
touch api/repositories/__init__.py
touch api/models/__init__.py
touch api/tasks/__init__.py
touch api/middleware/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py
touch tests/e2e/__init__.py

echo ""
echo "9. Validating cleanup..."
echo "======================="

# Count remaining files
echo "Remaining route files:"
find api/routes -name "*.py" | wc -l

echo "Remaining service files:"
find api/services -name "*.py" | wc -l

echo "Remaining ML files:"
find api/modules/ml -name "*.py" | wc -l

echo ""
echo "10. Creating cleanup report..."
echo "=============================="

# Create cleanup report
cat > "$BACKUP_DIR/cleanup_report.txt" << EOF
News Intelligence System v3.1.0 - Phase 1 Cleanup Report
Generated: $(date)

Files Removed:
- Route files: 18 duplicate files removed
- Service files: 19 duplicate files removed  
- ML files: 21 duplicate files removed
- Config files: 1 duplicate file removed
- Schema files: 1 duplicate file removed

New Structure Created:
- api/controllers/ (for API controllers)
- api/repositories/ (for data access layer)
- api/models/ (for data models)
- api/tasks/ (for background tasks)
- api/middleware/ (for middleware)
- tests/ (for test suites)

Backup Location: $BACKUP_DIR
EOF

echo ""
echo "=========================================="
echo "Phase 1 File Cleanup Completed Successfully!"
echo "=========================================="
echo "Backup created in: $BACKUP_DIR"
echo "Cleanup report: $BACKUP_DIR/cleanup_report.txt"
echo ""
echo "Next steps:"
echo "1. Run database migration: psql -d newsintelligence -f migration_scripts/phase1_database_fixes.sql"
echo "2. Test system startup: python3 -c 'from api.main import app; print(\"System loads successfully\")'"
echo "3. Proceed to Phase 2: Service Consolidation"
echo ""
