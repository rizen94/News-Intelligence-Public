#!/bin/bash

# Update API_BASE in web/index.html
echo "Updating API_BASE in web/index.html..."

# Backup original file
cp web/index.html web/index.html.backup

# Update API_BASE
sed -i "s|const API_BASE = 'http://localhost:8000/api';|const API_BASE = 'http://api.news-intelligence.local:8000/api';|g" web/index.html

echo "✅ Updated API_BASE to use custom domain"

# Deploy updated configuration
echo "Deploying updated configuration..."
docker cp web/index.html news-frontend:/usr/share/nginx/html/

echo "✅ Configuration deployed successfully"
echo ""
echo "🌐 Your News Intelligence System is now accessible at:"
echo "   Frontend: http://news-intelligence.local:3001"
echo "   API: http://api.news-intelligence.local:8000"
echo ""
echo "📱 Other devices on your network can access it using:"
echo "   http://192.168.93.92:3001"
echo "   http://192.168.93.92:8000"
