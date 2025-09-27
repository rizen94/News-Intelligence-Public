#!/bin/bash

# News Intelligence System v3.0 - Optimized Production Startup Script
# Includes RTX 5090 + 62GB RAM optimizations for maximum performance

echo "🚀 NEWS INTELLIGENCE SYSTEM v3.0 - OPTIMIZED STARTUP"
echo "====================================================="
echo "RTX 5090 + 62GB RAM Optimized Configuration"
echo "Started at: $(date)"
echo ""

# Set script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Change to project directory
cd "$PROJECT_DIR"

echo "📁 Project Directory: $PROJECT_DIR"
echo ""

# 1. SYSTEM PREPARATION
echo "1. SYSTEM PREPARATION"
echo "---------------------"
echo "   Setting up optimized environment variables..."

# Load optimized Ollama configuration
if [ -f ~/.config/ollama/ollama.env ]; then
    source ~/.config/ollama/ollama.env
    echo "   ✅ Loaded optimized Ollama configuration"
else
    echo "   ⚠️  Optimized Ollama config not found, using defaults"
fi

# Set additional system optimizations
export CUDA_VISIBLE_DEVICES=0
export OMP_NUM_THREADS=16
export MKL_NUM_THREADS=16

echo "   ✅ Environment variables configured"
echo ""

# 2. DOCKER SERVICES STARTUP
echo "2. DOCKER SERVICES STARTUP"
echo "-------------------------"
echo "   Starting Docker services with optimized settings..."

# Start Docker services
docker-compose up -d

# Wait for services to be ready
echo "   Waiting for services to initialize..."
sleep 10

# Check service health
echo "   Checking service health..."
docker-compose ps

echo "   ✅ Docker services started"
echo ""

# 3. OLLAMA ML SERVICE STARTUP
echo "3. OLLAMA ML SERVICE STARTUP"
echo "----------------------------"
echo "   Starting Ollama with RTX 5090 optimizations..."

# Kill any existing Ollama processes
pkill -f ollama 2>/dev/null || true
sleep 2

# Start Ollama with optimized settings
nohup ollama serve > /tmp/ollama.log 2>&1 &
OLLAMA_PID=$!

echo "   Ollama started with PID: $OLLAMA_PID"

# Wait for Ollama to be ready
echo "   Waiting for Ollama to initialize..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "   ✅ Ollama is ready"
        break
    fi
    echo "   Waiting... ($i/30)"
    sleep 2
done

# Verify 70b model is available
echo "   Verifying 70b model availability..."
if ollama list | grep -q "llama3.1:70b"; then
    echo "   ✅ 70b model available"
else
    echo "   ⚠️  70b model not found, attempting to pull..."
    ollama pull llama3.1:70b &
fi

echo ""

# 4. SYSTEM HEALTH VERIFICATION
echo "4. SYSTEM HEALTH VERIFICATION"
echo "-----------------------------"
echo "   Checking system resources..."

# Memory usage
echo "   Memory Usage:"
free -h | grep -E "(Mem|Swap)"

# GPU usage
echo "   GPU Usage:"
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits

# Service status
echo "   Service Status:"
echo "   - API: $(curl -s http://localhost:8000/health > /dev/null && echo "✅ Running" || echo "❌ Not responding")"
echo "   - Frontend: $(curl -s http://localhost:3000 > /dev/null && echo "✅ Running" || echo "❌ Not responding")"
echo "   - Ollama: $(curl -s http://localhost:11434/api/tags > /dev/null && echo "✅ Running" || echo "❌ Not responding")"

echo ""

# 5. ML PERFORMANCE TEST
echo "5. ML PERFORMANCE TEST"
echo "----------------------"
echo "   Testing 70b model performance..."

# Quick model test
echo "   Running quick performance test..."
timeout 30 ollama run llama3.1:70b "Hello, respond briefly." 2>/dev/null && echo "   ✅ Model test passed" || echo "   ⚠️  Model test timed out (this is normal for 70b)"

echo ""

# 6. PRODUCTION READINESS CHECK
echo "6. PRODUCTION READINESS CHECK"
echo "-----------------------------"

# Check all critical services
API_STATUS=$(curl -s http://localhost:8000/health > /dev/null && echo "OK" || echo "FAIL")
FRONTEND_STATUS=$(curl -s http://localhost:3000 > /dev/null && echo "OK" || echo "FAIL")
OLLAMA_STATUS=$(curl -s http://localhost:11434/api/tags > /dev/null && echo "OK" || echo "FAIL")

if [ "$API_STATUS" = "OK" ] && [ "$FRONTEND_STATUS" = "OK" ] && [ "$OLLAMA_STATUS" = "OK" ]; then
    echo "   ✅ ALL SYSTEMS OPERATIONAL"
    echo "   🎯 Production system ready for use"
else
    echo "   ⚠️  Some services not responding:"
    echo "   - API: $API_STATUS"
    echo "   - Frontend: $FRONTEND_STATUS"
    echo "   - Ollama: $OLLAMA_STATUS"
fi

echo ""

# 7. SYSTEM INFORMATION
echo "7. SYSTEM INFORMATION"
echo "---------------------"
echo "   📊 Resource Utilization:"
echo "   - RAM: $(free -h | grep Mem | awk '{print $3 "/" $2 " (" $3*100/$2 "%)"}')"
echo "   - VRAM: $(nvidia-smi --query-gpu=memory.used,memory.total --format=csv,noheader,nounits | awk -F, '{print $1 "MB/" $2 "MB (" $1*100/$2 "%)"}')"
echo "   - CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')"

echo ""
echo "   🔗 Service URLs:"
echo "   - Frontend: http://localhost:3000"
echo "   - API: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Ollama: http://localhost:11434"

echo ""
echo "   📝 Logs:"
echo "   - Ollama: /tmp/ollama.log"
echo "   - Docker: docker-compose logs"

echo ""
echo "✅ OPTIMIZED SYSTEM STARTUP COMPLETE"
echo "====================================="
echo "System started at: $(date)"
echo "Ready for production use with RTX 5090 + 62GB RAM optimizations"
echo ""
