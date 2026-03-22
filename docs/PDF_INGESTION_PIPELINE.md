# PDF fetching, processing, and ingestion (through text extraction)

This document describes **how PDFs enter the system and how bytes are fetched and turned into text**. Anything **after** usable text exists (section heuristics, entity/finding LLM calls, `document_intelligence`, context creation) is the **regular document pipeline** and is only summarized at the end.

**Future / larger redesign (not implemented):** [PDF_INGESTION_ENHANCEMENT_PLAN.md](archive/planning_incubator/PDF_INGESTION_ENHANCEMENT_PLAN.md) — DB-backed sources, discovery queue, multi-format extraction, QA; phased rollout recommended.

---

## 1. Configuration

| Location | Role |
|----------|------|
| `api/config/orchestrator_governance.yaml` → `document_sources` | **automated_sources**: which built-in collectors run (`crs`, `gao`, `cbo`, `arxiv`). **ingest_urls**: optional list of strings or `{url, title, source_type, ...}` for manual ingestion (no RSS). |

Runtime loader: `config.orchestrator_governance.get_orchestrator_governance_config()`.

Default **automated_sources** (as shipped): `crs`, `gao`, `cbo`, `arxiv`.  
Default **ingest_urls**: `[]`.

---

## 2. How rows get into `intelligence.processed_documents`

A row is **metadata + `source_url`** (and optional title, `source_type`, `source_name`, etc.). **No PDF is downloaded at insert time** for automated collectors or `ingest_urls`.

### 2.1 Automation — PDF discovery inside `collection_cycle` (v8)

- **Scheduler**: There is **no** standalone `document_collection` entry in `AutomationManager.schedules`. RSS-style PDF discovery runs as a **sub-step** of **`collection_cycle`** (interval from `orchestrator_governance.yaml` → `collection_cycle.interval_seconds`, default **7200 s** ≈ 2h, overridable via env).
- **Implementation**: `_execute_collection_cycle` → `_execute_document_collection` → `document_collector_service.collect_documents(max_per_source=15)`.
- **Behaviour**: For each key in `document_sources.automated_sources` that exists in `SOURCES`, runs the matching fetcher, normalizes/dedupes URLs, inserts new rows.

### 2.2 Config — `ingest_urls`

- **API**: `POST /api/context_centric/processed_documents/ingest_from_config` → `document_acquisition_service.ingest_from_config()`.
- **Behaviour**: Inserts one row per entry (string URL or dict with `url` / `source_url`). **No** PDF fetch.

### 2.3 API — single document create

- **API**: `POST /api/context_centric/processed_documents` → `document_acquisition_service.create_document(...)`.
- **Behaviour**: Inserts one row from the JSON body (`source_url` required).

### 2.4 Standalone `document_processing` schedule

**`document_processing`** also has its **own** schedule (interval **600 s** in `automation_manager.py`) so the PDF backlog can drain between collection cycles. **`PHASE_ESTIMATED_DURATION_SECONDS["document_processing"]`** is **180** (used for run-history estimates / UI), not the 600 s tick interval.

---

## 3. Built-in PDF sources (automated collectors)

All fetchers live in **`api/services/document_collector_service.py`**.  
**User-Agent** for RSS/HTML requests: `NewsIntelligence/1.0` (feedparser) or the string below for HTTP resolution.

### 3.1 Source table

| Key (`source_type` on row) | Display name (`source_name`) | Domain filter* | Feed / API URL | How PDF URL is obtained |
|----------------------------|------------------------------|----------------|----------------|-------------------------|
| **crs** | Congressional Research Service | `politics` | `https://crsreports.congress.gov/rss/reports` | `feedparser`; PDF from entry links/enclosures/summary; base URL `https://crsreports.congress.gov` for relatives. |
| **gao** | Government Accountability Office | *(none — all domains)* | `https://www.gao.gov/rss/reports.xml` | Same; base `https://www.gao.gov`. |
| **cbo** | Congressional Budget Office | *(none)* | `https://www.cbo.gov/publications/all/rss.xml` | Same; base `https://www.cbo.gov`. |
| **arxiv** | arXiv | `science-tech` | `http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL&sortBy=submittedDate&max_results=<N>` | Atom XML; PDF built as `http://arxiv.org/pdf/{arxiv_id}.pdf`. |

\*When `collect_documents(domain=...)` is called with a domain, only sources whose filter matches **or** is `None` run. Automation uses **`collect_documents(max_per_source=15)`** with **no** domain → all enabled sources run.

### 3.2 URL normalization (collector)

- **`document_collector_service._normalize_url`** delegates to **`document_download_service.normalize_source_url`**: strips fragments, drops common tracking query params (`utm_*`, `gclid`, etc.).
- **Dedupe**: skip insert if `source_url` already exists in `intelligence.processed_documents`.

### 3.3 Landing pages at collection time

If the candidate URL does **not** contain `.pdf` (case-insensitive):

- **`_resolve_pdf_url_from_page`** calls **`document_download_service.resolve_pdf_url_from_landing_page`**: same `GET`, UA, timeout **20 s**, first `.pdf` `href` then `download`/`attachment`/`file` hrefs containing `pdf`; result URL is **normalized**.
- **GAO / CBO exception**: if resolution fails, the collector may still insert the **non-PDF** URL with `metadata.collection`: `resolver_needed`, `source_url_kind: landing_page`, so **`document_processing`** can try heavier resolution (including Playwright) later.

### 3.4 Library

- **RSS/Atom**: `feedparser` (CRS, GAO, CBO); **urllib** + **ElementTree** (arXiv API).

---

## 4. Download and resolution — `document_processing` phase

### 4.1 When it runs

- **Automation**: task **`document_processing`** — schedule interval **600 s** (10 min) in `automation_manager.py`; **`PHASE_ESTIMATED_DURATION_SECONDS["document_processing"]`** is **180** for duration estimates. Also invoked from **`collection_cycle`** when draining backlog.
- **Implementation**: `_execute_document_processing` → `process_unprocessed_documents(limit)` with dynamic **limit** 10 / 15 / 25 from backlog.
- **Selection** (`process_unprocessed_documents`): rows with `source_url` set, `extracted_sections` null or `[]`, and **not** `metadata.processing.permanent_failure = true`.

### 4.2 Pipeline entry for a single document

- **`process_document(document_id)`** (also used by API) loads the row, then **`_process_from_url(source_url, title)`** unless sections are supplied manually.

### 4.3 Primary download — `download_pdf`

**File**: `document_download_service.py` (`fetch_pdf_from_url` / `download_pdf`). **`document_processing_service._process_from_url`** calls **`fetch_pdf_from_url`**.

| Step | Behaviour |
|------|-----------|
| **Headers** | `User-Agent: Mozilla/5.0 (compatible; NewsIntelligence/1.0; +https://news-intel/document-bot)`, `Accept: application/pdf,*/*` |
| **HEAD** (optional, `head_first=True` on first attempt) | Timeout **10 s**. **404 / 410** → immediate permanent-style failure string. Other **4xx** → fail with `HTTP {code}` (not necessarily permanent). **405 / errors** → fall through to GET. |
| **GET** | `stream=True`, timeout **45 s** (`DOWNLOAD_TIMEOUT`), up to **`DOWNLOAD_RETRIES + 1`** attempts, **`RETRY_BACKOFF_SEC`** between tries. **5xx** / timeout / generic errors → retry. **404/410** on GET → permanent. |
| **Size** | Max **50 MB** (`MAX_PDF_SIZE_MB`). |
| **Validation** | If URL does not end with `.pdf` and `Content-Type` lacks `pdf`, body must start with **`%PDF-`**. |

**Permanent HTTP codes** (no endless retry for these): **404, 410**. **403** is *not* in that tuple (treated as potentially transient), but repeated failures can still hit **`MAX_PROCESSING_ATTEMPTS`** (5) and become **`permanent_failure`**.

### 4.4 If the first download fails — resolution chain

Only if `download_error` matches loose markers: **`not a pdf`**, **`http 4`**, **`timeout`**, **`download failed`** (`_process_from_url`).

1. **`resolve_pdf_url_from_landing_page`** (`document_download_service`): plain **`requests.get`** (same Mozilla UA as download), timeout **20 s**, parse HTML for `.pdf` links and some `download`/`attachment`/`file` hrefs containing `pdf`.
2. If still failing: **`_resolve_pdf_url_via_browser`** (same module) — **Playwright** Chromium, **unless** `ENABLE_BROWSER_PDF_FALLBACK` is `0`/`false`/`no` (default **on**). Listens for responses with PDF `Content-Type` or `.pdf` URL; also scans `a[href]` and HTML regex for `.pdf`.

After a new `pdf_url` is found, **`download_pdf(..., head_first=False)`** is used for the resolved URL.

**Stored on success**: `metadata.processing.resolved_url`, `resolved_via` (`html` | `browser`) when applicable.

### 4.5 Text extraction (end of “ingestion” scope for this doc)

Once bytes are valid:

1. **`pdfplumber`** (primary).
2. On import or runtime failure: **PyMuPDF** (`fitz`) — **`pymupdf`** is a core dependency in `pyproject.toml`.
3. Else **`pdfminer.six`**.

If all fail or produce no text, errors are recorded under **`metadata.processing`** (`method: pdf_failed`, `error`, `attempts`, possibly **`permanent_failure`**).

### 4.6 Row provenance (migration 184, Phase A)

On **successful** PDF processing from a URL or upload, `intelligence.processed_documents` is updated with:

- **`file_hash`** — SHA-256 (hex) of the **raw PDF bytes** used for extraction.
- **`file_size_bytes`** — length of those bytes.
- **`extraction_method`** — `pdfplumber`, `pymupdf`, or `pdfminer` (whichever produced the text).

Older rows and failures keep these columns **NULL** until a successful reprocess. No btree index on `file_hash` in 184 (optional follow-up migration for duplicate detection).

---

## 5. Operational references

| Need | Where |
|------|--------|
| Failure mix by source (403/404 vs parser) | `GET /api/system_monitoring/document_sources/health?window_days=30` |
| Disable a bad collector | Remove key from `document_sources.automated_sources` in **`orchestrator_governance.yaml`** |
| Re-queue “no PDF parser” rows after fixing deps | `api/scripts/reset_pdf_parser_failed_documents.py` |

---

## 6. After text (out of scope for this report)

Downstream steps include: **`_identify_sections`**, heuristic/LLM **entities** and **key findings**, **`processed_documents` / `document_intelligence` updates**, and **context** rows for the intelligence pipeline. Treat that as the **standard analysis pipeline**, not part of **source acquisition**.

---

## 7. Source files (quick index)

| Area | File(s) |
|------|---------|
| YAML config | `api/config/orchestrator_governance.yaml` |
| RSS/API collectors + insert | `api/services/document_collector_service.py` |
| Config / API ingest (metadata only) | `api/services/document_acquisition_service.py` |
| Automation scheduling | `api/services/automation_manager.py` (`collection_cycle`, `document_processing`) |
| PDF download + URL resolution | `api/services/document_download_service.py` |
| Text extraction, sections, persist | `api/services/document_processing_service.py` |
| HTTP routes | `api/domains/intelligence_hub/routes/context_centric.py` (`processed_documents*`) |
| Source health endpoint | `api/domains/system_monitoring/routes/resource_dashboard.py` (`/document_sources/health`) |
