# Finance Orchestrator & Analysis — Consolidated TODO

## Pipeline Validation

- [x] **validate_finance_pipeline.py** — Script at `scripts/validate_finance_pipeline.py` validates:
  - Evidence ledger (record/retrieve)
  - Market data store (upsert/query)
  - Gold amalgamator (fetch → store → ledger)
  - Vector store (ChromaDB, SKIP if not installed)
  - Orchestrator gold refresh (full flow)
- [x] **FINANCE_PIPELINE.md** — Documents data stores and ingestion flow

Run: `PYTHONPATH=api python3 scripts/validate_finance_pipeline.py`

## Current Backend Development (in progress)

### From FINANCE_ORCHESTRATOR_BUILD.md — Remaining Items

- [ ] **evaluate_ingest** — Verify chunks retrievable after EDGAR ingest (deferred)
- [x] **Stale data check** — Gold evidence cached 1hr; analysis reuses cache when fresh
- [ ] **User preemption** — Queue ordering so user tasks preempt scheduled (deferred)
- [x] **Catch-up on startup** — Scheduler treats last=None as due; runs all on first poll
- [ ] **Checkpointing for EDGAR** — Deferred

### API Gaps for Frontend Integration

- [x] **GET /tasks** — List tasks with filters (status, type, limit, offset)
- [x] **Task status shape** — Added phase (planning|fetching|synthesizing|verifying|revising|complete|failed), provenance, sources in result
- [x] **GET /tasks/{id}/status** — Separate status-only endpoint
- [x] **GET /evidence** — Paginated evidence index from completed tasks
- [x] **GET /sources/status** — Source health with last_success, last_failure, freshness
- [x] **GET /verification** — Paginated verification history

---

## Phase 7 — Finance Analysis Frontend ✅ (implemented)

*From: Finance Analysis Frontend Design — Cursor Reference*

**Status:** Core pages and API service implemented. Routes and nav added for Finance domain.

**Context:** Extends existing News Intelligence React SPA. MUI v5, Axios, react-markdown, Recharts, MUI DataGrid. New pages under `/finance/*`. API via `/api/v4/finance/...`.

### New Routes (implemented)

| Route | Page Component | Purpose |
|-------|----------------|---------|
| `/finance/analysis` | FinancialAnalysis | Query input → submit → redirect to result |
| `/finance/analysis/:taskId` | FinancialAnalysisResult | Polling view, progress stepper, cited output |
| `/finance/evidence` | EvidenceExplorer | DataGrid of evidence index |
| `/finance/sources` | SourceHealth | Source status cards |
| `/finance/fact-check` | FactCheckViewer | Verification history DataGrid |
| `/finance/schedule` | RefreshSchedule | Schedule table + manual trigger |

Nav items added to finance sidebar.

### Core UI Flow: Analysis Page

1. **Input:** MUI TextField (query), date range pickers, source toggles (FRED/EDGAR/gold), submit → POST `/analyze` → `task_id`
2. **Processing:** Poll GET `/tasks/{taskId}/status` every 2s (back off to 5s after 30s). MUI Stepper: Planning → Data Collection → Synthesis → Verification → Revision → Complete. Live activity log (ledger entries).
3. **Result:** Redirect to `/finance/analysis/{taskId}`:
   - Confidence banner (MUI Alert): green ≥0.8, amber 0.5–0.8, red &lt;0.5
   - Cited analysis text (react-markdown, REF-XXX → CitationMarker, hover tooltip, click scrolls evidence sidebar)
   - Evidence sidebar (MUI Drawer right, Accordions by source)
   - Claim highlighting: verified green, unsupported amber, contradicted red (toggle via MUI Switch)

### Citation Rendering Pipeline

1. Pre-process markdown: replace REF-XXX with `<cite data-ref="REF-XXX">1</cite>`
2. react-markdown `components` prop overrides `cite` → CitationMarker
3. CitationMarker looks up evidence, renders MUI element; hover → `hoveredRefId` → sidebar highlight
4. Claim highlighting: wrap verified/unsupported spans in `<mark>`, override `mark` in components

### New API Service Module

`web/src/services/api/financeAnalysis.ts` — follows existing pattern, uses `getApi()`.

| Function | Endpoint | Returns |
|----------|----------|---------|
| submitAnalysis(query, options) | POST /analyze | { task_id } |
| getTaskStatus(taskId) | GET /tasks/{taskId}/status | Phase, progress, log entries |
| getTaskResult(taskId) | GET /tasks/{taskId}/result | Full TaskResult |
| listTasks(filters) | GET /tasks | Paginated task list |
| getEvidenceIndex(filters) | GET /evidence | Paginated evidence entries |
| getSourceStatus() | GET /sources/status | All source health |
| triggerRefresh(sourceId?) | POST /refresh | Refresh trigger |
| getRefreshSchedule() | GET /schedule | Schedule + queue |
| getVerificationHistory(filters) | GET /verification | Paginated verification results |

### Key Types (`web/src/types/finance.ts`)

- `FinancialAnalysisRequest`, `FinancialAnalysisResult`
- `EvidenceIndexEntry`, `VerificationResult`, `ClaimVerification`
- `SourceStatus`

### New Components

- **AnalysisMarkdownRenderer** — react-markdown + REF markers + claim highlighting
- **CitationMarker** — Inline ref, hover tooltip, click-to-detail
- **ConfidenceBadge** — MUI Chip, color by score
- **TaskProgressStepper** — MUI Stepper from phase prop
- **EvidenceCard** — Compact evidence entry card
- **SourceStatusChip** — Colored chip for source health

### Build Order (Frontend)

1. Types + API service module
2. AnalysisMarkdownRenderer + CitationMarker (mock data)
3. FinancialAnalysis page with mocks (input → progress → result)
4. EvidenceExplorer (DataGrid + Recharts)
5. SourceHealth + RefreshSchedule
6. FactCheckViewer

Build all pages against mocks in `web/src/mocks/financeAnalysis.ts`, swap for real API when backend ready.

### Integration Points

- Add analysis summary card to existing finance Dashboard
- Link from IntelligenceHub to analysis system
- Evidence sidebar: responsive Drawer (follow Navigation sidebar mobile pattern)
- Polling: `useTaskPolling` hook, not inside stepper
