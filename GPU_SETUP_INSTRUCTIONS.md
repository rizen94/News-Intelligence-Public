# 🚀 GPU Acceleration Setup Instructions

## ✅ **CURRENT STATUS**
- ✅ NVIDIA Drivers: Installed (570.172.08)
- ✅ CUDA: Available (12.8)
- ✅ GPU: RTX 5090 (32GB VRAM) - PERFECT!
- ❌ NVIDIA Container Toolkit: Not installed
- ❌ Docker GPU Support: Not configured

## 🔧 **REQUIRED STEPS (Run these commands)**

### **Step 1: Install NVIDIA Container Toolkit**
```bash
# Add NVIDIA repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install the toolkit
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker

# Restart Docker
sudo systemctl restart docker
```

### **Step 2: Enable GPU Mode**
```bash
# Navigate to project directory
cd /home/pete/Documents/projects/Projects/News\ Intelligence

# Stop current system
docker-compose down

# Enable GPU configuration (uncomment GPU section in docker-compose.yml)
sed -i '/# GPU Configuration/,/# End GPU Configuration/s/^#//' docker-compose.yml

# Start with GPU support
docker-compose up -d

# Verify GPU usage
nvidia-smi
```

## 🎯 **EXPECTED RESULTS**

**Before (CPU Mode):**
- Speed: ~15 tokens/second
- Memory: 8GB RAM
- Response: Slow

**After (GPU Mode):**
- Speed: ~75 tokens/second (5x faster!)
- Memory: 2GB VRAM + 2GB RAM
- Response: Much faster

## 🚀 **QUICK SETUP SCRIPT**

Run this single command to do everything:
```bash
sudo bash -c '
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed "s#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g" | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt update && apt install -y nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
echo "✅ NVIDIA Container Toolkit installed!"
'
```

Then run:
```bash
cd /home/pete/Documents/projects/Projects/News\ Intelligence
docker-compose down
sed -i "/# GPU Configuration/,/# End GPU Configuration/s/^#//" docker-compose.yml
docker-compose up -d
echo "🚀 GPU acceleration enabled!"
```
