# Machine Location Map — Local vs Production

> **Why this doc:** The repo contains target architecture docs and systemd/cron templates for Widow, but nothing clearly separates "what should be on Widow" from "what's running here on PopOS right now." This file is that reference. It stays current with deployment status so we don't forget what lives where.

---

## Quick Summary

| Machine | IP | Current Status |
|---------|-----|----------------|
| **PopOS** (this machine) | `192.168.93.99` | Development + HomeLab only — **API not yet deployed** |
| **Widow** (secondary) | `192.168.93.101` | **Target production host** — service templates in repo, not yet installed |
| **NAS** | `192.168.93.100` | Storage only (CIFS shares, backups) — no code execution |

---

## PopOS (`192.168.93.99`) — What Runs Here Today

### Actually deployed / running right now

| Component | How | Status |
|-----------|-----|--------|
| **HomeLab AI Stack** | Docker compose (`ai-lab-*` containers) | Active |
| **Caddy** (WAN entry point, TLS for both public hostnames) | `ai-lab-caddy` container | Active — routes to Widow via LAN |
| **Ollama** (70B inference) | Host Ollama on RTX 5090 (`:11434`) | Active — used as secondary LLM |
| **Dev workspace** | `/home/pete/Documents/projects/News Intelligence/` | Active — code lives here, edited locally |

### NOT deployed on PopOS (but repo exists here)

| Component | Should be on? | Notes |
|-----------|---------------|-------|
| **News Intelligence API** (`uvicorn :8000`) | No — target is Widow | Managed via systemd: `news-intel-api.service` and `news-intel-web.service` on PopOS; production runs on Widow via `news-intelligence.target`.|
| **PostgreSQL (NI)** | No — NI uses its own on Widow | HomeLab has separate Postgres (`:15432`) for Open WebUI only |
| **news-intelligence-api-public.service** | Not needed here — template exists in repo only | Install to `/etc/systemd/system/` only on Widow |

### What PopOS does for NI (infra role)

| Role | How |
|------|-----|
| Public HTTPS termination | Caddy proxies `news-intelligence-ag.duckdns.org` → Widow nginx LAN |
| 70B narrative finisher | Ollama on RTX 5090, accessed via `OLLAMA_POP_OS_HOST=http://192.168.93.99:11434` |

---

## Widow (`192.168.93.101`) — Target Production Host

### What should run here (target architecture)

| Component | Source in repo | Install method | Status on Widow |
|-----------|---------------|----------------|-----------------|
| **News Intelligence API** (uvicorn :8000, embeds AutomationManager/scheduler) | `infrastructure/news-intelligence-api-public.service` | `setup_widow_boot_stack.sh` or manual cp+systemctl | ❌ Not installed yet — templates only |
| **SPA frontend** (built React) | `web/dist/` | `deploy_public_demo_to_widow.sh` → `/var/www/news-intelligence/web/dist` | ❌ Not deployed |
| **nginx** (LAN backend, serves SPA + proxies /api/) | `nginx/widow-public-demo-site.conf.template` | Manual install to sites-available | ❌ Not installed |
| **PostgreSQL** (news_intel, :5432) | Native PG 16 on Widow | System service — should already be running | ? Unclear which instance |
| **Local Ollama** (8B-class, GTX 1080) | Native Ollama on Widow (:11434) | Service installed separately | ❓ Unknown status |
| **RSS secondary worker** (every 10 min) | `infrastructure/newsplatform-secondary.service` | setup_widow_boot_stack.sh | ❌ Not installed |
| **DB-adjacent cron** (every 15 min: syncs + flushes) | `infrastructure/widow-db-adjacent.cron` | setup_widow_boot_stack.sh → /etc/cron.d/ | ❌ Not installed |
| **Log archive cron** (daily) | `infrastructure/news-intelligence-log-archive.cron` | Same setup script | ❌ Not installed |
| **Weekly backup cron** | `infrastructure/news-intelligence-weekly-backup.cron` | Same setup script | ❌ Not installed |

### Deployment path to Widow production

```bash
# 1. SSH into Widow
ssh pete@192.168.93.101

# 2. Run the setup script (installs all systemd units + cron)
cd /home/pete/Documents/projects/News\ Intelligence
sudo ./scripts/setup_widow_boot_stack.sh

# 3. Verify everything booted correctly
sudo systemctl start news-intelligence.target
/opt/news-intelligence/scripts/verify_widow_boot.sh

# 4. Deploy the SPA frontend to nginx document root
./scripts/deploy_public_demo_to_widow.sh
```

---

## Deployment Artifacts Map (what's in repo vs what's installed)

### Systemd unit templates (in repo only — never run systemctl against these paths)

| File in repo | Installs to | Purpose | Needs on Widow? |
|-------------|-------------|---------|-----------------|
| `infrastructure/news-intelligence-api-public.service` | `/etc/systemd/system/` | Main API + AutomationManager | Required |
| `infrastructure/newsplatform-secondary.service` | `/etc/systemd/system/` | RSS collection worker | Required |
| `infrastructure/news-intelligence-boot-check.service` | `/etc/systemd/system/` | Post-reboot verification | Recommended |
| `infrastructure/widow-api-health-watchdog.service` + .timer | `/etc/systemd/system/` | Periodic health checks | Optional |
| `infrastructure/widow-disk-io-governor.service` + .timer | `/etc/systemd/system/` | USB root disk optimization | PopOS only |
| `infrastructure/news-intelligence-widow.service` (target) | `/etc/systemd/system/` | Groups API units together | Required (via PartOf) |

### Cron templates (in repo only — installed to /etc/cron.d/)

| File in repo | Installs to | Schedule | Purpose |
|-------------|-------------|----------|---------|
| `infrastructure/widow-db-adjacent.cron` | `/etc/cron.d/news-intelligence-widow-db` | Every 15 min | context_sync, entity_profile_sync, pending_db_flush |
| `infrastructure/news-intelligence-log-archive.cron` | `/etc/cron.d/news-intelligence-log-archive` | Daily | Archive logs to NAS |
| `infrastructure/news-intelligence-weekly-backup.cron` | `/etc/cron.d/news-intelligence-weekly-backup` | Weekly | DB backup rotation |
| `infrastructure/newsplatform-backup.cron` | `/etc/cron.d/newsplatform-backup` | Periodic | RSS worker backup |
| `infrastructure/cron.d/widow-daily-upgrade` | `/etc/cron.d/widow-daily-upgrade` | Daily | System update check |

### Service drop-in configs (in repo only)

| File in repo | Deployed with | Purpose |
|-------------|---------------|---------|
| `infrastructure/news-intelligence-api-public.service.d/memory.conf` | setup script → /etc/systemd/system/.../memory.conf | cgroup MemoryHigh/MemoryMax for API process |
| `infrastructure/news-intelligence-api-public.service.d/nonblocking-readiness.conf` | setup script → .../nonblocking-readiness.conf | Health check doesn't block boot |
| `infrastructure/journald-widow-usb-root.conf` | setup script → /etc/systemd/journald.conf.d/ | journald caps for USB root writes (PopOS only) |

---

## Current State — as of 2026-10-30

### What is actually running right now

| Component | Host | How started |
|-----------|------|-------------|
| HomeLab API (uvicorn) | PopOS :8000 | Dev uses `./start_system.sh`; production systemd on Widow (`news-intelligence-api-public.service`).
| Ollama proxy (ai-lab-ollama-proxy) | PopOS Docker container | Docker compose |
| Postgres (HomeLab) | PopOS :15432 (`ai-lab-postgres`) | Docker compose |

### What is NOT running (but should be for full production)

| Component | Where it should run | Why missing |
|-----------|---------------------|-------------|
| News Intelligence API as systemd service | Widow (:8000) | `setup_widow_boot_stack.sh` never executed on Widow; `/opt/news-intelligence/` doesn't exist |
| SPA frontend deployed to Widow nginx | Widow (`/var/www/news-intelligence/`) | `deploy_public_demo_to_widow.sh` never run |
| RSS secondary worker (every 10 min) | Widow systemd service | Setup script not run |
| DB-adjacent cron jobs (every 15 min) | Widow `/etc/cron.d/` | Not installed via setup script |
| Automated boot verification | Widow boot-check.service | Template exists but not enabled |

### The gap in one sentence

> **The target architecture says everything runs on Widow, but the Widow systemd services and cron jobs have never been deployed — only the templates exist in the repo.** PopOS holds the codebase (development) plus HomeLab infrastructure (Caddy, Ollama 70B, docker compose). The API is only running ad-hoc via manual `uvicorn` commands.

---

## Maintenance Rules

1. **After any deployment change**, update this doc and mark the status column as ✅ or ❌.
2. **When moving components between machines**, update both the "What Runs Here Today" table and the "Deployment Artifacts Map."
3. **Never assume Widow services are running** — check `sudo systemctl list-unit-files \| grep news-intelligence` before writing docs that say "the API does X on schedule."
4. **This doc takes priority** over any other architecture doc when there's a conflict between target design and actual state.

---

*Last updated: 2026-10-30 — created to prevent repeating the confusion of assuming Widow services are deployed when they only exist as templates.*
