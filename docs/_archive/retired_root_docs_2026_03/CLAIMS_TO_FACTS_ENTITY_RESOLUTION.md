# Claims → versioned_facts entity resolution

`claims_to_facts` (`promote_claims_to_versioned_facts` in `api/services/claim_extraction_service.py`) promotes rows from `intelligence.extracted_claims` into `intelligence.versioned_facts` so downstream story-state triggers can run.

## Root cause (fixed)

An earlier resolver:

1. Queried **`entity_profiles.display_name`**, which is **not** a column on `intelligence.entity_profiles` (names live in `metadata` and in domain `entity_canonical`).
2. Used an incorrect **`old_entity_to_new`** join (`entity_profile_id = ep.canonical_entity_id`).

The first failing `SELECT` raised an exception, so **no claim could ever resolve** and `versioned_facts` stayed empty despite millions of successful automation runs.

## Current resolution order

For each claim, `_resolve_claim_to_entity_profile(cur, subject_text, context_id)` tries, in order:

1. **Same context** — `context_entity_mentions` for `context_id` (exact match, then bidirectional substring match on mention text).
2. **Same article** — `article_to_context` → domain schema `article_entities` → `entity_profiles` / `entity_canonical` (name and aliases).
3. **Profile metadata** — `metadata->>'canonical_name'` or `metadata->>'display_name'`.
4. **Domain canonicals** — `entity_profiles` joined to `politics|finance|science_tech.entity_canonical` on `canonical_name` and `aliases`.
5. **Fallback** — any `context_entity_mentions` row with matching mention text (global).

Subjects are **normalized** (strip quotes, optional `Dr.` / `Mr.` prefix).

## Verification

```bash
PYTHONPATH=api uv run python scripts/diagnose_claims_to_facts.py
PYTHONPATH=api uv run python scripts/verify_intelligence_phases_productivity.py --write-report docs/generated/INTELLIGENCE_PHASES_PRODUCTIVITY_REPORT.md
```

## Entity enrichment backlog (related)

`run_enrichment_batch` used to **skip every run** when more than 1000 profiles lacked a Wikipedia section, which prevented `updated_at` / `sections` from changing during large backlogs. That guard is now a **warning only** (threshold `ENTITY_ENRICHMENT_QUEUE_WARN_THRESHOLD`, default `5000`).

## Future work (not implemented)

- Auto-create `entity_profiles` from unmatched high-confidence claims (gated by config).
- Fuzzy / embedding match across canonicals.
- Source-specific normalizers (government acronyms, citation patterns).
