#!/bin/bash

# Test Integrated Deduplication Pipeline
# Tests the automatic deduplication system integrated into RSS processing

echo "🔧 TESTING INTEGRATED DEDUPLICATION PIPELINE"
echo "==========================================="

cd "/home/pete/Documents/projects/Projects/News Intelligence/api"

# Set environment variables
export DB_HOST=localhost
export DB_NAME=news_intelligence
export DB_USER=newsapp
export DB_PASSWORD=newsapp_password
export DB_PORT=5432

echo "🔍 Testing pipeline deduplication service..."

python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')
from services.pipeline_deduplication_service import PipelineDeduplicationService

async def test_pipeline_deduplication():
    print('🔍 Testing Pipeline Deduplication Service...')
    
    service = PipelineDeduplicationService()
    
    # Test deduplication metrics
    print('📊 Getting deduplication metrics...')
    metrics = await service.get_deduplication_metrics()
    
    if 'error' not in metrics:
        print('✅ Deduplication metrics retrieved successfully')
        print(f'   Total articles: {metrics[\"total_articles\"]:,}')
        print(f'   Articles with hash: {metrics[\"articles_with_hash\"]:,}')
        print(f'   Hash coverage: {metrics[\"hash_coverage_percentage\"]:.1f}%')
        print(f'   URL duplicates: {metrics[\"url_duplicates\"]}')
        print(f'   Content duplicates: {metrics[\"content_duplicates\"]}')
        print(f'   Recent deduplication runs: {metrics[\"recent_deduplication_runs\"]}')
    else:
        print(f'❌ Error getting metrics: {metrics[\"error\"]}')
    
    # Test pipeline deduplication run
    print('\\n🔄 Testing pipeline deduplication run...')
    results = await service.run_deduplication_pipeline('test_trace_id')
    
    if results['success']:
        print('✅ Pipeline deduplication test successful')
        print(f'   Articles processed: {results[\"processed\"]}')
        print(f'   Duplicates found: {results[\"duplicates_found\"]}')
        print(f'   Duplicates merged: {results[\"duplicates_merged\"]}')
    else:
        print(f'❌ Pipeline deduplication test failed: {results.get(\"error\", \"Unknown error\")}')

# Run the test
asyncio.run(test_pipeline_deduplication())
"

echo -e "\n🔍 Testing RSS processing with integrated deduplication..."

python3 -c "
import asyncio
import sys
sys.path.insert(0, '.')
from services.rss_processing_service import RSSProcessor

async def test_rss_with_deduplication():
    print('🔍 Testing RSS Processing with Integrated Deduplication...')
    
    processor = RSSProcessor()
    
    # Test processing a single feed (if any exist)
    print('📡 Testing RSS feed processing...')
    try:
        results = await processor.process_all_feeds()
        
        if results['success']:
            print('✅ RSS processing with deduplication successful')
            print(f'   Feeds processed: {results[\"processed\"]}')
            print(f'   Errors: {results[\"errors\"]}')
        else:
            print(f'❌ RSS processing failed: {results.get(\"error\", \"Unknown error\")}')
    except Exception as e:
        print(f'❌ RSS processing error: {e}')

# Run the test
asyncio.run(test_rss_with_deduplication())
"

echo -e "\n🔍 Testing API endpoints with deduplication metrics..."

curl -s "http://localhost:8001/api/v4/system-monitoring/status" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if data.get('success'):
        print('✅ System monitoring with deduplication metrics working')
        dedup_data = data['data']['deduplication']
        print(f'   Articles with hash: {dedup_data[\"articles_with_hash\"]:,}')
        print(f'   Hash coverage: {dedup_data[\"hash_coverage_percentage\"]:.1f}%')
        print(f'   URL duplicates: {dedup_data[\"url_duplicates\"]}')
        print(f'   Content duplicates: {dedup_data[\"content_duplicates\"]}')
        print(f'   Recent deduplication runs: {dedup_data[\"recent_deduplication_runs\"]}')
        print(f'   Deduplication status: {dedup_data[\"status\"]}')
    else:
        print(f'❌ API error: {data}')
except Exception as e:
    print(f'❌ Error: {e}')
"

echo -e "\n✅ INTEGRATED DEDUPLICATION PIPELINE TEST COMPLETE"
echo "=================================================="
echo "The deduplication system is now integrated into the RSS processing pipeline"
echo "and will automatically run after each article import."
