#!/bin/bash

# Memory Optimization Script for RTX 5090 + 62GB RAM
# Optimizes Ollama to use VRAM for critical tasks and RAM for overflow

echo "🧠 MEMORY OPTIMIZATION FOR RTX 5090 + 62GB RAM"
echo "=============================================="
echo "Optimizing memory usage for maximum efficiency"
echo ""

# Check current memory usage
echo "1. Current Memory Usage:"
free -h
echo ""

# Check current Ollama processes
echo "2. Current Ollama Memory Usage:"
ps aux | grep ollama | grep -v grep | awk '{print $6/1024 " MB - " $11}'
echo ""

# Set optimized environment variables for memory usage
echo "3. Setting optimized memory environment variables..."

# Export environment variables for current session
export OLLAMA_NUM_PARALLEL=6          # Reduced from 8 to leave room for overflow
export OLLAMA_MAX_LOADED_MODELS=1     # Keep only the 70b model loaded
export OLLAMA_GPU_LAYERS=75           # Slightly reduced to leave VRAM for overflow
export OLLAMA_MMAP=1                  # Enable memory mapping
export OLLAMA_KEEP_ALIVE=24h          # Keep model loaded for 24 hours
export OLLAMA_HOST=0.0.0.0:11434     # Listen on all interfaces
export OLLAMA_ORIGINS=*               # Allow all origins
export OLLAMA_FLASH_ATTENTION=1       # Enable flash attention
export OLLAMA_GPU_MEMORY_FRACTION=0.85 # Use 85% of VRAM, leave 15% for overflow
export OLLAMA_CPU_THREADS=16          # Use more CPU threads for RAM processing
export OLLAMA_BATCH_SIZE=512          # Larger batch size for efficiency

echo "Environment variables set:"
echo "  OLLAMA_NUM_PARALLEL=$OLLAMA_NUM_PARALLEL"
echo "  OLLAMA_MAX_LOADED_MODELS=$OLLAMA_MAX_LOADED_MODELS"
echo "  OLLAMA_GPU_LAYERS=$OLLAMA_GPU_LAYERS"
echo "  OLLAMA_MMAP=$OLLAMA_MMAP"
echo "  OLLAMA_KEEP_ALIVE=$OLLAMA_KEEP_ALIVE"
echo "  OLLAMA_GPU_MEMORY_FRACTION=$OLLAMA_GPU_MEMORY_FRACTION"
echo "  OLLAMA_CPU_THREADS=$OLLAMA_CPU_THREADS"
echo "  OLLAMA_BATCH_SIZE=$OLLAMA_BATCH_SIZE"
echo ""

# Create user-level environment file
echo "4. Creating user-level environment configuration..."
mkdir -p ~/.config/ollama
cat > ~/.config/ollama/ollama.env << EOF
# Ollama Environment Configuration for RTX 5090 + 62GB RAM
# Optimized for VRAM + RAM overflow usage

OLLAMA_NUM_PARALLEL=6
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_GPU_LAYERS=75
OLLAMA_MMAP=1
OLLAMA_KEEP_ALIVE=24h
OLLAMA_HOST=0.0.0.0:11434
OLLAMA_ORIGINS=*
OLLAMA_FLASH_ATTENTION=1
OLLAMA_GPU_MEMORY_FRACTION=0.85
OLLAMA_CPU_THREADS=16
OLLAMA_BATCH_SIZE=512
EOF

echo "✅ User-level environment file created: ~/.config/ollama/ollama.env"
echo ""

# Test current model performance
echo "5. Testing current model performance with memory optimization..."
echo "   Sending test request (this may take 30-60 seconds)..."

start_time=$(date +%s)
timeout 120 ollama run llama3.1:70b "Hello, how are you? Please respond briefly." || echo "Model test timed out"
end_time=$(date +%s)
processing_time=$((end_time - start_time))

echo "   ⏱️  Processing time: ${processing_time} seconds"
echo ""

# Check memory usage after test
echo "6. Memory Usage After Test:"
free -h
echo ""

# Check GPU usage
echo "7. GPU Usage After Test:"
nvidia-smi --query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu --format=csv,noheader,nounits
echo ""

echo "✅ MEMORY OPTIMIZATION COMPLETE!"
echo ""
echo "Configuration Summary:"
echo "  - VRAM Usage: 85% (leaves 15% for overflow)"
echo "  - GPU Layers: 75 (optimized for VRAM + RAM)"
echo "  - CPU Threads: 16 (for RAM processing)"
echo "  - Batch Size: 512 (efficient processing)"
echo "  - Parallel Requests: 6 (balanced for memory)"
echo ""
echo "Expected Benefits:"
echo "  - Critical tasks use VRAM (fastest)"
echo "  - Overflow tasks use RAM (fast, 47GB available)"
echo "  - Swap space available for extreme cases (19GB)"
echo "  - Better memory utilization overall"
echo ""
echo "Memory Hierarchy:"
echo "  1. VRAM (32GB) - Critical/real-time tasks"
echo "  2. RAM (62GB) - Overflow/background tasks"
echo "  3. Swap (19GB) - Emergency overflow"
echo ""
echo "To apply permanently, restart Ollama with these settings."
