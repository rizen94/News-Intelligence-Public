# Git ignore reference

**Source of truth:** project root [`.gitignore`](../.gitignore) and [`web/.gitignore`](../web/.gitignore).

This page explains **why** paths are ignored so you can add new patterns consistently. When you introduce a new secret file or generated tree, update the root `.gitignore` and extend this doc if the pattern is non-obvious.

---

## Root `.gitignore` (summary)

| Category | Patterns (representative) | Why |
|----------|---------------------------|-----|
| Data / DB | `db_data/`, `*.db`, `postgres_data/`, `redis_data/`, `.local/`, `data/` | Local databases, dumps, and runtime spill (e.g. `db_pending_writes`) must not enter Git. |
| Docker / volumes | `docker/data/`, `volumes/` | Ephemeral container state. |
| Python | `.venv/`, `.venv.backup/`, `__pycache__/`, `*.pyc`, `.coverage`, `htmlcov/`, `.pytest_cache/` | Environments and build/cache artifacts. |
| Secrets | `.env`, `.env.local`, `.env.production`, `configs/ddns.env`, `config/.secrets`, `api/config/.secrets`, `.db_password_widow` | Credentials and tokens. |
| Logs | `*.log`, `logs/`, `log/` | Runtime noise and possibly sensitive paths. |
| Temp | `temp/`, `tmp/`, `*.tmp`, `api/temp/` | Scratch space. |
| IDE / OS | `.vscode/`, `.idea/`, `.DS_Store`, `Thumbs.db` | Machine-specific. |
| Legacy assistant dirs | `.aider/`, patterns with `*aider*` | Old tooling; keep out of clones. |
| Backups | `backups/`, `*.backup`, `*.bak` | Large and often sensitive. |
| Node (repo-wide) | `node_modules/`, `npm-debug.log*` | JS dependencies and debug logs. |
| Large binaries / exports | `*.csv`, `models/`, `news-system-backup-*/`, `*.zip`, `*.tar`, `*.tar.gz`, `*.7z` | Size and noise. |
| **External archive** | `/archive/` | **Repo-root only** — huge or historical trees kept outside Git (does **not** match `api/database/migrations/archive/`). |
| Ops / local | `scripts/pi_reports/`, `infrastructure/*.local.json`, `infrastructure/migration-state.local.json`, `my_docker.txt`, `my_pihole.txt` | Machine-specific or secret-bearing state. |
| Doc privacy | `configs/doc_obfuscation.local.yaml`, `configs/doc_obfuscation.local.yml`, `docs/_local_expanded/` | Real LAN IPs after obfuscation expand. |

---

## `web/.gitignore`

| Category | Patterns | Why |
|----------|----------|-----|
| Dependencies | `/node_modules` | Installed packages. |
| Build output | `/build`, `/dist` | Vite production output (rebuild for deploy). |
| Vite cache | `/.vite` | Local dev cache. |
| Env | `.env.local`, `*.local` | Frontend env overrides. |

---

## Related

- [REPO_MAINTENANCE.md](REPO_MAINTENANCE.md) — commit practice, `.cursorignore`, where to put retired docs/scripts.
- [OBFUSCATION.md](OBFUSCATION.md) — placeholders and local mapping files (gitignored).
- [SECURITY_OPERATIONS.md](SECURITY_OPERATIONS.md) — never commit secrets; extend `.gitignore` when adding new secret filenames.
