# Pipeline processing lanes (A→D)

**Purpose:** Define **strict priority** for flat pipeline admission so **spine SLA beats intake** before debt drains (event dedupe, research papers, editorial).

**Code SSOT:** `api/shared/pipeline_processing_lanes.py` (phase sets, lane pending helpers). Admission ordering: `api/shared/pipeline_admission.py` (`PREPROCESS_PRIORITY`, `POSTPROCESS_PRIORITY`, `MAINTENANCE_PRIORITY`).

See also: [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md), [spine_phase_order.py](../api/shared/spine_phase_order.py).

---

## Lanes (top → bottom)

| Lane | Goal | Phases (order) |
|------|------|----------------|
| **A — Spine SLA** | Today's news fully extracted | `content_enrichment` → `unified_intake_extraction` → `spine_sql_tail` → `document_processing` → `context_sync` |
| **B — Fresh structure** | Work tied to articles cleared in A | `event_tracking` → `mention_resolution` → `entity_profile_build` → `claim_extraction` → `claims_to_facts` (+ dedupe/gap helpers) |
| **C — Incremental sync** | New entities, not whole-catalog mapping | `entity_profile_sync` |
| **D — Debt & products** | Catch-up when A is stable | `chronological_events_catchup` → `event_deduplication`; research on dedicated GPU; editorial / storyline |

### Scheduling rule

While **lane A pending** (`enrichment` + `UIE` + `documents` + `context_sync` + `spine_sql_tail`) is above **`INTAKE_PREPROCESS_CLEAR_THRESHOLD`** (default 50), **lanes C and D must not** take GPU or high-frequency Widow slots.

Exceptions: ops (`pending_db_flush`, `health_check`, `rss_feed_health`) and **collection** (gated separately by collection throttle).

**Env:** `INTAKE_CATCHUP_STRICT=true` (default) enforces this via `intake_preprocess_defer_exempt_phases()`. Set `INTAKE_CATCHUP_STRICT=false` to restore legacy behavior (C/D phases exempt from the intake hot gate).

---

## Beat intake (capacity)

Spine SLA requires:

\[
\text{enrich completions/day} + \text{UIE completions/day} \geq \text{new articles/day} + \text{buffer}
\]

Bottleneck fixes:

- **Enrichment:** batch size / concurrency on Widow (fetch-bound).
- **UIE on PopOS:** keep fused intake worker saturated (`UNIFIED_INTAKE_EXTRACTION_*` on the PopOS worker).
- Track **UIE queue depth** alongside enrichment; if UIE ≫ 50 while enrich drains, GPU is the cap.

### Ops: spine until clear

Until lane A pending stays under target (e.g. &lt; 100 for 48h):

- Lower `COLLECTION_THROTTLE_PENDING_THRESHOLD` (e.g. 400).
- Optional `AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE=true` except periodic health passes.
- Pause manual bursts on lane D phases; run debt on side workers or strict windows.
- Reserve PopOS: research profiling on idle GPU / separate queue — not competing with UIE.

---

## Steady vs catch-up

| Mode | Behavior |
|------|----------|
| **Steady state** | Collection runs when lane A pending ≤ clear threshold, throttle not tripped, and 24h completes ≥ 24h ingests. |
| **Catch-up** | Lanes A+B on shared automation; C+D on side workers or time windows until enrichment pending trends down. |

**Postprocess mode** engages only when lane A is clear, preprocess band is stable, and fresh or debt structure still has work (debt does not flip postprocess while lane A is hot).

---

## Split structure band

| Band | Phases | Used for |
|------|--------|----------|
| **Fresh structure** | Lane B | Postprocess preference, refinement defer while spine underwater |
| **Debt / product** | Lane C + D | Drains after lane A clear; does not alone force postprocess over preprocess |

Do not optimize lane C/D debt while lane A is underwater — it does not improve spine SLA unless paired with enrich + UIE wins.