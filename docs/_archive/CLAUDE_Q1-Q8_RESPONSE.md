# Claude Q1–Q8 Response — Finance Infrastructure

**Source:** Answers to `FINANCE_INFRASTRUCTURE_HANDOFF.md` clarifying questions (2026-02-21)

---

## Q1 — Report Pipeline vs Amalgamator

Define the canonical source in config, not in the amalgamator's preference logic. Create `api/config/report_sources.yaml` (or a report_sources section inside sources.yaml):

```yaml
gold_spot_usd_oz:
  canonical: freegoldapi
  validation: fred_iq12260
  fallback: fred_iq12260
  citation_format: "Gold spot price (USD/oz) via FreeGoldAPI, {timestamp}"
```

The report pipeline reads this config and calls the source adapters directly through the hierarchy. It records in the evidence ledger which source it actually used, what the value was, and whether the validation source confirmed or diverged. The amalgamator continues doing its own thing for the dashboard — it doesn't read this config and it doesn't change.

**Don't build report_sources.yaml until the report pipeline is actively being developed**, but do build the report pipeline to expect it.

---

## Q2 — Dynamic Loader Usage

Keep both paths available for now. Routes that fetch a specific, known FRED series can continue calling `get_client()` directly. The dynamic loader is for discovery and enumeration: the /data-sources API endpoint, any future "fetch all configured series" batch job, and validation logic.

**Rule:** If someone adds a new data source, it must be registered in sources.yaml and accessible through the loader. The loader is the source of truth for "what data sources exist in this system."

---

## Q3 — embed_with_ollama_fallback

Make it the production embedding path, not a debug utility. Fallback order: sentence-transformers (bge-large) first, then Ollama nomic-embed-text. The returned `(vec, model_name)` tuple flows into `ingest_evidence_chunks`, which passes `model_name` to `vector_store.add`.

**Constraint:** Within a single ingestion batch, all chunks must use the same model. If sentence-transformers fails mid-batch, fail the whole batch and retry with Ollama from the start.

---

## Q4 — EDGAR Scope

Narrow 10-K/10-Q fetcher. Companies: Barrick Gold (GOLD), Newmont (NEM), Freeport-McMoRan (FCX), Agnico Eagle (AEM), Wheaton Precious Metals (WPM). Start with 10-K only.

**Three layers:**
1. Filing index fetcher — EDGAR full-text search or company filings endpoint
2. Filing downloader — retrieve primary document (.htm preferred)
3. Section extractor — Item 1, 7, 8 using `<ix:nonNumeric>` or heading-based heuristics

EDGAR: 10 req/sec, User-Agent header required.

---

## Q5 — GDELT

Later phase, after EDGAR and report pipeline. Use Events API (REST), not BigQuery. Focus on GoldsteinScale and tone for commodities, central banking, trade policy.

---

## Q6 — Politics Macro

Don't build stubs now. Build when a politics feature needs CPI, PPI, unemployment, or oil data. Add scope annotations in sources.yaml now (scope: finance vs scope: shared).

---

## Q7 — DataResult in Adapters

Yes. FRED `fetch_observations` and gold source `fetch()` return `DataResult[list[dict]]`. Error types: `no_data`, `network`, `parse`, `rate_limit`, `auth`.

Amalgamator does:
```python
if result.success:
    ledger.record(..., status="ok", ...)
else:
    ledger.record(..., status="error", error_type=result.error_type, error=result.error)
```

---

## Q8 — verify_environment Scope

Omit fredapi. Check: requests, chromadb, sentence-transformers, torch, pandas, numpy, pyyaml.

---

## Recommended Next Steps (Ordered)

**Immediate (done):**
1. DataResult in FRED adapter and both gold sources ✓
2. Add scope annotations to sources.yaml ✓

**Next session:**
3. EDGAR filing index fetcher — adapter in data_sources/edgar.py, add to sources.yaml
4. EDGAR filing downloader — cache in api_cache with source="edgar"
5. EDGAR section extractor — Item 1, 7, 8 → EvidenceChunk
6. Wire EDGAR chunks through ingestion pipeline

**When ready for reports:**
7. Report pipeline skeleton — topic → evidence retrieval → citations → LLM synthesis
8. report_sources.yaml — canonical source hierarchies
