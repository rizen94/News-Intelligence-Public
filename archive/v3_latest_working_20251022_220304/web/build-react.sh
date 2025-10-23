#!/bin/bash

# React Build Script for Node.js v12 Compatibility
echo "🔨 Building React app for Node.js v12 compatibility..."

# Set environment variables for compatibility
export NODE_OPTIONS="--max-old-space-size=4096"
export SKIP_PREFLIGHT_CHECK=true
export TSC_COMPILE_ON_ERROR=true

# Try to build
echo "📦 Running npm build..."
if npm run build; then
    echo "✅ React build successful!"
    echo "📁 Build output: web/build/"
    echo "🌐 Serve with: python3 -m http.server 3000 -d build/"
else
    echo "❌ React build failed - using HTML fallback"
    echo "🌐 HTML interfaces available at:"
    echo "   - Main: http://localhost:3001/web/index.html"
    echo "   - Admin: http://localhost:3001/web/admin.html"
    echo "   - API: http://localhost:3001/web/api.html"
fi
