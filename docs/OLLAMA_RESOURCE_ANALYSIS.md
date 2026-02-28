# Ollama Model and System Resource Usage Analysis

**Date:** February 2025  
**Purpose:** Ensure effective use of available resources (CPU/GPU/RAM)

---

## 1. Current Configuration Summary

### Models in Use
| Model | Disk Size | Use Case | Services |
|-------|-----------|----------|----------|
| `llama3.1:8b` | 4.6GB | Primary for most tasks | LLMService, TopicClustering, EntityExtractor, Summarization, etc. |
| `mistral:7b` | 262MB | Batch/alternative | LLMService (batch processing) |
| `nomic-embed-text` | ~270MB | Embeddings | Event dedup, AI storyline discovery, RAG, Intelligence analysis |

### Hardware (from GPU_SETUP.md)
- **GPU:** NVIDIA RTX 5090 (32GB VRAM)
- **Current mode:** Documented as "CPU" — but user-level `ollama serve` typically auto-detects GPU when NVIDIA drivers are present
- **OLLAMA_SETUP typo:** `llama3.1:405b` listed — likely meant `llama3.1:70b` (405B params would be huge)

---

## 2. Identified Issues

### 2.1 Ollama Environment Variables Not Applied
`start_system.sh` (the main startup script) **does not**:
- Start Ollama
- Export any `OLLAMA_*` environment variables

`scripts/start_production_ml.sh` sets useful vars but is a separate script:
```bash
OLLAMA_NUM_PARALLEL=4
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_GPU_LAYERS=80
OLLAMA_MMAP=1
```

**Impact:** When Ollama runs via `ollama serve` alone, it uses defaults (e.g. `OLLAMA_NUM_PARALLEL=1`), underutilizing the GPU.

### 2.2 `num_predict` Inconsistency
Different services request different max token outputs:

| Service | num_predict | Typical Need |
|---------|-------------|--------------|
| Topic clustering | 1500 | ~100–200 (2–5 topics) |
| LLMService | 2000 | Variable |
| Entity extractor | 1000 | ~200–400 |
| AI storyline discovery | 100 | Reasonable |
| Sentiment / trend / readability | 500–800 | Often sufficient |
| Deep content synthesis | 2000 | Legitimate for long synthesis |

**Impact:** Higher `num_predict` increases latency and memory; many tasks don’t need 1500–2000.

### 2.3 No Explicit Context Size
None of the API calls pass `num_ctx`. Ollama defaults (often 2048–4096) are used.

**Impact:** For long-article synthesis, context may be truncated. For topic extraction (2000 chars input), default is fine.

### 2.4 Concurrency / Parallelism
- **Topic extraction queue:** Sequential processing (one article per LLM call)
- **AutomationManager:** `max_concurrent_tasks=5` (but Ollama is single-process by default)
- **OLLAMA_NUM_PARALLEL:** 4 in production script — enables 4 concurrent inferences if set

**Impact:** With `OLLAMA_NUM_PARALLEL=1` (default), parallel API requests are serialized by Ollama.

### 2.5 Embedding Model
`nomic-embed-text` is used for embeddings — appropriate and efficient.

---

## 3. Recommendations

### 3.1 Apply Ollama Environment Variables on Startup
Create an Ollama startup wrapper or add env vars before `ollama serve`. Suggested settings for RTX 5090 (32GB):

```bash
export OLLAMA_NUM_PARALLEL=3          # 3 concurrent requests
export OLLAMA_MAX_LOADED_MODELS=1      # One model in VRAM
export OLLAMA_KEEP_ALIVE=10m          # Keep model loaded 10 min (reduce reloads)
export OLLAMA_MMAP=1                  # Memory-map for lower RAM
# GPU: Ollama auto-uses GPU; OLLAMA_GPU_LAYERS only needed for CPU/GPU split
```

For hybrid CPU/GPU (if ever needed):
```bash
export OLLAMA_GPU_LAYERS=40            # Layers on GPU (8B model ~32 layers, so all on GPU)
```

### 3.2 Reduce `num_predict` Where Appropriate
- **Topic clustering:** 1500 → 500 (output is a short list)
- **Entity extractor:** 1000 → 500
- Keep 2000 for summarization / deep synthesis.

### 3.3 Set Explicit `num_ctx` for Long-Context Tasks
For services handling long articles (e.g. deep content synthesis), pass:
```python
"options": {
    "num_ctx": 8192,      # Or 4096 if RAM/VRAM constrained
    "num_predict": 2000,
    "temperature": 0.3
}
```

### 3.4 Integrate Ollama Start into Main Startup
Options:
1. In `start_system.sh`, before API start: export OLLAMA vars and optionally start Ollama if not running.
2. Add `scripts/start_ollama_optimized.sh` and document it as the preferred way to run Ollama.

### 3.5 Fix Documentation
- **OLLAMA_SETUP.md:** Correct `llama3.1:405b` → `llama3.1:70b` (or remove if not used)
- **entity_extractor.py:** Fix `available_models = ["llama3.1:8b", "llama3.1:405b"]` → `["llama3.1:8b", "llama3.1:70b"]` if 70b is intended

### 3.6 Verify GPU Usage
```bash
# While a request is in progress:
nvidia-smi

# Ollama logs (if running in terminal):
# Should mention "gpu" or GPU layer count
```

---

## 4. Quick Resource Check Commands

```bash
# Is Ollama using GPU?
nvidia-smi

# Current models loaded
curl -s http://localhost:11434/api/ps | jq

# Active requests
curl -s http://localhost:11434/api/ps

# Model info
ollama list
```

---

## 5. Summary

| Area | Current | Recommendation |
|------|---------|----------------|
| OLLAMA_* env vars | Not set by main startup | Export in startup or wrapper |
| num_predict | 1000–2000 across tasks | Lower to 500 for topic/entity |
| num_ctx | Default | Set 8192 for long-article synthesis |
| Parallelism | OLLAMA_NUM_PARALLEL=1 (default) | Set to 2–3 for throughput |
| Model typo | llama3.1:405b | Fix to 70b or remove |
| GPU | Possibly used (auto-detect) | Verify with nvidia-smi |
