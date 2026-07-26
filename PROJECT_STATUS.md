# News Intelligence — Project Status

> **MIGRATION COMPLETE AND FINAL (June 2026)**
> PopOS → Widow migration is done. **Do not develop on the PopOS local copy** — it is headed for NAS cold storage. All active development, queries, and operations belong on **Widow**.

> **v10.1 in progress:** Active development on branch `release/10.1`. Production `/opt/news-intelligence` cuts over at tag `v10.1.0` only — no partial rsync during development. See [docs/UPGRADE_10.1.md](docs/UPGRADE_10.1.md).

---


## v11 cutover (Widow) — 2026-07-25

- Migrations **282–287** applied on Widow `news_intel` `:5432` and ledgered.
- Code + SPA deployed to `/opt/news-intelligence` and `/var/www/news-intelligence/web/dist`.
- Flags: packages on; `EDITORIAL_ROOM_LOOP_ENABLED=false`; `LEGACY_EDITORIAL_WRITERS_ENABLED=0`; collectors/appraisal **off**.
- Legacy seed: **52** packages / **2679** members / **31** draft `news_stories` (idempotent re-run creates 0).
- Repair during cutover: mig **287** allows `modal='system'` on packages/members/decisions (seed initially failed check constraint).
- API smoke: `/api/editorial/*`, registry domains (incl. neurodiversity corpus), monitoring overview + processing_progress OK.

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
| **Widow** | `192.168.93.101` | Full NI stack: API, frontend, Postgres (`news_intel`), PgBouncer (`:6432`), automation, local Ollama (GTX 1080 8 GB); dual routing to PopOS for 70B overflow |
| **PopOS** | `192.168.93.99` | HomeLab AI Stack + **Caddy WAN entry** (`:80/:443`); Ollama **5090** for 70B offload |
| **NAS** | `192.168.93.100` (CIFS `/mnt/nas`) | Storage, backups, Obsidian vault — **no GPU, no Ollama** |

## Public URLs (June 2026)

| URL | Entry | Backend |
|-----|-------|---------|
| `https://news-intelligence-ag.duckdns.org` | PopOS **Caddy** → Widow nginx | NI SPA + API on Widow |
| `https://legion-agent.duckdns.org` | PopOS **Caddy** | Open WebUI |

See [docs/WIDOW_PUBLIC_STACK.md](docs/WIDOW_PUBLIC_STACK.md) and HomeLab [PUBLIC_HTTPS_ROUTING.md](../HomeLab-AI-Stack/docs/PUBLIC_HTTPS_ROUTING.md).

## Database

- **Canonical database:** `news_intel` on Widow
- **Application connections:** PgBouncer **`localhost:6432`** (`DB_PORT=6432` in `/opt/news-intelligence/.env`)
- **Direct Postgres (migrations, psql admin):** **`localhost:5432`**
- **User:** `newsapp` (password in Widow `configs/.env` or `.db_password_widow`)
- **Homelab Postgres MCP** on PopOS reads this DB read-only via `NEWS_INTEL_DATABASE_URI` — it is **not** the Homelab local Postgres on `:15432`

## Active pipeline domains (June 2026)

All five registry domains are pipeline-active on Widow (no `PIPELINE_INCLUDE` / `PIPELINE_EXCLUDE` set):

| Domain key | Schema |
|------------|--------|
| `legal` | `legal` |
| `medicine` | `medicine` |
| `artificial-intelligence` | `artificial_intelligence` |
| `politics` | `politics` |
| `finance` | `finance` |

`science-tech` / `science_tech` schema **retired** (migration 212). Verify live state: `PYTHONPATH=api python3 scripts/verify_documentation_ground_truth.py`.

## NI + NRI unification (June 2026)

**Status: cutover complete** on branch `unification/big-bang`.

| Item | State |
|------|-------|
| Runtime | Single API (`news-intelligence-api-public`); `mention_resolution` automation phase |
| Package | `api/nri_core/` in-process; `/api/investigation/*` only |
| Schema | `intelligence.investigation_*` tables; `USE_INVESTIGATION_PREFIXED_TABLES=true` |
| Retired | `nri-api`, `nri-mention-resolver.timer`, `nri-loop.timer` disabled |
| Verify | `scripts/verify_unification_cutover.sh` — PASS on Widow prod |

Post-cutover bake (complete June 2026): `nri` schema dropped; `/api/nri/*` shims removed; Homelab MCP prompts use `intelligence.investigation_*`; env reads migrated to `config.runtime` for runtime code. See [docs/UNIFICATION_CUTOVER.md](docs/UNIFICATION_CUTOVER.md).

## Unified intake cutover (June 2026)

**Status: deployed on Widow prod** (`UNIFIED_INTAKE_EXTRACTION_ENABLED=true`, `LEGACY_INTAKE_EXTRACTION_ENABLED=false`).

| Entity extraction robustness | Improved JSON parsing with repair/retry mechanisms; topic extraction uses fast NER fallback |

Docs: [docs/PIPELINE_AND_AUTOMATION.md](docs/PIPELINE_AND_AUTOMATION.md), [docs/MONITOR_REPORTING_AND_METRICS.md](docs/MONITOR_REPORTING_AND_METRICS.md).

---

## Event-rail + editorial handoffs (July 2026)

**Status: deployed on Widow** (API restart 2026-07-25). Stages pass work along the critical path via backlog counts **and** inline `request_phase` (`api/shared/pipeline_handoffs.py`):

`UIE → CE catchup (if needed) → event_deduplication → story_continuation → editorial Research/Narrative/Reduction`

Operator SSOT: [docs/ASSEMBLY_MODEL.md](docs/ASSEMBLY_MODEL.md). Pipeline tables: [docs/PIPELINE_AND_AUTOMATION.md](docs/PIPELINE_AND_AUTOMATION.md).

---

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

- [DATABASE_DATA_QUALITY_AUDIT_2026-06.md](docs/DATABASE_DATA_QUALITY_AUDIT_2026-06.md) — denormalized column audit and repair runbook (applied 2026-06-19)
- [WIDOW_SERVER_MIGRATION_2026_06.md](docs/WIDOW_SERVER_MIGRATION_2026_06.md) — migration record (completed)
- [ARCHITECTURE_AND_OPERATIONS.md](docs/ARCHITECTURE_AND_OPERATIONS.md) — current architecture
- [PROJECT_BOUNDARIES.md](../PROJECT_BOUNDARIES.md) — NI vs HomeLab split (monorepo level)
- [docs/DOCS_INDEX.md](docs/DOCS_INDEX.md) — documentation index
- [docs/DOCUMENTATION_FACT_CHECK_2026-06.md](docs/DOCUMENTATION_FACT_CHECK_2026-06.md) — doc vs Widow alignment audit (June 2026)

*Last verified: 2026-07-04 — `scripts/verify_documentation_ground_truth.py` on Widow (exit 0).*
