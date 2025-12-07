#!/bin/bash

# Article Deduplication System Script
# Runs the comprehensive article deduplication system

echo "🔍 Article Deduplication System"
echo "=============================="

# Navigate to the API directory
cd "$(dirname "$0")/../api"

# Check if Python script exists
if [ ! -f "scripts/article_deduplication.py" ]; then
    echo "❌ Article deduplication script not found!"
    exit 1
fi

# Set environment variables
export DB_HOST=localhost
export DB_NAME=news_intelligence
export DB_USER=newsapp
export DB_PASSWORD=newsapp_password
export DB_PORT=5432

echo "🔧 Running article deduplication analysis..."
echo "==========================================="

# Run the deduplication script
python3 scripts/article_deduplication.py

echo ""
echo "🌐 You can also access the web interface at:"
echo "   http://localhost:3000/articles/duplicates"
echo ""
echo "🔧 API endpoints available:"
echo "   GET  /api/v4/articles/duplicates/detect"
echo "   GET  /api/v4/articles/duplicates/url"
echo "   GET  /api/v4/articles/duplicates/content"
echo "   GET  /api/v4/articles/duplicates/similar"
echo "   POST /api/v4/articles/duplicates/auto-merge"
echo "   POST /api/v4/articles/duplicates/prevent"
echo "   GET  /api/v4/articles/duplicates/stats"
echo ""
echo "✅ Article deduplication analysis complete!"
