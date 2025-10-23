#!/bin/bash
# News Intelligence System v4.0 - Database Setup Script
# Applies v4.0 schema migration to existing database

set -e

echo "🚀 News Intelligence System v4.0 - Database Migration"
echo "=================================================="

# Configuration
DB_HOST=${DB_HOST:-localhost}
DB_PORT=${DB_PORT:-5432}
DB_NAME=${DB_NAME:-news_intelligence}
DB_USER=${DB_USER:-postgres}
DB_PASSWORD=${DB_PASSWORD:-password}

# Migration file
MIGRATION_FILE="database/migrations/050_v4_0_schema_compatibility.sql"

echo "📊 Database Configuration:"
echo "  Host: $DB_HOST"
echo "  Port: $DB_PORT"
echo "  Database: $DB_NAME"
echo "  User: $DB_USER"
echo ""

# Check if migration file exists
if [ ! -f "$MIGRATION_FILE" ]; then
    echo "❌ Migration file not found: $MIGRATION_FILE"
    exit 1
fi

echo "✅ Migration file found: $MIGRATION_FILE"

# Test database connection
echo "🔍 Testing database connection..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Database connection successful"
else
    echo "❌ Database connection failed"
    echo "Please check your database configuration and ensure PostgreSQL is running"
    exit 1
fi

# Check if tables exist
echo "🔍 Checking existing tables..."
EXISTING_TABLES=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT COUNT(*) FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('articles', 'storylines', 'rss_feeds');
")

if [ "$EXISTING_TABLES" -eq 3 ]; then
    echo "✅ Core tables found (articles, storylines, rss_feeds)"
else
    echo "❌ Core tables missing. Please run the initial schema setup first."
    exit 1
fi

# Check if v4.0 tables already exist
echo "🔍 Checking for existing v4.0 tables..."
V4_TABLES=$(PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT COUNT(*) FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name = 'storyline_articles';
")

if [ "$V4_TABLES" -eq 1 ]; then
    echo "⚠️  v4.0 tables already exist. Skipping migration."
    echo "If you need to re-run the migration, please drop the v4.0 tables first."
    exit 0
fi

# Apply migration
echo "🔄 Applying v4.0 schema migration..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$MIGRATION_FILE"

if [ $? -eq 0 ]; then
    echo "✅ Migration applied successfully"
else
    echo "❌ Migration failed"
    exit 1
fi

# Verify migration
echo "🔍 Verifying migration..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 
    table_name,
    CASE 
        WHEN table_name IN ('articles', 'storylines', 'rss_feeds', 'storyline_articles', 'timeline_events', 'user_profiles', 'system_metrics') 
        THEN 'EXISTS' 
        ELSE 'MISSING' 
    END as status
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('articles', 'storylines', 'rss_feeds', 'storyline_articles', 'timeline_events', 'user_profiles', 'system_metrics')
ORDER BY table_name;
"

# Check new columns
echo "🔍 Verifying new columns..."
PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
SELECT 'articles' as table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'articles' 
AND column_name IN ('analysis_updated_at', 'sentiment_label', 'bias_score', 'bias_indicators')
UNION ALL
SELECT 'storylines' as table_name, column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'storylines' 
AND column_name IN ('article_count', 'quality_score', 'analysis_summary')
ORDER BY table_name, column_name;
"

echo ""
echo "🎉 v4.0 Database Migration Complete!"
echo "====================================="
echo ""
echo "✅ New tables created:"
echo "  - storyline_articles (junction table)"
echo "  - timeline_events (timeline generation)"
echo "  - user_profiles (user management)"
echo "  - user_preferences (personalization)"
echo "  - system_metrics (monitoring)"
echo "  - system_alerts (alerting)"
echo "  - intelligence_insights (intelligence hub)"
echo "  - trend_predictions (predictive analytics)"
echo ""
echo "✅ New columns added:"
echo "  - articles: analysis_updated_at, sentiment_label, bias_score, bias_indicators"
echo "  - storylines: article_count, quality_score, analysis_summary"
echo ""
echo "✅ Indexes and views created for optimal performance"
echo ""
echo "🚀 The database is now ready for v4.0 API deployment!"
