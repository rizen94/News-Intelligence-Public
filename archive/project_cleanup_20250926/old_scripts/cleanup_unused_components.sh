#!/bin/bash

# Cleanup script for unused frontend components
# This script removes components that are not referenced in the main App.tsx

echo "🧹 Starting frontend cleanup..."

# Define the web src directory
WEB_SRC="/home/pete/Documents/projects/Projects/News Intelligence/web/src"

# Create backup directory
BACKUP_DIR="/home/pete/Documents/projects/Projects/News Intelligence/web/backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "📁 Created backup directory: $BACKUP_DIR"

# List of unused page directories to remove
UNUSED_PAGES=(
    "pages/Debug"
    "pages/AdvancedMonitoring"
    "pages/RAGEnhanced"
    "pages/Clusters"
    "pages/Entities"
    "pages/Trends"
    "pages/StoryManagement"
    "pages/StorylineAlerts"
    "pages/StorylineTracking"
    "pages/DailyBriefings"
    "pages/EnhancedArticleViewer"
    "pages/Search"
    "pages/Sources"
    "pages/ContentPrioritization"
    "pages/LivingStoryNarrator"
    "pages/StoryDossiers"
    "pages/MLProcessing"
    "pages/AutomationPipeline"
    "pages/MorningBriefing"
    "pages/Discover"
    "pages/Articles/Articles.js"
    "pages/Articles/NewsStyleArticles.js"
    "pages/Articles/UnifiedArticlesAnalysis.js"
    "pages/Intelligence/IntelligenceDashboard.js"
    "pages/Intelligence/IntelligenceInsights.js"
    "pages/RSSFeeds/RSSFeeds.js"
    "pages/Storylines/Storylines.js"
    "pages/Storylines/StorylineDashboard.js"
    "pages/Dashboard/Dashboard.js"
    "pages/Monitoring/Monitoring.js"
    "pages/Monitoring/ResourceDashboard.js"
    "pages/Health/Health.js"
    "pages/Settings/Settings.js"
)

# Backup and remove unused pages
echo "🗑️  Removing unused pages..."
for page in "${UNUSED_PAGES[@]}"; do
    if [ -d "$WEB_SRC/$page" ] || [ -f "$WEB_SRC/$page" ]; then
        echo "  📦 Backing up: $page"
        cp -r "$WEB_SRC/$page" "$BACKUP_DIR/" 2>/dev/null || true
        echo "  🗑️  Removing: $page"
        rm -rf "$WEB_SRC/$page"
    else
        echo "  ⚠️  Not found: $page"
    fi
done

# Remove unused component files
UNUSED_COMPONENTS=(
    "components/ArticleReader.js"
    "components/StorylineCreationDialog.js"
    "components/StorylineConfirmationDialog.js"
    "components/Notifications/NotificationSystem.js"
    "components/ErrorBoundary/ErrorBoundary.js"
    "contexts/NewsSystemContext.js"
    "templates/ComponentTemplate.js"
    "utils/logger.js"
    "services/apiService.ts"
)

echo "🗑️  Removing unused components..."
for component in "${UNUSED_COMPONENTS[@]}"; do
    if [ -f "$WEB_SRC/$component" ]; then
        echo "  📦 Backing up: $component"
        cp "$WEB_SRC/$component" "$BACKUP_DIR/" 2>/dev/null || true
        echo "  🗑️  Removing: $component"
        rm -f "$WEB_SRC/$component"
    else
        echo "  ⚠️  Not found: $component"
    fi
done

# Clean up empty directories
echo "🧹 Cleaning up empty directories..."
find "$WEB_SRC" -type d -empty -delete 2>/dev/null || true

# Update package.json to remove unused dependencies
echo "📦 Cleaning up package.json..."
cd "$WEB_SRC/.."

# Remove unused dependencies (commented out for safety)
# npm uninstall @types/d3 d3 date-fns recharts zustand

echo "✅ Cleanup complete!"
echo "📁 Backup created at: $BACKUP_DIR"
echo "🔍 Review the changes and test the application"
echo "💡 If everything works, you can delete the backup directory"
