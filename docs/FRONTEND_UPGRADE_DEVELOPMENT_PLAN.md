# Frontend upgrade development plan — documentation audit

**Purpose:** Guide for upgrading the News Intelligence web UI. Summarizes current state, planned designs, and backend outputs not yet visualized.

**Date:** 2026-06-15 (refreshed per [NI_NRI_SYSTEM_AUDIT_2026-06.md](NI_NRI_SYSTEM_AUDIT_2026-06.md))  
**Authoritative routing:** `web/src/App.tsx`, `web/src/layout/AppNav.tsx` (not `SYSTEM_OVERVIEW.md` §4 — stale)

---

## 1. Documentation map

### News Intelligence (NI) — processing & UI

| Doc | Focus |
|-----|-------|
| [DOCS_INDEX.md](DOCS_INDEX.md) | Master index |
| [CODEBASE_MAP.md](CODEBASE_MAP.md) | API / web / scripts layout |
| [PIPELINE_AND_AUTOMATION.md](PIPELINE_AND_AUTOMATION.md) | Automation phases, scheduling, ingestion→storylines |
| [PIPELINE_OPERATIONS_WIDOW.md](PIPELINE_OPERATIONS_WIDOW.md) | Operator checklist, manual triggers |
| [PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md](PIPELINE_INGESTION_AND_PROCESS_METHODOLOGY.md) | Per-phase ingest methodology |
| [SYSTEM_OVERVIEW.md](SYSTEM_OVERVIEW.md) | System map (routes partially stale) |
| [API_REFERENCE.md](API_REFERENCE.md) | Endpoint catalog |
| [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md) | React → `/api` wiring |
| [NI_DATA_INVENTORY_AND_CONNECTIONS.md](NI_DATA_INVENTORY_AND_CONNECTIONS.md) | Tables, pipeline markers, planned graph edges |
| [CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md](CLAIMS_TO_FACTS_ENTITY_RESOLUTION.md) | Claims→facts, entity resolution |
| [LONGITUDINAL_INTELLIGENCE_EXECUTION.md](LONGITUDINAL_INTELLIGENCE_EXECUTION.md) | **Phase 5 UI specs** (arcs, citations, heatmap) |
| [LONGITUDINAL_OPERATOR_RUNBOOK.md](LONGITUDINAL_OPERATOR_RUNBOOK.md) | Longitudinal ops |
| [CHRONOLOGICAL_ACCURACY_DOCTRINE.md](CHRONOLOGICAL_ACCURACY_DOCTRINE.md) | Event / ingestion / vintage timestamps |
| [STORYLINE_AUTOMATION_GUIDE.md](STORYLINE_AUTOMATION_GUIDE.md) | Storyline RAG, review queue |
| [PDF_INGESTION_PIPELINE.md](PDF_INGESTION_PIPELINE.md) | Document ingest |
| [PUBLIC_DEPLOYMENT.md](PUBLIC_DEPLOYMENT.md) | Demo mode, read-only guards |
| [NI_NRI_SYSTEM_AUDIT_2026-06.md](NI_NRI_SYSTEM_AUDIT_2026-06.md) | Designed/built/wired/running matrix (June 2026) |

### News Review Investigator (NRI) — processing & NI integration

| Doc | Focus |
|-----|-------|
| [../../News-Review-Investigation/docs/PROJECT_READINESS_HANDOFF.md](../../News-Review-Investigation/docs/PROJECT_READINESS_HANDOFF.md) | M7 handoff, architecture, metrics |
| [../../News-Review-Investigation/docs/M7_CUTOVER_RUNBOOK.md](../../News-Review-Investigation/docs/M7_CUTOVER_RUNBOOK.md) | Cutover / rollback |
| [../../News-Review-Investigation/docs/NI_NRI_BOUNDARIES.md](../../News-Review-Investigation/docs/NI_NRI_BOUNDARIES.md) | Read/proxy write rules |
| [../../News-Review-Investigation/docs/NI_EVIDENCE_CONTRACT.md](../../News-Review-Investigation/docs/NI_EVIDENCE_CONTRACT.md) | Tables NRI reads/writes |
| [../../News-Review-Investigation/docs/EVIDENCE_SUBJECT_GATE.md](../../News-Review-Investigation/docs/EVIDENCE_SUBJECT_GATE.md) | Subject vs entity filtering |
| [../../News-Review-Investigation/docs/DATA_SOURCE_TOU.md](../../News-Review-Investigation/docs/DATA_SOURCE_TOU.md) | Spine data licensing |
| [../../News-Review-Investigation/docs/NRI_PORTS.md](../../News-Review-Investigation/docs/NRI_PORTS.md) | Port registry |

---

## 2. What we have today

### 2.1 Data processing pipelines (backend)

#### NI automation (`automation_manager.py` + cron)

```
RSS → articles → enrichment → contexts → claims/events
     → entity_profiles + mentions → storylines → editorial/report
```

Key stores: `intelligence.contexts`, `entity_profiles`, `context_entity_mentions`, `extracted_claims`, `tracked_events`, domain `storylines`, `articles`.

#### NRI layer (post-M7)

```
context_entity_mentions → mention_resolver (15 min)
  → identity_spine match / lazy mint
  → nri.resolved_mentions + parked_resolution + entity_bridge

nri-loop (daily 02:30, shadow) → vault/hypotheses/*.md + nri.loop_run
```

Spine datasets loaded: Wikidata (23.5k), EDGAR, Congress, wikidata_lazy. GLEIF **not** loaded.

### 2.2 Current web UI (routed pages)

| Area | Routes | Data source |
|------|--------|-------------|
| **Overview** | `dashboard` | Contexts, tracked events |
| **Corpus** | `articles`, `rss_feeds` | Domain articles, feeds |
| **Stories** | `storylines`, review-queue, discovery, timeline, synthesized | Storylines API, synthesis |
| **Signals** | `topics`, `events` | Topics, domain events |
| **Investigate** | `investigate`, entities, search, documents, narrative-threads, **entity-resolution**, **spine-browser**, **hypotheses** | `contextCentricApi` + **NRI** `/api/nri/*` |
| **Arcs** | `arcs`, `arcs/:arcId/spine`, `arcs/:arcId/heatmap`, `arcs/reports` | `/api/intelligence/arcs/*`, `arc_report/*` |
| **Outputs** | `briefings` | Report, briefing feed |
| **Operations** | `monitor`, sql-explorer, audit-checklist, **operations/nri-ops**, `operations/llm-activity` | Monitoring, NRI metrics, LLM activity |
| **Finance** | `analysis`, commodity, trace | Finance analysis APIs |

**NRI UI (v2 — June 2026):**

- `EntityResolutionPage` — resolved + parked tables, cross-domain parked triage, health chip, “Mark reviewed” (PATCH proxy)
- `SpineBrowserPage` — proxied `GET /api/nri/spine/entities`, `POST /api/nri/spine/match`
- `HypothesesPage` — vault hypothesis list + detail drawer; loop run sidebar
- `NriOpsPage` — resolution stats, loop runs, FtM cache breakdown, cross-domain parked sample, health
- `EntityDetailPage` / `EntityDossierPage` — `FtmBridgePanel`, entity claims (`GET /api/nri/entity_claims`)
- `ContextDetailPage` — context intel bundle (`GET /api/nri/context_intel/{id}`)

**Demo-guarded** (hidden on public read-only): RSS, watchlist, storyline write paths, monitor, finance, NRI ops, LLM activity.

### 2.3 NI ↔ NRI API bridge (implemented)

| NI route | NRI backing |
|----------|-------------|
| `GET /api/nri/health` | `:8010/health` |
| `GET /api/nri/resolved_mentions` | `nri.resolved_mentions` |
| `GET /api/nri/parked` | `nri.parked_resolution` |
| `PATCH /api/nri/parked/{id}` | Proxied to NRI |
| `GET /api/nri/entity_bridge/{id}` | `nri.entity_bridge` + cache |
| `GET /api/nri/bridge_qa/audit` | Bridge QA audit query (API only — no page yet) |
| `GET /api/nri/entity_claims` | Claims × FtM join |
| `GET /api/nri/context_intel/{id}` | Context + mentions + claims bundle |
| `GET /api/nri/parked_cross_domain` | Cross-domain parked triage |
| `GET /api/nri/hypotheses` | Vault reader |
| `GET /api/nri/hypotheses/{id}` | Vault detail |
| `GET /api/nri/spine/entities` | Proxied spine entity search |
| `POST /api/nri/spine/match` | Proxied spine match |
| `GET /api/nri/resolution_stats` | Aggregated resolver stats |
| `GET /api/nri/loop_runs` | `nri.loop_run` |
| `GET /api/nri/ftm_cache_stats` | `nri.ftm_entity_cache` by dataset |

---

## 3. Scheduled / designed (not fully built in UI)

### 3.1 Longitudinal intelligence — Phase 5 (spec in `LONGITUDINAL_INTELLIGENCE_EXECUTION.md`)

Backend routes exist under `/api/intelligence/arcs/*`, `arc_report/*`, `reference_events/*`, `citation/*`. **App.tsx routes added** (`ArcCatalogPage`, `ArcSpinePage`, `ArcHeatmapPage`, `ArcWeeklyBriefsPage`). DB tables (`arc_definitions`, `arc_reports`, etc.) are still empty on Widow — UI is a shell until longitudinal backfill feeds data.

| Designed UI | API | Status |
|-------------|-----|--------|
| Citation Drawer | `GET /api/intelligence/citation/{id}` | Component exists (`CitationDrawer.tsx`); **not wired** to arc/spine pages |
| Arc Spine view | `GET /api/intelligence/arcs/{arc_id}/spine` | **Routed** — `/{domain}/arcs/:arcId/spine` |
| Arc weekly brief | `GET /api/intelligence/arc_report/{arc_id}/latest` | **Routed** — `/{domain}/arcs/reports` (distinct from domain `briefings`) |
| Tension heatmap | `GET /api/intelligence/arcs/{arc_id}/heatmap` | **Routed** — `/{domain}/arcs/:arcId/heatmap` |
| Analogue comparison | `GET /api/intelligence/analogues/{arc_id}` | Not built |
| Reference event curation | `POST /api/intelligence/reference_events/*` | Phase 6 — no form UI |

### 3.2 Analyze product

`AnalyzePage` was **removed** from the repo (June 2026 cleanup). Cross-domain analytics remain planned under Phase C (§5); Finance uses `/analysis` directly.

### 3.3 Cross-domain & graph intelligence

APIs exist; no dedicated visualization pages:

- `network_graph`, `unified_timeline`, `meta_storylines`, `cross_domain_*`, `predictions`
- Materialized **graph edge projection** (`NI_DATA_INVENTORY`) — backend plan, no UI

### 3.4 NRI planned (backend ready, UI thin or missing)

| Feature | Backend | UI gap |
|---------|---------|--------|
| GLEIF spine ingest | CLI + manual systemd | No ingest status / entity source breakdown |
| Loop promotion (shadow→main) | `loop/promote/gate.py` | No promotion UI; hypotheses list doesn’t show branch |
| Vault facts / leads / entities | Writer + firewall | **No NI routes or pages** |
| Provisional mint review | `nri.provisional_mints` | No review queue |
| Bridge QA audit dashboard | `GET /api/nri/bridge_qa/audit` | API + client method only; wire on `NriOpsPage` |
| Lead inbox JSON | Mentioned in NRI_PORTS | Not implemented |
| Parked review with FtM link | `PATCH /api/parked/{id}` | UI marks “reviewed” + cross-domain triage; no candidate selection / bridge creation |
| Resolver status tabs | `resolved_mentions` by status | No dedicated tabs for `provisional` / `non_entity_topic` |

### 3.5 Orphan frontend (built, not in router)

Pages exist under `web/src/pages/` but lack `App.tsx` routes:

- Finance: `EvidenceExplorer`, `FactCheckViewer`, `SourceHealth`, `RefreshSchedule`, `GoldCommodity`

**Removed from repo (no longer orphans):** `AnalyzePage`, `Monitoring`, `Settings`, `StorylineTracking`, `StoryControlDashboard`, `FilteredArticles`.

**Routed but demo-guarded:** `MLProcessing` at `operations/llm-activity`.

---

## 4. Outputs NOT visually represented in the frontend

### 4.1 NRI / investigation layer

| Output | Table / artifact | UI today |
|--------|------------------|----------|
| Resolver watermark / backlog | `nri.watermarks` | Partial — `NriOpsPage` resolution stats + health |
| `non_entity_topic` mentions | `nri.resolved_mentions` | No dedicated tab (inflates “parked” perception) |
| `provisional` resolutions | `nri.resolved_mentions` | No tab |
| Provisional mint audit | `nri.provisional_mints` | None |
| Loop iteration metrics | `nri.loop_run` | `NriOpsPage`, `HypothesesPage` (list only) |
| FtM entity cache detail | `nri.ftm_entity_cache` | `NriOpsPage` dataset breakdown + `FtmBridgePanel` on entity pages |
| Identity spine browser | `identity_spine.*` | `SpineBrowserPage` (proxied via NI) |
| Spine match preview | `POST /api/nri/spine/match` | `SpineBrowserPage` |
| Bridge QA audit | `nri.entity_bridge` + QA rules | API only — no dashboard |
| Vault facts / leads | `vault/facts/`, `vault/leads/` | None |
| ACH / skeptic artifacts | Inside hypothesis markdown | Not structured in UI |
| Shadow vs main vault | Git branches | Not indicated |
| Resolver batch trigger | `POST /api/evidence/resolve` | Ops CLI only |

### 4.2 NI intelligence layer (API exists, no or weak UI)

| Output | API area | UI gap |
|--------|----------|--------|
| Arc catalog & spine | `/api/intelligence/arcs/*` | **Pages wired** — empty DB until backfill |
| Arc reports & feedback | `/api/intelligence/arc_report/*` | **Arc reports page** — feedback UI missing |
| Reference events & flags | `/api/intelligence/reference_events/*` | No curation UI |
| Citation provenance | `/api/intelligence/citation/{id}` | Component exists; not integrated into arc views |
| Wikidata review queue | `/api/intelligence/wikidata/review_queue` | None |
| Intelligence hub insights/trends | `/api/intelligence_hub/*` | No hub dashboard |
| Quality metrics | `/api/quality/*` | No quality dashboard |
| Enrichment status | `/api/enrichment/*` | Partial (entity pages only) |
| Cross-domain network | `network_graph`, `unified_timeline` | Watchlist mentions; no graph view |
| Congress.gov bills | `/api/politics/official/congress_gov/*` | No bill browser |
| LLM activity | `/api/content_analysis/llm/*` | `MLProcessing` at `operations/llm-activity` (demo-guarded) |
| User preferences | `/api/user_management/*` | No settings page (removed) |
| Public auth login | `/api/public/auth/*` | No login page in SPA |
| Realtime urgent ingest | `/api/realtime/*` | None |
| Content dedup P3 | `/api/deduplication/*` | Separate from article dedup page |
| Storyline bulk synthesis / hierarchy | synthesis APIs | Underused vs API surface |

### 4.3 Processing health (ops visibility)

| Signal | Where | UI |
|--------|-------|-----|
| NRI resolver timer last run | systemd / logs | `NriOpsPage` health + `EntityResolutionPage` chip |
| Park rate KPI (excl. subjects) | SQL per `EVIDENCE_SUBJECT_GATE` | Partial — resolution stats on NriOps / entity-resolution |
| Spine dataset counts | `nri.ftm_entity_cache` | `NriOpsPage` bridged-by-dataset table |
| Cross-domain parked triage | `nri.parked_resolution` | `NriOpsPage`, `EntityResolutionPage` |
| Automation phase status | `MonitorPage` | Partial |
| GPU / Ollama lanes | monitoring API | Monitor page |

---

## 5. Recommended frontend upgrade phases

### Phase A — NRI investigation UX (highest ROI, APIs exist)

1. **Entity resolution v2** — tabs for `auto_linked` / `parked` / `provisional` / `non_entity_topic`; link to context + entity profile; park-rate KPI excluding subjects — **partial** (cross-domain triage, stats; no status tabs)
2. **Parked review workflow** — show spine candidates; approve with `candidate_ftm_id`; wire bridge creation on approve — **partial** (mark reviewed only)
3. **Spine browser** — proxy spine entities + match through NI — **done** (`SpineBrowserPage`)
4. **Hypotheses v2** — loop_run timeline; shadow/main badge; structured ACH fields from frontmatter — **partial** (list + loop runs; no branch badge)
5. **NRI ops panel** — resolver, loop, FtM cache metrics — **done** (`NriOpsPage`)
6. **Bridge QA audit UI** — surface `GET /api/nri/bridge_qa/audit` on NriOps — **not started**

### Phase B — Longitudinal product (Phase 5 spec)

1. Citation drawer — **component created**; wire into arc/spine pages
2. Arc list + spine route — **done**
3. Arc weekly brief page — **done** (`arcs/reports`)
4. Tension heatmap — **done**; analogue comparison — not built
5. Reference event curation forms — not built
6. Longitudinal **data backfill** — prerequisite; arc tables empty on Widow

### Phase C — Cross-domain & analytics

1. Network graph + unified timeline views
2. Intelligence hub dashboard (insights, trends, topic clusters)
3. Quality / enrichment dashboards
4. Analyze page or merge into Investigate

### Phase D — Ops & finance cleanup

1. Route orphan pages or delete (five unrouted Finance sub-views; `MLProcessing` already at `operations/llm-activity`)
2. Congress.gov bill browser (politics)
3. Public auth login UI (settings page removed)
4. Bridge QA audit on `NriOpsPage` (read-only)

---

## 6. Deploy note

Production nginx serves **`/var/www/news-intelligence/web/dist`**, not `/opt/news-intelligence/web/dist`. Frontend releases must rsync to both or symlink.

---

## 7. Key metrics to surface in upgraded UI

| Metric | Source | Why |
|--------|--------|-----|
| auto_link rate (person/org) | `nri.resolved_mentions` excl. `non_entity_topic` | Resolver health |
| parked queue depth | `nri.parked_resolution` open | Analyst workload |
| entity_bridge count | `nri.entity_bridge` | FtM coverage |
| spine dataset breakdown | `identity_spine.spine_entities` | Ingest completeness |
| loop iteration summary | `nri.loop_run` | Investigation cadence |
| watermark lag | `nri.watermarks` vs max mention id | Backlog |

---

*Cross-reference: NRI handoff complete 2026-06-09; system audit [NI_NRI_SYSTEM_AUDIT_2026-06.md](NI_NRI_SYSTEM_AUDIT_2026-06.md) (2026-06-15).*
