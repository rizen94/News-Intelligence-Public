#!/bin/bash

# Script to unify frontend and backend into a single service
echo "🚀 Unifying frontend and backend into single service..."

# Stop existing services
echo "📦 Stopping existing services..."
docker-compose down

# Build React app
echo "🔨 Building React frontend..."
cd web
npm run build
cd ..

# Check if build was successful
if [ ! -d "web/build" ]; then
    echo "❌ React build failed! Please check for errors."
    exit 1
fi

echo "✅ React build completed successfully!"

# Start unified service
echo "🚀 Starting unified service on port 8000..."
docker-compose up -d news-system postgres

# Wait for services to be ready
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service status
echo "🔍 Checking service status..."
docker-compose ps

echo ""
echo "🎉 Unification complete!"
echo "📱 Your unified application is now available at: http://localhost:8000"
echo "🔌 API endpoints are available at: http://localhost:8000/api/*"
echo "🌐 React frontend is served from the same port"
echo ""
echo "💡 You can now stop the separate frontend service on port 3000"
echo "🔄 To rebuild and restart: ./unify-frontend-backend.sh"
