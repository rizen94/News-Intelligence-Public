# Research Paper Pathway — Spec Gap Matrix

> **Purpose:** Track divergence between the architecture described in `RESEARCH_PAPER_PATHWAY.md` (the "what we built") and this design doc (the "what it should be"). Each section maps to a layer in the four-layer digest model: Identity -> Semantics -> Appraisal -> Merge.
>
> **Status:** Architecture defined; implementation incomplete on Layers B, D routing, and reader product.

---

## Architecture Overview

```
Paper ingest -> classify (A) -> profile (B) -> bridge -> appraisal (C) -> merge (D) -> /research fact sheet
     |              |            |          |           |            |            |
  RSS/DOI/arXiv  stamps       question   processed    finding    is/is_not    reader UX
                   content_kind methods  _documents  + quotes   + open         missing
                                findings    (lit docs) grade      ledger       
                                implications
                                subjects
                                domain_facets
```

---

## Layer A — Document Identity & Routing (Structural)

### What exists

| Item | Status | Notes |
|------|--------|-------|
| content_kind=research_paper stamping | Implemented | research_paper_classifier.py handles arXiv, bioRxiv, medRxiv, DOI hosts |
| Pipeline skip for event/claim extraction | Implemented | Classified papers excluded from discovery/proactive/claim/event batches |
| Domain routing (neuro/AI/medicine) | Implemented | Three corridor domains with separate RSS feeds |
| Abstract-only detection | Implemented | processed_documents.metadata.abstract_only flag |
| ArXiv category enrichment | Partially implemented | fetch_arxiv_categories() exists in enrichment service; wired into classification metadata |
| Profile extraction axes | Implemented | question, methods, findings, implications, subjects_studied, domain_facets |

### Gaps

| Gap | Impact | Priority |
|-----|--------|----------|
| No doi_preprint_status structured field in profile (only string DOI in metadata) | Layer B cannot reliably distinguish preprint vs peer-reviewed without cross-reference to appraisal | Medium |
| No content_format field (meta-analysis, systematic review, cohort, RCT, animal, modeling, opinion) | Router cannot decide whether a paper needs full-text or is safe as abstract-only by design type | Medium |
| No explicit "sufficient for profiling" gate | Short content falls through to ArXiv enrichment; if that fails, still gets profiled with garbage | Low |

**Recommendation:** Add doi_preprint_status and content_format fields to research_paper_profiles. Populate from classifier metadata + fetch_arxiv_categories response. This feeds Layer B routing decisions.

---

## Layer B — Paper-Internal Semantics (What Authors Claim)

### What exists

| Item | Status | Notes |
|------|--------|-------|
| LLM profile prompt extracts research_question | Implemented | Extracted from body/abstract text |
| methods_summary extraction | Implemented | Approaches and methodology overview |
| findings_summary extraction | Implemented | Key results (authors interpretation) |
| implications extraction | Implemented | Who/what affected; implications for others |
| subjects_studied extraction | Implemented | Named models, organisms, datasets, systems |
| domain_facets extraction | Implemented | Domain-specific schema (medicine/AI/finance) |

### Gaps — **Critical: this is the biggest current gap**

| Spec Item | Current State | Gap Severity |
|-----------|---------------|-------------|
| Design type (RCT, cohort, meta-analysis, etc.) | Not in profile. Only in appraisal layer. | HIGH - routing decisions need this early |
| Population (age range, diagnosis criteria, n, geographic/clinical setting) | Not extracted | HIGH - scope qualification requires population metadata |
| Intervention/exposure (if any) | Not extracted | MEDIUM - needed for Layer D conflict resolution |
| Primary vs secondary outcomes | Not separated | MEDIUM |
| Effect direction + magnitude with uncertainty | Only in appraisal layer | MEDIUM |
| Authors stated limitations (quoted verbatim) | Not in profile; only in appraisal | LOW-MEDIUM - appraisal has this, but profile should have a pointer |
| What authors explicitly do NOT claim | Never extracted | LOW - useful for "is_not" routing later |

### Why Layer B matters for routing

The current design passes papers to the appraisal pipeline regardless of their design type. A mouse study or opinion piece goes through the same full pipeline as an RCT. This wastes compute and risks contaminating curated boards with low-evidence evidence.

**Fix:** Add a needs_full_text flag to profile that gates whether Layer C runs at all:
- opinion, editorial -> skip appraisal entirely
- animal_in_vitro, modeling -> route to preclinical/proof-of-concept bucket, not is_is_not boards
- cross_sectional, case_control -> limited strength; auto-grade floor = moderate

**Recommendation:** Add these fields to research_paper_profiles:

```json
{
  "study_design_class": "rct|cohort|meta_analysis|systematic_review|case_control|cross_sectional|animal_in_vitro|modeling|opinion|editorial|unknown",
  "population_description": "age range, diagnosis criteria, n, setting",
  "intervention_or_exposure": "what was applied or observed",
  "primary_outcomes": ["outcome 1", "outcome 2"],
  "secondary_outcomes": ["outcome 3"],
  "effect_direction": "positive|negative|mixed|null|unknown",
  "effect_magnitude": "Cohen d=0.4; HR=1.8; OR=2.3; etc.",
  "limitations_mentioned": true|false,
  "authors_no_claims": ["what they explicitly disclaim"],
  "needs_full_text": true|false,
  "sufficient_for_profiling": true|false
}
```

---

## Layer C — Evidence Appraisal (The Fact Engine)

### What exists

| Item | Status | Notes |
|------|--------|-------|
| study_design vocab (all values) | Implemented | meta_analysis through unknown |
| peer_review_status vocab | Implemented | peer_reviewed, preprint, registry_record, gray_literature, unknown |
| paper_support vocab | Implemented | supported_by_own_evidence through insufficient_reporting |
| replication_status vocab | Implemented | replicated_independent through needs_follow_up |
| evidence_grade vocab | Implemented | strong through unsubstantiated |
| Verbatim quote requirement + validation | Implemented | assert_valid_appraisal_payload checks quotes are substrings |
| "Never invent quotes" hard rule in prompt | Implemented | If no usable quote -> paper_support=insufficient_reporting |
| "Abstract-only != strong grade" rule in prompt | Implemented | Hardcoded in evidence_appraisal.md prompt |
| needs_follow_up != disproved clarification | Implemented | Explicitly stated in prompt hard rules |
| "Do not upgrade design" rule | Implemented | Editorial is opinion; mouse study stays animal_in_vitro |

### Gaps (Optional extensions per spec)

| Spec Item | Current State | Gap Severity |
|-----------|---------------|-------------|
| Conflicts of interest / funding | Not extracted | MEDIUM - informs trust tier, especially for industry-funded papers |
| Selection bias / spectrum bias signals | Not extracted | LOW-MEDIUM - clinical sample vs population matters for scope |
| Outcome switching or p-hacking signals | Not extracted | LOW - hard to detect automatically |
| Comparator quality (placebo, treatment as usual, active control) | Not extracted | MEDIUM - critical for interpreting RCT strength |
| Follow-up horizon (short-term vs long-term outcomes) | Not extracted | LOW-MEDIUM - matters for intervention validity |

### Recommendation

Add to evidence_appraisal.md prompt as optional fields:

```json
{
  "funding_disclosure": "text or null",
  "potential_conflict_of_interest": "none|disclosed_undisclosed|mixed|null",
  "comparator_type": "placebo|treatment_as_usual|active_control|no_comparator|unknown|null",
  "follow_up_duration": "6 months|12 months|longitudinal|null",
  "selection_bias_notes": "text or null"
}
```

Phase these in after the core pipeline is stable. These feed appraisal notes and inform whether something stays "open".

---

## Layer D — Subject Merge (Autism Fact Sheet)

### What exists

| Item | Status | Notes |
|------|--------|-------|
| auto_merge_from_appraisal merges into knowledge_profiles | Implemented | is/is_not/open assertions + research_claim_ledger |
| Curated subject matching | Implemented | _curated_subject_matches uses aliases + substring |
| Never wholesale-replace arrays | Implemented | _merge_assertion_lists appends, deduplicates by key |
| Open questions from inconclusive verdicts | Implemented | Hypothesis read as open question when it looks like a question |
| Grade floor for "supported" assertions | Implemented | _GRADE_FLOOR = {strong, moderate, limited}; weaker -> stays open |
| /research API endpoints defined | Implemented | GET /api/reader/research/subjects, GET /.../{entity_id} |

### Gaps — **Routing gaps: these are product-risk items**

| Spec Requirement | Current State | Gap Severity |
|-----------------|---------------|-------------|
| Off-topic gate: Non-Autism neuro papers must NOT land on Autism board | Substring match only. A paper about autistic traits in general population can match Autism subject even if the curated board is for clinical ASD research. | CRITICAL - exactly the risk the spec warns against |
| Subjects are curated anchors, not automatic dumps | Partially addressed in RESEARCH_PAPER_PATHWAY.md ("does not fall back to domain first subject") but no hard gate exists | HIGH |
| Normalized claim text format | Claim text is verbatim appraisal finding_text. No normalization to X associated with Y in population Z under conditions W | MEDIUM - needed for deduplication across papers |
| Scope qualifiers (subgroup, age band, definition of autism) | Only in free-text assertion. Not tracked as structured fields. | HIGH - two studies about different ASD subgroups should be distinguishable on the board |
| Provenance chain: paper -> appraisal -> ledger row -> member for reader | Partially | member_row_id is preserved; document_id is stored; but no explicit paper->ledger linkage in knowledge_profile assertions |
| Conflict policy (two moderate single studies disagree -> open with both cited) | Implicit via dedup logic | LOW - works by accident, not by design |
| Meta-analysis shifts -> update is with supersession note, not silent replace | Works by accident (merge appends; prior rows remain) | Verified |

### Critical Fix: Off-Topic Gate

The _curated_subject_matches function uses substring matching on aliases. A paper about autistic traits in neurotypical adults could match the Autism curated subject via partial word match on autistic -> autism.

**Fix:** Add an off_topic_score field to appraisal output:
- Score based on: population (clinical ASD vs general population), subject match precision (exact alias vs substring), and design type
- If off_topic_score > threshold, appraisal skips merge entirely and lands in a unmatched bucket for manual review or domain-level routing
- The current _haystack_for_subject_match already builds a haystack from subjects_studied + title + finding_text - enhance it to include explicit exclusion keywords

### Recommendation: Structured scope qualifiers

Add to knowledge_profile assertions:

```json
{
  "text": "normalized claim or verbatim quote",
  "verdict": "substantiated|proved|disproved|inconclusive|not_applicable",
  "evidence_grade": "strong|moderate|limited|preliminary|unsubstantiated",
  "scope_qualifiers": {
    "subgroup": "ASD level 1|ASD level 2|intervention-naive|medicated|null",
    "age_band": "3-5 years|8-12 years|adult|null",
    "asd_definition": "DSM-5|ADI-R+ADOS|parent_report|unknown|null"
  },
  "provenance": {
    "paper_title": "...",
    "appraisal_id": 42,
    "member_row_id": 7,
    "source_url": "..."
  }
}
```

---

## Product Layer — Reader-Facing Views

### What exists

| Item | Status | Notes |
|------|--------|-------|
| get_research_subject() API | Implemented | Returns entity, proteins, claims, assertion_counts |
| upsert_research_claim() API | Implemented | For manual ledger entries |
| package_knowledge_profile prompt | Implemented | Renders is/is_not/open as reader-facing markdown |
| /research concept defined | Defined | Not a paper-headline feed; it's a curated fact sheet |

### Gaps

| Spec Item | Current State | Gap Severity |
|-----------|---------------|-------------|
| Two twins, one spine: Research twin architecture separated from news | Pipeline separation exists (discovery/proactive skip research papers) but the merging layer still writes to knowledge_profiles which is also used by news storylines | MEDIUM - should clarify that research assertions and news facts coexist in same table but are distinguishable by source |
| Fact vs fiction mapping | Not enforced anywhere. The spec maps: widely believed weak/absent evidence -> open or is_not, debunked causal myth -> is_not. Currently no mechanism to mark a claim as debunked when new evidence contradicts it. | HIGH |
| Cross-links: news <-> research | No path for a news headline (Study shows X cures autism) to be checked against the research ledger. | HIGH - this is the killer feature of having research in the system |
| Research subject boards as curated topic index | API exists; UI missing | MEDIUM |

### Recommendation: Fact vs Fiction Enforcement

Add a belief_status field to knowledge_profile assertions:
- supported_by_evidence -> enters is bucket when grade is moderate+ and replicated
- claimed_but_unsubstantiated -> enters open when single study, weak evidence
- contradicted_by_better_studies -> enters is_not when higher-grade evidence exists that directly opposes it
- stale_belief -> separate flag; for widely held beliefs that newer evidence undermines

This is distinct from the verdict (which describes what THIS paper says). belief_status describes how this assertion sits in the corpus over time.

### Recommendation: News <-> Research Cross-Links

When a news article arrives and contains a claim about research (Study shows...), check:
1. Does article.title or content contain research-related trigger words? (study, research, found, discovered, evidence suggests)
2. If yes -> cross-reference against research_claim_ledger for matching entity
3. Append a Literature Check section to the news storyline showing relevant ledger rows

---

## Implementation Priority Matrix

| Gap | Impact | Effort | Priority |
|-----|--------|--------|----------|
| Layer B: Add design type, population, intervention fields | HIGH (affects all downstream) | MEDIUM | P1 - block appraisal routing |
| Layer D: Off-topic gate for curated boards | CRITICAL (product integrity) | LOW-MEDIUM | P1 - fix immediately |
| Fact vs fiction mapping (belief_status) | HIGH (core product differentiator) | MEDIUM | P2 |
| News <-> research cross-links | HIGH (killer feature) | MEDIUM | P2 |
| Scope qualifiers for assertions | HIGH (dedup quality) | LOW-MEDIUM | P3 |
| Evidence appraisal extensions (COI, bias, comparator) | MEDIUM (appraisal depth) | LOW | P3 |
| Research reader UX / topic index UI | MEDIUM (visibility) | HIGH | P4 - later |

---

## Current Pipeline Flow Diagram

```
RSS/ArXiv/PubMed -> classify_research_paper() -----> content_kind=research_paper
                                                       pipeline_skip for event/claim
research_paper_profile_service                         |
  .ensure_pending_profile()    ----> research_paper_profiles          |
  .drain_research_paper_profiling()                    |              v
  (LLM profile: question, methods, findings,           |  LLM Extract -> Layer A + partial B
   implications, subjects, domain_facets)              |              |
                                                       |    bridge upserts to processed_documents(source_type=literature)
research_literature_bridge_service ------------------> claim_evidence_appraisal_service
                                                         (evidence_grade, study_design, paper_support, replication_status, quotes)
claim_evidence_appraisal_service                        |
  .run_claim_evidence_appraisal_batch()                |    auto_merge_from_appraisal()
  .appraise_document()                                 |      -> knowledge_profiles (is/is_not/open)
  _insert_appraisal()                                  |      -> research_claim_ledger
                                                       |              |
  _assertions_from_appraisal_row() --------------------+--> /research subject API
    -> is_list, is_not_list, open_list                 |       (GET /research/subjects/{entity_id})
```

**Key missing node:** Between classify and profile, there's no design-type filter that could skip low-value papers early. Between merge and ledger, there's no belief_status computation. Between news intake and storylines, there's no research cross-reference check.

---

## Notes on What's Already Working Well

The following are solid and don't need changes:

1. **Refusal contract:** "No quotes -> insufficient_reporting" is correctly enforced in both appraisal prompt and validation layer
2. **Merge logic:** Never wholesale-replace arrays; dedup by key; open questions filtered against is/is_not - this prevents silent overwrites
3. **Grade floor:** Weak evidence (preliminary/unsubstantiated) cant enter is bucket regardless of paper_support
4. **needs_follow_up semantics:** Correctly distinguished from contradicted/disproved
5. **Abstract-only constraint:** Prompt explicitly forbids strong grade on abstract-only input
6. **Domain isolation:** News discovery/proactive/claim/event batches skip content_kind=research_paper
7. **Subject routing without fallback-to-first-subject:** Fixed in a prior fix; currently skips merge when no curated board matches

---
