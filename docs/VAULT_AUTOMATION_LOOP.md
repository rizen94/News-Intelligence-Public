# Vault automation loop (Phase 3)

Closed iterative loop: **Postgres canonical** → **Widow discovery API** → **Obsidian vault** → **promotion** → **storyline_assembly** → vault stubs.

See [STORYLINE_CANONICAL_MODEL.md](STORYLINE_CANONICAL_MODEL.md) for object roles and Phase 2 demotion.

---

## Components

| Component | Path | Role |
|-----------|------|------|
| Tracking discovery API | `GET /api/tracking/discovery` | Deterministic passes 1–5 (ports `news-tracking-discovery.md`) |
| Vault bridge | `api/services/vault_bridge_service.py` | Read/write `NEWS_INTEL_VAULT_PATH` |
| Promotion bridge | `api/services/tracking_promotion_service.py` | High-score candidates → assembly / work-queue |
| Cron runner | `api/scripts/run_tracking_discovery_loop.py` | Headless loop (no Open WebUI chat) |
| Event reconciliation | `GET /api/event_reconciliation` | Read-only tracked ↔ chronological ↔ storyline |

---

## Loop sequence

```
1. vault_bridge.read_cursors()
2. tracking_discovery.run(since=last_tracking_scan_at)
3. vault_bridge.write_candidates()
4. promotion_bridge.apply(top_n=5)
5. vault_bridge.update_cursors(now)
6. vault_bridge.append_session_log()
```

After storyline assembly promotes a concrete storyline, `vault_bridge.write_story_stub()` creates `30_Stories/{domain}-{id}-{slug}.md`.

### Editorial room loop (post-spine pass 2)

Headless iterative linking — same mount as OWUI + `obsidian-news-vault` MCP:

| Path | Purpose |
|------|---------|
| `00_Inbox/work-queue.md` | Cursors incl. `last_connection_loop_at` |
| `25_Connections/` | LLM-drafted connection notes (Postgres IDs in frontmatter) |
| `20_Investigations/` | Investigation threads (vault-first; promote via tracking promotion) |

Widow runs `editorial_room_loop_service` inside `assembly_conductor` (step 7). Prompts: `api/config/prompts/editorial_room/`.

```bash
EDITORIAL_ROOM_LOOP_ENABLED=true
EDITORIAL_ROOM_LOOP_MAX_ROUNDS=5
EDITORIAL_ROOM_PROPOSAL_MIN_CONFIDENCE=0.65
ASSEMBLY_PIPELINE_MODE=ordered
```

---

## Environment (Widow)

```bash
NEWS_INTEL_VAULT_PATH=/mnt/news-intelligence-vault
NEWS_INTEL_VAULT_WRITE=true
TRACKING_PROMOTION_TOP_N=5
TRACKING_PROMOTE_STORYLINE_MIN_SCORE=20
AUTOMATION_DISABLED_SCHEDULES=...,proactive_detection,storyline_discovery,narrative_thread_build
STORYLINE_ASSEMBLY_RUN_PROACTIVE=false
```

Mount must match Homelab `obsidian-news-vault` MCP path.

---

## Cron install (Widow)

```bash
# infrastructure/widow-tracking-discovery.cron — Mon/Thu 06:00
crontab -l 2>/dev/null | cat - infrastructure/widow-tracking-discovery.cron | crontab -
```

Manual run:

```bash
cd /opt/news-intelligence
set -a && . ./.env && set +a
PYTHONPATH=api .venv/bin/python3 api/scripts/run_tracking_discovery_loop.py
PYTHONPATH=api .venv/bin/python3 api/scripts/run_tracking_discovery_loop.py --dry-run
```

---

## Open WebUI role after integration

| Automation | After integration |
|------------|-------------------|
| Tracking discovery | **Widow cron** primary; OWUI optional reconcile-only |
| Journalism | Unchanged — incremental context cards |
| Editorial | Gap scan vs `30_Stories/` |
| Interactive chat | Human override, investigation |

Homelab prompt: `HomeLab-AI-Stack/docs/prompts/news-tracking-discovery.md` — thin client calling Widow API.

---

## Cursor sync

Vault `00_Inbox/work-queue.md` frontmatter (`last_tracking_scan_at`, `last_reviewed_at`) is mirrored to `public.automation_state` key `vault_work_queue` for Monitor visibility.

---

*Last updated: 2026-06-28*
