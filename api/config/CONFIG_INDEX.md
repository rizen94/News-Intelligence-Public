# Configuration index

| File | Purpose |
|------|---------|
| `api/config/runtime.py` | SSOT for `os.environ` reads; DB, investigation, Ollama host URLs |
| `api/config/settings.py` | Model names, resource limits, backward-compat shims to runtime |
| `api/config/database_targets.py` | DSN builders for news_intel and identity_spine |
| `api/config/investigation_tables.py` | Investigation table name constants |
| `api/config/paths.py` | Filesystem paths (data, logs, finance artifacts) |
| `api/config/schedulers.yaml` | Background scheduler intervals and rotation |
| `api/config/orchestrator_governance.yaml` | Pipeline phase governance rules |
| `api/config/context_centric.yaml` | Context-centric task toggles |
| `api/config/briefing_filters.yaml` | Briefing output filters |
| `api/config/domains/*.yaml` | Per-domain silo provisioning templates |

**Rules:** Application code imports env via `config.runtime` helpers. DB connections use `shared.database.connection` or `database_targets.*_dsn()`.
