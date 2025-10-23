#!/bin/bash

# News Intelligence System v4.0 - Complete Database Setup Script
# Applies comprehensive schema overhaul with consistent naming, pipeline processing, and topic clustering
# Created: October 22, 2025

set -e  # Exit on any error

# ============================================================================
# CONFIGURATION
# ============================================================================

DB_HOST="${DB_HOST:-localhost}"
DB_NAME="${DB_NAME:-news_intelligence}"
DB_USER="${DB_USER:-newsapp}"
DB_PASSWORD="${DB_PASSWORD:-newsapp_password}"
DB_PORT="${DB_PORT:-5432}"

MIGRATION_FILE="./database/migrations/100_v4_0_complete_schema_overhaul.sql"
BACKUP_DIR="./database/backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# FUNCTIONS
# ============================================================================

log_info() {
    echo -e "${BLUE}INFO:${NC} $1"
}

log_success() {
    echo -e "${GREEN}SUCCESS:${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

log_error() {
    echo -e "${RED}ERROR:${NC} $1" >&2
}

check_dependencies() {
    log_info "Checking dependencies..."
    
    if ! command -v psql &> /dev/null; then
        log_error "psql command not found. Please install PostgreSQL client tools."
        exit 1
    fi
    
    if ! command -v pg_dump &> /dev/null; then
        log_error "pg_dump command not found. Please install PostgreSQL client tools."
        exit 1
    fi
    
    log_success "Dependencies check passed"
}

check_database_connection() {
    log_info "Testing database connection to $DB_HOST:$DB_PORT/$DB_NAME as user $DB_USER..."
    
    if PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "\q" &> /dev/null; then
        log_success "Database connection successful"
    else
        log_error "Failed to connect to database. Please check your connection parameters."
        log_error "Host: $DB_HOST, Port: $DB_PORT, Database: $DB_NAME, User: $DB_USER"
        exit 1
    fi
}

create_backup() {
    log_info "Creating database backup before migration..."
    
    mkdir -p "$BACKUP_DIR"
    BACKUP_FILE="$BACKUP_DIR/news_intelligence_backup_$TIMESTAMP.sql"
    
    if PGPASSWORD=$DB_PASSWORD pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" > "$BACKUP_FILE"; then
        log_success "Database backup created: $BACKUP_FILE"
    else
        log_error "Failed to create database backup"
        exit 1
    fi
}

apply_migration() {
    log_info "Applying v4.0 complete schema overhaul migration..."
    
    if [ ! -f "$MIGRATION_FILE" ]; then
        log_error "Migration file not found: $MIGRATION_FILE"
        exit 1
    fi
    
    if PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$MIGRATION_FILE"; then
        log_success "Migration applied successfully"
    else
        log_error "Migration failed"
        exit 1
    fi
}

verify_schema() {
    log_info "Verifying schema changes..."
    
    # Check core tables
    local tables_to_check=(
        "rss_feeds"
        "articles" 
        "storylines"
        "processing_stages"
        "article_processing_log"
        "storyline_processing_log"
        "topic_clusters"
        "article_topic_clusters"
        "topic_keywords"
        "storyline_articles"
        "system_metrics"
        "system_alerts"
        "user_profiles"
        "intelligence_reports"
    )
    
    local missing_tables=0
    
    for table in "${tables_to_check[@]}"; do
        if PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT EXISTS (SELECT FROM pg_tables WHERE schemaname = 'public' AND tablename = '$table');" | grep -q "t"; then
            log_success "Table '$table' exists"
        else
            log_error "Table '$table' not found"
            missing_tables=$((missing_tables + 1))
        fi
    done
    
    if [ $missing_tables -eq 0 ]; then
        log_success "All required tables verified"
    else
        log_error "Schema verification failed: $missing_tables tables missing"
        exit 1
    fi
}

verify_indexes() {
    log_info "Verifying critical indexes..."
    
    local indexes_to_check=(
        "idx_articles_processing_status"
        "idx_articles_processing_stage"
        "idx_topic_clusters_type"
        "idx_article_topic_clusters_article_id"
        "idx_storyline_articles_storyline_id"
        "idx_system_metrics_name"
        "idx_system_alerts_severity"
    )
    
    local missing_indexes=0
    
    for index in "${indexes_to_check[@]}"; do
        if PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT EXISTS (SELECT FROM pg_indexes WHERE indexname = '$index');" | grep -q "t"; then
            log_success "Index '$index' exists"
        else
            log_error "Index '$index' not found"
            missing_indexes=$((missing_indexes + 1))
        fi
    done
    
    if [ $missing_indexes -eq 0 ]; then
        log_success "All critical indexes verified"
    else
        log_warning "Some indexes missing: $missing_indexes"
    fi
}

verify_processing_stages() {
    log_info "Verifying processing stages data..."
    
    local stage_count=$(PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM processing_stages;" | tr -d ' ')
    
    if [ "$stage_count" -ge 8 ]; then
        log_success "Processing stages verified: $stage_count stages found"
    else
        log_error "Processing stages verification failed: Expected 8+, got $stage_count"
        exit 1
    fi
}

verify_jsonb_columns() {
    log_info "Verifying JSONB column consistency..."
    
    # Check that all JSON columns are now JSONB
    local jsonb_columns=$(PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
        SELECT COUNT(*) 
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND data_type = 'jsonb'
        AND table_name IN ('articles', 'storylines', 'topic_clusters', 'system_metrics', 'system_alerts');
    " | tr -d ' ')
    
    if [ "$jsonb_columns" -ge 20 ]; then
        log_success "JSONB columns verified: $jsonb_columns JSONB columns found"
    else
        log_warning "JSONB verification: Found $jsonb_columns JSONB columns (expected 20+)"
    fi
}

test_pipeline_functionality() {
    log_info "Testing pipeline functionality..."
    
    # Test inserting a processing stage
    if PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
        INSERT INTO processing_stages (stage_name, stage_description, stage_order) 
        VALUES ('test_stage', 'Test processing stage', 999) 
        ON CONFLICT (stage_name) DO NOTHING;
    " &> /dev/null; then
        log_success "Processing stages functionality verified"
    else
        log_error "Processing stages functionality test failed"
        exit 1
    fi
    
    # Test topic cluster functionality
    if PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
        INSERT INTO topic_clusters (cluster_name, cluster_description, cluster_type) 
        VALUES ('test_cluster', 'Test topic cluster', 'semantic') 
        ON CONFLICT DO NOTHING;
    " &> /dev/null; then
        log_success "Topic clustering functionality verified"
    else
        log_error "Topic clustering functionality test failed"
        exit 1
    fi
}

generate_schema_report() {
    log_info "Generating schema report..."
    
    local report_file="./database/schema_report_$TIMESTAMP.txt"
    
    {
        echo "News Intelligence System v4.0 - Database Schema Report"
        echo "Generated: $(date)"
        echo "=================================================="
        echo ""
        
        echo "Database Connection:"
        echo "  Host: $DB_HOST"
        echo "  Port: $DB_PORT"
        echo "  Database: $DB_NAME"
        echo "  User: $DB_USER"
        echo ""
        
        echo "Table Counts:"
        PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
            SELECT 
                schemaname,
                COUNT(*) as table_count
            FROM pg_tables 
            WHERE schemaname = 'public'
            GROUP BY schemaname;
        "
        
        echo ""
        echo "Index Counts:"
        PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
            SELECT 
                schemaname,
                COUNT(*) as index_count
            FROM pg_indexes 
            WHERE schemaname = 'public'
            GROUP BY schemaname;
        "
        
        echo ""
        echo "JSONB Columns:"
        PGPASSWORD=$DB_PASSWORD psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
            SELECT 
                table_name,
                column_name,
                data_type
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND data_type = 'jsonb'
            ORDER BY table_name, column_name;
        "
        
    } > "$report_file"
    
    log_success "Schema report generated: $report_file"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    echo "=================================================="
    echo "News Intelligence System v4.0 - Database Setup"
    echo "Complete Schema Overhaul with Pipeline Processing"
    echo "=================================================="
    echo ""
    
    log_info "Starting v4.0 database setup..."
    
    check_dependencies
    check_database_connection
    create_backup
    apply_migration
    verify_schema
    verify_indexes
    verify_processing_stages
    verify_jsonb_columns
    test_pipeline_functionality
    generate_schema_report
    
    echo ""
    echo "=================================================="
    log_success "v4.0 Database Setup Completed Successfully!"
    echo "=================================================="
    echo ""
    echo "Key Features Implemented:"
    echo "✅ Consistent naming conventions (snake_case)"
    echo "✅ Robust metadata tracking (JSONB columns)"
    echo "✅ Pipeline processing stages"
    echo "✅ Topic clustering system"
    echo "✅ Scalable architecture"
    echo "✅ Performance-optimized indexes"
    echo "✅ Automatic timestamp updates"
    echo "✅ Comprehensive monitoring tables"
    echo ""
    echo "Next Steps:"
    echo "1. Update API code to use new schema"
    echo "2. Test pipeline processing functionality"
    echo "3. Verify topic clustering integration"
    echo "4. Update frontend to handle new data structures"
    echo ""
}

# Run main function
main "$@"
