#!/bin/bash

# News Intelligence System - Dual Frontend Starter
# Serves both React and HTML fallback versions

echo "🚀 Starting News Intelligence System - Dual Frontend"
echo "=================================================="

# Check if we're in the right directory
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Error: Must run from project root directory"
    exit 1
fi

# Start the backend API
echo "🔧 Starting backend API..."
docker-compose up -d postgres redis
sleep 5

# Start the API server
echo "🚀 Starting API server..."
cd api
python3 main.py &
API_PID=$!
cd ..

# Wait for API to start
echo "⏳ Waiting for API to start..."
sleep 10

# Test API health
echo "🔍 Testing API health..."
if curl -s http://localhost:8000/api/health/ > /dev/null; then
    echo "✅ API is healthy"
else
    echo "⚠️  API may not be ready yet"
fi

# Start HTML fallback server
echo "🌐 Starting HTML fallback server..."
python3 -m http.server 3001 &
HTML_PID=$!

# Try to start React development server
echo "⚛️  Attempting to start React development server..."
cd web

# Check if React can start
if npm start > /dev/null 2>&1 & then
    REACT_PID=$!
    echo "✅ React development server started"
    REACT_AVAILABLE=true
else
    echo "⚠️  React development server failed to start"
    REACT_AVAILABLE=false
fi

cd ..

echo ""
echo "✅ Frontend servers started!"
echo "================================"
echo "🔧 Backend API:    http://localhost:8000/"
echo "🌐 HTML Fallback:  http://localhost:3001/web/index.html"
echo "🔧 Admin Panel:    http://localhost:3001/web/admin.html"
echo "📊 API Testing:    http://localhost:3001/web/api.html"

if [ "$REACT_AVAILABLE" = true ]; then
    echo "⚛️  React App:      http://localhost:3000/"
    echo "📝 Note: React app may take a moment to load"
else
    echo "⚠️  React App:      UNAVAILABLE (using HTML fallback)"
fi

echo ""
echo "📋 Fallback Usage Logging:"
echo "   - Check console for fallback warnings"
echo "   - Check logs/fallback_usage.log for server logs"
echo "   - API endpoint: http://localhost:8000/api/fallback/stats"
echo ""
echo "Press Ctrl+C to stop all servers"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping servers..."
    kill $API_PID 2>/dev/null
    kill $HTML_PID 2>/dev/null
    if [ "$REACT_AVAILABLE" = true ]; then
        kill $REACT_PID 2>/dev/null
    fi
    docker-compose down
    echo "✅ All servers stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Wait for user to stop
wait
