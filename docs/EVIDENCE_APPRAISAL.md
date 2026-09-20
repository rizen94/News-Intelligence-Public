# Evidence Appraisal (v11 corpus band)

Corpus-mode domains (e.g. `neurodiversity`) stop at intake → fact promotion →
**evidence appraisal** → indexing. Research-mode domains additionally run
storyline / chemistry / narrative phases over graded facts.

## Goals

| Band | Goal |
|------|------|
| **Corpus** | Intake, fact checking, sorting/tagging/indexing |
| **Research** | Connections and insights from **verifiable, trackable** content with an audit trail |

## Vocabularies (`api/shared/evidence_grade.py`)

- `study_design`: meta_analysis, systematic_review, rct, cohort, case_control, cross_sectional, case_report, animal_in_vitro, modeling, opinion, unknown
- `peer_review_status`: peer_reviewed, preprint, registry_record, gray_literature, unknown
- `paper_support`: supported_by_own_evidence, partially_supported, not_supported_by_own_evidence, insufficient_reporting
- `replication_status`: replicated_independent, replicated_same_group, single_study, contradicted, **needs_follow_up**
- `evidence_grade`: strong, moderate, limited, preliminary, unsubstantiated

**`needs_follow_up` ≠ false.** Absence of replication must never be rendered as falsified.

## Refusal contract

The grader prompt (`api/config/prompts/research/evidence_appraisal.md`) requires
quoted spans from the document. If there is no quote, `paper_support` must be
`insufficient_reporting` — enforced by `assert_valid_appraisal_payload`.

Abstract-only literature (`articles.abstract_only=true`) cannot receive
`evidence_grade=strong`.

## Storage

- `intelligence.claim_evidence_appraisal` (migration 284)
- `intelligence.research_claim_ledger.verdict` includes `needs_follow_up`
- Query: `GET /api/research/{domain}/findings` (citation chain on every row)

## Phase registration

- Feature: `claim_evidence_appraisal` in `features.yaml` (`enabled: false`)
- Env: `CLAIM_EVIDENCE_APPRAISAL_ENABLED` (default false)
- Automation schedule + `PHASE_POLICIES` (PopOS GPU)
- Queue depth: `_count_claim_evidence_appraisal_pending` → SSOT
  `count_claim_evidence_appraisal_due`

## Collectors (literature identity)

- `api/collectors/europepmc_collector.py` — OA full text + references → `processed_documents.citations`
- `api/collectors/pubmed_eutils_collector.py` — MeSH PublicationType → study_design
- Domain columns: `doi`, `pmid`, `pmcid`, `nct_id`, `abstract_only` on corpus silos

## Local development

See [V11_CUTOVER_RUNBOOK.md](V11_CUTOVER_RUNBOOK.md). Develop against
`news_intel_dev` on PopOS; never write Widow until the cutover checklist.
