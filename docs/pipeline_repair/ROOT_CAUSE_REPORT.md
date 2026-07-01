# Pipeline Root-Cause Report (PR0)

**Date:** 2026-06-10  
**Host:** Widow (`192.168.93.101`)  
**Baseline:** `docs/pipeline_repair/baseline-20260610-before.json`  
**After PR1 reconcile:** `docs/pipeline_repair/baseline-20260610-after-pr1.json`

---

## Summary

Collection (RSS / `collection_cycle`) is healthy. Digestion lags due to **combined** factors: false pass markers hiding backlog, low nightly throughput caps, split scheduling (cron vs nightly unified), and connection pool pressure — not a single hard reject gate.

---

## Cause 1 — Stalled orchestration (CONFIRMED, nuanced)

### Mechanism

| Path | Code | Behavior |
|------|------|----------|
| Nightly unified drain | [`api/services/nightly_ingest_window_service.py`](../api/services/nightly_ingest_window_service.py) L418–655 | Runs 00:00–07:00 ET; drains enrichment → context_sync → sequential phases; exits with `stopped_reason=all_idle` when `get_all_pending_counts()` shows zero |
| Nightly scheduling gate | [`api/services/automation_manager.py`](../api/services/automation_manager.py) L2526–2527 | `nightly_enrichment_context` only schedules inside nightly window |
| Standalone context_sync | [`api/services/automation_manager.py`](../api/services/automation_manager.py) L3812–3818 | Returns early during nightly window (delegates to unified drain) |
| Widow cron path | [`api/scripts/run_widow_db_adjacent.py`](../api/scripts/run_widow_db_adjacent.py) L157–166 | **Authoritative** `context_sync` on Widow when `AUTOMATION_DISABLED_SCHEDULES` includes `context_sync` |

### Evidence

- `automation_run_history` last `nightly_enrichment_context`: **2026-06-02** (full drain stale).
- `automation_run_history` last `context_sync`: **2026-05-18** — **misleading** on Widow; cron runs do not write to this table.
- `widow_db_adjacent.log` (2026-06-10): `context_sync` active — politics/finance/legal/medicine batches succeeding.
- Env: `AUTOMATION_DISABLED_SCHEDULES=context_sync,entity_profile_sync,pending_db_flush,...`

### Root cause

1. **False `all_idle` exits** when pass markers clear backlog without output (Cause 5).
2. **Historical gap** persists because cron sync is **100 contexts/domain/15min** — insufficient for 6k+ article gap at current rate.
3. Nightly unified drain has not completed a full sequential sweep since early June.

### Fix (PR2)

- Phase heartbeats (`pipeline_phase_heartbeats` + cron/nightly recording).
- Re-run nightly drain after PR1 reconciliation.

---

## Cause 2 — Throughput debt (CONFIRMED)

### Mechanism

| Setting | Location | Default |
|---------|----------|---------|
| `ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN` | [`automation_manager.py`](../api/services/automation_manager.py) L5811 | **20** |
| `ENTITY_EXTRACTION_PARALLEL` | L5857 | 4 |
| Nightly loop cap `entity_extraction:8` | [`nightly_ingest_window_service.py`](../api/services/nightly_ingest_window_service.py) L271–285 | ~160 articles/night max |
| `context_sync` batch | [`run_widow_db_adjacent.py`](../api/scripts/run_widow_db_adjacent.py) L57 | 100/domain |

### Evidence

- ~42k articles with pass-null entity extraction (pre-PR1; includes false passes).
- 45 `entity_extraction` automation runs / 14 days.

### Fix (PR4 / PR4b)

- `bulk_catchup.py` with `--force` (one-time, no quiet-hour limit).
- Tune steady-state caps after bulk completes.

---

## Cause 3 — Schedule gating (CONFIRMED, by design)

### Mechanism

[`api/services/pipeline_schedule_service.py`](../api/services/pipeline_schedule_service.py) L125–135, L145–149:

- **Quiet:** 16:00–00:00 daily + weekend daytime — only `health_check`, `pending_db_flush`.
- **Nightly heavy:** 00:00–07:00 — unified drain + allowed phases.
- **Weekday daytime:** 07:00–16:00 Mon–Fri — full automation.

### Fix

- Do **not** remove quiet hours.
- Bulk catch-up uses explicit `--force` (operator one-time exception per plan).

---

## Cause 4 — Connection pool exhaustion (CONFIRMED)

### Mechanism

| Pool | [`connection.py`](../api/shared/database/connection.py) | Default max |
|------|-----------------------------------------------------------|-------------|
| worker | L204–209 | 28 |
| ui | L198–199 | 16 |
| health | L201–202 | 2 → **4** (PR3) |

Stale connections: L296–301 — `conn.close()` without `putconn` exhausts pool.

### Evidence

- 81× `health_check` failures / 24h: `connection pool exhausted`.
- Monitor `backlog_status` holds UI pool connections during long queries.

### Fix (PR3)

- Entity extraction fetch uses `get_db_connection_context()` (PR3).
- Health pool default raised to 4.
- Existing cron `terminate-idle-in-tx` remains safety net.

---

## Cause 5 — False pass markers (CONFIRMED, primary metric corruption)

### Mechanism

[`automation_manager.py`](../api/services/automation_manager.py) L5874–5883 (pre-PR1):

```python
record_article_phase_pass(..., "no_entities_stored")  # even when len(content) > 400
```

[`shared/pipeline_pass_marker.py`](../api/shared/pipeline_pass_marker.py) — backlog SQL treated any `last_pass_at` as cleared.

[`claim_extraction_service.py`](../api/services/claim_extraction_service.py) L675–677 — `no_claims_after_filters` without claims rows.

### Evidence

- politics: 21 articles with `no_entities_stored` pass but no `article_entities` (sample query).
- `nightly_phase_idle.phase_has_pending_work` reads corrupted counts → `all_idle`.

### Fix (PR1)

- Tri-state: `processed_with_output`, `processed_empty_legitimate`, `failed_needs_retry`.
- `reconcile_false_pass_markers.py` re-queues without deleting intelligence.
- Backlog SQL updated to treat legacy false outcomes as pending.

---

## Cause 6 — Embeddings + storylines (CONFIRMED downstream)

- `embedding_chunks`: **0** — semantic search inoperative.
- ~99% articles unlinked to storylines — clustering runs on thin enrichment.

### Fix (PR5)

- `backfill_embedding_chunks.py`
- Storyline discovery after entity/claim catch-up in `bulk_catchup.py`.

---

## NRI handoff (Phase 6)

- Watermark: `nri.watermarks.mention_resolver` vs `max(context_entity_mentions.id)` — tracked in diagnostic H8.
- NI writes mentions only; NRI resolves (boundary preserved).

---

## Deliverables map

| PR | Deliverable |
|----|-------------|
| PR0 | This report + baseline JSON |
| PR1 | Pass-marker tri-state + reconciliation |
| PR2 | Heartbeats + stall alerts in `backlog_status` |
| PR3 | Pool leak fix + health pool size |
| PR4 | `bulk_catchup.py` + runbook |
| PR4b | `backlog_trend_service` alerts |
| PR5 | Embedding + storyline scripts |
| PR6 | NRI watermark in diagnostic |
