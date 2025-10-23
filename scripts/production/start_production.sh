#!/bin/bash
# News Intelligence System - Production Startup
# Complete system startup with verification

echo "🚀 Starting News Intelligence System - Production Mode"
echo "======================================================"

# Navigate to project directory
cd /home/pete/Documents/projects/Projects/News\ Intelligence

# Start all services
echo "📦 Starting Docker Compose services..."
docker-compose up -d

# Wait for services to initialize
echo "⏳ Waiting for services to initialize..."
sleep 15

# Verify all services are running
echo "🔍 Verifying system status..."
echo ""
echo "Container Status:"
docker-compose ps

echo ""
echo "API Endpoints:"
echo "Health: $(curl -s http://localhost:8000/api/health | jq -r '.success // "null"')"
echo "RSS Feeds: $(curl -s http://localhost:8000/api/rss-feeds/ | jq -r '.data | length') feeds"
echo "Story Timeline: $(curl -s http://localhost:8000/api/story-timeline/ | jq -r '.success // "null"')"
echo "Bias Detection: $(curl -s http://localhost:8000/api/bias-detection/sources | jq -r '.data | length') sources"
echo "ML Monitoring: $(curl -s http://localhost:8000/api/ml-monitoring/status/ | jq -r '.success // "null"')"

echo ""
echo "Web Interface:"
echo "Status: $(curl -s -o /dev/null -w "%{http_code}" http://localhost/)"

echo ""
echo "ML System:"
docker exec news-intelligence-ollama ollama list

echo ""
echo "✅ News Intelligence System is ready!"
echo "🌐 Web Interface: http://localhost/"
echo "📊 API Documentation: http://localhost:8000/docs"
echo "🤖 Ollama API: http://localhost:11435"
