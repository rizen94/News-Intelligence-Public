# Pulse digest and follow registry

Operator-facing ranked movement digest, follow tiers, living-story republish loop, and external research attach.

## Pulse (`GET /api/pulse`)

Read-only ranked list of episode/container movement for a time window (default 48h).

- **Service:** `api/services/pulse_service.py` — velocity from `event_episode_links`, lifecycle bonuses, container updates from `tracked_events`.
- **Domain filter:** `?domain=` scopes episodes/containers; domains with `topic_filter.include_keywords` (e.g. **neurodiversity**) are **opt-in** — cards must match Autism / ADHD / AuDHD / ASD terms in title or movement (not broad neuro* filters). Config errors on allowlist domains **fail-closed** (card dropped).
- **Kind-aware links:** container → Investigate; `matter_docket` → dockets; `evidence_thread` / `research_topic` → research subjects; narrative kinds → storylines. Never treat Pulse episode ids as curated arc catalog keys.
- **Preview:** `PYTHONPATH=api python3 api/scripts/pulse_preview.py`
- **Digest job:** `api/scripts/run_pulse_digest.py` — computes pulse, stamps `last_surfaced_at` on active follows, writes `intelligence.pulse_snapshots` (migration **303**).

Env knobs (`api/config/runtime.py`): `PULSE_WINDOW_HOURS`, `PULSE_LIMIT`, scoring bonus vars. Master switch: `PULSE_DIGEST_ENABLED` (default on).

**Automation:** `pulse_digest` phase in AutomationManager (every 6h); `living_story_cooling_sweep` daily. See `api/config/schedulers.yaml`.

**Per-domain pathing / membership funnel:** see [ASSEMBLY_MODEL.md](ASSEMBLY_MODEL.md) (decision matrix + silent attach gates).

## Follow registry (`/api/follows`)

Table: `intelligence.followed_items` (migration **302**).

| Tier | Behavior |
|------|----------|
| **quiet** | Surface movement on Following page; no auto-publish |
| **living** | Episode only — promotes to editorial package + published story; throttled auto-republish |

Cap: `FOLLOW_LIVING_CAP` (default 15). Mutating routes **403 on public demo** (expected).

## Living stories

- **Promote:** `PATCH /api/follows/{id}` with `promote_living: true` or `POST /api/follows` with `tier=living`.
- **Orchestration:** `api/services/living_story_service.py` — `ensure_package_from_storyline`, `publish_story`, republish throttle via `LIVING_REPUBLISH_MIN_HOURS` / `LIVING_REPUBLISH_MIN_NEW_MEMBERS`. Auto-republish is also gated when the episode is at/over `attach_hard_cap` or fails kitchen-sink / cohesion assess (`living_republish_allowed`).
- **Cooling sweep:** `api/scripts/living_story_cooling_sweep.py` — pauses living follows when episode stays dormant/cooling past `LIVING_COOLING_DAYS`.

## Web UI

- `/{domain}/pulse` — ranked cards, follow menu (hidden in demo readonly)
- `/{domain}/following` — movement since last read, living/quiet groups

## Related

- Build plan: `docs/build-plans/PULSE_DIGEST_LIVING_FOLLOWS_BUILD_PLAN.md`
- External research: `docs/N8N_EXTERNAL_RESEARCH_LOOP.md`
- Attach quality gates: `docs/EDITORIAL_PACKAGE_QUALITY.md`
- Domain matrix / membership funnel: `docs/ASSEMBLY_MODEL.md`

### Neurodiversity cutover ops

After changing `topic_filter.include_keywords` or deploying the allowlist: restart API/workers (config is process-cached). Soft-purge historical offtopic with `PYTHONPATH=api python3 api/scripts/purge_neurodiversity_offtopic.py` (dry-run) then `--apply`. Soft-removed articles (`enrichment_status=removed`) are excluded from `GET /api/research/{domain}/findings` via join on `{schema}.articles`.

### Medicine bioRxiv subjects

Medicine no longer seeds bioRxiv `subject=all` (plant/ecology firehose). Spec + YAML use curated clinical/translational subjects (`pathology`, `immunology`, `microbiology`, `pharmacology_and_toxicology`, `genetics`, `genomics`, `cancer_biology`, `epidemiology`, `clinical_trials`, `physiology`) — not `neuroscience` (neurodiversity). Migration **305** deactivates leftover `subject=all` rows and seeds curated URLs. Safety net: `topic_filter.include_keywords_for_feed_url_substrings` on `biorxiv_xml.php?subject=all` in `domain_synthesis_config.yaml`, enforced by `rss_collector.is_excluded_content`.
