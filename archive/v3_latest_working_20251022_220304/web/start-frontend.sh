#!/bin/bash

# News Intelligence System - Dual Frontend Starter
# Serves both React and HTML versions

echo "🚀 Starting News Intelligence System Frontend"
echo "=============================================="

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Must run from web directory"
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node --version)
echo "📋 Node.js version: $NODE_VERSION"

# Start React development server in background
echo "⚛️  Starting React development server..."
npm start &
REACT_PID=$!

# Wait a moment for React to start
sleep 5

# Start Python HTTP server for HTML fallback
echo "🌐 Starting HTML fallback server..."
cd ..
python3 -m http.server 3001 &
HTML_PID=$!

echo ""
echo "✅ Frontend servers started!"
echo "================================"
echo "⚛️  React App:     http://localhost:3000/"
echo "🌐 HTML Fallback: http://localhost:3001/web/index.html"
echo "🔧 Admin Panel:   http://localhost:3001/web/admin.html"
echo "📊 API Testing:   http://localhost:3001/web/api.html"
echo ""
echo "Press Ctrl+C to stop all servers"

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping servers..."
    kill $REACT_PID 2>/dev/null
    kill $HTML_PID 2>/dev/null
    echo "✅ Servers stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Wait for user to stop
wait
