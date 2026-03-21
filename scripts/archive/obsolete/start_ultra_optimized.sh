#!/bin/bash

# Ultra-Optimized News Intelligence System Startup
# RTX 5090 + 62GB RAM Maximum Performance

echo "🚀 ULTRA-OPTIMIZED NEWS INTELLIGENCE SYSTEM"
echo "==========================================="
echo "RTX 5090 + 62GB RAM Maximum Performance"
echo "Started at: $(date)"
echo ""

# Load ultra-optimized configuration
source ~/.config/ollama/ollama.env

# Set environment variables
export CUDA_VISIBLE_DEVICES=0
export OMP_NUM_THREADS=24
export MKL_NUM_THREADS=24

# Start Docker services
echo "Starting Docker services..."
docker-compose up -d

# Wait for services
sleep 10

# Start Ollama with ultra-optimization
echo "Starting ultra-optimized Ollama..."
nohup ollama serve > /tmp/ollama_ultra.log 2>&1 &

# Wait for Ollama
sleep 15

# Verify system
echo "System Status:"
echo "Memory: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
echo "GPU: $(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)%"
echo "Ollama: $(curl -s http://localhost:11434/api/tags > /dev/null && echo 'Ready' || echo 'Not Ready')"

echo ""
echo "✅ ULTRA-OPTIMIZED SYSTEM READY"
echo "==============================="
