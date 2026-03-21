#!/bin/bash

# RSS Feed Duplicate Detection and Management Script
# Runs the duplicate detection system and provides management options

echo "🔍 RSS Feed Duplicate Detection System"
echo "====================================="

# Navigate to the API directory
cd "$(dirname "$0")/../api"

# Check if Python script exists
if [ ! -f "scripts/rss_duplicate_detector.py" ]; then
    echo "❌ RSS duplicate detector script not found!"
    exit 1
fi

# Set environment variables
export DB_HOST=localhost
export DB_NAME=news_intelligence
export DB_USER=newsapp
export DB_PASSWORD=newsapp_password
export DB_PORT=5432

echo "🔧 Running duplicate detection..."
echo "================================="

# Run the duplicate detection script
python3 scripts/rss_duplicate_detector.py

echo ""
echo "🌐 You can also access the web interface at:"
echo "   http://localhost:3000/rss-feeds/duplicates"
echo ""
echo "🔧 API endpoints available:"
echo "   GET  /api/v4/rss-feeds/duplicates/detect"
echo "   GET  /api/v4/rss-feeds/duplicates/exact"
echo "   GET  /api/v4/rss-feeds/duplicates/similar"
echo "   POST /api/v4/rss-feeds/duplicates/auto-merge"
echo "   POST /api/v4/rss-feeds/duplicates/prevent"
echo ""
echo "✅ Duplicate detection complete!"
