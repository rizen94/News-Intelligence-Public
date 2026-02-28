# Ollama AI Model Setup and Configuration

## 🎯 Current Implementation Status

**Last Updated**: December 2024  
**Status**: User-level installation (NOT Docker)

### Active Configuration
- **Installation Type**: User-level Ollama service
- **Storage Location**: `~/.ollama/models` (45GB)
- **Models Installed**: 3 models
  - `llama3.1:70b` - ~40GB on disk (70B parameters, optional for high-quality analysis)
  - `llama3.1:8b` - 4.6GB on disk (8B parameters, primary for most tasks)
  - `mistral:7b` - 262MB on disk (7B parameters, alternative)
- **Service**: Runs via `ollama serve` command
- **Port**: 11434 (default)

### Historical Note
The project previously used a Docker-based setup with `./ollama_data:/root/.ollama` mount, but this has been replaced with a user-level installation. The `ollama_data` directory in the project is an old/unused copy and can be removed.

---

## 📋 Configuration

### Service Startup
Ollama is started via system scripts:
- **`scripts/start_ollama_optimized.sh`** - **Recommended** - Exports optimal env vars, then `ollama serve`
- `scripts/start_production_ml.sh` - Production ML system startup (70b model)
- `scripts/production/start.sh` - Ultra-optimized startup
- `scripts/setup.sh` - Initial setup

Preferred: `./scripts/start_ollama_optimized.sh` (user-level, not Docker)

### Environment Variables (Recommended)
For optimized performance, use the startup script or export before `ollama serve`:
```bash
# Use the optimized startup script (recommended):
./scripts/start_ollama_optimized.sh

# Or export manually:
export OLLAMA_NUM_PARALLEL=3
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_KEEP_ALIVE=10m
export OLLAMA_MMAP=1
```
See `docs/OLLAMA_RESOURCE_ANALYSIS.md` for full analysis.

---

## 🔧 Verification Commands

### Check Ollama Status
```bash
# Check if Ollama is running
curl -s http://localhost:11434/api/tags > /dev/null && echo "Running" || echo "Not running"

# List installed models
ollama list

# Check service process
pgrep -f ollama
```

### Check Storage
```bash
# User installation storage
du -sh ~/.ollama/models

# Check individual models
ls -lh ~/.ollama/models/blobs/
```

### Test Model Availability
```bash
# Check available models via API
curl http://localhost:11434/api/tags | jq '.models[] | .name'

# Test model response
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Hello",
  "stream": false
}'
```

---

## 🚨 Important Requirements

### DO:
- ✅ Use user-level installation (`~/.ollama`)
- ✅ Start service with `ollama serve`
- ✅ Monitor disk usage for large models
- ✅ Verify persistence after system restarts
- ✅ Use environment variables for optimization

### DO NOT:
- ❌ Use Docker volumes for Ollama (causes persistence issues)
- ❌ Mount to `/home/user/.ollama` in Docker (conflicts with user installation)
- ❌ Use multiple storage locations (causes duplicates)
- ❌ Mix Docker and user-level installations

---

## 📊 Storage Management

### Current Storage
- **Active**: `~/.ollama/models` - 45GB
- **Unused**: `./ollama_data/` - 4.6GB (old Docker copy, can be removed)

### Model Sizes
| Model | Parameters | Disk Size | Use Case |
|-------|-----------|-----------|----------|
| llama3.1:70b | 70B | ~40GB | High-quality analysis (optional) |
| llama3.1:8b | 8B | 4.6GB | Primary for most tasks |
| mistral:7b | 7B | 262MB | Alternative / batch |

### Storage Recommendations
- Monitor disk space before downloading large models
- Use smaller models (8b) for development
- Use larger models (405b) for production analysis
- Consider moving models to NAS for shared access

---

## 🎯 Production Setup

### For Production Model (llama3.1:70b)
1. Ensure sufficient disk space (42GB+)
2. Download: `ollama pull llama3.1:70b-instruct-q4_K_M`
3. Verify: `ollama list`
4. Monitor storage: `du -sh ~/.ollama/models`

### Backup Strategy
- Model data stored in `~/.ollama/models`
- Can be backed up to NAS or external storage
- Version control friendly (exclude large model files in `.gitignore`)
- Easy to restore on new systems

---

## 🔄 Migration Notes

### From Docker to User-Level
The system migrated from Docker-based Ollama to user-level installation:
- **Old**: Docker container with `./ollama_data:/root/.ollama` mount
- **New**: User-level service with `~/.ollama/models` storage
- **Reason**: Simplified management, better persistence, no Docker conflicts

### Cleanup
- Old `ollama_data` directory can be safely removed (4.6GB duplicate)
- Docker volumes for Ollama have been removed
- All references updated to user-level installation

---

## ✅ Verification Checklist

- [x] Ollama service installed and accessible
- [x] Models persist across system restarts
- [x] Single storage location (`~/.ollama/models`)
- [x] No duplicate installations
- [x] Service starts automatically via scripts
- [x] API accessible on port 11434
- [x] Models available for ML pipeline

---

## 📚 Related Documentation

- **Resource Analysis**: `docs/OLLAMA_RESOURCE_ANALYSIS.md` - Model usage, num_predict, env vars
- **ML Processing**: `ML_PROCESSING_BREAKDOWN.md`
- **System Architecture**: `docs/V4_COMPLETE_ARCHITECTURE.md`
- **Deployment**: `docs/deployment/PRODUCTION_DEPLOYMENT_CHECKLIST.md`

