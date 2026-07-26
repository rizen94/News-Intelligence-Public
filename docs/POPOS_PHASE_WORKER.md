# PopOS phase worker

**Model:** Widow orchestrates (API, admission, Monitor, light DB/fetch). PopOS **executes** heavy phase drains against local Ollama (RTX 5090) and writes results to Widow `news_intel` via PgBouncer.

**Placement rule:** `REMOTE_PHASE_WORKER_OWNED_PHASES` (Widow) is the only true offload. Policy labels like `popos_gpu` do **not** move work by themselves.

## Components

| Piece | Location |
|-------|----------|
| Worker loop | [`scripts/run_popos_phase_worker.py`](../scripts/run_popos_phase_worker.py) (`--phases`, `--worker-id`) |
| Drain dispatch | [`api/shared/phase_drain_dispatch.py`](../api/shared/phase_drain_dispatch.py) |
| Ownership SSOT | [`api/shared/remote_phase_worker.py`](../api/shared/remote_phase_worker.py) |
| Split user units | `infrastructure/news-intelligence-popos-worker-{uie,claim-topic,assembly}.user.service` |
| Target | [`infrastructure/news-intelligence-popos-workers.target`](../infrastructure/news-intelligence-popos-workers.target) |
| Installer | [`scripts/install_popos_phase_worker.sh`](../scripts/install_popos_phase_worker.sh) |
| PopOS env | [`configs/env.popos_worker.example`](../configs/env.popos_worker.example) (DB/Ollama; phases come from `--phases`) |
| Widow env | [`configs/env.widow_thin_orchestrator.example`](../configs/env.widow_thin_orchestrator.example) |

## Idle gate + backoff

PopOS workers probe eligibility **before** calling `drain_phase`, using
[`api/shared/phase_idle_gate.py`](../api/shared/phase_idle_gate.py):

| Behavior | Detail |
|----------|--------|
| Idle probe | Cheap `LIMIT 1` / EXISTS SQL aligned with backlog eligibility |
| Skip | No drain, no "running" heartbeat, no empty `automation_run_history` row |
| Backoff | Exponential per phase: base 30s → … → max 300s (`POPOS_IDLE_BACKOFF_*`) |
| Wake | Next cycle after backoff expires re-probes; work resets the streak |

Env (optional):

```bash
POPOS_IDLE_GATE_ENABLED=true
POPOS_IDLE_BACKOFF_BASE_SEC=30
POPOS_IDLE_BACKOFF_MAX_SEC=300
POPOS_IDLE_BACKOFF_FACTOR=2
```

## Desk schedule (GPU deferral)

Workers honor [`pipeline_schedule_service.popos_gpu_work_allowed()`](../api/services/pipeline_schedule_service.py). During **desk_light** (default 10:00–01:00 America/New_York) the worker logs `desk_gpu_deferred` and skips owned GPU phases so Ollama VRAM stays free for interactive use. Widow continues RSS/enrich independently. Heavy (01:00–06:00) and morning_ingest (06:00–10:00) run drains normally.

### Desk presence (automatic soft gate)

[`scripts/popos_desk_presence.py`](../scripts/popos_desk_presence.py) (timer: `infrastructure/ni-desk-presence.user.timer`) polls:

1. `loginctl` **LockedHint** — locked session → allow NI GPU even in desk hours
2. Homelab proxy `GET /api/proxy/stats` — HIGH `in_flight` / `queued_high` / recent `last_high_at` → defer GPU

Writes `$XDG_RUNTIME_DIR/ni-desk-presence.json` and upserts `public.automation_state` key `desk_presence` for Widow. Stale readings (>90s) are ignored → wall-clock only.

**PopOS workers must use the proxy with LOW priority** (`OLLAMA_PRIORITY=low` → `X-Ollama-Priority: low`). Loopback without the header looks like HIGH and will falsely trip interactive deferral.

Enable:

```bash
systemctl --user enable --now ni-desk-presence.user.timer
# one-shot check:
python3 scripts/popos_desk_presence.py --json -v
```

Full checklist: [DESK_SCHEDULE_DEPLOY.md](DESK_SCHEDULE_DEPLOY.md).

When every assigned phase is idle, the worker sleeps until the soonest backoff
expiry (instead of re-checking every `--idle-sleep` seconds).

**Monitor alignment:** Widow `queue_depth` for PopOS-owned phases uses the same
eligibility predicates as these probes/drains (`claim_extraction` gap-fill SQL,
`topic_clustering` first-pass `count_pending_articles`, `storyline_assembly`
threshold via `count_assembly_actionable_pending`). When Monitor shows 0 and the
worker logs `skip … no eligible work`, they agree.

## Supported phases (allowlist ⊆ drains)


| Phase | Notes |
|-------|--------|
| `unified_intake_extraction` | Spine `unified_intake_queue` |
| `chronological_events_catchup` | CE restore LLM (pair with UIE worker) |
| `claim_extraction` | Automation claim drain |
| `topic_clustering` | Per-domain catchup clustering |
| `storyline_assembly` | All-domain assembly runner |
| `editorial_research_pass` | v11 Research modal (local Ollama) |
| `editorial_narrative_pass` | v11 Narrative modal |
| `editorial_reduction_pass` | v11 Reduction modal |
| `content_enrichment` / `spine_sql_tail` | Optional drains (not default-owned) |

## Split workers (default — recommended)

Five parallel user units so assembly (long/RAM-heavy), editorial LLM, and refine (profiles / ~70B queue) do not block UIE:

| Unit | Phases |
|------|--------|
| `…-uie` | `unified_intake_extraction`, `chronological_events_catchup` |
| `…-claim-topic` | `claim_extraction`, `topic_clustering` |
| `…-assembly` | `storyline_assembly` |
| `…-editorial` | `story_continuation`, `editorial_research_pass`, `editorial_narrative_pass`, `editorial_reduction_pass` |
| `…-refine` | `entity_profile_build`, `content_refinement_queue` |

Widow must list the same owned set in `REMOTE_PHASE_WORKER_OWNED_PHASES` (see `configs/env.widow_thin_orchestrator.example`).

```bash
./scripts/install_popos_phase_worker.sh          # split (default)
# ./scripts/install_popos_phase_worker.sh --monolith   # single process (legacy)
systemctl --user status news-intelligence-popos-worker-uie \
  news-intelligence-popos-worker-claim-topic \
  news-intelligence-popos-worker-assembly \
  news-intelligence-popos-worker-editorial \
  news-intelligence-popos-worker-refine --no-pager
```

CLI override (beats `.env.popos_worker` `WORKER_PHASES`):

```bash
python scripts/run_popos_phase_worker.py --worker-id uie --phases unified_intake_extraction,chronological_events_catchup
```

## Widow ownership

```bash
REMOTE_PHASE_WORKER_ENABLED=true
REMOTE_PHASE_WORKER_OWNED_PHASES=unified_intake_extraction,claim_extraction,topic_clustering,storyline_assembly,editorial_research_pass,editorial_narrative_pass,editorial_reduction_pass,chronological_events_catchup,story_continuation,entity_profile_build,content_refinement_queue
AUTOMATION_MAX_CONCURRENT_TASKS=2
AUTOMATION_BLOCK_PHASES=document_processing
AUTOMATION_RSS_PAUSE_MB=1800
FINANCE_USE_SENTENCE_TRANSFORMERS=false
```

Keep `document_processing` off the API process. Monitor shows `popos_phase_worker` heartbeats from each split worker. **Current activity** merges in-flight PopOS drains (`detail.status=running` on phase heartbeats) with Widow AutomationManager rows and labels each row PopOS vs Widow.

## Homelab MCP

Unchanged: read-only `mcp_reader`. Worker uses **newsapp** write — never through MCP.
