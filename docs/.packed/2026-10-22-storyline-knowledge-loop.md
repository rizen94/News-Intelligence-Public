# Storyline Knowledge Loop — Materiality Gate → Narrow Debt → Nightly Drain

*Date created: 2026-10-22*
*Source: `api/services/content_refinement_queue_service.py`, `api/services/storyline_narrative_materiality.py`, `api/main.py` (cron route)*

---

## 1. The Knowledge Loop in One Sentence

When a storyline is created or updated, articles are automatically queued for refinement; the system classifies **materiality** of the change and chooses one of three paths: skip (no meaningful change), narrow debt (minor debt to be drained nightly), or full rewrite (substantial facts demand a ~70B-class LLM narrative generation).

---

## 2. Materiality Gate

### 2.1 Evidence Fingerprinting

Each time an article is linked to a storyline, its extracted evidence produces a deterministic fingerprint:

```python
# Pseudocode (see content_refinement_queue_service.py)
def compute_evidence_fingerprint(evidence: List[Evidence]) -> str:
    """
    Canonicalise, sort, hash the set of facts extracted from
    newly linked articles. Returns hex digest.
    """
    facts = sorted(
        frozenset(fact.canonical_form() for fact in evidence)
    )
    return hashlib.sha256(str(facts).encode()).hexdigest()
```

This fingerprint is stored on the `refine_job` record (column `evidence_fingerprint`). On subsequent runs:
- If the fingerprint matches the **prior** canonical's fingerprint → the change is considered **noise**. The system skips the prompt to the LLM entirely.
- If fingerprints differ → materiality classification proceeds.

### 2.2 Materiality Classification

Three categories (see `storyline_narrative_materiality.py`):

| Category | Signal | Action |
|----------|--------|--------|
| **skip** | Fingerprint unchanged, or delta below threshold | Do nothing — no LLM call |
| **narrow_debt** | Small factual delta (e.g. a sentence added to a timeline) | Queue debt drain task for nightly batch |
| **material** | Large factual delta, new events, new entities | Enqueue full refinement with priority=HIGH |

Classification thresholds are configured via environment variables:
- `MATERIALITY_DELTA_THRESHOLD` — cosine similarity of evidence vectors
- `NARROW_DEBT_MAX_SENTENCES` — max added/deleted sentences before promoting to material

### 2.3 Auto-enqueue Triggers

Materiality triggers fire when:
1. A new article is linked to an existing storyline (via route `POST /api/storylines/{id}/articles`).
2. An article's content is updated (route `PUT /api/articles/{id}`).
3. A user manually triggers refinement (`POST /api/storylines/{id}/refine`).
4. Nightly cron runs `GET /api/automation/narrow-debt-drain`.

---

## 3. Content Refinement Queue Service

### 3.1 Table Schema (conceptual)

```sql
CREATE TABLE refine_jobs (
    id              SERIAL PRIMARY KEY,
    storyline_id    INT REFERENCES storylines(id),
    job_type        VARCHAR(32),   -- full_rewrite | narrow_debt | auto_refine
    priority        SMALLINT,      -- 1=LOW 2=MEDIUM 3=HIGH 4=URGENT
    status          VARCHAR(16),   -- pending | running | done | failed
    evidence_fingerprint TEXT,
    materiality     VARCHAR(16),   -- skip | narrow_debt | material
    gpu_required    BOOLEAN,       -- True if model is large (>7B params)
    created_at      TIMESTAMPTZ DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ
);
```

### 3.2 Job Types

| Type | When Enqueued | GPU Required? |
|------|---------------|---------------|
| `full_rewrite` | Material change detected, or manual trigger | Yes (70B-class) |
| `narrow_debt`  | Nightly drain of minor debt backlog | No (can use smaller model) |
| `auto_refine`  | New article linked; moderate delta | Conditional |

### 3.3 Priority Tiers

```python
PRIORITY_LEVELS = {
    "URGENT": 4,   # breaking news event → immediate processing
    "HIGH":   3,   # material factual change → process within 1h
    "MEDIUM": 2,   # moderate delta → batch window (next 6h)
    "LOW":    1,   # narrow debt / optional rewrites → overnight batch
}
```

### 3.4 GPU-Friendly Scheduling

- **High-priority** jobs are dispatched immediately to the GPU node (PopOS RTX 5090 via `OLLAMA_HOST` or LAN proxy).
- **Low-priority** jobs are batched and processed during off-hours using the cron window at `2:00–6:00 UTC`.
- The system checks GPU availability (`ollama_model_policy.py`) before dispatch:
  ```python
  def gpu_available() -> bool:
      return ollama_health_probe(OLLAMA_POP_OS_HOST).status == "healthy"
  ```
- If the GPU node is down, high-priority jobs are downgraded to CPU fallback (with a latency warning).

---

## 4. Narrow Debt Drain Mechanism

### 4.1 What Is "Narrow Debt"?

Narrow debt represents minor factual updates that don't justify an immediate LLM rewrite but would degrade narrative quality if left unaddressed:
- New dates or times extracted from linked articles
- Minor corrections to existing facts
- Additional entities not changing the storyline's core

### 4.2 Drain Process (Nightly Cron)

```python
# api/main.py — cron route handler
def handle_narrow_debt_drain():
    """
    SELECT * FROM refine_jobs
    WHERE job_type = 'narrow_debt'
      AND status = 'pending'
      AND created_at < now() - interval '24 hours'  -- force-finish
    ORDER BY priority ASC, created_at DESC
    LIMIT :batch_size;   -- default 50 per cycle
    """
```

The drain process:
1. **Force-completes** all narrow_debt jobs older than 24h (even if the LLM hasn't run them yet).
2. For each job, runs a lightweight delta merge against the existing canonical narrative.
3. Updates `evidence_fingerprint` on the storyline after merge.
4. Marks the job as done.

### 4.3 Integration with Knowledge Loop

The nightly drain feeds back into the materiality gate:
- After each narrow_debt merge, the new fingerprint is compared to pre-merge.
- If the delta has grown beyond `MATERIALITY_DELTA_THRESHOLD` during accumulation → **promote** to full_rewrite.

---

## 5. Flow Diagram

```
New article linked to storyline
            │
            ▼
   Compute evidence_fingerprint
            │
            ▼
   Compare to prior fingerprint ──┐
            │                     │
   MATCH → skip (no LLM)          │
            │                      │
   DIFFER → classify materiality  │
            │                      │
   narrow_debt ──► queue for nightly drain
   material ────► enqueue full_rewrite (URGENT/HIGH)
            │
            ▼
   Nightly cron at 2:00 UTC
   ├─ Process narrow_debt backlog
   ├─ Merge deltas into canonical
   └─ Re-classify: promote if delta grew
```

---

## 6. Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MATERIALITY_DELTA_THRESHOLD` | `0.3` | Cosine similarity below which diffs are "material" |
| `NARROW_DEBT_MAX_SENTENCES` | `15` | Max added/deleted sentences for narrow_debt classification |
| `DEBT_DRAIN_BATCH_SIZE` | `50` | Jobs processed per cron cycle |
| `DEBT_DRAIN_MIN_AGE_HOURS` | `24` | Minimum age before a debt job can be force-completed |
| `LLM_MODEL_FALLBACK_TO_CPU` | `true` | If GPU unavailable, use CPU Ollama instance |

---

## 7. Key Files

- `api/services/storyline_narrative_materiality.py` — Materiality classification logic
- `api/services/content_refinement_queue_service.py` — Queue management, scheduling, drain
- `api/services/ollama_model_policy.py` — GPU/CPU routing for refinement jobs
- `api/main.py` — Cron route registration (`narrow-debt-drain`)
