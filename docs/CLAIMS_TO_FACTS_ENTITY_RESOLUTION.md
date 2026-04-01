# Claims → facts entity resolution

`claims_to_facts` promotes rows from `intelligence.extracted_claims` into `intelligence.versioned_facts` via `promote_claims_to_versioned_facts()` in `api/services/claim_extraction_service.py`. A claim is promoted only when its **subject string** resolves to `intelligence.entity_profiles.id`.

## Resolution order (per subject variant)

Subject strings are expanded into **variants** (normalized text, whole-string demonyms, **leading demonym + remainder** e.g. *Japanese Chief …* → *japan* plus role-stripped / tail tokens from the rest, stripped role prefixes, last-token fallbacks). For each variant, the resolver tries:

1. **`context_entity_mentions`** for the same `context_id` — exact match, then bidirectional substring match (preferring profiles in the context article’s domain when known).
2. **`article_entities`** for the article linked by **`article_to_context`** — exact `entity_name`, then `entity_canonical` name/aliases, then **bounded substring** match on `entity_name` (max length cap to avoid sentence-long spans).
3. **`entity_profiles.metadata`** — `canonical_name` / `display_name` **exact** (domain-preference when context domain is known).
4. **`entity_profiles.metadata`** — **bounded bidirectional substring** on `canonical_name` / `display_name` (when the variant is at least 4 characters). Domain preference when applicable.
5. **`entity_canonical`** (+ profile) across **active domain schemas** — exact name/alias (domain-preference when applicable).
6. **`entity_canonical.canonical_name`** — **bounded bidirectional substring** (shorter canonical names preferred as tie-breakers). Cap: `CLAIM_RESOLVE_SUBSTRING_MAX_CANON_LEN` (default 120, combined with variant length).
7. **Global `context_entity_mentions`** — exact `mention_text` (domain-preference when applicable).
8. **`pg_trgm`** (if extension installed) — `similarity()` on canonical names per schema, then on profile metadata names. Thresholds default to **0.52** (short strings) / **0.40** (longer); override with **`CLAIM_RESOLVE_TRGM_THRESHOLD_SHORT`** and **`CLAIM_RESOLVE_TRGM_THRESHOLD_LONG`**. Domain preference applies when the context’s article domain is known.

## Database

- Migration **`189_pg_trgm_claim_resolution.sql`** ensures `CREATE EXTENSION IF NOT EXISTS pg_trgm`. Apply via your normal migration path; fuzzy steps are skipped if the extension is missing.
- After adding the extension, restart the API if you rely on the module-level `pg_trgm` availability cache (first connection sets it).

## External bulk seeds (REST Countries, Wikidata, CSV, DB frequency)

See **`docs/EXTERNAL_ENTITY_SEEDS.md`** for `restcountries_seed.py`, `wikidata_sparql_seed.py`, CSV import, and the **second-pass** frequent-subject seeder.

## Curated world-entity seed (matching, not one-by-one discovery)

- **File:** `api/config/seed_world_entities.yaml` — lists major organizations, countries, and public figures per `domain_key`, with optional **aliases** (alternate strings in news text).
- **Run:** `PYTHONPATH=api uv run python api/scripts/seed_world_entities_from_yaml.py`  
  Optional: `--domain politics` (repeatable), `--no-sync` (skip profile sync; not recommended for production).
- **Effect:** Inserts into `{domain}.entity_canonical` (idempotent) and runs **`sync_domain_entity_profiles`** so **`entity_profiles`** exist for claim resolution. Extend the YAML over time; re-run merges new **aliases** onto existing rows.
- **API types:** `seed_canonical_from_gap` and bulk seed accept **ORG / PERSON / GPE** style labels; they are normalized to **`organization` / `person` / `subject`** (`api/services/entity_seed_catalog_service.py`).

## Vague or generic subjects (“Company”, “the Administration”, …)

**Facts require a real `entity_profiles` row.** Do not mint fake canonicals for placeholders that are not real-world entities.

1. **Operator decision in the gap catalog** — Refresh `claim_subject_gap_catalog`, review high `unpromoted_claim_count` rows, then either:
   - **Seed** a real canonical + profile when the string should map to one entity (e.g. a specific person or org with a stable name), or  
   - **Ignore** when the subject is too generic to ever be a useful fact anchor (role labels, “Company” without a name, etc.).

2. **`POST /api/context_centric/claim_subject_gaps/{id}/ignore`** — Marks `(subject_norm, domain_key)` as **`ignored`**. Promotion and backlog counts **skip** those claims so the pipeline does not keep resolving them in every batch.

3. **Extraction quality** — The claim LLM prompt already asks for Wikipedia-style subjects; tighten further if generic triples dominate (see `extract_claims_for_context` in `claim_extraction_service.py`).

4. **Optional later** — Bulk-ignore patterns (script/API) or a small blocklist table if you need many rows without one-by-one gap ids.

## Claim subject gap catalog (research list)

Table **`intelligence.claim_subject_gap_catalog`** (migration **`198_claim_subject_gap_catalog.sql`**) stores a **refreshed snapshot** of unpromoted high-confidence claims whose subject text still has **no** matching `entity_profiles.metadata.canonical_name` and **no** `{domain}.entity_canonical` row (case-insensitive), grouped by domain (from `article_to_context`).

- **Refresh:** `POST /api/context_centric/claim_subject_gaps/refresh` or `PYTHONPATH=api uv run python scripts/refresh_claim_subject_gaps.py`
- **List:** `GET /api/context_centric/claim_subject_gaps`
- **Seed pool:** `POST /api/context_centric/claim_subject_gaps/seed` with `domain_key`, `canonical_name`, `entity_type` (e.g. `PERSON` / `ORG` / `GPE`), optional `gap_id` to mark the row `seeded`
- **Ignore:** `POST /api/context_centric/claim_subject_gaps/{id}/ignore`

After seeding, run **`entity_profile_sync`** (or rely on seed handler) and **`claims_to_facts`** so promotions can resolve—aliases on `entity_canonical` still help where the claim string differs from the canonical form.

## Diagnostics

- **Backlog count** (`get_all_pending_counts` → `claims_to_facts`) uses **`CLAIMS_TO_FACTS_MIN_CONFIDENCE`**, matching `promote_claims_to_versioned_facts` (not a hardcoded 0.7).
- **Dry-run resolution rate:** `sample_unpromoted_claim_resolution_stats()` in `claim_extraction_service.py` runs the same subject resolver on a sample of unpromoted rows without inserting — compare **resolved** vs **unresolved** before changing thresholds or seeding entities.

```bash
PYTHONPATH=api uv run python scripts/diagnose_claims_to_facts.py
PYTHONPATH=api uv run python scripts/diagnose_claims_to_facts.py --sample-limit 800
PYTHONPATH=api uv run python scripts/diagnose_claims_to_facts.py --skip-sample
```

**Duplicate claims:** same context + normalized subject/predicate/object can appear many times. `scripts/merge_duplicate_extracted_claims.py` deletes extras (keeps highest confidence), skipping rows already tied to `versioned_facts`. Dry-run by default; use `--apply`.

**Default promotion floor:** `CLAIMS_TO_FACTS_MIN_CONFIDENCE` defaults to **0.75** in code (override via env).

## Validation (after resolver or `pg_trgm` changes)

Runs a promote batch and reports recent `versioned_facts` from `claim_extraction` (loads `.env` / `.db_password_widow` like the diagnose script):

```bash
PYTHONPATH=api uv run python scripts/validate_claims_to_facts.py
PYTHONPATH=api uv run python scripts/validate_claims_to_facts.py --limit 1000 --dry-run
```

Then confirm automation-scale output:

```bash
PYTHONPATH=api uv run python scripts/verify_intelligence_phases_productivity.py --hours 24
```

See also `docs/TROUBLESHOOTING.md` (“`claims_to_facts` runs but `versioned_facts` stays empty”).

## Fact verification (separate from promotion)

`verify_claim` / automation phase `fact_verification` use `api/services/fact_verification_service.py`: corroboration blends **orchestrator `source_credibility`** (YAML) with legacy source labels, uses **flexible full-text** (AND 3→2→1 terms then `plainto_tsquery`), **excludes the originating article** when `claim_id` is known, maps **tier_1 single-source** to `authoritative_single` (surfaced as corroborated), **tier_2** to `single_established`. **Reference cross-checks** (in `reference_checks` / `reference_boosts`): **Wikipedia** summary overlap; **Wikidata** label/description overlap and **year alignment** for dated claims; **GDELT** DOC mention count (capped low-weight confidence bump); **SEC** — for `finance` only, recent `finance.articles` with `sec.gov` URLs matching `plainto_tsquery` on claim terms; **internal** same-subject claim counts; **LLM entailment** (Llama 8B) only when corroboration is **borderline**, with verdict supports/contradicts/insufficient. Env toggles: **`FACT_VERIFY_WIKIPEDIA`**, **`FACT_VERIFY_WIKIDATA`**, **`FACT_VERIFY_GDELT`**, **`FACT_VERIFY_SEC_FINANCE`**, **`FACT_VERIFY_ENTAILMENT_LLM`** (all default on except where noted in `configs/env.example`). Results are returned on the API / batch summary; they are **not** written to `extracted_claims` rows yet.

## Surname families (article / canonical layer)

When several **person** rows share a surname, **`entity_resolution_service`** can create a **`family`** row on **`{schema}.entity_canonical`** (display name like *Trump family*), link each person with **`intelligence.entity_relationships`** **`member_of_family`**, and resolve surname-only or ambiguous mentions to that umbrella. **`article_entities.entity_type`** stays in sync (**migration `199`** widens checks; **`200`** adds **`family`** to **`story_entity_index`**). Claim subject resolution still maps through **`entity_profiles`** and mention tables—family profiles behave like other canonical-backed profiles after **`entity_profile_sync`**. Env: **`SURNAME_FAMILY_*`**, **`ENTITY_EXTRACTION_MAX_PER_TYPE`**, optional **`ENTITY_EXTRACTION_POST_SYNC`** — see `configs/env.example`.

## Operational levers

- **Entity profile sync:** `sync_domain_entity_profiles` upserts **`entity_profiles`** and **`old_entity_to_new`** in **bulk** (two SQL statements per domain), then runs several rounds of **`backfill_context_entity_mentions_for_domain`**. Tune with **`ENTITY_PROFILE_SYNC_MENTION_BACKFILL_LIMIT`** (contexts per round per domain, default 10000) and **`ENTITY_PROFILE_SYNC_MENTION_BACKFILL_ROUNDS`** (default 3). **`backfill_entity_canonical`** treats names **case-insensitively** when deduping and when linking **`article_entities.canonical_entity_id`**.
- **Entity data:** `context_entity_mentions`, `article_to_context`, `article_entities`, `entity_canonical.aliases`, and profile metadata quality drive match rate more than fuzzy thresholds.
- **New claims:** The claim-extraction prompt asks for short, Wikipedia-style subjects (under ~80 characters when possible).

## Throughput (scheduling, night vs day, drain)

- **Nightly batch size:** If **`NIGHTLY_CLAIMS_TO_FACTS_BATCH_LIMIT`** is unset, it matches **`CLAIMS_TO_FACTS_BATCH_LIMIT`** (`get_nightly_claims_to_facts_batch_limit()` in `claim_extraction_service.py`) so each nightly sequential promote uses the same slice size as daytime unless you override.
- **Daytime drain:** With **`CLAIMS_TO_FACTS_DRAIN=true`** (default), scheduled automation runs **`drain_claims_to_facts_for_automation_task`**: multiple promote batches in one task until no candidates, a time/batch cap, or consecutive batches with zero promotions (unresolved subjects). Nightly sequential runs **one** promote per `run_nightly_sequential_phase` call; **`NIGHTLY_SEQUENTIAL_PHASE_LOOP_CAPS`** repeats that while backlog remains.
- **Workload balancer:** With **`WORKLOAD_BALANCER_ENABLED=true`**, **`claims_to_facts`** is included in the default phase set so effective cooldown shrinks when pending is large relative to batch size. Tune **`AUTOMATION_WORKLOAD_MIN_COOLDOWN_SECONDS`** and **`AUTOMATION_SCHEDULER_TICK_SECONDS`** for how often the scheduler re-checks eligibility.
- **Parallel workers:** **`AUTOMATION_PER_PHASE_CONCURRENT_CAP_OVERRIDES=…,claims_to_facts:2`** — selection uses **`SKIP LOCKED`**; watch DB pool usage.

## DB tuning (indexes and plans)

Promotion selects unpromoted high-confidence rows with **`ORDER BY confidence DESC`** and **`NOT EXISTS`** against **`versioned_facts`** on `metadata->>'source_claim_id'`. If plans show sequential scans or high cost on large tables, use **`EXPLAIN (ANALYZE, BUFFERS)`** on that query and consider:

- A **partial or expression index** supporting the anti-join on **`versioned_facts`** (e.g. btree on `(metadata->>'source_claim_id')` where that key is present), if not already present.
- An index on **`extracted_claims`** that helps **confidence-ordered** scans for unpromoted rows (exact definition depends on existing indexes and statistics).

Ensure **`pg_trgm`** is installed if fuzzy resolution is enabled (**migration `189`**). After adding indexes on large tables in production, prefer **`CREATE INDEX CONCURRENTLY`** outside a transaction when appropriate.
