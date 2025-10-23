#!/bin/bash
# One-command GPU acceleration setup for News Intelligence System

echo "🚀 Setting up GPU acceleration for News Intelligence System"
echo "=========================================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ This script needs sudo privileges to install NVIDIA Container Toolkit"
    echo "   Please run: sudo ./setup_gpu_acceleration.sh"
    exit 1
fi

echo "📦 Step 1: Installing NVIDIA Container Toolkit..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt update
apt install -y nvidia-container-toolkit

echo "📦 Step 2: Configuring Docker for GPU support..."
nvidia-ctk runtime configure --runtime=docker

echo "📦 Step 3: Restarting Docker daemon..."
systemctl restart docker

echo "📦 Step 4: Enabling GPU mode in News Intelligence System..."
cd /home/pete/Documents/projects/Projects/News\ Intelligence

# Stop current system
docker-compose down

# Enable GPU configuration
sed -i '/# GPU Configuration/,/# End GPU Configuration/s/^#//' docker-compose.yml

# Start with GPU support
docker-compose up -d

echo "⏳ Waiting for services to initialize..."
sleep 15

echo "🔍 Verifying GPU acceleration..."
echo ""
echo "Container Status:"
docker-compose ps

echo ""
echo "GPU Usage:"
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader,nounits

echo ""
echo "Ollama Model Status:"
docker exec news-intelligence-ollama ollama list

echo ""
echo "✅ GPU acceleration setup complete!"
echo "🌐 Web Interface: http://localhost/"
echo "🤖 Ollama API: http://localhost:11435"
echo ""
echo "💡 Your AI processing should now be 5-10x faster!"
