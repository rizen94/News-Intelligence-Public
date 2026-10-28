# News Intelligence — Project Status

> **MIGRATION COMPLETE AND FINAL (June 2026)**  
> PopOS → Widow migration is done. **Do not develop on the PopOS local copy** — it is headed for NAS cold storage. All active development, queries, and operations belong on **Widow**.

---

## Where to work

| Item | Value |
|------|-------|
| **Authoritative host** | Widow — `192.168.93.101` |
| **Dev workspace (Widow)** | `/home/pete/Documents/projects/News Intelligence` |
| **Production runtime (Widow)** | `/opt/news-intelligence` (currently serving API on `:8000`; may drift from dev tree — sync before deploys) |
| **Deprecated duplicate (Widow)** | `/home/pete/projects/News Intelligence` — stale; do not use |
| **PopOS local copy** | `/home/pete/Documents/projects/News Intelligence` on this device — **cold storage only** after NAS move |
| **NAS cold storage** | `/mnt/nas/News-Intelligence-Archive-2026-06-03` |

## Access methods

- **VS Code Remote SSH:** `code --remote ssh-remote+widow` (see [docs/WIDOW_DEVELOPMENT_MOUNT.md](docs/WIDOW_DEVELOPMENT_MOUNT.md))
- **SSH:** `ssh widow` or `ssh pete@192.168.93.101`
- **SSHFS mount:** `./scripts/mount_widow_project.sh` (from PopOS, before cold storage)

## Host roles (post-migration)

| Host | IP | Role |
|------|-----|------|
| **Widow** | `192.168.93.101` | Full NI stack: API, frontend, Postgres (`news_intel`), automation, local Ollama (GTX 1080 8 GB) |
| **PopOS** | `192.168.93.99` | HomeLab AI Stack + **Caddy WAN entry** (`:80/:443`); Ollama **5090** for 70B offload |
| **NAS** | `192.168.93.100` (CIFS `/mnt/nas`) | Storage, backups, Obsidian vault — **no GPU, no Ollama** |

## Public URLs (June 2026)

| URL | Entry | Backend |
|-----|-------|---------|
| `https://news-intelligence-ag.duckdns.org` | PopOS **Caddy** → Widow nginx | NI SPA + API on Widow |
| `https://legion-agent.duckdns.org` | PopOS **Caddy** | Open WebUI |

See [docs/WIDOW_PUBLIC_STACK.md](docs/WIDOW_PUBLIC_STACK.md) and HomeLab [PUBLIC_HTTPS_ROUTING.md](../HomeLab-AI-Stack/docs/PUBLIC_HTTPS_ROUTING.md).

## Product surface (current)

| Surface | Status |
|---------|--------|
| **News default** | `https://news-intelligence-ag.duckdns.org/` broadsheet (`web/src/v2/`; Living context + Pull context); legacy `/v2/*` redirects |
| **Finance** | `/finance/*` |
| **Admin** | `/admin` |
| **Classic** | **Retired** — cold storage `archive/classic_web_ui/` (not mounted) |
| **Vault notes** | Obsidian SSOT for soft tags/wikilinks; PG mirror + context packs; fan-out/writer/tag sync automation |
| **Pull context** | `POST /api/reader/articles/{id}/pull-context` → executive brief from vault + RAG + article |

See [docs/VAULT_NOTES_AND_PULL_CONTEXT.md](docs/VAULT_NOTES_AND_PULL_CONTEXT.md) and [AGENTS.md](AGENTS.md).

## Database

- **Canonical database:** `news_intel` on Widow `localhost:5432`
- **User:** `newsapp` (password in Widow `configs/.env` or `.db_password_widow`)
- **Homelab Postgres MCP** on PopOS reads this DB read-only via `NEWS_INTEL_DATABASE_URI` — it is **not** the Homelab local Postgres on `:15432`

## Production vs dev tree

**Authoritative runtime:** Widow systemd unit **`news-intelligence-api-public`** with `WorkingDirectory=/opt/news-intelligence/api` (see [infrastructure/news-intelligence-api-public.service](infrastructure/news-intelligence-api-public.service)). The workspace tree (`/home/pete/Documents/projects/News Intelligence`) is the **edit surface only** until deploy.

**Deploy gates:** `./scripts/deploy_to_widow.sh` rsyncs to `/opt`, writes `BUILD_INFO` (git SHA + UTC time), runs schema audit/migrations, then `scripts/ensure_widow_api_runtime.sh` which stops ad-hoc workspace uvicorn on `:8000`, enables/restarts the unit, and **fails** if the listener cwd is not under `/opt/news-intelligence`. Restart failure fails the deploy (no `|| true`).

See [docs/WIDOW_BOOT_RESILIENCE.md](docs/WIDOW_BOOT_RESILIENCE.md). Editorial lede backfill after deploy: `PYTHONPATH=api python3 api/scripts/backfill_editorial_ledes.py`.

**Catchup:** AutomationManager owns continuous backlog drain. `run_major_backlog_catchup.py` is ops `--force` only — see [docs/PIPELINE_AND_AUTOMATION.md](docs/PIPELINE_AND_AUTOMATION.md).

## Cold storage handoff checklist

Complete before removing the PopOS local copy:

1. [ ] Obsidian vault notes updated ([`/mnt/obsidian-vault`](../News%20Intelligence.COLD_STORAGE.md))
2. [ ] MemPalace drawers updated and searchable — **partial (2026-10-08 audit)**; see below / [`docs/MEMPALACE_NI.md`](docs/MEMPALACE_NI.md)
3. [ ] Homelab docs reference Widow (not local NI path)
4. [ ] Final doc rsync to Widow complete
5. [ ] `rsync` PopOS folder to `/mnt/nas/News-Intelligence-Archive-2026-06-03`
6. [ ] Verify NAS copy; remove PopOS local folder
7. [ ] Leave stub: [`../News Intelligence.COLD_STORAGE.md`](../News%20Intelligence.COLD_STORAGE.md)

### MemPalace audit evidence (2026-10-08)

| Check | Result |
|-------|--------|
| Palace up | Yes — ~70k drawers; vector enabled (`mempalace_reconnect` OK) |
| Runtime brief rooms (`News Intelligence`) | Present: `watches` 10, `preferred_narratives` 16, `brief_diary` 10, `skip_list` 1; **no** `morning_brief` room listed |
| Curated decisions (`News Intelligence` / `decisions`) | 4 drawers incl. knowledge-loop intent (2026-10-08), quality bar, NRI unification |
| Widow host authority | KG: `News Intelligence` → `runs_on_server` / `migrated_to` Widow `192.168.93.101`; global search hits ADR + PROJECT_STATUS drawers under wing `news_intelligence` |
| Knowledge loop / materiality | Drawer readable by id; **global** search finds it; wing-filtered search on `News Intelligence` **fails** (`Error finding id`) |
| Wing hygiene | Split: `News Intelligence` (~90) vs `news_intelligence` (~5203 mined) vs stray `NewsIntelligence` / `News_Intelligence` (1 each) — agents must search carefully |

**Keep item 2 open** until wing-filtered search on `News Intelligence` works (or drawers are consolidated onto one canonical wing name used by `mempalace_brief_memory` / MCP).

## Related docs

- [WIDOW_SERVER_MIGRATION_2026_06.md](docs/WIDOW_SERVER_MIGRATION_2026_06.md) — migration record (completed)
- [ARCHITECTURE_AND_OPERATIONS.md](docs/ARCHITECTURE_AND_OPERATIONS.md) — current architecture
- [PROJECT_BOUNDARIES.md](../PROJECT_BOUNDARIES.md) — NI vs HomeLab split (monorepo level)
- [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md) — documentation index
- [docs/VAULT_NOTES_AND_PULL_CONTEXT.md](docs/VAULT_NOTES_AND_PULL_CONTEXT.md) — living vault + Pull context
