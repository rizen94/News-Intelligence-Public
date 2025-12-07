#!/bin/bash
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
find api/domains -name "*.py.backup_*" -exec bash -c 'mv "$1" "${1%.backup_*}"' _ {} \;

# Restore frontend files
echo "🔄 Restoring frontend files..."
find web/src -name "*.js.backup_*" -exec bash -c 'mv "$1" "${1%.backup_*}"' _ {} \;
find web/src -name "*.ts.backup_*" -exec bash -c 'mv "$1" "${1%.backup_*}"' _ {} \;

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
