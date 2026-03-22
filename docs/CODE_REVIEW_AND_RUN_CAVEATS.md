# Code review and run caveats

**Purpose:** Set expectations for anyone **reading** or **trying to run** this repository on their own machine. This project is **not** a minimal demo app.

---

## Recommended: read-first path

You can understand most of the architecture **without** a running stack:

1. [README.md](../README.md) → [CODEBASE_MAP.md](CODEBASE_MAP.md) → [PIPELINE_AND_ORDER_OF_OPERATIONS.md](PIPELINE_AND_ORDER_OF_OPERATIONS.md)
2. [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md) + [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md)
3. Skim `api/main.py`, then `api/services/automation_manager.py` (schedules / phase names), then one domain under `api/domains/*/routes/`.

Optional: `uv sync` and static checks without PostgreSQL if your goal is only code navigation.

---

## If you want to run it: requirements (summary)

| Need | Why |
|------|-----|
| **PostgreSQL** | All app state; domain schemas + `intelligence`. |
| **Applied migrations** | Schema must match code; see [api/database/migrations/README.md](../api/database/migrations/README.md) and `api/scripts/`. |
| **`.env`** | At minimum `DB_PASSWORD` and correct `DB_HOST` / `DB_NAME` / `DB_USER` (see [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md)). |
| **Ollama** (for LLM features) | Local inference; model pulls are **large**. Configure `OLLAMA_HOST` if remote. |
| **Python 3.11+** | Recommended for dependencies (e.g. Finance/Chroma paths). **`uv sync`** from repo root. |
| **Node.js** | For `web/` — `npm install`, `npm run dev` or production build. |

Disk: clone + `.venv` + `node_modules` is typically **1–3+ GB**; Ollama models add **many GB**; the **database** grows with usage (see [_archive/retired_root_docs_2026_03/STORAGE_ESTIMATES_AND_OPTIMIZATION.md](_archive/retired_root_docs_2026_03/STORAGE_ESTIMATES_AND_OPTIMIZATION.md) for scale planning, archived, not a “demo minimum”).

GPU: **not strictly required** to browse code; for **continuous** operation with default automation, a capable **NVIDIA GPU** + Ollama is what the system is tested around. CPU-only Ollama is possible but slow and easy to overload.

---

## Why we do **not** recommend a casual “clone and run” (today)

- **Docker is archived** (not the default path): old Compose + Dockerfiles live under [`docs/archive/docker_stack/`](archive/docker_stack/README.md). The running API uses **`DB_*`** via [`api/shared/database/connection.py`](../api/shared/database/connection.py) on **bare metal** (`start_system.sh`).
- **Defaults target a lab setup** (e.g. DB host / tunnel behavior in connection helpers). You must **override env** for your network.
- **Automation is heavy**: many phases call **Ollama** and touch the DB on timers — weak laptops will struggle; you may need to tune or disable phases in governance config.
- **Multi-service reality**: RSS workers, NAS paths, and optional Redis may exist in ops docs; a minimal run still needs **Postgres + API + (optional) web + Ollama** thought through.
- **Secrets**: never commit `.env` or password files; see [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md).

---

## Multi-machine layout (optional)

The docs describe a **Primary + Widow (+ NAS)** pattern. Code only needs **TCP reachability**: set `DB_HOST`, optional `OLLAMA_HOST`, and storage env vars (e.g. `NEWS_INTEL_ARCHIVE_DIR`) appropriately. See [ARCHITECTURE_AND_OPERATIONS.md](ARCHITECTURE_AND_OPERATIONS.md).

---

## Where to ask next

- **Setup steps:** [SETUP_ENV_AND_RUNTIME.md](SETUP_ENV_AND_RUNTIME.md)
- **Security when exposing the API:** [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md)
- **Troubleshooting:** [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
