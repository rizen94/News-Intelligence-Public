# Chronological accuracy doctrine

Governance for NI Longitudinal Intelligence. Every ingest path, migration, and synthesis feature must comply before production.

**Related:** [LONGITUDINAL_INTELLIGENCE_EXECUTION.md](LONGITUDINAL_INTELLIGENCE_EXECUTION.md) · [DATA_FLOW_ARCHITECTURE.md](DATA_FLOW_ARCHITECTURE.md)

---

## Four rules

### 1. Three timestamps on every fact

| Field | Meaning | Reader-facing |
|-------|---------|---------------|
| `event_date` | When the event happened in the world | Yes (primary cite) |
| `ingestion_date` | When NI first stored the row | Internal / drawer |
| `vintage_date` | When the source last revised the value | Internal / drawer |

Without `vintage_date`, macro series (FRED/ALFRED) and revised Wikipedia dumps silently rewrite history.

### 2. Reference vs living layers never blur

- **Reference** (`intelligence.reference_events`): human-curated, append-only, visually distinct in UI.
- **Living**: RSS `published_at` → `event_date`; row `created_at` → `ingestion_date`.
- **LLMs never assign dates** — only structured fields and approved importers.

### 3. Point-in-time queries are first-class

APIs and synthesis must accept `as_of_date` (UTC). `versioned_facts.valid_from` / `valid_to` remain authoritative for living facts; reference events use `event_date` / `end_date`.

### 4. Arc chapter boundaries are stored and dated

Chapter transitions (e.g. sanctions era starting 2022-02) are rows in arc config, not LLM inference at render time.

---

## Chronology gates (production checklist)

Before a new data source ships:

1. `event_date` ≠ `ingestion_date` on sample rows
2. Timestamps stored as `timestamptz` (UTC)
3. Documented vintage policy (when `vintage_date` updates)
4. Five hand-checked historical date sanity tests pass
5. Citation drawer can show all three timestamps

---

## Schema (Phase 0)

Migration **221** adds provenance columns to:

- `{domain}.articles`
- `intelligence.contexts`
- `intelligence.extracted_claims`
- `intelligence.versioned_facts`
- `public.chronological_events`

Backfill uses best-available fields; rows with uncertain dates set `metadata.provenance_needs_review = true`.

---

## LLM containment (Phase 4+)

Slow reports and narrative finisher:

- Connective prose only
- Dates and numbers from structured IDs
- Post-generation citation density validation
- Predictive language forbidden; use “rhymes with / analogous to”
