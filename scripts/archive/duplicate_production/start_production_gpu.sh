#!/bin/bash
# News Intelligence System - Production Startup with GPU Support
# Complete system startup with GPU-accelerated Ollama

echo "🚀 Starting News Intelligence System - Production Mode with GPU"
echo "=============================================================="

# Navigate to project directory
cd /home/pete/Documents/projects/Projects/News\ Intelligence

# Check GPU availability
echo "🔍 Checking GPU availability..."
if nvidia-smi >/dev/null 2>&1; then
    echo "✅ NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits
    echo ""
    echo "📋 To enable GPU acceleration for Ollama:"
    echo "   1. Install NVIDIA Container Toolkit:"
    echo "      curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg"
    echo "      curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list"
    echo "      sudo apt update && sudo apt install -y nvidia-container-toolkit"
    echo "      sudo systemctl restart docker"
    echo ""
    echo "   2. Uncomment GPU configuration in docker-compose.yml"
    echo ""
else
    echo "⚠️  No NVIDIA GPU detected - running in CPU mode"
fi

# Start all services
echo "📦 Starting Docker Compose services..."
docker-compose up -d

# Wait for services to initialize
echo "⏳ Waiting for services to initialize..."
sleep 15

# Verify all services are running
echo "🔍 Verifying system status..."
echo ""
echo "Container Status:"
docker-compose ps

echo ""
echo "API Endpoints:"
echo "Health: $(curl -s http://localhost:8000/api/health | jq -r '.success // "null"')"
echo "RSS Feeds: $(curl -s http://localhost:8000/api/rss-feeds/ | jq -r '.data | length') feeds"
echo "Story Timeline: $(curl -s http://localhost:8000/api/story-timeline/ | jq -r '.success // "null"')"
echo "Bias Detection: $(curl -s http://localhost:8000/api/bias-detection/sources | jq -r '.data | length') sources"
echo "ML Monitoring: $(curl -s http://localhost:8000/api/ml-monitoring/status/ | jq -r '.success // "null"')"

echo ""
echo "Web Interface:"
echo "Status: $(curl -s -o /dev/null -w "%{http_code}" http://localhost/)"

echo ""
echo "ML System:"
docker exec news-intelligence-ollama ollama list

echo ""
echo "✅ News Intelligence System is ready!"
echo "🌐 Web Interface: http://localhost/"
echo "📊 API Documentation: http://localhost:8000/docs"
echo "🤖 Ollama API: http://localhost:11435"
echo ""
echo "💡 GPU Acceleration: $(if nvidia-smi >/dev/null 2>&1; then echo 'Available - install NVIDIA Container Toolkit to enable'; else echo 'Not available - running in CPU mode'; fi)"
