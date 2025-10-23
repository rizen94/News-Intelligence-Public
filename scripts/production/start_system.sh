#!/bin/bash
# News Intelligence System - Startup Script
# This script starts the entire system after reboot

echo "🚀 Starting News Intelligence System..."
echo "====================================="

# Navigate to project directory
cd /home/pete/Documents/projects/Projects/News\ Intelligence

# Start all services
echo "Starting Docker Compose services..."
docker-compose up -d

# Wait for services to start
echo "Waiting for services to initialize..."
sleep 10

# Check service status
echo "Checking service status..."
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "✅ System startup complete!"
echo "🌐 Web Interface: http://localhost"
echo "🔧 API: http://localhost:8000"
echo "🤖 Ollama: http://localhost:11435"
