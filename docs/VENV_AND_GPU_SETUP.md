# Virtual Environment and GPU Setup

**Last updated:** 2026-02-27

## Overview

News Intelligence uses `uv` for Python package management and a project-level `.venv` with:
- Python 3.10
- PyTorch with CUDA 12.8 (for GPU acceleration)
- All API dependencies from `pyproject.toml`

## Quick Start

```bash
# Activate environment (sets up paths, verifies GPU)
source activate.sh

# Or manually:
source .venv/bin/activate
```

## Prerequisites

- **NVIDIA driver 570+** (RTX 5090)
- **uv** (install: `curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Verification

```bash
# Full GPU and environment check
python scripts/verify_gpu.py

# Resource monitor (live GPU/RAM stats)
python scripts/resource_monitor.py

# LLM inference benchmark (requires Ollama running)
python scripts/benchmark_inference.py
```

## Resource Manager

The `ResourceManager` (`api/shared/llm/resource_manager.py`) tracks GPU and RAM usage per workload:

- **BATCH_PROCESSING** — RSS, entity extraction, topic clustering
- **REAL_TIME** — Quick summaries, API responses
- **REPORT_GENERATION_*** — Future expanded report features
- **IDLE** — No models loaded

Use before loading large models to avoid OOM:

```python
from shared.llm.resource_manager import ResourceManager, WorkloadProfile

rm = ResourceManager()
can_run, reason = rm.validate_workload(WorkloadProfile.BATCH_PROCESSING)
if can_run:
    rm.switch_workload(WorkloadProfile.BATCH_PROCESSING)
```

## Adding Dependencies

```bash
source activate.sh
uv pip install <package>
uv pip freeze > requirements.lock
```

## CUDA Toolkit (Optional)

For compiling `llama-cpp-python` with CUDA support:
- Install CUDA 12.8+ from NVIDIA
- Set `CUDA_HOME=/usr/local/cuda` and add to PATH
- `CMAKE_ARGS="-DGGML_CUDA=on" uv pip install llama-cpp-python --no-cache-dir`

News Intelligence uses Ollama (pre-built) for LLM inference, so the toolkit is optional.

**Optional GPU container setup:** Detailed steps for NVIDIA Container Toolkit and Docker GPU mode were in `GPU_SETUP.md`; that doc is in `docs/_archive/GPU_SETUP.md` for reference.
