#!/bin/bash

# News Intelligence System - Frontend Starter (with file watcher fix)
# This script starts the React dev server with polling to avoid file watcher limits

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

# Check file watcher limit
CURRENT_LIMIT=$(cat /proc/sys/fs/inotify/max_user_watches 2>/dev/null || echo "unknown")
echo "📊 Current file watcher limit: $CURRENT_LIMIT"

if [ "$CURRENT_LIMIT" != "unknown" ] && [ "$CURRENT_LIMIT" -lt 524288 ]; then
    echo "⚠️  Warning: File watcher limit is low ($CURRENT_LIMIT)"
    echo "   Using polling mode to avoid issues."
    echo "   To permanently increase the limit, run:"
    echo "   sudo sysctl -w fs.inotify.max_user_watches=524288"
    echo "   echo 'fs.inotify.max_user_watches=524288' | sudo tee -a /etc/sysctl.conf"
    echo ""
    CHOKIDAR_USEPOLLING=true
else
    CHOKIDAR_USEPOLLING=false
fi

# Start React development server
echo "⚛️  Starting React development server..."
if [ "$CHOKIDAR_USEPOLLING" = "true" ]; then
    echo "   (Using polling mode to avoid file watcher limits)"
    CHOKIDAR_USEPOLLING=true BROWSER=none npm start
else
    BROWSER=none npm start
fi

