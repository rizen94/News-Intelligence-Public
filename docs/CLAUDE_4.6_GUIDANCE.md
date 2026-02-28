# Claude 4.6 Guidance — Finance Infrastructure

**Source:** Response to `FINANCE_INFRASTRUCTURE_HANDOFF.md`

---

## Architecture & Design

### 1. ChromaDB Evidence Ingestion Flow

**Introduce an intermediate `EvidenceChunk` model.** Don't go raw document → vector store.

**Flow:**
```
raw document → EvidenceChunk (text, source, document_id, chunk_index, timestamp, metadata)
             → chunking module → embedding module → vector store
```

- `EvidenceChunk` is the canonical object; ledger and vector store reference by ID.
- Ledger records what will be embedded *before* embedding happens.
- Different document types (FRED descriptions, EDGAR paragraphs, GDELT summaries) need different chunking strategies upstream.
- Vector store never receives raw text directly — always pre-chunked, pre-catalogued evidence.

**Implementation:**
- `api/domains/finance/data/evidence_chunk.py` — dataclass
- Embedding module accepts `list[EvidenceChunk]`, embeds in batch, upserts to ChromaDB.
- Evidence ledger gets `record_embedding()` for which chunks were embedded and when.

### 2. Canonical Gold Price Source

**Amalgamator vs Report Pipeline:**
- **Amalgamator** = display tool (best available price for dashboard).
- **Report pipeline** = evidence tool (cite specific source with provenance).

**Source hierarchy config:**
- Canonical: FreeGoldAPI (gold spot USD/oz)
- Validation: FRED IQ12260 (cross-reference)
- Fallback: FRED IQ12260 if FreeGoldAPI unavailable

Report pipeline queries through hierarchy; evidence ledger records which source was used per data point. Don't conflate amalgamator (frontend convenience) with report pipeline (evidence + provenance).

### 3. Dynamic Data Source Loader

**Yes, build it — keep minimal.**

- Function in `data_sources/__init__.py` reads `sources.yaml`, uses `importlib.import_module` for each `module_path`, instantiates, validates subclass of `BaseDataSource`.
- Run at startup (or lazy first access); fail loudly if module/class is wrong.
- Registry dict keyed by source name.
- No plugin system, no entry points, no directory scanning. YAML is the registry.
- Adding a source = write adapter + add YAML entry.

---

## Dependencies & Environment

### 4. ChromaDB Installation

- Add `scripts/verify_environment.py` — import chromadb, sentence-transformers, fredapi, pandas, numpy, torch; report missing with install commands.
- Add `[project.optional-dependencies] finance = ["chromadb", "sentence-transformers", "fredapi"]` to pyproject.toml.
- Document: `pip install -e ".[finance]"` gets everything.
- Venv should be reproducible from pyproject.toml.

### 5. load_dotenv() at API Startup

**Add it.** First call in `main_v4.py`, before any settings/config imports.

```python
load_dotenv(override=False)  # Shell/env takes precedence over .env
```

Makes API self-contained — works with uvicorn directly, IDE debugger, test runner, or restart script. Restart script's .env sourcing becomes belt-and-suspenders redundancy.

---

## API & Frontend

### 6. _check_domain vs validate_domain

**Keep both. Document the rule.**

| Route touches … | Use |
|-----------------|-----|
| Finance-silo only (SQLite, FRED, ChromaDB, local files) | `_check_domain()` |
| Main PostgreSQL database | `validate_domain()` |

Don't migrate PostgreSQL routes to `_check_domain()` — that would hide legitimate DB dependency failures.

Add a comment at top of `routes/finance.py` with the rule; inline comment per route indicating which infrastructure it depends on.

### 7. Dual Caching — Consolidate

**One cache path per external API call.**

- FRED adapter caches under `fred` — correct and sufficient.
- `fred_gold.py` should **call the FRED adapter** (which handles caching), not make raw HTTP + cache separately.
- Amalgamator's job = source selection and merging, not fetching/caching.
- If amalgamator caches its merged output, use `gold_amalgam` with short TTL (minutes). Underlying source data cached once at adapter level.
- **Remove duplicate FRED caching from fred_gold.py; delegate to FRED adapter.**

---

## Future Scope

### 8. EDGAR vs GDELT Priority

**EDGAR first, narrow scope.**

- Fetcher for 10-K and 10-Q filings from major mining/commodity companies: Barrick Gold, Newmont, Freeport-McMoRan, Rio Tinto, BHP, etc.
- EDGAR: well-documented, 10 req/sec rate limit, structured filing indexes.

**GDELT later** — sentiment/event signals add color but system can produce solid reports without it. Higher infra complexity, lower evidence reliability (news vs audited statements).

### 9. Evidence Ledger First Integration

**Wire into gold amalgamator first.**

- Each data point from amalgamator fetch → ledger entry: source, raw value, retrieval timestamp, whether preferred or validation-only.
- ~15–20 lines in amalgamator.
- Gold card can show sources disclosure: "Price from FreeGoldAPI at 14:32 UTC, cross-validated against FRED IQ12260".
- Don't wait for full report pipeline — ledger is more valuable the longer it accumulates.

### 10. Politics Domain Macro Data

**Shared macro module** — `api/shared/macro/` fetches and stores canonical numbers (CPI, PPI, WTI crude, unemployment, fed funds) on a schedule or first request. Cache in shared SQLite or shared schema in market data store. Each domain reads from the shared store and applies its own lens:

- Finance: "What does rising CPI mean for gold as an inflation hedge?"
- Politics: "How does rising CPI affect incumbent approval ratings?"

Data is the same; interpretation is domain-specific.

**Concrete structure:**
- `api/shared/macro/macro_store.py`
- `api/shared/macro/macro_sources.py` — uses existing FRED adapter
- `macro_data.db` SQLite under shared data directory
- `sources.yaml` entries tagged `scope: shared` for macro series
- Finance and politics routes import from `shared/macro`

**Don't build until a politics route needs macro data.** When it does, go straight to the shared module — resist copy-pasting FRED logic into politics.

---

## Coding Concerns — Claude's Responses

### Error Handling — Result Types Over Silent Failures

Returning `[]` or `None` hides "no data" vs "network failed" vs "DB locked." Introduce a lightweight result type:

```python
@dataclass
class DataResult(Generic[T]):
    success: bool
    data: T | None = None
    error: str | None = None
    error_type: str | None = None  # "no_data", "network", "storage", "parse"
```

Retrofit into `market_data_store.get_series`, FRED adapter, gold source adapters first. Include `error_type` in evidence ledger when a source is unavailable.

### Type Hints — Standardize on X | None

Project-wide: `Optional[X]` → `X | None`, remove `Optional` imports. Single dedicated commit, no logic changes.

### Testing — Priority Order

1. `api_cache.py`, `market_data_store.py` — SQLite, `:memory:`, test insert/retrieve/expiry and no-data vs error.
2. `gold_amalgamator.py` with mocked source adapters.
3. FRED adapter with mocked HTTP (responses/respx).
4. Evidence ledger — provenance metadata.

No integration tests hitting real APIs on every commit; those go in `tests/integration/`, run on a schedule.

### Database Migrations — Tripwire

No full migrations system for now. Add `schema_version` in a meta table per DB. On startup, if version doesn't match: log "market_data.db schema version 1 does not match expected 2. Delete file to recreate, or run migrations." Prevents silent schema drift corruption.

### ChromaDB Dimension Mismatch — Separate Collections

bge-large = 1024 dims, nomic-embed = 768 dims. Encode model name into collection name: `finance_evidence_bge_large` vs `finance_evidence_nomic_embed`. `get_or_create_collection` includes model suffix. `embed_with_ollama_fallback` returns vectors + model name so vector store knows which collection. Log which embedding model and collection are active at startup.

### Path Conventions — Shared paths.py

`api/config/paths.py` defines `PROJECT_ROOT`, `API_ROOT`, `CONFIG_DIR`, `DATA_DIR`, `FINANCE_DATA_DIR`, etc., all from `PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent`. Every module imports from paths.py. Enables test overrides via monkeypatch.

---

## Updated Implementation Checklist

**Quick wins (single session):** ✅
1. ~~`load_dotenv(override=False)` in main_v4.py~~ — Done.
2. ~~Remove duplicate FRED caching in fred_gold.py~~ — Done; delegates to FRED adapter.
3. ~~Create `api/config/paths.py`~~ — Done; settings imports from it.

**Architectural improvements:** ✅
4. ~~Add `DataResult` type~~ — Done; retrofit in market_data_store, gold amalgamator, finance routes.
5. ~~Document _check_domain vs validate_domain~~ — Done; docstring + inline comments in routes/finance.py.
6. ~~Wire evidence ledger into gold amalgamator~~ — Done; one entry per source per fetch.

**Hardening:**
7. ~~Create `EvidenceChunk` dataclass and ingestion function~~ — Done.
8. ~~Schema version tripwire in each SQLite database~~ — Done.
9. ~~Unit tests: cache → market_data_store → gold_amalgamator → evidence_ledger~~ — Done; `tests/unit/test_finance_*.py`.
10. ~~`Optional[X]` → `X | None` sweep~~ — Done (finance domain).
11. ~~ChromaDB collection naming with embedded model name~~ — Done; `finance_evidence_bge_large` / `finance_evidence_nomic_embed`.
12. ~~`scripts/verify_environment.py` and pyproject extras group~~ — Done; `[project.optional-dependencies] finance = ["chromadb", "sentence-transformers"]`.

**Post-2026-02-21:**
13. ~~Dynamic data source loader~~ — Done; `get_source()`, `get_all_sources()` in data_sources/__init__.py.
14. ~~embed_with_ollama_fallback returns (vec, model_name)~~ — Done; `vector_store.add(model_name=...)` added.
15. ~~fetch-fred uses get_source("fred") with get_client() fallback~~ — Done.

**New scope:**
16. EDGAR 10-K/10-Q fetcher (when scope confirmed).

---

*Incorporated from Claude 4.6 response.*
