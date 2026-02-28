#!/bin/bash

# Vite Development Server Starter
# Optimized for fast HMR and native file watching

set -e

echo "🚀 Starting News Intelligence System Frontend (Vite)"
echo "===================================================="

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Must run from web directory"
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node --version)
echo "📋 Node.js version: $NODE_VERSION"

# Check if dependencies are installed
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies..."
    npm install
fi

# Clear any cached builds
echo "🧹 Clearing build cache..."
rm -rf node_modules/.vite
rm -rf dist

echo ""
echo "⚡ Starting Vite development server..."
echo "   - Fast HMR enabled"
echo "   - Native file watching"
echo "   - Proxy: http://localhost:8000"
echo ""
echo "   Open http://localhost:3000 in your browser"
echo ""

# Start Vite dev server
npm run dev
