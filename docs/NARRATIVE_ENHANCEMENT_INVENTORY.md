# Narrative Enhancement Inventory

Phase 0 hygiene for the Narrative Enhancement Roadmap. Classifies each A/B/C item as **consume existing SSOT**, **new collector**, or **new feature**, with file pointers.

Collectors not yet built are documented here only (no `under_developed` feature-registry stubs until code lands). See [`api/config/features.yaml`](../api/config/features.yaml) and [`FEATURE_REGISTRY.md`](FEATURE_REGISTRY.md).

---

## Legend

| Class | Meaning |
|-------|---------|
| **Consume existing SSOT** | Code/tables already exist; deepen wiring, consumption, or enablement |
| **New collector** | Ingest script/service feeding existing tables (prefer extend over new silos) |
| **New feature** | Product/capability not yet present (or only stubbed) |

---

## A — Deepen / turn on existing capabilities

| ID | Item | Class | Status / notes | Primary pointers |
|----|------|-------|----------------|------------------|
| A1 | `causal_edges` → scoring | **Consume existing SSOT** | Harvest + CoT scaffold live; **not** in `blend_link_score` until Phase 4 | `api/services/causal_edges_service.py`, `api/services/narrative_reasoning_service.py`, `api/services/embedding_link_candidate_service.py` (`blend_link_score`), migration `271_narrative_inference_roadmap.sql`, feature `causal_edges` |
| A2 | Membership review + mega harden | **Consume existing SSOT** | Code default ON; mega auto-apply; core prune / `dissimilar_to_core`; contradiction splits = Phase 4 | `api/services/storyline_membership_review_service.py`, `api/services/storyline_core_prune_service.py`, `api/services/storyline_membership_llm_agent.py`, `api/scripts/run_storyline_core_prune.py`, feature `storyline_membership_review` (staged, enabled) |
| A3 | `graph_link_drift_review` | **Consume existing SSOT** | Keep **disabled** until Phase 3 eval; temporal decay planned Phase 4 | `api/services/graph_link_drift_service.py`, feature `graph_link_drift_review` |
| A4 | Arc-stage state (`rolling_12m_arcs` × patterns) | **Consume existing SSOT** | Arcs exist; typed stage priors not wired | `api/services/rolling_arc_service.py`, `api/config/domain_synthesis_config.yaml` (`storyline_patterns`), feature `rolling_12m_arcs` |
| A5 | Generalize `stimulus_rag` | **Consume existing SSOT** | Beaker RAG exists (arXiv-heavy); extend source types Phase 5 | `api/services/rag_evidence_pull_service.py`, `api/shared/chemistry_beaker.py`, feature `stimulus_rag` |
| A6 | Trading signals outcomes | **Consume existing SSOT** + thin **new collector** | HITL signals live; free price snapshots + outcome writeback later | `api/services/trading_signals_service.py`, `api/scripts/backtest_event_ticker_impacts.py`, feature `trading_signals` |
| A7 | Recurring-event patterns | **Consume existing SSOT** | Clarify vs retired/`under_developed` `pattern_recognition` before expand | `api/config/features.yaml` → `pattern_recognition`, link-indexer / discovery paths |
| A8 | Score calibration (`score_parts` + accept/reject) | **New feature** (training table) on **consume** paths | Needs Phase 3 gold + desk accept/reject labels | `embedding_link_candidate_service.py` / graph evidence helpers, `desk_agent_writeback`, review-agent paths |
| A9 | `entity_position_tracker` | **Consume existing SSOT** | Phase exists; deepen → `versioned_facts` + storyline events | `api/services/entity_position_tracker_service.py`, `api/services/dossier_compiler_service.py`, assembly phase `entity_position_tracker` |
| A10 | Desk writeback (minimal) | **Consume existing SSOT** | Staged/off; enable accept/reject only after Phase 3 | `api/services/desk_promotion_service.py`, feature `desk_agent_writeback` |

### Mega-harden related (supporting A2)

| Concern | Class | Pointers |
|---------|-------|----------|
| Membership fit + demote/unlink | Consume | `storyline_membership_review_service.py` (`dissimilar_to_core`, mega auto-apply) |
| Core dissimilar prune (pre-synth) | Consume | `storyline_core_prune_service.py`, `content_refinement_queue_service._ensure_core_prune_before_synthesis`, `api/scripts/run_storyline_core_prune.py` |
| Auto-add threshold / mega bag gates | Consume | `storyline_automation_service.py` (`effective_auto_add_threshold`, `title_looks_mega_bag`) |
| Narrative finisher trim | Consume | `storyline_narrative_finisher_service.py` |
| Chemistry harden (edge promote) | Consume | `protein_harden_service.py`, feature `protein_harden` |
| Ops / audit scripts | Consume | `api/scripts/audit_kitchen_sink_storylines.py`, `prune_bad_mega_storylines.py`, `repair_duplicate_mega_storylines.py`, `purge_cross_domain_mega_bags.py` |
| Operator notes | Docs | [`STORYLINE_GRAPH_HYGIENE_RUNBOOK.md`](STORYLINE_GRAPH_HYGIENE_RUNBOOK.md), [`STORYLINE_CANONICAL_MODEL.md`](STORYLINE_CANONICAL_MODEL.md) |
| Tests | — | `tests/unit/test_storyline_mega_harden_pillar_b.py`, `tests/unit/test_storyline_membership_review.py` |

---

## B — Free / public collectors (prefer existing tables)

**Registry policy:** document placeholders here; register in `features.yaml` only when a collector module ships (`lifecycle: under_developed`).

| ID | Collector | Class | Partial exists? | Target tables / consumers | Pointers / stubs |
|----|-----------|-------|-----------------|---------------------------|------------------|
| B1 | CourtListener / RECAP | **New collector** | Config stub | Legal events / matter dockets / case entities | `api/config/government_sources.yaml` → `courtlistener` |
| B2 | GovInfo + Federal Register | **New collector** | FR API stub; FR RSS in legal feeds | Legal arc stages / chronological_events | `government_sources.yaml` → `federal_register` |
| B3 | Congress.gov deepen | **Consume** + **new collector** depth | Citation snapshots live | `intelligence.legislative_references` + timeline status events | `api/services/legislative_reference_service.py`, `government_sources.yaml` → `congress_gov` |
| B4 | MA legislature + Newton agendas | **New collector** | — | Legal geo chronological_events / sources | Domain `legal` feeds / future `api/collectors/` |
| B5 | SEC EDGAR | **Consume** + deepen | Finance ingest path exists | Finance events / contexts | Finance routes `edgar_ingest`, `api/scripts/add_official_feeds.py` |
| B6 | FRED expand | **Consume existing SSOT** | Series fetch live | Macro anchors / `economic_event` | Finance FRED routes, `domains/finance/data_sources/fred_*` |
| B7 | GDELT 2.0 events/GKG | **Consume** (aid only) | RAG module exists | Coreference aid — not primary event SSOT | `api/modules/ml/gdelt_rag_service.py` |
| B8 | ACLED / UCDP | **Consume** + finish UCDP | ACLED client + upsert live | `external_events` → storylines | `api/services/acled_client.py`; UCDP still greenfield |
| B9 | Wikidata relationship backfill | **Consume** + batch job | Mint/resolve live | Entity edges / identity spine | `api/nri_core/spine/`, entity resolution routes |
| B10 | OpenSanctions bulk enrich | **Consume** + batch | Mention resolver source | Entity profiles / sanctions flags | `api/nri_core/spine/resolution/matcher.py` (`opensanctions`) |
| B11 | ClinicalTrials / openFDA / PubMed / bioRxiv / OpenAlex | **Consume** + **new collectors** | CT.gov fetch + fulltext gate | Medicine research proteins / evidence | `api/services/clinicaltrials_study_fetch.py`, `api/shared/fulltext_pull_gate.py` |
| B12 | Wayback proactive archive | **Consume** + schedule | Enrichment fallback fetch | Article fulltext resilience | `article_content_enrichment_service._fetch_via_wayback` |
| — | Quiver (already shipped) | **Consume existing SSOT** | Live collector | `intelligence.quiver_*` | `api/collectors/quiver_collector.py` |

**Collector pattern (when building):** `api/collectors/<name>_collector.py` + cron/phase + feature registry entry; idempotent upserts; rate-limit; Monitor-visible run history. Existing examples: `rss_collector.py`, `quiver_collector.py`.

---

## C — New / unlock features

| ID | Item | Class | Depends on | Primary pointers |
|----|------|-------|------------|------------------|
| C1 | Canonical event / coreference harden | **Consume existing SSOT** (harden + consume) | — (Phase 2 unlock) | `api/services/event_coreference_service.py`, `api/services/event_deduplication_service.py`, migration `276_event_coreference_clusters.sql`, `tests/unit/test_event_coreference.py`, timeline / story_continuation consumers |
| C2 | Lifecycle state machine | **New feature** | C1 preferred | Storyline status fields; transition rules TBD |
| C3 | Prediction / expectation tracking | **New feature** | C1 | Forward claims → due queue → outcome |
| C4 | Source-disagreement surface | **New feature** | C1 | Contested claim variants per canonical event |
| C5 | Narrative gap → evidence pull | **New feature** | C1, A4, A5 | Missing arc stage → `rag_evidence_pull_queue` |
| C6 | Entity dossier diffs | **New feature** on **consume** facts | A9 | `intelligence.versioned_facts`, dossier compiler |
| C7 | Hyperedge meta-storylines UX | **Consume** proposals + **new** UI | C1 | `graph_connection_queue_service.record_storyline_hyperedge_groups`, distillation |
| C8 | Dual centroids | **New feature** | Scoring Phase 2 | Consolidation / discovery centroid helpers |
| C9 | Gold eval harness (~200) | **New feature** | Before A1/A3 enable | CI script + gold pairs (attach + coref) |
| C10 | Signals price outcomes | See A6 | A6 collector | Trading signals HITL labels |

---

## Phase gate (do not skip)

| Gate | Rule |
|------|------|
| Phase 0 (this doc) | Registry notes aligned; inventory complete |
| Phase 1 | Collectors B1–B8 style before threshold surgery |
| Phase 2 | C1 cluster consumption in timeline + link scoring |
| Phase 3 | C9 + A8 (+ minimal A10) before enabling drift / desk mass writeback |
| Phase 4 | A1 consume causal in `blend_link_score`; A3 drift + temporal decay; A2 contradiction splits |
| Phase 5+ | Arcs, stimulus generalize, gaps, then C3+ UX |

---

*Created 2026-07-22 — Phase 0 Narrative Enhancement Roadmap.*
