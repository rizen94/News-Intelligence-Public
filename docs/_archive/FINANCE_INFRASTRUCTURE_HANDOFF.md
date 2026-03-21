# Finance Infrastructure — Development Handoff & Clarifications

**Date:** 2026-02-21  
**Purpose:** Reflect current state, divide work into self-service vs Claude-supported, and prepare clarifying questions for Claude to guide next phases.

---

## Current State (As of 2026-02-21)

### Completed — Nine Layers + Extras

| Layer | Status | Notes |
|-------|--------|------|
| 1. Config & Secrets | Done | settings, paths.py, sources.yaml, .env.example |
| 2. Logging | Done | finance logger, settings wiring |
| 3. Database | Done | api_cache, market_data_store, vector_store, evidence_ledger |
| 4. Resource Manager | Done | Existing shared |
| 5. Embedding | Done | bge-large, chunking, EvidenceChunk, ingest_evidence_chunks |
| 6. LLM | Done | Thin wrapper around shared LLMService |
| 7. Data Sources | Done | base, fred (custom HTTP client, not fredapi) |
| 8. Evidence Ledger | Done | Schema version, wired into gold amalgamator |
| 9. Statistical Engine | Done | price_change_pct, validate_range, latest_value |

### Gold Amalgamator

- **Sources:** FreeGoldAPI (USD/oz), FRED IQ12260 (index via FRED adapter).
- **Storage:** `source="gold_amalgam"`, symbol per source. Evidence ledger records each fetch.
- **API:** `GET /{domain}/finance/gold`, `POST /{domain}/finance/gold/fetch`.

### Claude 4.6 Guidance — Implemented

- `load_dotenv(override=False)` at API startup
- Duplicate FRED caching removed from fred_gold; delegates to FRED adapter
- `api/config/paths.py` centralized
- `DataResult` in market_data_store, gold amalgamator, routes
- `_check_domain` vs `validate_domain` documented
- Evidence ledger in gold amalgamator (one entry per source per fetch)
- `EvidenceChunk` dataclass + `ingest_evidence_chunks()`
- Schema version tripwire in all finance SQLite DBs
- Unit tests: api_cache, market_data_store, evidence_ledger, gold_amalgamator (mocked)
- `Optional[X]` → `X | None` in finance domain
- ChromaDB collection naming with model suffix (`finance_evidence_bge_large`, `finance_evidence_nomic_embed`)
- `scripts/verify_environment.py` + `[project.optional-dependencies] finance`

### Remaining Gaps (Claude or Future)

- **DataResult in FRED/gold adapters** — they return `[]` on failure; no `error_type` for ledger (see Q7)

---

## Work Split: Self-Service vs Claude Support

### What We Can Do Ourselves (No Claude Needed)

| Item | Effort | Notes |
|------|--------|-------|
| Fix deprecated GOLDAMGBD228NLBM in fetch-fred docstring | Trivial | Use IQ12260 or DCOILWTICO |
| Add startup logging for embedding model/collection | Trivial | Log in main or finance init |
| Implement dynamic data source loader | Small | Read sources.yaml, importlib, registry dict |
| Add FRED adapter unit tests (mocked HTTP) | Small | Use responses/respx or unittest.mock |
| Improve embed_with_ollama_fallback → return (vec, model_name) | Small | Tuple or dataclass; update vector_store.add to accept model_name |

### What Would Help to Have Claude Expand On or Support

| Topic | Why Claude |
|-------|------------|
| **EDGAR 10-K/10-Q fetcher** | Scope: generic vs narrow, which companies, filing types, rate limits, schema for evidence chunks |
| **Shared macro module for politics** | Architecture: when to build, `api/shared/macro/` structure, how politics consumes without coupling to finance |
| **GDELT integration** | Priority vs EDGAR, BigQuery setup, schema, evidence format |
| **Report pipeline architecture** | How evidence ledger plugs into report generation; canonical gold source for report citations vs amalgamator |
| **DataResult retrofit for FRED/gold** | Whether to change adapter signatures; impact on amalgamator and routes; error_type taxonomy |
| **Project-wide Optional → X \| None** | Large sweep; want systematic plan, no logic changes |
| **Integration test strategy** | Which tests hit real APIs, scheduling, fixtures |

---

## New Clarifying Questions for Claude

### Architecture (Unresolved)

1. **Report pipeline vs amalgamator:** For report generation that cites gold prices, should we define a single canonical source (e.g. "always FreeGoldAPI for USD/oz, FRED for validation") in config, or is the amalgamator's preference logic sufficient? The guidance distinguished amalgamator (display) from report pipeline (evidence + provenance).

2. **Dynamic loader usage:** Once we implement the data source loader, should *all* FRED access go through it (e.g. `get_source("fred").fetch_observations(...)`), or can routes continue to call `get_client()` directly for now?

3. **embed_with_ollama_fallback:** If we return `(vec, model_name)` and wire it into the ingestion pipeline, how should the fallback order work—try sentence-transformers first, then Ollama, and pass model_name to vector_store.add? Or keep it as a standalone test/debug utility?

### Future Scope (Need Scope Input)

4. **EDGAR:** Narrow 10-K/10-Q fetcher for mining companies (Barrick, Newmont, etc.) vs generic SEC filing fetcher? Which companies/symbols initially?

5. **GDELT:** Near-term or later phase? What evidence structure (event codes, actors, sentiment) do we want to store?

6. **Politics macro:** Build shared macro module only when a politics route needs CPI/PPI/oil, or add stubs now?

### Implementation Detail

7. **DataResult in adapters:** Should FRED `fetch_observations` and gold source `fetch()` return `DataResult[list[dict]]` instead of `list[dict]`? That would let the amalgamator record `error_type` in the ledger when a source fails. Tradeoff: more boilerplate, clearer failure modes.

8. **verify_environment scope:** Guidance mentioned fredapi, pandas, numpy, torch. We use custom FRED client (not fredapi). Should we add fredapi to optional-deps for future use, or omit?

---

## Siloing Rules (Unchanged)

- **Finance-only:** FRED client, market store schema, finance ChromaDB, evidence ledger, gold amalgamator.
- **Shared (verify politics/science-tech if changed):** Config, logging, paths, DataResult, LLM abstraction.
- **Core change rule:** Any change to `api/config`, shared modules, or domain routing → verify politics/science-tech.

---

## Running Tests (Use Project Venv)

All edits are in **project source files**, not inside `.venv/`. The venv holds installed packages; run from it so project deps and editable source are used:

```bash
# From project root
uv run pytest tests/unit/test_finance_*.py -v
# or
./scripts/run_finance_tests.sh
```

**Note:** If `uv run` fails on onnxruntime (Python 3.10 vs 3.11+ wheels), use a venv with Python 3.11+ or run `pytest` directly from an existing working venv.

---

## File Reference (Current)

```
api/config/settings.py
api/config/paths.py
api/config/sources.yaml
api/config/logging_config.py
api/main.py
api/domains/finance/
  data/api_cache.py
  data/market_data_store.py
  data/vector_store.py
  data/evidence_ledger.py
  data/evidence_chunk.py
  data/schema_version.py
  data_sources/__init__.py      # Loader to be implemented
  data_sources/base.py
  data_sources/fred.py
  embedding.py
  llm.py
  stats.py
  gold_amalgamator.py
  gold_sources/freegoldapi.py
  gold_sources/fred_gold.py
  routes/finance.py
api/shared/data_result.py
scripts/verify_environment.py
scripts/restart_api_with_db.sh
.env.example
tests/unit/test_finance_api_cache.py
tests/unit/test_finance_market_data_store.py
tests/unit/test_finance_evidence_ledger.py
tests/unit/test_finance_gold_amalgamator.py
tests/unit/test_finance_fred_adapter.py
tests/unit/test_finance_data_source_loader.py
scripts/run_finance_tests.sh
docs/CLAUDE_4.6_GUIDANCE.md
docs/FINANCE_INFRASTRUCTURE_PLAN.md
```

---

## Self-Service Implementation Plan — Done

All self-service items implemented (2026-02-21):

1. ~~Fix deprecated GOLDAMGBD228NLBM in fetch-fred~~ — Example updated to IQ12260, DCOILWTICO
2. ~~Add startup logging for embedding model/collection~~ — `get_embedding_collection_info()` in vector_store; logged in main lifespan
3. ~~Implement dynamic data source loader~~ — `data_sources/__init__.py`: `get_source()`, `get_all_sources()`, `list_source_ids()`
4. ~~Add FRED adapter unit tests~~ — `tests/unit/test_finance_fred_adapter.py` (mocked HTTP)
5. ~~Improve embed_with_ollama_fallback~~ — Returns `(vec, model_name)`; `vector_store.add(model_name=...)` added

---

*Share this document with Claude to align on architecture, answer new questions, and guide EDGAR/GDELT/macro scope.*
