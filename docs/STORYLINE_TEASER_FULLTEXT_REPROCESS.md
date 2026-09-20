# Storyline-first teaser fulltext reprocess (ONE-OFF CATCHUP)

**This is a one-off historical catchup, not always-on methodology.**

Steady-state ingest already uses the fulltext-first gate: short RSS stays
`pending`, `content_enrichment` fetches the page, and UIE runs only on real
fulltext. These scripts repair rows that were wrongly marked `enriched` with a
teaser body **before** that gate. Do **not** wire them into AutomationManager
schedules or treat them as a recurring phase.

Reprocess **only** short-`enriched` articles that already sit on a storyline
(~2k rows), not the full ~13.7k orphan teasers. After fulltext + UIE, re-score
membership on those episodes.

## Why scoped

| Cohort | Approx size | Action |
|--------|-------------|--------|
| Teaser `enriched` **in** a storyline | ~1,994 | Reset → fetch → UIE → membership review |
| Teaser `enriched` **not** in a storyline | ~11.7k | Leave parked (UIE-ineligible after fulltext gate) |

`content_enrichment` only selects `NULL` / `pending` / `failed`. Historical
short-`enriched` rows enter the fetch queue **only** via the reset script.

## Prerequisites

1. Deploy the fulltext-first gate + this wave tooling to Widow `/opt/news-intelligence`.
2. Restart API / worker so enrichment and UIE use the new gates.
3. Keep ClinicalTrials.gov / pull-deferred policy unchanged.
4. Do **not** enable global `storyline_membership_review` in `features.yaml` for
   this wave (that would drain every mega, not just wave-tagged IDs).

## Phase 1 — reset + fetch + UIE

From Widow (repo root / `/opt/news-intelligence`):

```bash
# Dry-run counts (expect ~938 politics, ~986 finance, plus small legal/medicine/AI)
PYTHONPATH=api uv run python api/scripts/reset_teaser_enrichment_for_fulltext.py --in-storyline

# Optional: one domain at a time
PYTHONPATH=api uv run python api/scripts/reset_teaser_enrichment_for_fulltext.py \
  --in-storyline --apply --domain politics

PYTHONPATH=api uv run python api/scripts/reset_teaser_enrichment_for_fulltext.py \
  --in-storyline --apply --domain finance

# Or all pipeline domains with storyline membership
PYTHONPATH=api uv run python api/scripts/reset_teaser_enrichment_for_fulltext.py \
  --in-storyline --apply
```

**Do not** `--apply` without `--in-storyline` unless you intentionally want the
full orphan teaser backlog.

What the reset does per row:

- `enrichment_status = pending`, `enrichment_attempts = 0`
- Clears UIE / entity / event pass markers
- Sets `metadata.fulltext_reset = {wave: storyline, at: ..., in_storyline: true}`

Then wait for scheduled automation:

1. `content_enrichment` fetches the page (success → `enriched` + ≥900 chars; miss → `failed`)
2. Successful bodies clear pass markers → `unified_intake_extraction` remaps entities

Monitor: enrichment pending should jump by ~2k, **not** ~13k.

## Character limits (steady-state)

| Stage | Cap | Notes |
|--------|-----|--------|
| Enriched / UIE eligibility | 900 min | `FULLTEXT_MIN_CHARS` — floor, not a ceiling |
| Enrichment store | 50_000 | Almost never hit |
| Contexts | 500_000 | Full body when chunking off |
| Fast NER | 24_000 | `FAST_NER_MAX_CHARS` |
| UIE LLM prompt per article | 24_000 | `UNIFIED_INTAKE_MAX_ARTICLE_CHARS` (aligned with Fast NER; was 8k) |

After CE + UIE drain this wave, run the one-off membership review (not always-on).

## Phase 2 — membership review

After CE + UIE have largely drained the wave:

```bash
# List storylines tagged by the wave
PYTHONPATH=api uv run python api/scripts/review_storylines_after_teaser_fulltext.py

# Run review (propose-only for small episodes; mega auto-apply stays as env default)
PYTHONPATH=api uv run python api/scripts/review_storylines_after_teaser_fulltext.py --apply

# Optional observe-only pass
PYTHONPATH=api uv run python api/scripts/review_storylines_after_teaser_fulltext.py \
  --apply --review-dry-run --domain politics
```

The script calls `review_storyline_membership(domain, id)` directly and **bypasses**
the mega-only drain (`article_count >= 50`). Mid-band actions go to
`intelligence.storyline_membership_actions` for HITL resolve:

`POST /api/{domain}/storylines/membership-actions/{id}/resolve`

## Verify

- Dry-run `--in-storyline` counts ≈ 938 / 986 / 26 / 35 / 9
- After apply: those IDs are `pending`, then `enriched` with `LENGTH >= 900`, or `failed`
- Membership-actions pending only for the reviewed storyline set
- Enrichment queue depth does **not** jump by ~13k
- Orphan teasers remain `enriched` + short and stay out of UIE

## Related code

- Gates (always-on): `api/shared/article_processing_gates.py`
- Enrichment select (always-on): `api/services/article_content_enrichment_service.py`
- Reset (**one-off**): `api/scripts/reset_teaser_enrichment_for_fulltext.py`
- Review (**one-off**): `api/scripts/review_storylines_after_teaser_fulltext.py`
- Membership scoring (reuse): `api/services/storyline_membership_review_service.py`
