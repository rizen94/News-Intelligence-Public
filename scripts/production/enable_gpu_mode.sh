#!/bin/bash
# Enable GPU Mode for News Intelligence System
# Run this after installing NVIDIA Container Toolkit

echo "🚀 Enabling GPU Mode for News Intelligence System"
echo "================================================"

# Navigate to project directory
cd /home/pete/Documents/projects/Projects/News\ Intelligence

echo "📦 Step 1: Stopping current system..."
docker-compose down

echo "📦 Step 2: Enabling GPU configuration in docker-compose.yml..."
# Uncomment GPU configuration
sed -i '/# GPU Configuration/,/# End GPU Configuration/s/^#//' docker-compose.yml

echo "📦 Step 3: Starting system with GPU acceleration..."
docker-compose up -d

echo "⏳ Waiting for services to initialize..."
sleep 15

echo "🔍 Verifying GPU acceleration..."
echo ""
echo "Container Status:"
docker-compose ps

echo ""
echo "GPU Usage Check:"
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader,nounits

echo ""
echo "Ollama Model Status:"
docker exec news-intelligence-ollama ollama list

echo ""
echo "✅ GPU acceleration enabled!"
echo "🌐 Web Interface: http://localhost/"
echo "🤖 Ollama API: http://localhost:11435"
echo ""
echo "💡 Your AI processing should now be 5-10x faster!"
