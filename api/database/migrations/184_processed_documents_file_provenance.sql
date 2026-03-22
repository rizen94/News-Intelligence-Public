-- 184: Provenance for PDF bytes used during extraction (Phase A).
-- file_hash: SHA-256 hex of raw PDF; file_size_bytes: len(bytes); extraction_method: pdfplumber | pymupdf | pdfminer
-- Populated on successful URL/upload processing only; no historical backfill.

ALTER TABLE intelligence.processed_documents
  ADD COLUMN IF NOT EXISTS file_hash TEXT,
  ADD COLUMN IF NOT EXISTS file_size_bytes BIGINT,
  ADD COLUMN IF NOT EXISTS extraction_method TEXT;

COMMENT ON COLUMN intelligence.processed_documents.file_hash IS 'SHA-256 hex of raw PDF bytes last used for successful extraction';
COMMENT ON COLUMN intelligence.processed_documents.file_size_bytes IS 'Size of raw PDF bytes last used for successful extraction';
COMMENT ON COLUMN intelligence.processed_documents.extraction_method IS 'Backend used for text extraction: pdfplumber, pymupdf, or pdfminer';
