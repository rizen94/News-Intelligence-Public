#!/bin/bash
#
# Fix Missing Data Pipeline
# This script addresses the missing articles, topics, and storylines issue
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
API_DIR="$PROJECT_ROOT/api"

echo "🔧 FIXING MISSING DATA PIPELINE"
echo "================================"
echo ""

# Step 1: Check and setup database connection
echo "Step 1: Database Connection Setup"
echo "-----------------------------------"

# Check if DB_HOST is set
if [ -z "$DB_HOST" ]; then
    echo "   ⚠️  DB_HOST not set"
    
    # Check if SSH tunnel is running
    if ps aux | grep -q "ssh.*5433.*5432" | grep -v grep; then
        echo "   ✅ SSH tunnel detected on port 5433"
        export DB_HOST=localhost
        export DB_PORT=5433
    else
        echo "   ⚠️  SSH tunnel not running"
        echo "   📝 Attempting to start SSH tunnel..."
        
        if [ -f "$SCRIPT_DIR/setup_nas_ssh_tunnel.sh" ]; then
            bash "$SCRIPT_DIR/setup_nas_ssh_tunnel.sh" || echo "   ❌ Failed to start SSH tunnel"
        else
            echo "   ❌ SSH tunnel script not found at $SCRIPT_DIR/setup_nas_ssh_tunnel.sh"
            echo "   💡 Please set DB_HOST manually:"
            echo "      export DB_HOST=192.168.93.100  # Direct NAS connection"
            echo "      OR"
            echo "      export DB_HOST=localhost       # If SSH tunnel on 5433"
            exit 1
        fi
        
        # Try again
        if ps aux | grep -q "ssh.*5433.*5432" | grep -v grep; then
            export DB_HOST=localhost
            export DB_PORT=5433
            echo "   ✅ SSH tunnel started"
        else
            echo "   ❌ Could not establish database connection"
            exit 1
        fi
    fi
else
    echo "   ✅ DB_HOST is set: $DB_HOST"
fi

# Set other DB variables if not set
export DB_NAME=${DB_NAME:-news_intelligence}
export DB_USER=${DB_USER:-newsapp}
export DB_PORT=${DB_PORT:-5432}

echo "   Database config:"
echo "      DB_HOST=$DB_HOST"
echo "      DB_PORT=$DB_PORT"
echo "      DB_NAME=$DB_NAME"
echo "      DB_USER=$DB_USER"
echo ""

# Step 2: Verify database connection and domains
echo "Step 2: Verifying Database and Domains"
echo "---------------------------------------"

cd "$API_DIR"
python3 << 'PYTHON_EOF'
import os
import sys
sys.path.insert(0, '.')

try:
    from shared.database.connection import get_db_connection
    
    conn = get_db_connection()
    if not conn:
        print("   ❌ Database connection failed")
        sys.exit(1)
    
    print("   ✅ Database connection successful")
    
    with conn.cursor() as cur:
        # Check domains
        cur.execute("SELECT domain_key, schema_name, is_active FROM domains ORDER BY domain_key")
        domains = cur.fetchall()
        
        print(f"\n   Domains ({len(domains)} total):")
        for domain_key, schema_name, is_active in domains:
            status = "✅ ACTIVE" if is_active else "❌ INACTIVE"
            print(f"      - {domain_key}: {schema_name} ({status})")
            
            # If inactive, activate it
            if not is_active:
                print(f"         🔧 Activating {domain_key}...")
                cur.execute("UPDATE domains SET is_active = TRUE WHERE domain_key = %s", (domain_key,))
                conn.commit()
                print(f"         ✅ {domain_key} activated")
        
        # Check RSS feeds
        print("\n   RSS Feeds:")
        for domain_key, schema_name, is_active in domains:
            if not is_active:
                continue
            try:
                cur.execute(f"SELECT COUNT(*) FROM {schema_name}.rss_feeds")
                feed_count = cur.fetchone()[0]
                cur.execute(f"SELECT COUNT(*) FROM {schema_name}.rss_feeds WHERE is_active = true")
                active_feeds = cur.fetchone()[0]
                print(f"      - {domain_key}: {feed_count} total, {active_feeds} active")
            except Exception as e:
                print(f"      - {domain_key}: ❌ Error - {e}")
        
        # Check articles
        print("\n   Articles:")
        for domain_key, schema_name, is_active in domains:
            if not is_active:
                continue
            try:
                cur.execute(f"SELECT COUNT(*) FROM {schema_name}.articles")
                article_count = cur.fetchone()[0]
                print(f"      - {domain_key}: {article_count} articles")
            except Exception as e:
                print(f"      - {domain_key}: ❌ Error - {e}")
        
        # Check topic clusters
        print("\n   Topic Clusters:")
        for domain_key, schema_name, is_active in domains:
            if not is_active:
                continue
            try:
                cur.execute(f"SELECT COUNT(*) FROM {schema_name}.topic_clusters")
                topic_count = cur.fetchone()[0]
                print(f"      - {domain_key}: {topic_count} topic clusters")
            except Exception as e:
                print(f"      - {domain_key}: ❌ Error - {e}")
    
    conn.close()
    
except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYTHON_EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Database verification failed"
    exit 1
fi

echo ""

# Step 3: Trigger RSS feed collection
echo "Step 3: Triggering RSS Feed Collection"
echo "--------------------------------------"

cd "$API_DIR"
python3 << 'PYTHON_EOF'
import os
import sys
sys.path.insert(0, '.')

try:
    from collectors.rss_collector import collect_rss_feeds
    
    print("   📰 Starting RSS feed collection...")
    articles_added = collect_rss_feeds()
    print(f"   ✅ RSS collection complete: {articles_added} articles added")
    
except Exception as e:
    print(f"   ⚠️  RSS collection error: {e}")
    import traceback
    traceback.print_exc()
PYTHON_EOF

echo ""

# Step 4: Trigger topic clustering
echo "Step 4: Triggering Topic Clustering"
echo "------------------------------------"

cd "$API_DIR"
python3 << 'PYTHON_EOF'
import os
import sys
import asyncio
sys.path.insert(0, '.')

async def run_clustering():
    try:
        from scripts.daily_batch_processor import process_topic_clustering
        
        print("   🔍 Starting topic clustering...")
        result = await process_topic_clustering()
        if result and result.get('success'):
            processed = result.get('processed', 0)
            print(f"   ✅ Topic clustering complete: {processed} articles processed")
        else:
            print(f"   ⚠️  Topic clustering: {result}")
    except Exception as e:
        print(f"   ⚠️  Topic clustering error: {e}")
        import traceback
        traceback.print_exc()

asyncio.run(run_clustering())
PYTHON_EOF

echo ""
echo "================================"
echo "✅ DATA PIPELINE FIX COMPLETE"
echo ""
echo "Next steps:"
echo "  1. Check the frontend to see if data appears"
echo "  2. If still empty, check API logs for errors"
echo "  3. Verify RSS feeds are configured in the database"
echo ""

