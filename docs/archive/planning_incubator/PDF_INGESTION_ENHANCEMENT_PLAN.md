# PDF Ingestion Enhancement Plan

**Status:** Proposal / backlog — not implemented.  
**Current shipped behaviour:** [PDF_INGESTION_PIPELINE.md](PDF_INGESTION_PIPELINE.md).

Domain-agnostic vision for discovery, download, extraction, and source management. If adopted, implement in **small phases** (migrations + one service at a time); avoid big-bang rewrites.

---

## Phased rollout (A → E)

| Phase | Focus | Status |
|-------|--------|--------|
| **A** | Schema: `processed_documents` provenance columns | **Done** — migration `184_processed_documents_file_provenance.sql`; populated on successful URL/upload processing in `document_processing_service._process_from_url` / upload path |
| **B** | Refactor: download + URL resolution module | **Done** — `document_download_service.py`; processing calls `fetch_pdf_from_url` |
| **B.1** | Collector landing-page resolver delegates to download service | **Done** — `resolve_pdf_url_from_landing_page` + shared `normalize_source_url` |
| **C** | Config: optional `document_source_configs` + YAML fallback | Backlog |
| **D** | Queue: `document_discovery_queue` if backlog ordering is insufficient | Backlog |
| **E** | Metadata tables, QA/dedupe, multi-format extractors, new APIs | Backlog |

**Already in the codebase:** `GET /api/system_monitoring/document_sources/health`, `document_collector_service.py`, `document_download_service.py`, `document_processing_service.py`, `orchestrator_governance.yaml` — extend before adding parallel frameworks.

---

## Phase B — `document_download_service` (refactor, no behaviour change)

### Objective

Move **PDF byte fetch** and **landing-page → PDF URL resolution** out of `document_processing_service.py` into a dedicated module so processing stays “extract → sections → entities → findings → persist,” while download/retry/Playwright concerns live in one place. **No API changes, no migration, no user-visible behaviour change.**

### Scope — code to relocate

**From** `api/services/document_processing_service.py` (today):

| Block | Approx. lines (as of plan date) | Notes |
|-------|----------------------------------|--------|
| Module constants | `MAX_PDF_SIZE_MB`, `DOWNLOAD_TIMEOUT`, `DOWNLOAD_RETRIES`, `RETRY_BACKOFF_SEC`, `PERMANENT_HTTP_CODES`, `MAX_PROCESSING_ATTEMPTS` (download-related only), `ENABLE_BROWSER_PDF_FALLBACK` | Keep `MAX_PROCESSING_ATTEMPTS` in processing if still used for DB attempt counters; only move what is download-only |
| `_is_permanent_failure` | **Keep in** `document_processing_service` (also used by `process_unprocessed_documents` when marking permanent failures) | Optionally extract to a shared helper later; not required for B |
| `_download_pdf` | ~97–166 | `requests` stream, HEAD fast-fail, retries |
| `_resolve_pdf_url_from_landing_page` | ~167–198 | HTML parse for `.pdf` links |
| `_resolve_pdf_url_via_browser` | ~199–257 | Playwright fallback |

**Caller to thin:** `_process_from_url` should call a small orchestrator in the new module, e.g. `fetch_pdf_bytes_with_resolution(original_url: str) -> PdfFetchOutcome`, where `PdfFetchOutcome` carries `(bytes | None, error | None, resolved_url | None, resolved_via: Literal["html","browser"] | None)` matching what `_process_from_url` already derives today.

**Explicitly out of scope for Phase B**

- `_extract_text_from_pdf` and everything downstream (sections, LLM, DB writes) — stays in `document_processing_service.py`
- ~~`document_collector_service._resolve_pdf_url_from_page`~~ — **B.1** delegates to `resolve_pdf_url_from_landing_page`
- New environment variables (reuse existing `ENABLE_BROWSER_PDF_FALLBACK`)
- Changes to automation limits or `backlog_metrics` `document_processing` counts

### New module

- **Path:** `api/services/document_download_service.py`
- **Docstring:** Point to [PDF_INGESTION_PIPELINE.md](PDF_INGESTION_PIPELINE.md) §4 (download / resolution).
- **Dependency rule:** The new module must **not** import `document_processing_service` (avoid cycles). It may use `requests`, stdlib, Playwright only.

### Implementation steps

1. **Inventory** — Grep for `_download_pdf`, `_resolve_pdf`, `_is_permanent_failure` across `api/`; confirm no route imports private helpers (today: only `document_processing_service` uses them).
2. **Create** `document_download_service.py` — move functions + constants; add a single orchestration function used by `_process_from_url` (mirror current control flow: direct download → if error markers, HTML resolve → retry download → browser resolve → retry download).
3. **Wire** — `document_processing_service._process_from_url` calls the orchestrator; keep return shape to the rest of `process_document` unchanged (`file_hash`, `file_size_bytes`, `extraction_method`, `resolved_url`, `resolved_via`, sections, etc.).
4. **Verify** — Process one known-good PDF URL via existing API/automation; one landing-page-only URL (HTML resolve); optionally one path that hits Playwright (if enabled).
5. **Lint / compile** — `PYTHONPATH=api uv run python -m py_compile` on touched files.

### Phase B.1 — Align collector resolver (done)

`document_collector_service._resolve_pdf_url_from_page` calls **`document_download_service.resolve_pdf_url_from_landing_page`**; **`normalize_source_url`** is shared for insert dedupe and resolved hrefs.

### Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Circular import | Download module stays free of processing imports |
| Playwright / env in CI | Same `ENABLE_BROWSER_PDF_FALLBACK` gating as today |
| Subtle behaviour drift | Keep orchestration order and error strings aligned with current `_process_from_url`; add a short comment in processing pointing to the moved block for diff review |

### Acceptance criteria

- [ ] No new migrations or config keys required for deploy
- [ ] `process_document` / `process_unprocessed_documents` outcomes unchanged for a fixed set of test URLs (manual checklist is enough initially)
- [ ] `document_processing_service.py` is materially shorter; download logic has a single home
- [ ] [PDF_INGESTION_PIPELINE.md](PDF_INGESTION_PIPELINE.md) updated only if section numbers or file names change (optional in same PR)

### Suggested implementation order (original backlog, unchanged intent)

1. ~~**Schema:** provenance columns on `processed_documents`~~ → Phase A  
2. **Refactor:** Phase B (this section)  
3. **Config:** Phase C — `document_source_configs` + YAML fallback  
4. **Queue:** Phase D  
5. **Metadata / QA / multi-format:** Phase E  

---

## 1. Database Schema Enhancements

### 1.1 Core schema updates

```sql
-- Enhanced processed_documents (conceptual — align names/types with migration review)
ALTER TABLE intelligence.processed_documents ADD COLUMNS:
  - content_format TEXT -- 'pdf', 'html', 'xml', 'epub' (note: document_type already exists for 'report'/'paper'; avoid naming collision)
  - file_hash TEXT -- SHA256 of original file
  - file_size_bytes BIGINT
  - extraction_method TEXT -- 'pdfplumber', 'ocr', 'xml_parse', etc.
  - language_detected TEXT -- ISO 639-1
  - confidence_scores JSONB

CREATE TABLE intelligence.document_source_configs (
  source_key TEXT PRIMARY KEY,
  source_type TEXT,
  base_url TEXT,
  authentication JSONB,
  rate_limits JSONB,
  selector_rules JSONB,
  metadata_mappings JSONB,
  active BOOLEAN,
  last_successful_run TIMESTAMPTZ,
  error_count INTEGER,
  configuration JSONB
);

CREATE TABLE intelligence.document_discovery_queue (
  id BIGSERIAL PRIMARY KEY,
  source_key TEXT,
  discovered_url TEXT,
  discovery_method TEXT,
  discovery_metadata JSONB,
  priority INTEGER,
  attempts INTEGER DEFAULT 0,
  status TEXT,
  created_at TIMESTAMPTZ,
  processed_at TIMESTAMPTZ
);

-- Prefer object storage over BYTEA at scale
CREATE TABLE intelligence.document_binaries (
  document_id INTEGER REFERENCES intelligence.processed_documents(id),
  file_data BYTEA,
  storage_location TEXT,
  compression TEXT,
  created_at TIMESTAMPTZ
);
```

### 1.2 Metadata schema

```sql
CREATE TABLE intelligence.document_metadata_extracted (
  document_id INTEGER REFERENCES intelligence.processed_documents(id),
  metadata_type TEXT,
  metadata_value TEXT,
  extraction_source TEXT,
  confidence DOUBLE PRECISION,
  PRIMARY KEY (document_id, metadata_type, metadata_value)
);

CREATE TABLE intelligence.source_metadata_mappings (
  source_key TEXT,
  field_name TEXT,
  extraction_path TEXT,
  target_field TEXT,
  transform_function TEXT
);
```

## 2. Service architecture (sketches)

- **`DocumentDiscoveryService`** with strategies: `rss`, `api`, `sitemap`, `crawler`, etc. — fold existing `document_collector_service` fetchers in as `RSSDiscoveryStrategy` implementations first.
- **`EnhancedDocumentDownloadService`** — wrap today’s `_download_pdf`, landing-page resolve, Playwright fallback; add auth hooks and optional DOI/Wayback strategies later.
- **`UniversalDocumentExtractor`** — keep PDF stack; add HTML/XML/docx/epub behind feature flags and new deps.

## 3. Configuration

- Richer `document_sources` in YAML (templates, per-source `extends`) or move to DB `document_source_configs` with YAML as seed only.
- **Secrets:** never commit `authentication` JSON; use env references in config.

## 4. Queue and QA

- **Priority queue** — only if `ORDER BY created_at` + backlog metrics is insufficient.
- **QA / duplicates** — `file_hash` + optional `content_hash`; integrate with existing dedupe by `source_url`.

## 5. Monitoring

- Extend `document_sources/health` before building `/api/monitoring/sources/*` parallel trees.
- Materialized views after query patterns are stable.

## 6. API surface (future)

```text
POST /api/document_sources/register
GET  /api/document_sources/discover/{domain}
POST /api/documents/queue_bulk
GET  /api/documents/quality/{doc_id}
```

Mount under existing domain routers (`context_centric` / `system_monitoring`) per [WEB_API_CONNECTIONS.md](WEB_API_CONNECTIONS.md) conventions (`snake_case`, flat `/api`).

---

## Full original specification

The user-provided plan included additional pseudocode for `DocumentDiscoveryService`, `EnhancedDocumentDownloadService`, `UniversalDocumentExtractor`, YAML examples (PubMed Central, scrapers), `DocumentQueueManager`, `DocumentQualityAssurance`, indexes, and materialized views. The sections above preserve the intent; when implementing, treat the original message in chat as the full pseudocode reference or split into tickets per phase.
