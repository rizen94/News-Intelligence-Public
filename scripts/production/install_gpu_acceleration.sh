#!/bin/bash
# GPU Acceleration Installation Script for News Intelligence System
# Run this script with sudo to enable GPU acceleration

echo "🚀 Installing NVIDIA Container Toolkit for GPU Acceleration"
echo "=========================================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Please run this script with sudo:"
    echo "   sudo ./install_gpu_acceleration.sh"
    exit 1
fi

echo "📦 Step 1: Adding NVIDIA Container Toolkit repository..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

echo "📦 Step 2: Installing NVIDIA Container Toolkit..."
apt update
apt install -y nvidia-container-toolkit

echo "📦 Step 3: Configuring Docker for GPU support..."
nvidia-ctk runtime configure --runtime=docker

echo "📦 Step 4: Restarting Docker daemon..."
systemctl restart docker

echo "✅ GPU acceleration installation complete!"
echo ""
echo "🎯 Next steps:"
echo "1. Run: ./enable_gpu_mode.sh"
echo "2. Restart your News Intelligence system"
echo "3. Enjoy 5-10x faster AI processing!"
