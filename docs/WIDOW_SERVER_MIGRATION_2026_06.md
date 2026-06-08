# Widow Server Migration — Completed June 2026

**Status: COMPLETE AND FINAL**

The News Intelligence system has been migrated from the main (5090) server to Widow. The 5090 main server is retained for the 70B narrative finisher only. See [PROJECT_STATUS.md](../PROJECT_STATUS.md) for current host/path authority.

---

## Current architecture (post-migration)

| Host | IP | Role |
|------|-----|------|
| **Widow** | `192.168.93.101` | Full NI stack: API, frontend, Postgres, automation, local Ollama (8B, 7B, Phi-3.5, Mistral-Nemo) |
| **Main / NAS GPU** | `192.168.93.100` | Ollama 70B narrative finisher only — GPU offload for Widow |
| **PopOS dev machine** | `192.168.93.99` | HomeLab AI Stack only; NI local copy → NAS cold storage |
| **NAS** | CIFS `/mnt/nas` | Archives, backups, Obsidian vault |

### Widow paths

| Path | Purpose |
|------|---------|
| `/home/pete/Documents/projects/News Intelligence` | **Canonical dev workspace** |
| `/opt/news-intelligence` | **Production runtime** (API currently served from here) |
| `/home/pete/projects/News Intelligence` | **Deprecated duplicate** — do not use; archive/remove when convenient |

**Deploy note:** Reconcile dev tree → `/opt/news-intelligence` before production deploys to avoid drift.

### Ollama dual-host routing

| Server | Models | VRAM |
|--------|--------|------|
| **Widow (3060)** | `llama3.1:8b`, `qwen2.5:7b`, `phi3.5`, `mistral-nemo` | 5–9 GB |
| **Main (5090)** | `llama3.1:70b` (narrative finisher only) | 45+ GB |

Routing is handled by `api/shared/services/ollama_model_caller.py`:

| Invocation Kind | Model | Location |
|-----------------|-------|----------|
| `STORYLINE_NARRATIVE_FINISH` | Llama 70B | Main (`192.168.93.100`) |
| `REAL_TIME_UI` | Llama 8B | Widow |
| `BACKGROUND_BATCH` | Llama 8B | Widow |
| `STRUCTURED_EXTRACTION` | Qwen 7B | Widow |
| `FAST_SIMPLE` | Phi-3.5 | Widow |
| `LONG_SYNTHESIS` | Llama 8B | Widow (or Main) |

---

## Migration record (historical)

The steps below were executed during June 2026 migration.

### Phase 1: Backup creation (main server)

```bash
cd "/home/pete/Documents/projects/News Intelligence"
bash scripts/archive_for_migration.sh
bash scripts/backup_project_for_widow_migration.sh
bash scripts/backup_database_for_widow_migration.sh
ls -lh "/mnt/nas/Data Lake Storage/news-intelligence/migration-2026-06/"
```

### Phase 2: Widow preparation

- PostgreSQL, Python 3.11+ (`uv`), Node.js 18+, Ollama installed
- NAS mounted at `/mnt/nas`
- RTX 3060 verified (`nvidia-smi`)

### Phase 3: Restore on Widow

```bash
cd "/home/pete/Documents/projects/News Intelligence"
bash scripts/restore_news_intelligence_on_widow.sh
```

### Phase 4: Configuration (Widow `.env`)

```bash
SERVER_ROLE="widow"
SERVER_HOSTNAME="widow"
DB_HOST="localhost"
DB_PORT="5432"
OLLAMA_HOST="http://localhost:11434"
OLLAMA_DUAL_HOST_ROUTING_ENABLED="true"
OLLAMA_CPU_HOST="http://localhost:11434"
OLLAMA_GPU_HOST="http://192.168.93.100:11434"
```

### Phase 5: Verification

```bash
curl http://localhost:8000/api/system_monitoring/health
psql -h localhost -d news_intel -c "SELECT COUNT(*) FROM public.domains;"
ollama run llama3.1:8b "Test"
curl http://192.168.93.100:11434/api/tags
```

---

## Monitoring

```bash
# Widow resources
watch -n2 nvidia-smi
watch -n2 free -m

# Main server (70B only)
watch -n5 nvidia-smi

# API / automation
journalctl -u news-intelligence-widow -f
curl http://localhost:8000/api/system_monitoring/automation/status
```

## Troubleshooting

### 70B calls failing

```bash
curl http://192.168.93.100:11434/api/tags
ollama list | grep 70b
ping 192.168.93.100
```

### Database connection errors

```bash
pg_isready -h localhost -p 5432
psql -h localhost -d news_intel -c "SELECT count(*) FROM pg_stat_activity;"
```

### Ollama VRAM on Widow

```bash
nvidia-smi
ollama stop mistral-nemo
# Reduce concurrency: OLLAMA_CPU_CONCURRENCY="2" in .env
```

## Scripts reference

| Script | Purpose |
|--------|---------|
| `archive_for_migration.sh` | Archive unnecessary files |
| `backup_project_for_widow_migration.sh` | Compressed project backup |
| `backup_database_for_widow_migration.sh` | Database backup |
| `restore_news_intelligence_on_widow.sh` | Full restore to Widow |

## Notes

- **NAS backups:** `/mnt/nas/Data Lake Storage/news-intelligence/migration-2026-06/`
- **Database:** `localhost:5432/news_intel` on Widow
- **Access:** [WIDOW_DEVELOPMENT_MOUNT.md](WIDOW_DEVELOPMENT_MOUNT.md)

---

## Checklist (completed)

- [x] Archive unnecessary files on main server
- [x] Create project backup (tar.gz to NAS)
- [x] Create database backup (sql.gz to NAS)
- [x] Verify backups on NAS
- [x] Prepare Widow (PostgreSQL, Python, Node, Ollama)
- [x] Mount NAS on Widow
- [x] Run restore script on Widow
- [x] Verify API health on Widow
- [x] Test Ollama dual-host routing
- [x] Update DNS/hosts to point to Widow
- [x] Verify web frontend
- [x] Check automation is running
- [x] Monitor resources (VRAM, RAM, CPU)
- [x] Confirm 70B routing to main server works
- [x] Archive old main server installation
