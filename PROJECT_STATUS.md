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

## Database

- **Canonical database:** `news_intel` on Widow `localhost:5432`
- **User:** `newsapp` (password in Widow `configs/.env` or `.db_password_widow`)
- **Homelab Postgres MCP** on PopOS reads this DB read-only via `NEWS_INTEL_DATABASE_URI` — it is **not** the Homelab local Postgres on `:15432`

## Production vs dev tree

Production runs from `/opt/news-intelligence` via **`news-intelligence-api-public.service`** (enabled June 2026). Sync dev → prod before deploys; restart with `sudo systemctl restart news-intelligence-api-public`. See [docs/WIDOW_BOOT_RESILIENCE.md](docs/WIDOW_BOOT_RESILIENCE.md).

**Dev fix ≠ prod fix** until `./scripts/deploy_to_widow.sh` completes successfully (migrations 196/231/232, schema audit, API restart, smoke curls). Editorial lede backfill after deploy: `PYTHONPATH=api python3 api/scripts/backfill_editorial_ledes.py`.

## Cold storage handoff checklist

Complete before removing the PopOS local copy:

1. [ ] Obsidian vault notes updated ([`/mnt/obsidian-vault`](../News%20Intelligence.COLD_STORAGE.md))
2. [ ] MemPalace drawers updated and searchable
3. [ ] Homelab docs reference Widow (not local NI path)
4. [ ] Final doc rsync to Widow complete
5. [ ] `rsync` PopOS folder to `/mnt/nas/News-Intelligence-Archive-2026-06-03`
6. [ ] Verify NAS copy; remove PopOS local folder
7. [ ] Leave stub: [`../News Intelligence.COLD_STORAGE.md`](../News%20Intelligence.COLD_STORAGE.md)

## Related docs

- [WIDOW_SERVER_MIGRATION_2026_06.md](docs/WIDOW_SERVER_MIGRATION_2026_06.md) — migration record (completed)
- [ARCHITECTURE_AND_OPERATIONS.md](docs/ARCHITECTURE_AND_OPERATIONS.md) — current architecture
- [PROJECT_BOUNDARIES.md](../PROJECT_BOUNDARIES.md) — NI vs HomeLab split (monorepo level)
- [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md) — documentation index
