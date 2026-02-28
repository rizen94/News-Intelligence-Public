#!/bin/bash

# Optimized React Development Server
# This script ensures proper hot reloading and prevents caching issues

set -e

echo "🚀 Starting Optimized React Development Server"
echo "================================================"

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Must run from web directory"
    exit 1
fi

# Clear any cached builds
echo "🧹 Clearing build cache..."
rm -rf node_modules/.cache
rm -rf build

# Set optimal environment variables for development
export NODE_ENV=development
export GENERATE_SOURCEMAP=true
export FAST_REFRESH=true
export CHOKIDAR_USEPOLLING=true
export CHOKIDAR_INTERVAL=1000
export WDS_SOCKET_HOST=localhost
export WDS_SOCKET_PORT=3000
export BROWSER=none

# Disable service worker
export SKIP_SERVICE_WORKER=true

# React Scripts optimizations
export TSC_COMPILE_ON_ERROR=true
export SKIP_PREFLIGHT_CHECK=true

echo "📋 Configuration:"
echo "   - Hot Module Replacement: ENABLED"
echo "   - Fast Refresh: ENABLED"
echo "   - File Watching: POLLING MODE"
echo "   - Cache: DISABLED"
echo ""

# Start the development server
echo "⚛️  Starting React development server..."
echo "   Open http://localhost:3000 in your browser"
echo ""
echo "   💡 TIP: If changes don't appear:"
echo "      1. Check browser console for HMR messages"
echo "      2. Look for 'webpackHotUpdate' in Network tab"
echo "      3. Hard refresh only if HMR fails (Ctrl+Shift+R)"
echo ""

npm start

