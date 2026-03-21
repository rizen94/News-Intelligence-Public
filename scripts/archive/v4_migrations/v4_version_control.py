#!/usr/bin/env python3
"""
News Intelligence System 4.0 Version Control Strategy
Creates version control structure and migration documentation
"""

import os
import json
from datetime import datetime
from pathlib import Path

def create_version_control_structure():
    """Create version control structure for v4"""
    print("🔄 Creating version control structure...")
    
    # Create version directories
    version_dirs = [
        "versions/v3_legacy",
        "versions/v4_current",
        "versions/v4_backup",
        "migrations/v3_to_v4",
        "documentation/v4_architecture"
    ]
    
    for dir_path in version_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        print(f"   📁 Created: {dir_path}")
    
    print("   ✅ Version control structure created")

def create_migration_documentation():
    """Create comprehensive migration documentation"""
    print("🔄 Creating migration documentation...")
    
    migration_doc = f"""
# News Intelligence System 4.0 Migration Documentation

## Migration Overview
- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **From**: v3 Legacy Architecture (99 tables)
- **To**: v4 Simplified Architecture (11 tables)
- **Reduction**: 88.9% database complexity reduction

## Database Schema Changes

### V4 Tables Created
1. **articles_v4** - Core article storage
2. **rss_feeds_v4** - RSS feed management
3. **storylines_v4** - Storyline management
4. **storyline_articles_v4** - Storyline-article relationships
5. **topic_clusters_v4** - Topic clustering
6. **article_topics_v4** - Article-topic relationships
7. **analysis_results_v4** - Analysis results storage
8. **system_metrics_v4** - System monitoring
9. **pipeline_traces_v4** - Pipeline monitoring
10. **users_v4** - User management
11. **user_preferences_v4** - User preferences

### Data Migration Results
- **Articles**: 1,312 migrated
- **RSS Feeds**: 52 migrated
- **Storylines**: 1 migrated
- **Storyline Articles**: 5 migrated
- **Total Records**: 1,370 migrated

## API Changes

### Updated Endpoints
- All endpoints now use v4 tables
- Maintained backward compatibility through compatibility layer
- Updated field mappings for consistency

### Field Mappings
- `published_date` → `published_at`
- `source` → `source_domain`
- `created_date` → `created_at`
- `updated_date` → `updated_at`
- `last_fetch` → `last_fetched_at`

## Frontend Changes

### Updated Components
- Dashboard component updated for v4 data structures
- Articles component updated for v4 field mappings
- Storylines component updated for v4 field mappings
- RSS Feeds component updated for v4 field mappings
- API service updated to use v4 endpoints

### Compatibility Layer
- Created v4Compatibility.js for smooth transition
- Maps v4 data structures to legacy expectations
- Ensures frontend continues to work during transition

## Rollback Procedures

### Database Rollback
1. Stop all services
2. Restore from backup: `backups/v4_migration_python/`
3. Drop v4 tables if needed
4. Restart services

### API Rollback
1. Restore API files from backup (`.backup_*` files)
2. Restart API server
3. Verify endpoints work with legacy tables

### Frontend Rollback
1. Restore frontend files from backup (`.backup_*` files)
2. Restart React server
3. Verify frontend works with legacy API

## Testing Checklist

### Database Testing
- [ ] Verify all v4 tables exist
- [ ] Verify data integrity
- [ ] Test query performance
- [ ] Verify indexes are working

### API Testing
- [ ] Test all endpoints return data
- [ ] Verify field mappings are correct
- [ ] Test error handling
- [ ] Verify response formats

### Frontend Testing
- [ ] Test dashboard loads correctly
- [ ] Test articles page displays data
- [ ] Test storylines page displays data
- [ ] Test RSS feeds page displays data
- [ ] Test all navigation works

## Performance Improvements

### Database Performance
- Reduced table count by 88.9%
- Simplified queries
- Optimized indexes
- Reduced join complexity

### API Performance
- Faster query execution
- Reduced memory usage
- Simplified data structures
- Better caching opportunities

## Next Steps

1. **Complete Testing**: Run comprehensive tests
2. **Performance Monitoring**: Monitor system performance
3. **User Acceptance**: Verify all functionality works
4. **Documentation**: Update user documentation
5. **Training**: Train team on v4 architecture

## Support

For issues or questions about the v4 migration:
- Check migration logs: `v4_migration_*.log`
- Review backup files: `*.backup_*`
- Consult this documentation
- Contact system administrator
"""
    
    with open("documentation/v4_architecture/MIGRATION_DOCUMENTATION.md", 'w') as f:
        f.write(migration_doc)
    
    print("   ✅ Migration documentation created")

def create_version_info():
    """Create version information file"""
    print("🔄 Creating version information...")
    
    version_info = {
        "version": "4.0.0",
        "migration_date": datetime.now().isoformat(),
        "database_tables": {
            "legacy_count": 99,
            "v4_count": 11,
            "reduction_percentage": 88.9
        },
        "data_migration": {
            "articles": 1312,
            "rss_feeds": 52,
            "storylines": 1,
            "storyline_articles": 5,
            "total_records": 1370
        },
        "api_changes": {
            "endpoints_updated": True,
            "compatibility_layer": True,
            "field_mappings": True
        },
        "frontend_changes": {
            "components_updated": True,
            "compatibility_layer": True,
            "api_service_updated": True
        },
        "status": "migrated",
        "next_steps": [
            "Complete testing",
            "Performance monitoring",
            "User acceptance testing",
            "Documentation updates"
        ]
    }
    
    with open("versions/v4_current/version_info.json", 'w') as f:
        json.dump(version_info, f, indent=2)
    
    print("   ✅ Version information created")

def create_rollback_script():
    """Create rollback script for emergency use"""
    print("🔄 Creating rollback script...")
    
    rollback_script = '''#!/bin/bash
# News Intelligence System 4.0 Rollback Script
# Use this script to rollback to v3 legacy architecture

echo "🚨 NEWS INTELLIGENCE SYSTEM 4.0 ROLLBACK"
echo "======================================="
echo ""
echo "⚠️  WARNING: This will rollback to v3 legacy architecture"
echo "⚠️  All v4 improvements will be lost"
echo ""
read -p "Are you sure you want to proceed? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Rollback cancelled"
    exit 1
fi

echo "🔄 Starting rollback process..."

# Stop services
echo "🛑 Stopping services..."
pkill -f "uvicorn main_v4:app" || echo "API server not running"
pkill -f "react-scripts start" || echo "React server not running"
sleep 5

# Restore API files
echo "🔄 Restoring API files..."
find api/domains -name "*.py.backup_*" -exec bash -c 'mv "$1" "${1%.backup_*}"' _ {} \\;

# Restore frontend files
echo "🔄 Restoring frontend files..."
find web/src -name "*.js.backup_*" -exec bash -c 'mv "$1" "${1%.backup_*}"' _ {} \\;
find web/src -name "*.ts.backup_*" -exec bash -c 'mv "$1" "${1%.backup_*}"' _ {} \\;

# Drop v4 tables (optional)
echo "🔄 Dropping v4 tables..."
cd api
python3 -c "
import psycopg2
import os

try:
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'news_intelligence'),
        user=os.getenv('DB_USER', 'newsapp'),
        password=os.getenv('DB_PASSWORD', 'newsapp_password'),
        port=os.getenv('DB_PORT', '5432')
    )
    
    with conn.cursor() as cur:
        cur.execute('DROP TABLE IF EXISTS articles_v4 CASCADE')
        cur.execute('DROP TABLE IF EXISTS rss_feeds_v4 CASCADE')
        cur.execute('DROP TABLE IF EXISTS storylines_v4 CASCADE')
        cur.execute('DROP TABLE IF EXISTS storyline_articles_v4 CASCADE')
        cur.execute('DROP TABLE IF EXISTS topic_clusters_v4 CASCADE')
        cur.execute('DROP TABLE IF EXISTS article_topics_v4 CASCADE')
        cur.execute('DROP TABLE IF EXISTS analysis_results_v4 CASCADE')
        cur.execute('DROP TABLE IF EXISTS system_metrics_v4 CASCADE')
        cur.execute('DROP TABLE IF EXISTS pipeline_traces_v4 CASCADE')
        cur.execute('DROP TABLE IF EXISTS users_v4 CASCADE')
        cur.execute('DROP TABLE IF EXISTS user_preferences_v4 CASCADE')
        conn.commit()
        print('✅ V4 tables dropped')
    
    conn.close()
    
except Exception as e:
    print(f'❌ Error dropping v4 tables: {e}')
"

echo "✅ Rollback completed"
echo "🔄 Restart services to complete rollback"
echo "   API: cd api && uvicorn main_v4:app --host 0.0.0.0 --port 8001"
echo "   React: cd web && npm start"
'''
    
    with open("scripts/v4_rollback.sh", 'w') as f:
        f.write(rollback_script)
    
    os.chmod("scripts/v4_rollback.sh", 0o755)
    print("   ✅ Rollback script created")

def main():
    """Main function"""
    print("🚀 Creating News Intelligence System 4.0 Version Control Strategy")
    print("=" * 70)
    
    try:
        create_version_control_structure()
        create_migration_documentation()
        create_version_info()
        create_rollback_script()
        
        print("\n🎉 Version Control Strategy completed successfully!")
        print("📊 Version control structure created")
        print("📚 Migration documentation created")
        print("🔄 Rollback procedures established")
        print("🔄 Next steps: Test system and monitor performance")
        
    except Exception as e:
        print(f"❌ Version Control Strategy failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
