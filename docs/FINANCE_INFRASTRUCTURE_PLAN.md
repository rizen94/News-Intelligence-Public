# Finance Domain — Infrastructure Build Plan

**Purpose:** Implement infrastructure layers for finance domain (market data, economic indicators, evidence-led reports). Build one layer at a time. Silo to finance where possible; core changes propagate to politics/science-tech.

**Reference:** Commodity Analysis Infrastructure Specification (Untitled document 1)

---

## Implementation Order

| Layer | Status | Scope | Notes |
|-------|--------|-------|-------|
| 1. Config & Secrets | Done | Finance + shared | settings, sources.yaml, .env.example |
| 2. Logging | Done | Shared | logging_config wired to settings, finance logger |
| 3. Database | Done | Finance | api_cache.py, market_data_store.py, vector_store.py (ChromaDB) |
| 4. Resource Manager | Done | Shared | api/shared/llm/resource_manager.py |
| 5. Embeddings | Done | Finance | domains/finance/embedding.py (bge-large, chunking) |
| 6. LLM Inference | Done | Shared | domains/finance/llm.py wraps shared LLMService |
| 7. Data Sources | Done | Finance | data_sources/base.py, data_sources/fred.py |
| 8. Evidence Ledger | In progress | Finance | Report provenance |
| 9. Statistical Engine | Pending | Finance | Price analysis, validation |
| Web Portal | Pending | Finance | Display collected data |

---

## Siloing Rules

- **Finance-only:** FRED client, market data store schema, finance ChromaDB collection, finance report manifests
- **Shared (adjust politics if changed):** Config layout, logging, resource manager, LLM abstraction, data source base class
- **Core changes:** Any change to api/config, shared modules, or domain routing → verify politics/science-tech still work

---

## Finance Data Sources (initial)

| Source | Type | Data | Auth |
|-------|------|------|------|
| FRED | API | Gold, rates, CPI, dollar index, etc. | FRED_API_KEY |
| (Future) GDELT | BigQuery | News/sentiment | BIGQUERY_PROJECT_ID |
| (Future) EDGAR | API | SEC filings | EDGAR_USER_AGENT |
