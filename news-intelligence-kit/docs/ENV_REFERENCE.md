# Environment reference (kit)

Copy `.env.template` to `.env` on first install. `install.sh` generates `DB_PASSWORD`.

## Required

| Variable | Default | Purpose |
|----------|---------|---------|
| `DB_HOST` | `postgres` | Postgres service name in Compose |
| `DB_PORT` | `5432` | Postgres port |
| `DB_NAME` | `news_intel` | Database name |
| `DB_USER` | `newsapp` | Database user |
| `DB_PASSWORD` | *(generated)* | Database password |
| `OLLAMA_HOST` | `http://ollama:11434` | Ollama inside Compose |
| `NEWS_INTEL_KIT_MODE` | `true` | Enables kit patches and setup gate |
| `NRI_VAULT_PATH` | `/data/vault` | Vault mount in API container |

## Recommended

| Variable | Default | Purpose |
|----------|---------|---------|
| `OLLAMA_MODEL_PRIMARY` | `llama3.1:8b` | Main LLM |
| `OLLAMA_MODEL_EMBEDDING` | `nomic-embed-text` | Embeddings |
| `OLLAMA_MODEL_PHI` | `phi3.5:latest` | Fast/simple tasks |
| `KIT_HARDWARE_TIER` | `standard` | `minimal` / `standard` / `performance` — controls model pull set |
| `INTAKE_WEB_PORT` | `8080` | Host port for intake nginx |
| `OPENWEBUI_PORT` | `3001` | Host port for Open WebUI |
| `NEWS_INTEL_DISABLE_AUTOMATION` | `true` until setup | Set `false` via `enable_automation.sh` after setup |
| `NEWS_INTEL_DEFAULT_DOMAIN_FALLBACK` | *(empty)* | No politics fallback in kit mode |

## Optional tuning

| Variable | Purpose |
|----------|---------|
| `DB_POOL_UI_MAX` | UI connection pool cap |
| `DB_POOL_WORKER_MAX` | Worker pool cap |
| `OLLAMA_TIMEOUT` | LLM request timeout seconds |
| `NEWS_INTEL_FORCE_AUTOMATION` | Start automation even if setup incomplete (debug) |
| `AUTOMATION_DISABLED_SCHEDULES` | Comma-separated phases to skip |

## Not needed in kit

These appear in the full NI `configs/env.example` but are **omitted or unused** in the portable kit:

| Variable | Reason |
|----------|--------|
| `OLLAMA_POP_OS_HOST` | Single-host; no PopOS GPU handoff |
| `REDIS_*` | Optional; LLM cache off by default |
| `NEWS_INTEL_DEMO_*` | Public demo mode not bundled |
| `JWT_*` / `NEWS_INTEL_PUBLIC_WEB_AUTH` | Local kit; auth disabled on Open WebUI |
| `AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE` | Widow cron split not used |
| Multi-host DB tunnel vars | Kit uses local Postgres volume |

Full upstream reference: `configs/env.example` in the parent News Intelligence repo.
