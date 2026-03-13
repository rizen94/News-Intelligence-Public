# GPU Acceleration Setup Guide

**Last Updated**: December 2024  
**Status**: Optional Enhancement

---

## ✅ Current Status

**GPU Detected:** NVIDIA GeForce RTX 5090 (32GB VRAM)  
**NVIDIA Drivers:** Installed (570.172.08)  
**CUDA:** Available (12.8)  
**Current Mode:** CPU (NVIDIA Container Toolkit not installed)  
**System Status:** Production ready with CPU-accelerated Ollama

**Note:** The system works perfectly in CPU mode. GPU acceleration is optional and provides 5-10x faster inference.

---

## 🔧 Installation Steps

### Step 1: Install NVIDIA Container Toolkit

```bash
# Add NVIDIA Container Toolkit repository
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

# Install the toolkit
sudo apt update
sudo apt install -y nvidia-container-toolkit

# Configure Docker
sudo nvidia-ctk runtime configure --runtime=docker

# Restart Docker daemon
sudo systemctl restart docker
```

### Step 2: Enable GPU Configuration

**Option A: Manual Configuration**

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

**Option B: Automated Configuration**

```bash
# Navigate to project directory
cd "/home/pete/Documents/projects/Projects/News Intelligence"

# Stop current system
docker-compose down

# Enable GPU configuration (uncomment GPU section in docker-compose.yml)
sed -i '/# GPU Configuration/,/# End GPU Configuration/s/^#//' docker-compose.yml

# Start with GPU support
docker-compose up -d
```

### Step 3: Verify GPU Usage

```bash
# Check GPU status
nvidia-smi

# Verify Docker GPU support
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi

# Check Ollama is using GPU
docker exec news-intelligence-ollama nvidia-smi
```

---

## 🚀 Quick Setup Script

Run this single command to install everything:

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

Then enable GPU in docker-compose:

```bash
cd "/home/pete/Documents/projects/Projects/News Intelligence"
docker-compose down
sed -i "/# GPU Configuration/,/# End GPU Configuration/s/^#//" docker-compose.yml
docker-compose up -d
echo "🚀 GPU acceleration enabled!"
```

---

## 🎯 Performance Comparison

### CPU Mode (Current)
- **Model**: llama3.1:8b (4.9GB)
- **Inference Speed**: ~10-20 tokens/second
- **Memory Usage**: 8GB RAM
- **Status**: ✅ Production ready

### GPU Mode (After Setup)
- **Model**: llama3.1:8b (4.9GB)
- **Inference Speed**: ~50-100 tokens/second
- **Memory Usage**: 2GB VRAM + 2GB RAM
- **Performance Gain**: **5-10x faster inference!**
- **Status**: ✅ Production ready with enhanced performance

---

## 🔍 Troubleshooting

### GPU Not Detected
```bash
# Check NVIDIA drivers
nvidia-smi

# Verify CUDA
nvcc --version

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

### Container Not Using GPU
```bash
# Verify docker-compose.yml has GPU configuration uncommented
grep -A 5 "nvidia" docker-compose.yml

# Restart containers
docker-compose down
docker-compose up -d

# Check container GPU access
docker exec news-intelligence-ollama nvidia-smi
```

### Performance Issues
- Ensure GPU is not being used by other processes
- Check GPU temperature: `nvidia-smi`
- Verify model is loaded on GPU: Check Ollama logs
- Monitor VRAM usage: `watch -n 1 nvidia-smi`

---

## 📚 Related Documentation

- **Setup Guide**: `docs/SETUP_AND_DEPLOYMENT.md`
- **Ollama Setup**: `docs/OLLAMA_SETUP.md`
- **System Requirements**: `README.md`

---

## ✅ Verification Checklist

- [ ] NVIDIA drivers installed and working
- [ ] CUDA available
- [ ] NVIDIA Container Toolkit installed
- [ ] Docker GPU support configured
- [ ] GPU configuration enabled in docker-compose.yml
- [ ] Containers restarted with GPU support
- [ ] GPU usage verified with `nvidia-smi`
- [ ] Ollama using GPU for inference

---

*Last Updated: December 2024*  
*Status: Optional Enhancement*  
*Version: 1.0*

