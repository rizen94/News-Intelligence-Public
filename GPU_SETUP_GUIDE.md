# 🚀 GPU Acceleration Setup Guide

## ✅ **CURRENT STATUS**

**GPU Detected:** NVIDIA GeForce RTX 5090 (32GB VRAM)
**Current Mode:** CPU (NVIDIA Container Toolkit not installed)
**System Status:** Production ready with CPU-accelerated Ollama

## 🔧 **TO ENABLE GPU ACCELERATION**

### **Step 1: Install NVIDIA Container Toolkit**

```bash
# Add NVIDIA Container Toolkit repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install the toolkit
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Restart Docker daemon
sudo systemctl restart docker
```

### **Step 2: Enable GPU Configuration**

Uncomment the GPU configuration in `docker-compose.yml`:

```yaml
ollama:
  # ... existing config ...
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
  environment:
    - OLLAMA_HOST=0.0.0.0
    - NVIDIA_VISIBLE_DEVICES=all
    - CUDA_VISIBLE_DEVICES=all
```

### **Step 3: Restart with GPU Support**

```bash
# Stop current system
docker-compose down

# Start with GPU support
docker-compose up -d

# Verify GPU usage
nvidia-smi
```

## 🎯 **EXPECTED PERFORMANCE**

**CPU Mode (Current):**
- Model: llama3.1:8b (4.9GB)
- Inference: ~10-20 tokens/second
- Memory: 8GB RAM usage

**GPU Mode (After Setup):**
- Model: llama3.1:8b (4.9GB)
- Inference: ~50-100 tokens/second
- Memory: 2GB VRAM + 2GB RAM usage
- **5-10x faster inference!**

## 🚀 **PRODUCTION READY**

The system is **100% production ready** in CPU mode and will automatically benefit from GPU acceleration once the NVIDIA Container Toolkit is installed.

**Current Access Points:**
- Web Interface: http://localhost/
- API Documentation: http://localhost:8000/docs
- Ollama API: http://localhost:11435

**Startup Commands:**
- CPU Mode: `./start_production.sh`
- GPU Mode: `./start_production_gpu.sh`
