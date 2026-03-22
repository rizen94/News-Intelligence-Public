# Archived Docker stack (not in active use)

**Status:** Archived **2026-03** — the project’s **current path is bare metal**: `start_system.sh` / `restart_system.sh`, PostgreSQL on Widow (or NAS tunnel), local `.venv`, Vite on port 3000, uvicorn on 8000. Docker is **not** required for development or the home deployment described in `docs/ARCHITECTURE_AND_OPERATIONS.md`.

## Contents

| File | Origin |
|------|--------|
| `docker-compose.yml` | Repo root — illustrative postgres/api/nginx stack |
| `root.dockerignore` | Was `.dockerignore` at repo root |
| `api.Dockerfile` | `api/Dockerfile` |
| `api.Dockerfile.production` | `api/Dockerfile.production` |
| `web.Dockerfile` | `web/Dockerfile` |
| `docker-manage.sh` | `scripts/maintenance/docker-manage.sh` |
| `pi_docker_status.sh` | `scripts/pi_docker_status.sh` |
| `test_pipeline.sh.docker-legacy` | `tests/test_pipeline.sh` (Docker-based) |
| `my_docker.txt` | Local notes (if present) |
| `TROUBLESHOOTING_DOCKER_LEGACY.md` | Docker-only troubleshooting snippets |

To revive a container workflow, copy files back to their original paths and align env with bare-metal `DB_*` / API keys.

## Additional archived scripts (same folder)

| File | Was |
|------|-----|
| `monitor.sh.docker-legacy` | `scripts/monitor.sh` |
| `start_production_ml.sh.docker-legacy` | `scripts/start_production_ml.sh` |
| `hybrid_dev_prod_system.sh` | `development/scripts/hybrid_dev_prod_system.sh` |
| `quick_fix_startup.sh` | `development/scripts/quick_fix_startup.sh` |
