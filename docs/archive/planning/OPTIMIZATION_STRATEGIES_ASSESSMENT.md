# Optimization Strategies — What’s Implemented vs Gaps

Assessment of current retention, cleanup, and caps. Goal: stay under ~1 TB without hurting query/ingestion performance. Related: [STORAGE_ESTIMATES_AND_OPTIMIZATION.md](STORAGE_ESTIMATES_AND_OPTIMIZATION.md).

---

## 1. What’s already implemented

### 1.1 Intelligence layer (daily `data_cleanup` task)

| Strategy | Where | What it does | Performance impact |
|----------|--------|--------------|---------------------|
| **Entity noise removal** | `IntelligenceCleanupController` | Removes entities that are clearly noise (numbers, too-long, generic names) | Low – one pass per domain |
| **Entity duplicate merge** | Same | Merges case-insensitive duplicate `entity_canonical`; cascades to profiles | Low – reduces rows |
| **Low-value entity prune** | Same | Removes entities with ≤1 mention, older than 14 days | Low – targets tail only |
| **Orphan profile cleanup** | Same | Deletes `entity_profiles` with no `entity_canonical`; cleans `old_entity_to_new` | Low – keeps referential integrity |
| **Entity cap per domain** | Same | Keeps at most **10,000** entity profiles per domain; drops least-referenced | Medium – enforces hard cap |
| **Stale event archival** | Same | Sets `end_date` on `tracked_events` with no new chronicle in **30 days** | Low – soft archive |

**Policy (default):** `intelligence_cleanup_controller.DEFAULT_POLICY` — all of the above enabled; cap = 10,000; stale events = 30 days.

### 1.2 Articles and domain data

| Strategy | Where | What it does | Note |
|----------|--------|--------------|------|
| **Old article delete** | `AutomationManager._execute_data_cleanup` | `DELETE FROM articles WHERE published_at < cutoff AND created_at < cutoff` (cutoff = 30 days) | Runs once per task; **no schema prefix** — only affects the connection’s default schema (e.g. one domain). Should be per-domain in multi-schema setups. |
| **Smart article cleanup** | `manage_intelligence_database.py` | Optional smart pruner (max_age_days, dry_run); not wired into automation | Manual / script only |

### 1.3 Storage cleanup policies (migration 009)

| Policy | Table | Retention | Condition |
|--------|--------|-----------|-----------|
| old_raw_articles | articles | 30 days | `processing_status = 'raw'` |
| old_failed_articles | articles | 7 days | `processing_status = 'failed'` |
| old_timeline_events | timeline_events | 90 days | by created_at |
| old_ml_tasks | ml_task_queue | 14 days | completed/failed |
| old_system_logs | system_logs | 30 days | by created_at |

**Note:** `run_cleanup_policies()` uses unqualified `table_name` (e.g. `articles`). In a multi-schema layout these tables are per-domain (`politics.articles`, etc.), so these policies only apply if the function runs per-schema or there is a single shared `articles` table.

### 1.4 Cache and logs (non-Postgres)

| Component | Retention / limit | Where |
|-----------|-------------------|--------|
| **Smart cache** | Expired entries purged | `cache_cleanup` task (hourly); `cleanup_expired_entries()` |
| **Log files** | Compress after 7 days; delete after `retention_days` (default 30) | `LogStorageService` |
| **Resource metrics** | 30 days | `ResourceLogger.cleanup_old_metrics(30)` |
| **File cleanup** | Logs 7d, temp 1d, docker 7d, backups/exports by config | `automated_cleanup.py` |

---

## 2. Gaps — no retention or caps

These grow unbounded and are the main risk for exceeding 1 TB:

| Component | Schema / table | Risk |
|-----------|----------------|------|
| **Versioned facts** | `intelligence.versioned_facts` | One row per fact (and versions); no delete of old/superseded. |
| **Fact change log** | `intelligence.fact_change_log` | Processed rows never removed. |
| **Story update queue** | `intelligence.story_update_queue` | Processed rows never removed. |
| **Pattern matches** | `intelligence.pattern_matches` | Every run adds rows; no purge. |
| **Storyline states** | `intelligence.storyline_states` | New row per update; full history kept. |
| **Contexts** | `intelligence.contexts` | One row per article (and future sources); no age-based limit. |
| **Extracted claims** | `intelligence.extracted_claims` | No retention. |
| **Event chronicles / tracked_events** | `intelligence.event_chronicles`, `tracked_events` | Only “stale” events get `end_date`; no row delete. |

**Vectors:** Migration 151 has no embedding column yet; when added, vector storage will grow with `versioned_facts` / profiles unless compressed or pruned.

---

## 3. Recommended limits (stay under ~1 TB)

Target: keep hot data and recent history without hurting normal reads/writes. Assume “medium” scale (~50k facts/day, ~100k entities) and [STORAGE_ESTIMATES_AND_OPTIMIZATION](STORAGE_ESTIMATES_AND_OPTIMIZATION.md) ballpark.

### 3.1 Already aligned

- **Entity profiles:** cap 10,000 per domain — keep; consider 15k–20k if you need more headroom before pruning.
- **Stale events:** 30 days — keep.
- **Articles:** 30-day cutoff — keep; fix to run **per domain** (e.g. `politics.articles`, `finance.articles`, `science_tech.articles`).

### 3.2 Add retention / caps (performance-safe)

| Data | Recommendation | Rationale |
|------|----------------|------------|
| **fact_change_log** | Delete processed rows older than **7 days** | Only needed for catch-up; 7 days is enough for retries and debugging. |
| **story_update_queue** | Delete processed rows older than **7 days** | Same as above. |
| **pattern_matches** | Delete rows older than **90 days** | Keeps recent alerts; old matches rarely needed. |
| **storyline_states** | Keep **last N per storyline** (e.g. 50) or **states older than 1 year** | Balances “story evolution” view with size; 50 versions or 1 year is usually enough. |
| **versioned_facts** | Optional: **prune superseded chain** (keep head + every Nth or last 1 year) | Largest table; pruning superseded versions reduces size without hurting “current fact” queries. |
| **contexts** | Optional cap per domain (e.g. **500k**) or **delete contexts for articles older than 2 years** | Prevents unbounded growth; 2 years keeps RAG and events well fed. |

### 3.3 What to avoid (for performance)

- **No aggressive pruning of “current” versioned_facts** — only superseded / very old.
- **No full-table scans on hot path** — run retention in batch jobs (e.g. same `data_cleanup` window).
- **No dropping indexes** on hot tables — keep existing indexes; add partial indexes only if retention is by date and queries are date-scoped.

---

## 4. Summary

| Area | Implemented | Gap | Suggested next step |
|------|-------------|-----|----------------------|
| Entity profiles | Cap 10k, noise/dup/orphan cleanup | — | Optional: raise cap slightly if needed. |
| Tracked events | Stale archive (30 d) | No row delete | Optional: archive/delete events older than 1–2 years. |
| Articles | 30-day delete in data_cleanup | Single-schema only | Run delete **per domain** (politics, finance, science_tech). |
| fact_change_log / story_update_queue | Processed, never deleted | Unbounded growth | **Add:** delete processed rows older than 7 days. |
| pattern_matches | None | Unbounded growth | **Add:** delete rows older than 90 days. |
| storyline_states | None | Unbounded growth | **Add:** keep last 50 per storyline (or 1 year). |
| versioned_facts | None | Unbounded growth | **Add (later):** prune superseded chain (e.g. keep head + 1 year). |
| contexts | None | Unbounded growth | **Add (later):** cap or 2-year cutoff. |

Implementing the **bold** items (fact_change_log, story_update_queue, pattern_matches, storyline_states) gives the biggest gain with minimal impact on performance and keeps total storage well under 1 TB for typical medium-scale use.
