# News Intelligence Feature Audit (v11 generations) — 2026-07-25

**Scope:** Read-only audit of features across three architectural generations vs the north-star loop: *ingest RSS/docs → preprocess + compare → story updates + new highlights in &lt;6 hours*.  
**Evidence date:** 2026-07-25/26 (Widow `news_intel` via postgres-mcp).  
**Sources:** `api/config/features.yaml`, `AGENTS.md`, `PROJECT_STATUS.md`, `docs/PIPELINE_AND_AUTOMATION.md`, `docs/FEATURE_REGISTRY.md`, `docs/V11_CUTOVER_RUNBOOK.md`, `api/_archived/`, `api/services/automation_manager.py`, `api/shared/intake_catchup_latency.py`, `api/shared/assembly_phase_order.py`, live DB counts/heartbeats.  
**Constraint:** Analysis only — no code/config/DB changes.

---

## Addendum — binding assembly model (2026-07-25)

**Operator decision (SSOT intent):** Keep **`chronological_events`** and **`tracked_events`**. Drop atom / megathread / chemistry product vocabulary. Meld chemistry-named work into **matching → related-event chains → storyline → Research/Narrative/Reduction/Editor**. Do **not** expand collision / harden / stimulus features.

- Binding doc: [`docs/ASSEMBLY_MODEL.md`](../ASSEMBLY_MODEL.md)
- Critical path remains: RSS → enrichment → UIE → CE → matching/attach → storyline update → Briefings/editorial
- Chemistry / beaker rows below stay as historical audit evidence; treat them as **parked / meld**, not a parallel product to grow
- Code symbols (`protein_harden`, `collision_sampling`, …) may remain until a later rename pass

---

## Executive summary

Three generations coexist and **compete for the same jobs** (events, membership, narrative delivery):

| Generation | Intent | Live reality (Jul 2026) |
|---|---|---|
| **v5 original** | Per-phase intake + story_continuation + editorial documents / digests / briefings | Intake phases archived; **Briefings UI still reads legacy `storylines.editorial_document`**; digests schedule-retired but code/table remain |
| **Chemistry / beaker** | Storylines as proteins; loose→solid bonds (`inference_stage`); collision / stimulus_rag / protein_harden; blend scores | Graph tables populated (~16k proposals, ~31k links) but **`embedding_chunks=0`**, **`hypothesized=0`**, **`rag_evidence_pull_queue=0`**; accepted CONCEPTUAL_REVIEW calls similarity-attach “wrong at the root” vs event-core |
| **v11 modalities** | `editorial_packages` → Research/Narrative/Reduction/Editor → cited `news_stories` | **Cutover applied on Widow 2026-07-25** (mig 282–287; packages on; legacy writers off). **53 packages / 31 draft stories / 0 package links** — seeded shell, not a live insight loop |

The **6h SLA path is well-defined in code** (`intake_catchup_latency.py`: enrichment → UIE → context_sync → topic_clustering → storyline link) but **delivery is disconnected**: Monitor measures preprocess latency; Dashboard/Briefings surface legacy storyline prose and raw contexts; v11 `news_stories` are not wired into “What’s New.”

**Critical operational finding:** `content_enrichment` heartbeat is **auto-silenced** (since 2026-07-21, “flat backlog + zero-progress”). `chronological_events` was empty until today’s recovery (**11 rows**, newest ~hours ago) while **`tracked_events` holds 2,425** as a parallel rail. That single event-rail failure collapses story_continuation, coreference, and highlight freshness even when UIE pass markers look healthy (**~71.7k UIE-cleared articles**).

---

## Ground-truth snapshot (DB)

| Object | Count / state | Notes |
|---|---|---|
| UIE-cleared articles (5 research domains) | **71,655** | `last_terminal_state` ∈ processed_* |
| Articles total (5 domains) | ~87.6k | politics 31.6k, finance 27.6k, AI 15.7k, medicine 9.0k, legal 3.7k |
| Storylines | **61** (12/15/18/15/1) | Tiny vs article volume — assembly bottleneck or hygiene over-prune |
| Topic clusters (finance alone) | **4,322** | Staging clusters ≫ storylines; never auto-promote |
| `public.chronological_events` | **11** (all recent) | Was empty; unique-index / save_events failure; catchup in flight |
| `intelligence.tracked_events` | **2,425** | Growing; parallel event rail |
| `event_coreference_links` | **0** | Schema live, unused |
| `event_article_membership` | **76** | Event-core barely engaged |
| `graph_connection_proposals` | **16,144** | candidate 11,158 / established 4,917 / quarantined 69 / **hypothesized 0** |
| `graph_connection_links` | **~30.8k** | Distillation active (recovered from false silence) |
| `embedding_chunks` | **0** | Embedding-link / collision beaker starved |
| `rag_evidence_pull_queue` | **0** | stimulus_rag idle |
| `causal_edges` | **504** | Harvest writing; blend hook still deferred |
| `rolling_arcs` | **4** | Thin |
| `editorial_packages` | **53** | Seeded; statuses mix in_editing / in_reduction / in_research / draft |
| `editorial_package_links` | **0** | Modal passes not creating links |
| `editorial_package_members` | **~2.9k** | From legacy seed |
| `news_stories` | **31** (all `draft`) | Not published / not on Dashboard |
| `claim_evidence_appraisal` | **0** | Flag off |
| `trading_signals` | **2** | Peripheral |
| `weekly_digests` | **16** (newest 2026-06-01) | Schedule-retired; table stale |
| `neurodiversity.articles` | **0** | Corpus silo empty (collectors off) |
| Heartbeats of note | `content_enrichment` **silenced**; `entity_profile_build` **silenced**; UIE / claim / topic / storyline_assembly running on PopOS; chemistry phases “recovered” awaiting schedule |

Domains: all six `is_active`; five research + `neurodiversity` corpus.

---

## Summary table

Legend — **Gen:** v5 / chem / v11 / infra. **Status:** implemented / partial / abandoned. **6h:** core / peripheral / no. **Verdict:** keep / fix / merge / retire.

| Feature | Gen | Status | DB evidence | Serves 6h? | Verdict |
|---|---|---|---|---|---|
| `collection_cycle` / RSS ingest | infra | implemented | Articles still inserting (~80/24h politics+finance+legal) | **core** | **keep** |
| `content_enrichment` | infra | implemented but **silenced** | Heartbeat silenced Jul 21; pending enrich≈0 now | **core** | **fix** (unsilence + idle-silence policy) |
| `fulltext_pull_gate` | infra | implemented | ClinicalTrials triage | core (quality) | **keep** |
| `unified_intake_extraction` | v10 spine | implemented | ~71.7k cleared; PopOS heartbeats alive | **core** | **keep** (protect GPU time) |
| Legacy entity/event/sentiment/quality/ml/metadata | v5 | abandoned→archived | Rollback-only | no | **retire** (keep rollback flag) |
| `spine_sql_tail` / `link_indexer` / co-mention | infra | implemented | link_indexer pass markers on many articles | core→peripheral | **keep** |
| `context_sync` | infra | implemented | Inline from enrich + cron; heartbeat stale Jun 16 | **core** | **fix** heartbeat freshness |
| `article_signal_gate` + governor | infra | implemented | Off by default | peripheral (throughput lever) | **keep** — enable if UIE backlog returns |
| `rss_feed_silencing` | infra | implemented | medicine/AI 0 articles/24h may indicate quiet or silenced feeds | peripheral | **keep** — audit yield |
| `chronological_events` + UIE `save_events` | v5/v10 | **partial / broken until today** | **11 rows** vs 71k UIE | **core** (events for updates) | **fix** (unique index + catchup) |
| `chronological_events_catchup` | infra | staged/partial | Recovery path for flush/orphan | core when triggered | **keep** until CE healthy |
| `topic_clustering` | v5/v10 | implemented | Thousands of clusters; PopOS OK | peripheral (SLA-listed) | **merge** role: staging only; don’t treat as insight |
| `storyline_discovery` (post-spine full scan) | v5 | abandoned | In `POST_SPINE_RETIRED_PHASES` | no | **retire** schedule (done); clarify vs SLA name |
| Storyline attach / `storyline_automation` | v5→chem | implemented | 61 storylines | **core** (insight surface) | **fix** — quality + volume |
| `story_continuation` | v5 | implemented / starved | CE nearly empty ⇒ no input | **core** for updates | **fix** (depends on CE) |
| `narrative_first_linking` | chem-adj | implemented | Inline in automation | core | **merge** into one attach SSOT |
| `blend_link_score` | chem | implemented | Called from ≥5 services | peripheral scoring | **merge** single call-site |
| `tracked_events` | v5/v10 | implemented | **2.4k** rows | core (investigations) | **keep** as megathread rail — reconcile with CE |
| `event_coreference` / cluster links | chem | partial | **0 links** | peripheral | **fix or retire** until CE volume exists |
| `event_core_membership` | chem→v11 | partial | **76** memberships; no schedule sweep | core (membership SSOT intent) | **fix** — finish as winner of attach |
| Chemistry beaker (`collision_sampling`, `stimulus_rag`, `protein_harden`) | chem | partial | No hypothesized; empty RAG queue; empty embeddings | **no** (gated after catchup) | **retire from hot path** / park until event-core Phase 4 |
| `embedding_link_candidates` | chem | partial | Recovered silence; **0 embedding_chunks** | no | **fix** embeddings or **retire** phase |
| `graph_connection_distillation` | chem | implemented | ~31k links; active | peripheral | **keep** as non-arbitrating proposals only |
| `storyline_hygiene` / membership_review | chem | staged | 9.7k membership_actions | peripheral | **keep** (prevents kitchen-sink) |
| Staged-off C-series (lifecycle, dual_centroid, hyperedge, gap, disagreement, dossier diffs, arc_stage, membership_llm, drift_review) | chem | abandoned mid-flight | Code present, flags off | no | **retire** or freeze until event-core lands |
| `causal_edges` | chem | partial | 504 edges; not in production blend | no | **park** — don’t expand until wired |
| `rolling_12m_arcs` | chem | thin | 4 rows | no | **park** |
| Public-data collectors (CourtListener, FR, Congress, EDGAR, GDELT, …) | v10.1 | under_developed | All disabled | no | **park** — don’t dilute 6h focus |
| Corpus collectors + `claim_evidence_appraisal` | v11 | under_developed | 0 appraisal; 0 neuro articles | no (research silos) | **park** until research domains hit 6h |
| `editorial_packages` + modal passes | v11 | partial (seeded) | 53 pkgs, **0 links**, 31 draft stories | **no** (slow lane) | **keep as slow lane**; don’t block 6h; wire publish→UI later |
| Legacy `editorial_document` / Briefings report | v5 | implemented (writers archived) | 32 storylines still have docs; Report UI live | **core delivery today** | **keep until** news_stories feed Briefings |
| Digests / daily_briefing_synthesis | v5 | abandoned (schedule) | 16 stale weekly_digests | no | **retire** reachable code/routes |
| Desk agent writeback / editorial_room_loop | v5 | staged off / archived | Flags off on Widow | no | **retire** after packages prove out |
| `entity_profile_build` / dossier compile | context | implemented but silenced / stale | EPB silenced | no | **demote** — out of SLA |
| Monitor + `intake_catchup_latency` | infra | implemented | Only place 6h is measured | **core ops** | **keep** — extend to “surfaced” KPI |
| Trading signals / USD tracker / public demo / investigation | misc | implemented / peripheral | Thin or orthogonal | no / ops | **keep** (don’t expand) |
| `pipeline_controller` / PopOS phase workers | infra | implemented | UIE/claim/topic/assembly heartbeats fresh | **core** | **keep** |

---

## Competing implementations (which should win)

### 1. Event rails: `chronological_events` vs `tracked_events` vs coreference vs event-core membership

| Contender | Role claimed | Winner |
|---|---|---|
| `chronological_events` | Per-article timeline atoms from UIE | **Keep as atom SSOT** — must be healthy; currently broken volume |
| `tracked_events` | Cross-domain investigative megathread | **Keep as megathread SSOT** (event-core direction) |
| `event_coreference_links` | Soft same-event clusters on CE | **Defer** until CE has volume; 0 rows today |
| `event_article_membership` | Typed article↔TE membership | **Win for membership** once event-core finishes |

**Call:** Do not invent a fifth event object. Atoms = CE; megathreads = TE; membership = `event_article_membership`. Coreference links are optional clustering on CE after volume returns. Read-only `event_reconciliation` stays diagnostic until arbitration exists.

### 2. “Does this belong?” attach paths

| Contender | Mechanism |
|---|---|
| `story_continuation` | CE → SEI / event-type → LLM → storyline |
| `narrative_first_linking` | TE first, then storylines; overlap + blend |
| `blend_link_score` + consolidation / protein_harden | Similarity bag scoring |
| Chemistry proposals → distillation | Graph bonds |
| `event_core_membership` | Co-reference / rare-anchor founding (intended successor) |

**Call:** **event_core_membership wins** for evidence membership (per accepted CONCEPTUAL_REVIEW). Collapse narrative_first + story_continuation into one attach path that *consults* TE membership and uses blend only as a non-arbitrating prior. Chemistry proposals remain exploratory — **non-arbitrating** until Phase 4 reconcile.

### 3. Narrative / insight delivery

| Contender | Live? | Winner |
|---|---|---|
| `storylines.editorial_document` → `GET /api/{domain}/report` | **Yes — Briefings** | **Interim winner** for &lt;6h “story updates” |
| Dashboard “What’s New” (`intelligence.contexts`) | Yes — raw | Keep as intake pulse only |
| v11 `news_stories` (Editor) | Draft only; not on Dashboard/Briefings | **Longform winner** (slow lane, citation gate) |
| Digests / daily briefing synthesizers | Schedule dead; code zombie | **Retire** |
| Chemistry / rolling arcs / causal CoT | Sparse | Not delivery surfaces |

**Call:** Split products explicitly:

1. **Fast lane (&lt;6h):** preprocess + attach → storyline/TE material update → Briefings/Dashboard delta (can stay on lightweight lede or auto stub until Editor publishes).
2. **Slow lane (hours–days):** packages → Research/Narrative/Reduction → Editor → published `news_stories`.

Do not expect the modality cycle to meet the 6h SLA.

### 4. Topic clusters vs storylines

**Call:** Topic clusters = **staging only** (manual `convert_to_storyline`). Storylines (and TE megathreads) = insight objects. Stop measuring “insight health” by cluster counts.

### 5. Chemistry beaker vs v11 Research modality vs claim_evidence_appraisal

All three claim “pull evidence / harden connections.”

**Call:** For research domains: **event-core + storyline attach** for connections; v11 **Research modal** for package-scoped evidence; corpus appraisal only for corpus-mode domains. **stimulus_rag / protein_harden** demoted until embeddings and CE exist — otherwise they burn schedule noise.

### 6. Dual domain→product maps

`briefing_filter_helper` (`narrative_briefing` vs `connection_digest`) vs `post_processing_modals.yaml` allowlists — agree today, not SSOT.

**Call:** **One map** (prefer `post_processing_modals.yaml` or domain specs); briefing helper should import it.

---

## 6-hour SLA path (minimal chain)

Defined in `api/shared/intake_catchup_latency.py` (default `CATCHUP_SLA_HOURS=6`):

```
collection_cycle (RSS / docs)
  → content_enrichment          [Pass 0 — currently AUTO-SILENCED]
  → unified_intake_extraction   [Pass 1 — PopOS 5090 bottleneck; ~71.7k done]
       ↳ MUST write chronological_events via save_events  [BROKEN until today]
  → spine_sql_tail              [Pass 2 — SQL; co-mention]
  → context_sync                [often inline from enrich]
  → topic_clustering
  → storyline link / automation [61 storylines]
  → story_continuation / event-core attach  [starved without CE]
  → SURFACING (today): Briefings editorial_document + Dashboard contexts
       (NOT yet: news_stories publish)
```

**Explicitly out of 6h scope (correct):** EPB, dossier, chemistry beaker (after `catchup_clear_threshold`), editorial modal rounds, corpus appraisal.

### Bottlenecks & blockers (priority)

1. **`content_enrichment` auto-silence** — new RSS bodies may not enrich if silence persists when backlog appears; idle-silence policy is hostile to SLA.
2. **`chronological_events` near-empty** — breaks continuation, highlights, TE founding from atoms; catchup must finish; unique index must stay.
3. **UIE GPU contention** — sole LLM spine step; chemistry/editorial LLM passes must stay behind catchup gate (already intended).
4. **Attach fragmentation** — three “belong?” paths + empty CE ⇒ few storyline updates despite 71k UIE-complete articles (61 storylines).
5. **Delivery gap** — even if attach works, “new highlights” UI is legacy; v11 packages don’t close the SLA.
6. **`embedding_chunks=0`** — chemistry embedding phases look scheduled but cannot produce hypothesized bonds.

### What must be kept / fixed / retired for &lt;6h reliability

| Action | Items |
|---|---|
| **Keep & protect** | RSS collection, enrichment, UIE, spine_sql_tail, context_sync, pipeline_controller, PopOS UIE worker, Monitor SLA metric, storyline/TE surfaces for Briefings |
| **Fix now** | Unsilence enrichment safely; finish CE catchup + save_events integrity; restore story_continuation input; single attach SSOT toward event-core; feed Briefings from material storyline/TE changes (not only stale editorial_document) |
| **Retire / park** | Chemistry hot-path while embeddings/CE empty; staged-off C-series; zombie digest routes; public collectors expansion; corpus appraisal until research loop green |
| **Slow lane (don’t block 6h)** | editorial_packages modal cycles → news_stories; wire publish into UI only after fast lane green |

---

## Retirement recommendations

| Feature / cluster | Justification | Risk if retired |
|---|---|---|
| **Chemistry beaker schedules** (collision_sampling, stimulus_rag, protein_harden) while `embedding_chunks=0` & hypothesized=0 | Burns ops attention; CONCEPTUAL_REVIEW demotes them for membership; no RAG queue | Low — distillation/links already exist; re-enable after embeddings + event-core Phase 4 |
| **Staged-off C-series** (storyline_lifecycle, dual_centroid, hyperedge_meta, narrative_gap, source_disagreement, entity_dossier_diffs, arc_stage_inference, storyline_membership_llm, graph_link_drift_review, stimulus_rag_* specialized sources) | Registered, never on; dilutes focus | Low — code can stay; remove from “active roadmap” |
| **Digest / daily_briefing / editorial_briefing synthesizers (reachable code)** | features.yaml archived; table stale since Jun 1 | Low — Briefings use `/report`; confirm no OWUI consumer |
| **Legacy editorial writers / desk writeback** | Already off on Widow; packages are handoff | Medium until news_stories appear on Briefings — keep rollback flag |
| **`relationship_extraction` / LLM topic_clustering_service / pattern_recognition** | Already archived | None |
| **Parallel public-data collectors (under_developed)** | Don’t compete with RSS 6h until CE/attach fixed | Low — leave code, keep flags false |
| **Corpus neurodiversity collectors + appraisal** | Empty silo; not Widow priority for 6h | Low — park |
| **`causal_edges` expansion / Neo4j projection** | 504 edges unused in blend | Low — stop expanding |
| **`rolling_12m_arcs` push** | 4 rows; overlaps curated arcs | Low |
| **Demote EPB / dossier from “must run”** | Auto-silenced; out of SLA | Low — Keep optional |

**Do not retire yet:** `tracked_events`, storyline tables, Briefings/`editorial_document` readers, UIE, enrichment, Monitor, graph_connection_links (as exploratory graph), event_core_membership (finish it).

---

## Prioritized action list → &lt;6h intake→insight

### P0 — Unblock the atom path (this week)

1. Confirm `save_events` unique index + write path; finish `chronological_events_catchup` until CE volume matches recent UIE output.
2. Fix `content_enrichment` auto-silence so idle ≠ permanent silence when new RSS arrives.
3. Verify story_continuation / narrative_first receive CE rows and update storylines/TE within hours of ingest.
4. Add Monitor KPI: **time-to-surfaced** (article `created_at` → storyline `last_article_added_at` or TE chronicle update), not only preprocess clear.

### P1 — One attach SSOT (1–2 weeks)

5. Designate **event_core_membership + TE** as membership authority; fold story_continuation + narrative_first behind it.
6. Freeze chemistry beaker schedules until `embedding_chunks` populated **or** explicitly mark beaker non-production.
7. Audit RSS yield for medicine/AI (0 articles/24h).

### P2 — Delivery honesty (2–4 weeks)

8. Keep Briefings on fast-lane deltas (material storyline/TE changes); stop implying v11 packages are the 6h product.
9. When packages produce links + published stories, wire **published** `news_stories` into Dashboard/Briefings as slow-lane highlights.
10. Delete or hard-410 zombie digest product routes; collapse dual domain→product maps.

### P3 — After loop is green

11. Revisit chemistry Phase 4 reconcile; specialized stimulus_rag sources; corpus neurodiversity; public collectors; causal blend hook.

---

## Feature inventory notes by generation

### A. Intake / preprocess (6h core)

Well-isolated: `SPINE_PHASE_ORDER` = enrichment → UIE → spine_sql_tail. Legacy per-phase intake archived under `api/_archived/intake/` with `LEGACY_INTAKE_EXTRACTION_ENABLED` rollback. Signal gate + feed silencing are throughput levers. Catchup recovery phase exists because flush ops can orphan CE while UIE markers remain — operational fragility, not a second product.

### B. Chemistry / storylines

Living graph volume proves distillation ran historically, but **loose-bond factory is dead** (no embeddings, no hypothesized, no RAG queue). Storyline counts are tiny relative to corpus — either attach is failing or hygiene froze growth. Event-core is the stated successor but only lightly engaged (76 memberships). Accepted review: similarity-to-bag attach is wrong for megathread evidence.

### C. v11 modalities / delivery

Widow cutover **done** (PROJECT_STATUS 2026-07-25) contrary to older “local only” AGENTS wording — treat PROJECT_STATUS + DB as authority. Packages are seeded from legacy; **links empty** means Research/Narrative/Reduction have not formed a real connection graph inside packages. All `news_stories` remain `draft`. Live user-facing “story updates” = Report/Briefings + Dashboard contexts + tracked_events investigations.

---

## Appendix: heartbeat status (selected)

| Phase | Path | Last success | Detail |
|---|---|---|---|
| unified_intake_extraction | popos_worker | ~hours ago | complete, often 0 items (caught up) |
| claim_extraction / topic_clustering | popos_worker | hours ago | complete |
| storyline_assembly | popos_worker | minutes ago | complete, 0 linked |
| content_enrichment | widow | Jul 21 | **silenced** (flat backlog) |
| entity_profile_build | widow | Jul 25 | **silenced** (stalled) |
| graph_connection_distillation | widow | Jul 25 | active (recovered) |
| embedding_link_candidates / stimulus_rag | widow | Jul 21 fail | recovered, awaiting run |
| context_sync | cron | Jun 16 | stale heartbeat (inline sync may hide this) |

---

## Appendix: methodology

- Registry lifecycle from `api/config/features.yaml` (under_developed | staged | incorporated | deprecated | archived).
- Runtime schedules from `automation_manager.py` + `assembly_phase_order.py` retired sets + `schedulers.yaml` chemistry band.
- DB: cheap `COUNT(*)`, `MAX(created_at)`, heartbeat rows, domain storyline/article aggregates — no heavy scans.
- Parallel read-only exploration of intake, chemistry, and v11/delivery surfaces.

*Generated for internal planning. Do not treat as a cutover runbook — see `docs/V11_CUTOVER_RUNBOOK.md` for deploy steps.*
