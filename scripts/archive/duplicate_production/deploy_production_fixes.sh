#!/bin/bash

echo "🚀 News Intelligence System - Production Deployment"
echo "=================================================="
echo ""
echo "Deploying critical fixes:"
echo "✅ HTML structure fixes"
echo "✅ Nginx API proxy configuration"
echo "✅ JavaScript API endpoint updates"
echo "✅ Docker Compose configuration"
echo ""

# Stop all services
echo "1. Stopping all services..."
docker-compose down

# Clean up any orphaned containers
echo "2. Cleaning up orphaned containers..."
docker system prune -f

# Start services with updated configuration
echo "3. Starting services with updated configuration..."
docker-compose up -d

# Wait for services to be ready
echo "4. Waiting for services to initialize..."
sleep 10

# Update nginx configuration in running container
echo "5. Applying nginx API proxy configuration..."
CONTAINER_NAME=$(docker ps --format "table {{.Names}}" | grep web | head -1)
if [ ! -z "$CONTAINER_NAME" ]; then
    docker cp web/nginx.conf $CONTAINER_NAME:/etc/nginx/conf.d/default.conf
    docker exec $CONTAINER_NAME nginx -s reload
    echo "✅ Nginx configuration updated"
else
    echo "❌ Web container not found"
fi

# Test all services
echo "6. Testing all services..."
echo "   PostgreSQL: $(docker exec news-intelligence-postgres pg_isready -U newsapp 2>/dev/null && echo '✅ Ready' || echo '❌ Not ready')"
echo "   Redis: $(docker exec news-intelligence-redis redis-cli ping 2>/dev/null && echo '✅ Ready' || echo '❌ Not ready')"
echo "   API: $(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health/health/ | grep -q "200" && echo '✅ Ready' || echo '❌ Not ready')"
echo "   Web: $(curl -s -o /dev/null -w "%{http_code}" http://localhost/ | grep -q "200" && echo '✅ Ready' || echo '❌ Not ready')"

# Test API proxy
echo "7. Testing API proxy functionality..."
API_TEST=$(curl -s http://localhost/api/health/health/ | jq -r '.success' 2>/dev/null)
if [ "$API_TEST" = "true" ]; then
    echo "✅ API proxy working correctly"
else
    echo "❌ API proxy not working"
fi

echo ""
echo "🎉 Production deployment complete!"
echo "================================="
echo "Web Interface: http://localhost"
echo "API Documentation: http://localhost:8000/docs"
echo "Health Check: http://localhost/api/health/health/"
echo ""
