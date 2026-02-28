# Finance Data Ingestion Pipeline

## Overview

The finance domain ingests data from multiple sources, stores it persistently, and uses it for analysis. Each step is designed for auditability and graceful degradation.

## Data Stores

| Store | Path | Purpose |
|-------|------|---------|
| **Evidence Ledger** | `data/finance/evidence_ledger.db` | Audit trail: every fetch, success/failure, timestamps |
| **Market Data** | `data/finance/market_data.db` | Time series (gold, FRED): `market_series` table |
| **Vector Store** | `data/finance/chroma/` | ChromaDB: embedded EDGAR chunks for semantic search |
| **API Cache** | `data/finance/api_cache.db` | HTTP response cache |

## Pipeline Flow

### 1. Gold Price (freegoldapi, fred_iq12260)

```
fetch_all(start, end, store=True)
  → FreeGoldAPI / FRED Gold fetches
  → upsert_observations(market_data_store)  ← SQLite
  → ledger_record(gold_price, source_id, status)  ← SQLite
```

### 2. FRED Economic Series

```
FRED client.fetch_observations(symbol, start, end, store=True)
  → FRED API
  → upsert_observations(market_data_store)  ← SQLite
  → (orchestrator logs via _ledger_record when run via refresh)
```

### 3. EDGAR 10-K

```
ingest_edgar_10ks(filings_per_company, record_ledger=True)
  → SEC EDGAR API (index + filings)
  → Extract sections (Items 1, 7, 8)
  → embed_with_ollama_fallback + vector_store.add  ← ChromaDB
  → ledger_record(evidence_chunk, ...)  ← SQLite
```

### 4. Orchestrator Tasks

- **Refresh** (gold/edgar/fred): Runs workers, records to ledger with `report_id=orchestrator_{task_id}`
- **Analysis**: Runs refresh (or uses cache), builds evidence index, retrieves from vector store, calls LLM

Tasks and results live in memory. Evidence index, provenance, and ledger entries persist.

## Validation

Run the pipeline validation script:

```bash
cd "News Intelligence"
PYTHONPATH=api python3 scripts/validate_finance_pipeline.py
```

Checks:

1. Evidence ledger — record and retrieve
2. Market data store — upsert and query
3. Gold amalgamator — fetch, store, ledger
4. Vector store — ChromaDB (SKIP if chromadb not installed)
5. Orchestrator refresh — full gold refresh + ledger persistence

## Environment

- `FRED_API_KEY` — required for FRED sources
- `FINANCE_DATA_DIR` — default `data/finance` (from paths.py)
- ChromaDB — optional; required for EDGAR semantic search
