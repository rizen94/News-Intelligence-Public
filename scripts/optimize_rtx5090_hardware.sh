#!/bin/bash

# RTX 5090 Hardware Optimization Script
# Optimizes Ollama for maximum GPU utilization on RTX 5090 (32GB VRAM)

echo "🚀 RTX 5090 HARDWARE OPTIMIZATION"
echo "=================================="
echo "Optimizing for 32GB VRAM utilization"
echo ""

# Check current GPU status
echo "1. Current GPU Status:"
nvidia-smi --query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu --format=csv,noheader,nounits
echo ""

# Check current Ollama processes
echo "2. Current Ollama Processes:"
ps aux | grep ollama | grep -v grep
echo ""

# Stop Ollama service
echo "3. Stopping Ollama service..."
sudo systemctl stop ollama
sleep 3

# Create optimized environment file
echo "4. Creating optimized environment configuration..."
sudo tee /etc/systemd/system/ollama.service.d/override.conf > /dev/null << 'EOF'
[Service]
Environment="OLLAMA_NUM_PARALLEL=8"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_GPU_LAYERS=80"
Environment="OLLAMA_MMAP=1"
Environment="OLLAMA_KEEP_ALIVE=24h"
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_ORIGINS=*"
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_GPU_MEMORY_FRACTION=0.95"
EOF

# Reload systemd and start Ollama
echo "5. Reloading systemd and starting Ollama with optimized settings..."
sudo systemctl daemon-reload
sudo systemctl start ollama
sleep 5

# Wait for Ollama to fully start
echo "6. Waiting for Ollama to initialize..."
for i in {1..30}; do
    if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
        echo "   ✅ Ollama is ready"
        break
    else
        echo "   ⏳ Waiting for Ollama... ($i/30)"
        sleep 2
    fi
done

# Check GPU utilization after optimization
echo ""
echo "7. GPU Utilization After Optimization:"
nvidia-smi --query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu --format=csv,noheader,nounits

# Test model performance
echo ""
echo "8. Testing 70b Model Performance..."
echo "   Sending test request (this may take 30-60 seconds)..."

start_time=$(date +%s)
timeout 120 ollama run llama3.1:70b "Hello, how are you? Please respond briefly." || echo "Model test timed out"
end_time=$(date +%s)
processing_time=$((end_time - start_time))

echo "   ⏱️  Processing time: ${processing_time} seconds"

# Check final GPU utilization
echo ""
echo "9. Final GPU Utilization:"
nvidia-smi --query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu --format=csv,noheader,nounits

# Check Ollama status
echo ""
echo "10. Ollama Service Status:"
sudo systemctl status ollama --no-pager -l

echo ""
echo "✅ RTX 5090 Hardware Optimization Complete!"
echo "   - GPU layers: 80 (maximum)"
echo "   - Parallel requests: 8"
echo "   - Memory mapping: enabled"
echo "   - Keep alive: 24 hours"
echo "   - Flash attention: enabled"
echo "   - GPU memory fraction: 95%"
echo ""
echo "Expected improvements:"
echo "   - Response time: 10-30 seconds (vs 60+ before)"
echo "   - GPU utilization: 60-80% (vs 1.4% before)"
echo "   - Parallel processing: 4-8 concurrent requests"
echo "   - Throughput: 10-20 articles/hour"
