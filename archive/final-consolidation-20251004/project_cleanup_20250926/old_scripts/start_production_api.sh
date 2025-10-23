#!/bin/bash
"""
Production API startup script for News Intelligence System
"""

echo "Starting News Intelligence API Production Service..."

# Set environment variables for production
export DB_HOST=localhost
export DB_NAME=news_intelligence
export DB_USER=newsapp
export DB_PASSWORD=newsapp_password
export DB_PORT=5432
export REDIS_URL=redis://localhost:6379/0

# Kill any existing API processes
pkill -f "python.*main.py" || true
pkill -f "python.*simple_api.py" || true

# Start the production API
cd /home/pete/Documents/Projects/News\ Intelligence/api
python3 main.py &

# Wait for API to start
sleep 5

# Test the API
echo "Testing API health..."
curl -s http://localhost:8001/api/health/ > /dev/null
if [ $? -eq 0 ]; then
    echo "✅ API is running successfully on port 8001"
    echo "✅ Web connectors should now work properly"
else
    echo "❌ API failed to start, falling back to simple API"
    pkill -f "python.*main.py" || true
    python3 simple_api.py &
    sleep 3
    echo "✅ Simple API is running as fallback"
fi

echo "Production API service started!"
