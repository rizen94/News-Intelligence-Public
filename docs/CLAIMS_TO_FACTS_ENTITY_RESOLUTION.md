# Claims → facts entity resolution

`claims_to_facts` promotes rows from `intelligence.extracted_claims` into `intelligence.versioned_facts` via `promote_claims_to_versioned_facts()` in `api/services/claim_extraction_service.py`. A claim is promoted only when its **subject string** resolves to `intelligence.entity_profiles.id`.

## Resolution order (per subject variant)

Subject strings are expanded into **variants** (normalized text, whole-string demonyms, **leading demonym + remainder** e.g. *Japanese Chief …* → *japan* plus role-stripped / tail tokens from the rest, stripped role prefixes, last-token fallbacks). For each variant, the resolver tries:

1. **`context_entity_mentions`** for the same `context_id` — exact match, then bidirectional substring match (preferring profiles in the context article’s domain when known).
2. **`article_entities`** for the article linked by **`article_to_context`** — exact `entity_name`, then `entity_canonical` name/aliases, then **bounded substring** match on `entity_name` (max length cap to avoid sentence-long spans).
3. **`entity_profiles.metadata`** — `canonical_name` / `display_name` exact (domain-preference when context domain is known).
4. **`entity_canonical`** (+ profile) across **active domain schemas** — exact name/alias (domain-preference when applicable).
5. **Global `context_entity_mentions`** — exact `mention_text` (domain-preference when applicable).
6. **`pg_trgm`** (if extension installed) — `similarity()` on canonical names per schema, then on profile metadata names, with stricter thresholds for short strings. Domain preference applies when the context’s article domain is known.

## Database

- Migration **`189_pg_trgm_claim_resolution.sql`** ensures `CREATE EXTENSION IF NOT EXISTS pg_trgm`. Apply via your normal migration path; fuzzy steps are skipped if the extension is missing.
- After adding the extension, restart the API if you rely on the module-level `pg_trgm` availability cache (first connection sets it).

## Diagnostics

```bash
PYTHONPATH=api uv run python scripts/diagnose_claims_to_facts.py
```

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

## Operational levers

- **Entity data:** `context_entity_mentions`, `article_to_context`, `article_entities`, `entity_canonical.aliases`, and profile metadata quality drive match rate more than fuzzy thresholds.
- **New claims:** The claim-extraction prompt asks for short, Wikipedia-style subjects (under ~80 characters when possible).
