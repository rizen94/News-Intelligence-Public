#!/bin/bash

# Ultra-Optimized News Intelligence System Stop Script
# RTX 5090 + 62GB RAM Maximum Performance

echo "🛑 STOPPING ULTRA-OPTIMIZED NEWS INTELLIGENCE SYSTEM"
echo "=================================================="
echo "Stopped at: $(date)"
echo ""

# Stop Docker services
echo "Stopping Docker services..."
docker-compose down

# Stop Ollama with ultra-optimized cleanup
echo "Stopping ultra-optimized Ollama..."
pkill -f ollama
sleep 5

# Clean up ultra-optimized processes
echo "Cleaning up ultra-optimized processes..."
pkill -f "optimize_ollama_load_balancing" 2>/dev/null || true

# Display final status
echo "System Status:"
echo "Memory: $(free -h | grep Mem | awk '{print $3 "/" $2}')"
echo "GPU: $(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits)%"
echo "Ollama: $(ps aux | grep ollama | grep -v grep > /dev/null && echo 'Stopped' || echo 'Not Running')"

echo ""
echo "✅ ULTRA-OPTIMIZED SYSTEM STOPPED"
echo "================================="
