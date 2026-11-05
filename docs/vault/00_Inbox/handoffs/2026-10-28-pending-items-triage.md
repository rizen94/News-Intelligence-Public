# Pipeline Pending Items Investigation — 2026-10-28

## Executive Summary

~1M+ items stuck in `public.storyline_article_suggestions.status = 'pending'`. ~696k expired by date (7-day TTL) but never marked `expired` because **no code enforces it**. The `storyline_review_agent` review phase has a fully implemented service (`storyline_review_agent_service.py`) but is disconnected from the AutomationManager scheduler — scheduling knows about it, execution doesn't.

---

## Finding 1: Root Cause — Missing Dispatch in AutomationManager

### Symptom
Items enter `pending` via `storyline_automation_service.py` (auto-matching articles to storylines), but have no automated path to approval/rejection/expiration.

### Evidence

**`pipeline_admission.py` (scheduling layer) — line 61:**
```python
POSTPROCESS_PRIORITY: tuple[str, ...] = (
    ...
    "storyline_review_agent",      # <-- scheduling knows about it
    ...
)
```

**`pipeline_admission.py` (scheduling layer) — line 94:**
```python
MAINTENANCE_PRIORITY: tuple[str, ...] = (
    ...
    "storyline_review_agent",      # <-- also in maintenance
    ...
)
```

**`pipeline_conductor_service.py` (lines 26-30):**
```python
_STORYLINE_SCOPED_PHASES = frozenset({
    "storyline_review_agent",
    "watchlist_alerts",
})
```

**`pipeline_conductor_service.py` (line 60):** also in `_FALLBACK_PIPELINE_PHASES`.

### The Gap — AutomationManager has NO entry for this phase:

1. **Not in `PHASE_ESTIMATED_DURATION_SECONDS`** (automation_manager.py lines 898-965): No duration estimate exists → scheduler cannot plan it.
2. **Not in `phase_definitions` dict** (automation_manager.py lines ~1030+): No interval, priority, phase number, depends_on, or enabled flag.
3. **grep returned zero matches**: `storyline_review_agent` does not appear anywhere in automation_manager.py.

### Result
Even though the flat scheduler picks `storyline_review_agent` as a desired phase (via pipeline_admission.py), AutomationManager cannot dispatch it because there's no function mapping or task definition to execute it. It silently drops from the desired list.

---

## Finding 2: Secondary Root Cause — Zero Expiration Enforcement

### The TTL Column Exists but is Never Checked

**Migration 120** (`archive/historical/120_storyline_automation_settings.sql`):
```sql
expires_at TIMESTAMP WITH TIME ZONE,  -- Auto-expire old suggestions
```

**storyline_automation_service.py (INSERT — ~line 1328):**
```python
(
    ...
    "pending",
    datetime.now(),                                    # suggested_at = now()
    datetime.now() + timedelta(days=7),               # expires_at = now() + 7d
)
```

### The Bug: `storyline_article_suggestions` table schema has no `status = 'expired'` handling:
- Review agent (`storyline_review_agent_service.py`) only filters `WHERE status = 'pending'`.
- No cron, no periodic cleanup task, no TTL check anywhere in the codebase.
- Grep for `expired` across both files returns **zero results**.
- Items accumulate forever with `status='pending'` even after expires_at passes.

### Scale Impact
Per the context summary: ~696k items expired by date but never marked as such. These are stale entries consuming DB rows, indexes, and skewing backlog metrics.

---

## Finding 3: Data Flow — How Items Enter Pending

**Insert path** (`storyline_automation_service.py` ~line 1290):
```sql
INSERT INTO public.storyline_article_suggestions (
    domain_key, storyline_id, article_id, relevance_score, semantic_score,
    keyword_score, quality_score, combined_score, reasoning,
    matched_keywords, matched_entities, status, suggested_at, expires_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (domain_key, storyline_id, article_id) DO UPDATE SET
    ... 
    status = 'pending'
WHERE public.storyline_article_suggestions.status NOT IN ('added', 'approved')
```

Valid statuses observed: `pending`, `approved`, `added`. The migration 232 does not add an `expired` status — only the insert/update logic sets these.

---

## Findings Summary

| # | Issue | Impact | Fix Required |
|---|-------|--------|-------------|
| 1 | Phase in scheduling but NOT in AutomationManager execution | No review agent runs → items never get approve/reject/dispositioned | Add PHASE_ESTIMATED_DURATION_SECONDS entry + phase_definitions entry + dispatch mapping |
| 2 | expires_at column has no enforcement | ~696k stale rows accumulate with status='pending' forever | Add expiration cleanup task (cron or periodic) |
| 3 | No 'expired' status in DB schema/constraints | Cannot mark expired items properly without migration | Either add 'expired' to valid statuses OR use a cleanup that deletes/archives |

