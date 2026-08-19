# v11 Cutover Runbook — Corpus / Research Band + Neurodiversity

**Status:** executed on Widow 2026-07-25 (migrations 282–287, code+SPA deploy, legacy package seed).
Collectors / claim_evidence_appraisal remain **off** until validated.

Development and testing happen on PopOS against `news_intel_dev`
(see `scripts/dev/bootstrap_local_db.sh` and `.env.dev`).

## What ships in v11 (this branch)

| Area | Artifacts |
|------|-----------|
| Dev isolation | `api/shared/dev_guard.py`, `.env.dev`, `scripts/dev/bootstrap_local_db.sh` |
| Processing mode | Migration **282**, `api/shared/domain_processing_mode.py` |
| Neurodiversity silo | Spec + YAML, migration **283**, publication identity columns |
| Evidence appraisal | Migration **284**, `evidence_grade.py`, appraisal service/prompt/phase |
| Literature collectors | Europe PMC + PubMed E-utilities (feature flags default **off**) |
| Provenance repair | `sources` on promote; column `verification_status` writeback; backfill script |
| Query surface | `GET /api/research/{domain}/findings` |
| Editorial packages | Migration **285–290**, `editorial_package_service`, `/api/editorial/*`, modal nav |
| Reduction modality | `editorial_package_reduction_service`, prompt `reduction/package_reduction.md`, automation `editorial_reduction_pass` |
| Narrative modality | `editorial_package_narrative_service`, prompt `narrative/package_narrative.md`, automation `editorial_narrative_pass`, cycle escape with Reduction |
| Research modality | `editorial_package_research_service`, prompt `research/package_research.md`, automation `editorial_research_pass`, cycle escape with Reduction (partner counters) |
| Dual editorial worlds | **v11 packages/`news_stories`** = reader product path; **legacy** writers archived under `api/_archived/editorial/` (shims + flags) |
| Legacy seed | `api/scripts/backfill_editorial_packages_from_legacy.py` (storyline → draft packages) |

## Dual editorial worlds (coexistence)

Until Widow cutover retires the desk path:

| Path | Artifact | Who writes longform |
|------|----------|---------------------|
| **v11 Editor modal** | `intelligence.editorial_packages` → `intelligence.news_stories` (+ citations / decision log) | Editor modal only; citation gate |
| **Legacy desk / vault** | `storylines.editorial_document` columns remain readable for seed/audit; **writers archived** | Re-enable only via `LEGACY_EDITORIAL_WRITERS_ENABLED=1` |

Do not treat storyline megathread prose as the v11 published product. Packages are the handoff artifact between Research / Narrative / Reduction / Editor.

### Local isolation flags (`.env.dev`)

| Flag | Local default | Purpose |
|------|---------------|---------|
| `EDITORIAL_PACKAGES_ENABLED` | on (feature registry) | Package APIs |
| `EDITORIAL_REDUCTION_ENABLED` | **true** | LLM Reduction prune pass + automation drain |
| `EDITORIAL_REDUCTION_AUTO_APPLY` | **true** | Apply uncouples without operator confirm |
| `REDUCTION_MAX_ROUNDS` | **3** | Escape to Editor (with Narrative both-zero) |
| `EDITORIAL_NARRATIVE_ENABLED` | **true** | LLM Narrative assembly + automation drain |
| `EDITORIAL_NARRATIVE_AUTO_APPLY` | **true** | Apply attaches/links without operator confirm |
| `NARRATIVE_MAX_ROUNDS` | **3** | Escape to Editor |
| `EDITORIAL_RESEARCH_ENABLED` | **true** | LLM Research assembly + automation drain |
| `EDITORIAL_RESEARCH_AUTO_APPLY` | **true** | Apply attaches/links without operator confirm |
| `RESEARCH_MAX_ROUNDS` | **3** | Escape to Editor |
| `EDITORIAL_ROOM_LOOP_ENABLED` | **false** | Skip room loop schedule |
| `LEGACY_EDITORIAL_WRITERS_ENABLED` | **0** | Archived writers stay unloaded |
| `DESK_AGENT_WRITEBACK_ENABLED` | **false** | No desk writeback |
| `VITE_LEGACY_DESK_UI` | **0** | Hide SynthesizedView product surface |

## Migration order (Widow cutover)

1. **282** `domain_processing_mode.sql`
2. **283** `neurodiversity_domain_silo.sql`
3. **284** `claim_evidence_appraisal.sql`
4. **285** `editorial_packages_and_news_stories.sql` (packages, handoffs, news_stories)
5. **286** `editorial_package_legacy_seed_index.sql` (idempotent `legacy_seed` unique index)
6. **287** `editorial_packages_primary_modal_system.sql` (allow `primary_modal=system`)
7. **288** `editorial_reduction_decision_actions.sql` (`reduction_pass` / `converged` decisions)
8. **289** `editorial_narrative_decision_actions.sql` (`narrative_pass` decision)
9. **290** `editorial_research_decision_actions.sql` (`research_pass` decision)
10. Register in `public.applied_migrations`
11. Seed neurodiversity RSS via `provision_domain.py` / `seed_domain_rss_from_yaml.py`
12. Dry-run then apply `backfill_editorial_packages_from_legacy.py`
13. Run `api/scripts/backfill_versioned_facts_provenance.py` **on Widow only after**
   approving production writes (script refuses Widow when `ENVIRONMENT=development`)
14. Flip Widow flags to match local isolation (archive writers OFF, packages ON, reduction/narrative/research ON)

## Feature flags (remain off until validated)

| Flag | Default |
|------|---------|
| `CLAIM_EVIDENCE_APPRAISAL_ENABLED` | false |
| `EUROPEPMC_COLLECTOR_ENABLED` | false |
| `PUBMED_EUTILS_COLLECTOR_ENABLED` | false |
| `NEURODIVERSITY_COLLECTORS_ENABLED` | false |
| `features.yaml` entries for collectors + appraisal | `enabled: false` |

Automation schedule `editorial_reduction_pass` drains `in_reduction` packages every ~30m when
`EDITORIAL_REDUCTION_ENABLED=true` (LLM on PopOS via `STRUCTURED_EXTRACTION`).
Automation schedule `editorial_narrative_pass` drains `in_narrative` similarly when
`EDITORIAL_NARRATIVE_ENABLED=true`.
Automation schedule `editorial_research_pass` drains `in_research` when
`EDITORIAL_RESEARCH_ENABLED=true`.

### Narrative/Research ↔ Reduction cycle escape

Cycle escape is **modality-symmetric**. Research packages use `research_rounds` /
`last_research_change_count`; Narrative packages use Narrative counters. Reduction
picks the partner from `presentation_kind` / `reduction_return_modal`.

1. Research or Narrative pass with **changes** → Reduction.
2. Research or Narrative pass with **zero changes**:
   - if last Reduction pass also had zero changes → **Editor** (`ready_for_editor`);
   - else → Reduction once (coherence gate).
3. Reduction pass with **changes** → back to Narrative (or Research for `research_brief`).
4. Reduction pass with **zero changes**:
   - if last partner pass also had zero changes → **Editor** (auto-clear);
   - else → partner modal for confirmation.
5. Max rounds on either side → **Editor** (never infinite ping-pong).

### Reduction modality (operator + automation)

1. Package enters `status=in_reduction` (handoff / rework / Send to Reduction).
2. Automation or **Run reduction pass** (`POST /api/editorial/packages/{id}/reduction/run`) loads
   title+summary+active members/links, then **uncouples** unrelated / weak / geo-entity-mismatched
   members from **this package only** (`member status=removed|quarantined`, link `status=removed`).
   Underlying articles, events, entities, and claims are **never deleted**.
3. Routing follows the cycle escape rules above (not a permanent park in Reduction).

### Narrative modality (operator + automation)

1. Package enters `status=in_narrative`.
2. Automation or **Run narrative pass** (`POST /api/editorial/packages/{id}/narrative/run`) discovers
   candidates (search, coreference, causal edges), attaches members, assigns anchors, creates links,
   updates `summary_stub` — package membership only.
3. Routing follows the cycle escape rules above.

### Research modality (operator + automation)

1. Package enters `status=in_research` (Research allowlist domains: medicine, neurodiversity, AI).
2. Automation or **Run research pass** (`POST /api/editorial/packages/{id}/research/run`) runs a
   **package-scoped** spine (missing claim extract → claims→facts promote → optional literature
   appraisal when `CLAIM_EVIDENCE_APPRAISAL_ENABLED`), then LLM attaches claims/facts/papers/
   hypotheses and research links. Prefer `versioned_fact` over raw claims; refuse attach without
   citeable provenance. Never deletes source rows.
3. Routing mirrors Narrative (changes → Reduction; both-zero / max rounds → Editor).
4. Finance Quiver/EDGAR and politics/legal remain outside this modal (Narrative/HITL).

## Known blockers before Widow apply

### Migration 258 (`claim_fingerprint`)

`258_unique_index_on_extracted_claims_claim_fingerprint.sql` sets
`claim_fingerprint NOT NULL` with a unique index, but no insert path writes the
column. **Applying 258 as written breaks every claim insert.** Fix with a
generated column or DEFAULT/trigger **before** applying on Widow. Do not apply
258 during this cutover unless repaired.

### Embedding dimension mismatch

`intelligence.embedding_chunks.embedding` is `vector(768)` (`nomic-embed-text`).
`settings.EMBEDDING_DIMENSION` historically says 1024. Prefer 768 + nomic for
`processed_document` seeding.

## Rollback

1. Set all v11 feature flags / schedule entries back to disabled (no-op drains).
2. `UPDATE public.domains SET processing_mode='research' WHERE domain_key='neurodiversity'`
   only if you temporarily need research-band drains (not recommended).
3. To remove the silo: deactivate domain (`is_active=false`); dropping schema is a
   separate destructive ops step — not part of soft rollback.
4. Migrations 282–286 are additive; reverse only with explicit DROP scripts if required.

## Widow activation checklist

- [ ] PopOS golden-set appraisal diffs reviewed (`tests/fixtures/evidence_appraisal_golden/`)
- [ ] Poisoning check: weak preprint never grades `strong`
- [ ] `verify_pipeline_queue_alignment.py` static checks for corpus zero-depth on research phases
- [ ] Migrations 282–286 applied on Widow maintenance port `:5432`
- [ ] Legacy writers remain off (`LEGACY_EDITORIAL_WRITERS_ENABLED=0`) unless emergency rollback
- [ ] Optional: `backfill_editorial_packages_from_legacy.py --dry-run` then apply
- [ ] `neurodiversity` present in `public.domains` with `processing_mode='corpus'`
- [ ] Collectors still **off** until first local-validated harvest is approved
- [ ] Monitor shows **zero** research-phase queue_depth for neurodiversity
- [ ] Provenance backfill run with production `ENVIRONMENT` (not `development`)

## Local bootstrap (PopOS)

```bash
./scripts/dev/bootstrap_local_db.sh --with-sample   # applies 282–286 after schema restore
set -a; source .env.dev; set +a
PYTHONPATH=api python3 scripts/dev/verify_editorial_package_local.py
PYTHONPATH=api python3 scripts/verify_editorial_archive.py
PYTHONPATH=api python3 api/scripts/backfill_editorial_packages_from_legacy.py --dry-run
```

Container default: `news-intel-dev-pg` on `127.0.0.1:5433` (Docker pgvector).
Bootstrap applies migrations **282–286** automatically after restore.