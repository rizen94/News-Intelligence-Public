# Setup, environment, and runtime

**Purpose:** Single entry point for installation, Python/venv, GPU, Ollama, and day-to-day service startup.  
**Last updated:** March 2026

---

## Quick start

From the project root:

```bash
./start_system.sh          # API, frontend, checks Redis/DB as configured
./status_system.sh
./stop_system.sh
./restart_system.sh        # after .env changes (e.g. API keys)
```

- **Frontend:** typically `http://localhost:3000` (Vite dev) or your reverse proxy in production.
- **API:** `http://localhost:8000` — health: `/api/system_monitoring/health`.
- **Ollama:** `http://localhost:11434` (user-level `ollama serve` — see below).

---

## Requirements

- **PostgreSQL** reachable from the app (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` in project-root `.env`). See [DATABASE.md](DATABASE.md) and [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md).
- **Python 3.11+** recommended (Finance/Chroma/onnxruntime). Use **`uv`** and project **`.venv`**:
  ```bash
  uv sync
  source .venv/bin/activate   # or ./activate.sh if present
  ```
- **Node.js 16+** for `web/` (`npm install`, `npm run dev` / build).
- **Redis** — optional; host install if you use Redis features.
- **Ollama** — local LLM inference; models pulled to `~/.ollama/models`.
- **NVIDIA GPU** — optional; used for CUDA PyTorch workloads and Ollama GPU inference. Driver/CUDA per machine.

---

## Environment variables

1. Copy or merge from `configs/env.example` → project-root `.env`.
2. **Required for DB:** `DB_PASSWORD` (and usually `DB_HOST`, `DB_NAME`, `DB_USER`). Never commit `.env`.
3. **Optional:** `NEWS_API_KEY`, `FRED_API_KEY`, `OLLAMA_HOST`, finance keys — see `configs/env.example` and [_archive/retired_root_docs_2026_03/SOURCES_AND_EXPECTED_USAGE.md](_archive/retired_root_docs_2026_03/SOURCES_AND_EXPECTED_USAGE.md) (archived source inventory).
4. **Production / exposure:** see [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) — `NEWS_INTEL_ENV`, `NEWS_INTEL_CORS_ORIGINS`, `NEWS_INTEL_TRUSTED_HOSTS`, API docs toggles.

---

## Database and migrations

- Single connection module: `api/shared/database/connection.py`.
- Apply SQL migrations with `PYTHONPATH=api` and scripts under `api/scripts/` — see [api/database/migrations/README.md](../api/database/migrations/README.md) and [scripts/SCRIPTS_INDEX.md](../scripts/SCRIPTS_INDEX.md).
- Verify objects: `api/scripts/verify_migrations_160_167.py` (see script docstring).

Legacy step-by-step for `news_intelligence` vs `news_intel` names may appear in archived setup text; follow **DATABASE.md** and your actual `DB_NAME`.

---

## Finance / ChromaDB

ChromaDB (evidence embeddings) needs a **Python 3.11+** venv and successful `uv sync`. Data under `data/finance/chroma/`. Optional Chroma/RAG check script (archived): `scripts/archive/retired_scripts_2026_03/validate_finance_pipeline.py`.

---

## Ollama

- **Install:** user-level Ollama; **not** required to run in Docker for typical setups.
- **Start:** `ollama serve` (tune `OLLAMA_*` env vars per host; see [scripts/SCRIPTS_INDEX.md](../scripts/SCRIPTS_INDEX.md) and `api/scripts/refresh_ollama_models.py`):
  - `OLLAMA_NUM_PARALLEL`, `OLLAMA_MAX_LOADED_MODELS`, `OLLAMA_KEEP_ALIVE`, etc.
- **Models:** align tags with `api/config/settings.py` `MODELS` and `ollama pull`. Refresh weights: `PYTHONPATH=api uv run python api/scripts/refresh_ollama_models.py` (see [scripts/SCRIPTS_INDEX.md](../scripts/SCRIPTS_INDEX.md)).
- **Optional large model:** narrative finisher (~70B) — [_archive/retired_root_docs_2026_03/STORYLINE_70B_NARRATIVE_FINISHER.md](_archive/retired_root_docs_2026_03/STORYLINE_70B_NARRATIVE_FINISHER.md).

Full historical detail (storage sizes, extra commands): [_archive/consolidated/OLLAMA_SETUP.md](_archive/consolidated/OLLAMA_SETUP.md).

---

## GPU, venv, and thermal throttling

- **Venv / CUDA PyTorch:** use `uv` + `.venv`; verify GPU with `scripts/verify_gpu.py` if present.
- **ResourceManager:** `api/shared/llm/resource_manager.py` — workload profiles for batch vs real-time (see archived venv doc for examples).
- **Runtime behavior:** `api/shared/gpu_metrics.py` — health exposes GPU stats; `AutomationManager` throttles Ollama when GPU temp is high and caps concurrent Ollama tasks.

Tuning (temp threshold, concurrency) and migration-162 RSS/topic note: [_archive/consolidated/GPU_AND_OLLAMA_MANAGEMENT.md](_archive/consolidated/GPU_AND_OLLAMA_MANAGEMENT.md).

---

## Background services

The API process starts **AutomationManager** and related workers (RSS, ML phases, storyline automation, etc.). Intervals are configured in orchestration/automation code — not duplicated here to avoid drift.

---

## Logs

Typical locations: `logs/api_server.log`, `logs/frontend.log`, `logs/startup.log`; systemd `journalctl --user` if installed. See archived [SETUP_AND_DEPLOYMENT.md](_archive/consolidated/SETUP_AND_DEPLOYMENT.md) for Docker-oriented log commands.

---

## Production checklist (short)

- Build frontend: `cd web && npm run build`.
- Set **`NEWS_INTEL_ENV=production`** and tighten CORS/hosts (see [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md)).
- Disable public OpenAPI unless needed: default is off in production without `NEWS_INTEL_ENABLE_API_DOCS=true`.
- HTTPS at the reverse proxy; do not expose PostgreSQL or Ollama to the internet without tunnel/auth.

---

## Related docs

- [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md) — three-machine layout, Widow, scripts.
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md) — common failures.
- [NAS_LEGACY_AND_STORAGE.md](NAS_LEGACY_AND_STORAGE.md) — NAS rollback and storage.
- [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md) — frontend → API base URL.
- [VENV_AND_GPU_SETUP.md](_archive/consolidated/VENV_AND_GPU_SETUP.md) — archived full venv/GPU page.

---

## Superseded full copies (archive)

Detailed versions of this guide (merged here) live under `docs/_archive/consolidated/`:

- `SETUP_AND_DEPLOYMENT.md`
- `VENV_AND_GPU_SETUP.md`
- `OLLAMA_SETUP.md`
- `GPU_AND_OLLAMA_MANAGEMENT.md`
