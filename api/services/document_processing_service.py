"""
Document processing service — PDF parsing, text extraction, section identification,
entity tagging, and key findings extraction.

HTTP download and landing-page PDF resolution live in document_download_service.
This module extracts text via pdfplumber, identifies document sections (headings,
paragraphs, tables), runs entity extraction and LLM-based key findings extraction,
then stores everything in processed_documents and document_intelligence.

T3.2 of V6_QUALITY_FIRST_TODO.md. See docs/V6_QUALITY_FIRST_UPGRADE_PLAN.md.
"""

import hashlib
import io
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from shared.database.connection import get_db_connection

from services.document_download_service import fetch_pdf_from_url

logger = logging.getLogger(__name__)

MAX_PAGES = 200
# After this many failed attempts (any error), mark as permanent to avoid infinite retry
MAX_PROCESSING_ATTEMPTS = 5
# Process this many documents in parallel per batch (throughput vs LLM/DB load)
BATCH_PARALLEL_WORKERS = 3

# Section heading heuristics: lines that are short, often bold/large, start sections
HEADING_PATTERN = re.compile(
    r"^(?:\d+\.?\s+|[IVX]+\.?\s+|[A-Z]\.\s+)?"  # optional numbering
    r"[A-Z][A-Za-z\s,&\-:]{3,80}$"  # title-case line, 4-80 chars
)

FINDINGS_PROMPT = """Analyze this document and extract the key findings, conclusions, and recommendations.

Document title: {title}
Document sections:
{sections_text}

For each finding, provide:
- finding: a concise statement of the finding
- section: which section it came from (or "general")
- importance: high, medium, or low

Return a JSON array of objects. If no clear findings, return [].
Respond with ONLY a JSON array."""

ENTITY_EXTRACTION_PROMPT = """Extract all named entities (people, organizations, locations, laws, programs) mentioned in this document excerpt.

For each entity, provide:
- name: the entity name
- type: person, organization, location, legislation, program, or other
- context: a brief phrase showing how they appear

Return a JSON array. Respond with ONLY a JSON array.

Text:
{text}"""


# ---------------------------------------------------------------------------
# Permanent-failure policy (download HTTP details live in document_download_service)
# ---------------------------------------------------------------------------


def _is_permanent_failure(error_message: str) -> bool:
    """True if we should stop retrying this URL (404/410 or explicit 'permanent')."""
    if not error_message:
        return False
    msg = error_message.lower()
    if "permanent" in msg:
        return True
    for code in (404, 410):
        if str(code) in msg or ("not found" in msg and code == 404):
            return True
    return False


# ---------------------------------------------------------------------------
# PDF text extraction with pdfplumber
# ---------------------------------------------------------------------------


def _extract_text_from_pdf(pdf_bytes: bytes, max_pages: int = MAX_PAGES) -> dict[str, Any]:
    """
    Extract text, sections, and tables from PDF bytes using pdfplumber.
    Returns {pages: [{page_num, text, tables}], metadata: {...}, total_text: str}.
    """
    try:
        import pdfplumber
    except ImportError:
        return _extract_text_fallback(pdf_bytes, max_pages)

    result: dict[str, Any] = {
        "pages": [],
        "metadata": {},
        "total_text": "",
        "table_count": 0,
    }

    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            result["metadata"] = {
                "page_count": len(pdf.pages),
                "info": pdf.metadata or {},
            }

            all_text_parts: list[str] = []
            for i, page in enumerate(pdf.pages[:max_pages]):
                page_text = page.extract_text() or ""
                tables = page.extract_tables() or []
                table_data = []
                for table in tables:
                    if table:
                        table_data.append(
                            {
                                "rows": len(table),
                                "cols": len(table[0]) if table[0] else 0,
                                "data": [
                                    [str(cell) if cell else "" for cell in row]
                                    for row in table[:20]  # cap table rows
                                ],
                            }
                        )

                result["pages"].append(
                    {
                        "page_num": i + 1,
                        "text": page_text,
                        "tables": table_data,
                    }
                )
                all_text_parts.append(page_text)
                result["table_count"] += len(table_data)

            result["total_text"] = "\n\n".join(all_text_parts)
    except Exception as e:
        logger.warning("pdfplumber extraction failed: %s", e)
        return _extract_text_fallback(pdf_bytes, max_pages)

    result["extraction_method"] = "pdfplumber"
    return result


def _extract_text_pymupdf(pdf_bytes: bytes, max_pages: int = MAX_PAGES) -> dict[str, Any] | None:
    """Optional: extract text with PyMuPDF (fitz) — often faster and handles some PDFs better."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return None
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        pages = []
        all_text = []
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            text = page.get_text() or ""
            all_text.append(text)
            pages.append({"page_num": i + 1, "text": text, "tables": []})
        doc.close()
        return {
            "pages": pages,
            "metadata": {"page_count": len(pages)},
            "total_text": "\n\n".join(all_text),
            "table_count": 0,
            "extraction_method": "pymupdf",
        }
    except Exception as e:
        logger.debug("PyMuPDF extraction failed: %s", e)
        return None


def _extract_text_fallback(pdf_bytes: bytes, max_pages: int = MAX_PAGES) -> dict[str, Any]:
    """Fallback: try PyMuPDF (if available), then pdfminer, or return minimal result."""
    result = _extract_text_pymupdf(pdf_bytes, max_pages)
    if result and (result.get("total_text") or "").strip():
        return result

    try:
        from pdfminer.high_level import extract_text as pdfminer_extract

        text = pdfminer_extract(io.BytesIO(pdf_bytes), maxpages=max_pages)
        if text and text.strip():
            return {
                "pages": [{"page_num": 1, "text": text, "tables": []}],
                "metadata": {},
                "total_text": text,
                "table_count": 0,
                "extraction_method": "pdfminer",
            }
    except Exception:
        pass

    return {
        "pages": [],
        "metadata": {},
        "total_text": "",
        "table_count": 0,
        "error": "No PDF parser available (install pdfplumber, pymupdf, or pdfminer.six)",
    }


# ---------------------------------------------------------------------------
# Section identification
# ---------------------------------------------------------------------------


def _identify_sections(total_text: str) -> list[dict[str, Any]]:
    """
    Parse extracted text into sections based on heading detection.
    Returns [{title, content, level, start_pos}].
    """
    lines = total_text.split("\n")
    sections: list[dict[str, Any]] = []
    current_title = "Document Header"
    current_content: list[str] = []
    current_level = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            current_content.append("")
            continue

        is_heading = False
        level = 1

        # Detect numbered headings: "1.", "1.1", "I.", "A."
        if re.match(r"^\d+(\.\d+)*\.?\s+[A-Z]", stripped) and len(stripped) < 100:
            is_heading = True
            dots = stripped.split(".")[0]
            level = len(dots.split(".")) if "." in stripped[:6] else 1
        elif re.match(r"^[IVX]+\.\s+", stripped) and len(stripped) < 100:
            is_heading = True
            level = 1
        elif HEADING_PATTERN.match(stripped) and len(stripped) < 80:
            # All-caps or title-case short lines
            if stripped.isupper() and len(stripped) > 3:
                is_heading = True
                level = 1
            elif stripped[0].isupper() and not stripped.endswith(".") and len(stripped) < 60:
                word_count = len(stripped.split())
                if word_count <= 8:
                    is_heading = True
                    level = 2

        if is_heading:
            # Save previous section
            content_text = "\n".join(current_content).strip()
            if content_text or current_title != "Document Header":
                sections.append(
                    {
                        "title": current_title,
                        "content": content_text,
                        "level": current_level,
                    }
                )
            current_title = stripped
            current_content = []
            current_level = level
        else:
            current_content.append(stripped)

    # Final section
    content_text = "\n".join(current_content).strip()
    if content_text:
        sections.append(
            {
                "title": current_title,
                "content": content_text,
                "level": current_level,
            }
        )

    return sections


# ---------------------------------------------------------------------------
# Entity extraction from document text
# ---------------------------------------------------------------------------


def _extract_entities_from_text(text: str, max_chars: int = 3000) -> list[dict[str, Any]]:
    """Extract entities from document text via LLM with heuristic fallback."""
    excerpt = text[:max_chars]

    try:
        from shared.services.llm_service import LLMService

        llm = LLMService()
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=excerpt)
        response = llm.generate(prompt, max_tokens=500)
        if response:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
            entities = json.loads(cleaned)
            if isinstance(entities, list):
                return [
                    {
                        "name": e.get("name", "")[:255],
                        "type": e.get("type", "other"),
                        "context": e.get("context", "")[:300],
                    }
                    for e in entities
                    if e.get("name")
                ]
    except Exception as e:
        logger.debug("LLM entity extraction from document: %s", e)

    # Heuristic fallback: find capitalized multi-word phrases
    entities = []
    seen = set()
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", excerpt):
        name = match.group(1)
        if name.lower() not in seen and len(name) > 4:
            seen.add(name.lower())
            entities.append({"name": name, "type": "unknown", "context": ""})
            if len(entities) >= 30:
                break
    return entities


# ---------------------------------------------------------------------------
# Key findings extraction via LLM
# ---------------------------------------------------------------------------


def _extract_key_findings(
    title: str,
    sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Use LLM to extract key findings from document sections."""
    sections_text = ""
    for s in sections[:15]:
        sections_text += f"\n### {s['title']}\n{s['content'][:500]}\n"
        if len(sections_text) > 4000:
            break

    if not sections_text.strip():
        return []

    try:
        from shared.services.llm_service import LLMService

        llm = LLMService()
        prompt = FINDINGS_PROMPT.format(title=title or "Untitled", sections_text=sections_text)
        response = llm.generate(prompt, max_tokens=600)
        if response:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
            findings = json.loads(cleaned)
            if isinstance(findings, list):
                return [
                    {
                        "finding": f.get("finding", "")[:500],
                        "section": f.get("section", "general"),
                        "importance": f.get("importance", "medium"),
                    }
                    for f in findings
                    if f.get("finding")
                ]
    except Exception as e:
        logger.debug("LLM key findings extraction: %s", e)

    return []


# ---------------------------------------------------------------------------
# Main processing pipeline
# ---------------------------------------------------------------------------


def process_document(
    document_id: int,
    storyline_connections: list[dict[str, Any]] | None = None,
    extracted_sections: list[dict[str, Any]] | None = None,
    key_findings: list[dict[str, Any]] | None = None,
    entities_mentioned: list[dict[str, Any]] | None = None,
    force_reprocess: bool = False,
) -> dict[str, Any]:
    """
    Full document processing pipeline:
      1. Fetch document metadata from processed_documents
      2. If source_url points to a PDF, download and parse it
      3. Identify sections from extracted text
      4. Extract entities via LLM (or heuristic fallback)
      5. Extract key findings via LLM
      6. Store everything back to processed_documents + document_intelligence

    If extracted_sections/key_findings/entities_mentioned are provided directly,
    those override the automatic extraction (useful for manual or pre-processed input).
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database unavailable"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_url, title, source_type, document_type, extracted_sections, metadata
                FROM intelligence.processed_documents
                WHERE id = %s
                """,
                (document_id,),
            )
            doc_row = cur.fetchone()
            if not doc_row:
                conn.close()
                return {"success": False, "error": f"Document {document_id} not found"}

            (
                doc_id,
                source_url,
                title,
                source_type,
                doc_type,
                existing_sections,
                existing_metadata,
            ) = doc_row

            # Skip if already processed (unless forced)
            if existing_sections and not force_reprocess and not extracted_sections:
                existing = existing_sections if isinstance(existing_sections, list) else []
                if len(existing) > 0:
                    conn.close()
                    return {
                        "success": True,
                        "document_id": doc_id,
                        "status": "already_processed",
                        "section_count": len(existing),
                    }

        conn.close()

        # Automatic extraction if not provided
        auto_extracted = False
        processing_metadata: dict[str, Any] = {"method": "manual"}
        provenance_file_hash: str | None = None
        provenance_file_size_bytes: int | None = None
        provenance_extraction_method: str | None = None
        prev_attempts = 0
        if existing_metadata and isinstance(existing_metadata, dict):
            proc = existing_metadata.get("processing") or {}
            if isinstance(proc, dict):
                try:
                    prev_attempts = int(proc.get("attempts") or 0)
                except (TypeError, ValueError):
                    pass

        if not extracted_sections and source_url:
            pdf_result = _process_from_url(source_url, title or "")
            if pdf_result.get("success"):
                auto_extracted = True
                extracted_sections = pdf_result.get("sections", [])
                key_findings = key_findings or pdf_result.get("key_findings", [])
                entities_mentioned = entities_mentioned or pdf_result.get("entities", [])
                processing_metadata = {
                    "method": "pdf_auto",
                    "page_count": pdf_result.get("page_count", 0),
                    "table_count": pdf_result.get("table_count", 0),
                    "text_length": pdf_result.get("text_length", 0),
                }
                if pdf_result.get("resolved_url"):
                    processing_metadata["resolved_url"] = pdf_result.get("resolved_url")
                if pdf_result.get("resolved_via"):
                    processing_metadata["resolved_via"] = pdf_result.get("resolved_via")
                if pdf_result.get("file_hash"):
                    provenance_file_hash = pdf_result.get("file_hash")
                    provenance_file_size_bytes = pdf_result.get("file_size_bytes")
                    provenance_extraction_method = pdf_result.get("extraction_method")
            else:
                error_msg = pdf_result.get("error", "unknown")
                attempts = prev_attempts + 1
                processing_metadata = {
                    "method": "pdf_failed",
                    "error": error_msg,
                    "attempts": attempts,
                }
                if _is_permanent_failure(error_msg) or attempts >= MAX_PROCESSING_ATTEMPTS:
                    processing_metadata["permanent_failure"] = True
                    extracted_sections = []
                    key_findings = key_findings or []
                    entities_mentioned = entities_mentioned or []
                    logger.info(
                        "Document %s marked permanent failure (attempts=%s, error=%s)",
                        document_id,
                        attempts,
                        error_msg[:80],
                    )
                    if "HTTP 403" in error_msg or "HTTP 404" in error_msg:
                        logger.warning(
                            "Document %s: repeated HTTP access failure — if many rows share "
                            "source_type, assess that collector (RSS/HTML → PDF links, bot blocks). "
                            "See GET /api/system_monitoring/document_sources/health and "
                            "document_sources.automated_sources in orchestrator_governance.yaml.",
                            document_id,
                        )

        # Store results
        conn = get_db_connection()
        if not conn:
            return {"success": False, "error": "Database unavailable for storage"}

        try:
            with conn.cursor() as cur:
                updates = ["updated_at = NOW()"]
                params: list[Any] = []

                if extracted_sections is not None:
                    updates.append("extracted_sections = %s")
                    params.append(json.dumps(extracted_sections))
                if key_findings is not None:
                    updates.append("key_findings = %s")
                    params.append(json.dumps(key_findings))
                if entities_mentioned is not None:
                    updates.append("entities_mentioned = %s")
                    params.append(json.dumps(entities_mentioned))

                # Store processing metadata
                updates.append("metadata = COALESCE(metadata, '{}') || %s")
                params.append(json.dumps({"processing": processing_metadata}))

                if provenance_file_hash is not None:
                    updates.append("file_hash = %s")
                    params.append(provenance_file_hash)
                if provenance_file_size_bytes is not None:
                    updates.append("file_size_bytes = %s")
                    params.append(provenance_file_size_bytes)
                if provenance_extraction_method:
                    updates.append("extraction_method = %s")
                    params.append(provenance_extraction_method)

                params.append(document_id)
                cur.execute(
                    f"UPDATE intelligence.processed_documents SET {', '.join(updates)} WHERE id = %s",
                    params,
                )

                # Upsert document_intelligence
                connections = json.dumps(storyline_connections or [])
                cur.execute(
                    "SELECT id FROM intelligence.document_intelligence WHERE document_id = %s",
                    (document_id,),
                )
                existing_di = cur.fetchone()

                impact = _assess_impact(extracted_sections or [], key_findings or [])

                if existing_di:
                    cur.execute(
                        """
                        UPDATE intelligence.document_intelligence
                        SET storyline_connections = %s, impact_assessment = %s
                        WHERE document_id = %s
                        RETURNING id
                        """,
                        (connections, impact, document_id),
                    )
                    di_id = cur.fetchone()[0]
                else:
                    cur.execute(
                        """
                        INSERT INTO intelligence.document_intelligence
                        (document_id, storyline_connections, impact_assessment)
                        VALUES (%s, %s, %s)
                        RETURNING id
                        """,
                        (document_id, connections, impact),
                    )
                    di_id = cur.fetchone()[0]

                # Create intelligence.contexts for each section so they join extraction/synthesis pipeline
                # v8: domain_key from document metadata (politics/finance/science-tech) for discovery/synthesis
                cur.execute(
                    """
                    SELECT COALESCE(metadata->'processing'->>'domain_key', metadata->>'domain_key')
                    FROM intelligence.processed_documents WHERE id = %s
                    """,
                    (document_id,),
                )
                row = cur.fetchone()
                doc_domain = (row[0] if row and row[0] else None) or "documents"
                if doc_domain and doc_domain not in ("politics", "finance", "science-tech"):
                    doc_domain = "documents"
                sections_list = extracted_sections or []
                doc_title = (title or "Document")[:500]
                for idx, sec in enumerate(sections_list):
                    if not isinstance(sec, dict):
                        continue
                    sec_title = (sec.get("title") or f"Section {idx + 1}")[:2000]
                    sec_content = (sec.get("content") or "")[:500000]
                    if not sec_content.strip():
                        continue
                    cur.execute(
                        """
                        INSERT INTO intelligence.contexts
                        (source_type, domain_key, title, content, raw_content, metadata)
                        VALUES ('pdf_section', %s, %s, %s, %s, %s)
                        """,
                        (
                            doc_domain,
                            f"{doc_title}: {sec_title}",
                            sec_content,
                            sec_content,
                            json.dumps({"document_id": document_id, "section_index": idx}),
                        ),
                    )

            conn.commit()
            conn.close()

            return {
                "success": True,
                "document_id": document_id,
                "document_intelligence_id": di_id,
                "auto_extracted": auto_extracted,
                "section_count": len(extracted_sections or []),
                "finding_count": len(key_findings or []),
                "entity_count": len(entities_mentioned or []),
                "processing": processing_metadata,
            }
        except Exception as e:
            logger.exception("process_document storage: %s", e)
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
            return {"success": False, "error": str(e)}

    except Exception as e:
        logger.exception("process_document: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def _process_from_url(url: str, title: str) -> dict[str, Any]:
    """Download PDF from URL and extract text, sections, entities, findings."""
    pdf_bytes, download_error, pdf_url, resolved_via = fetch_pdf_from_url(url)
    if download_error:
        return {"success": False, "error": download_error}

    extraction = _extract_text_from_pdf(pdf_bytes)
    if extraction.get("error"):
        return {"success": False, "error": extraction["error"]}

    total_text = extraction.get("total_text", "")
    if not total_text.strip():
        return {"success": False, "error": "No text extracted from PDF"}

    sections = _identify_sections(total_text)
    entities = _extract_entities_from_text(total_text)
    key_findings = _extract_key_findings(title, sections)

    file_hash = hashlib.sha256(pdf_bytes).hexdigest()
    file_size_bytes = len(pdf_bytes)
    extraction_method = extraction.get("extraction_method")
    if not extraction_method:
        extraction_method = "pdfplumber"

    return {
        "success": True,
        "resolved_url": pdf_url if pdf_url != url else None,
        "resolved_via": resolved_via,
        "sections": sections,
        "entities": entities,
        "key_findings": key_findings,
        "page_count": extraction.get("metadata", {}).get("page_count", 0),
        "table_count": extraction.get("table_count", 0),
        "text_length": len(total_text),
        "tables": [t for page in extraction.get("pages", []) for t in page.get("tables", [])],
        "file_hash": file_hash,
        "file_size_bytes": file_size_bytes,
        "extraction_method": extraction_method,
    }


def _assess_impact(
    sections: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> str:
    """Generate a brief impact assessment from sections and findings."""
    high_findings = [f for f in findings if f.get("importance") == "high"]
    section_count = len(sections)

    parts = []
    if section_count:
        parts.append(f"Document contains {section_count} sections.")
    if high_findings:
        parts.append(f"{len(high_findings)} high-importance findings identified.")
        parts.append("Key: " + "; ".join(f["finding"][:100] for f in high_findings[:3]))
    elif findings:
        parts.append(f"{len(findings)} findings extracted.")

    return " ".join(parts) if parts else "Document processed; no significant findings identified."


# ---------------------------------------------------------------------------
# Process from raw PDF bytes (for file upload)
# ---------------------------------------------------------------------------


def process_uploaded_pdf(
    pdf_bytes: bytes,
    title: str,
    source_name: str | None = None,
    source_type: str = "upload",
    document_type: str = "report",
    domain_key: str | None = None,
) -> dict[str, Any]:
    """
    Process a directly uploaded PDF (not from URL).
    Creates a processed_documents row, then runs the full extraction pipeline.
    """
    # Extract text
    extraction = _extract_text_from_pdf(pdf_bytes)
    total_text = extraction.get("total_text", "")
    if not total_text.strip():
        return {"success": False, "error": "No text could be extracted from the uploaded PDF"}

    sections = _identify_sections(total_text)
    entities = _extract_entities_from_text(total_text)
    key_findings = _extract_key_findings(title, sections)

    file_hash_hex = hashlib.sha256(pdf_bytes).hexdigest()
    file_size_bytes = len(pdf_bytes)
    extraction_method = extraction.get("extraction_method") or "pdfplumber"

    # Create document record
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database unavailable"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO intelligence.processed_documents
                (source_type, source_name, title, document_type,
                 extracted_sections, key_findings, entities_mentioned, metadata,
                 file_hash, file_size_bytes, extraction_method)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    source_type,
                    source_name or "upload",
                    title,
                    document_type,
                    json.dumps(sections),
                    json.dumps(key_findings),
                    json.dumps(entities),
                    json.dumps(
                        {
                            "processing": {
                                "method": "upload_pdf",
                                "page_count": extraction.get("metadata", {}).get("page_count", 0),
                                "table_count": extraction.get("table_count", 0),
                                "text_length": len(total_text),
                                "domain_key": domain_key,
                            }
                        }
                    ),
                    file_hash_hex,
                    file_size_bytes,
                    extraction_method,
                ),
            )
            doc_id = cur.fetchone()[0]

            # Create document_intelligence
            impact = _assess_impact(sections, key_findings)
            cur.execute(
                """
                INSERT INTO intelligence.document_intelligence
                (document_id, impact_assessment)
                VALUES (%s, %s)
                RETURNING id
                """,
                (doc_id, impact),
            )
            di_id = cur.fetchone()[0]

        conn.commit()
        conn.close()

        return {
            "success": True,
            "document_id": doc_id,
            "document_intelligence_id": di_id,
            "section_count": len(sections),
            "finding_count": len(key_findings),
            "entity_count": len(entities),
            "page_count": extraction.get("metadata", {}).get("page_count", 0),
        }
    except Exception as e:
        logger.exception("process_uploaded_pdf: %s", e)
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------


def process_unprocessed_documents(limit: int = 10) -> dict[str, Any]:
    """Process documents that have a source_url but no extracted_sections yet."""
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database unavailable"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, source_url, title
                FROM intelligence.processed_documents
                WHERE source_url IS NOT NULL
                  AND source_url != ''
                  AND (extracted_sections IS NULL OR extracted_sections = '[]'::jsonb)
                  AND (metadata IS NULL OR (metadata->'processing'->>'permanent_failure') IS DISTINCT FROM 'true')
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            docs = cur.fetchall()
        conn.close()

        results = []
        workers = min(BATCH_PARALLEL_WORKERS, len(docs)) if docs else 1
        if workers <= 1 or len(docs) <= 1:
            for doc_id, url, title in docs:
                r = process_document(doc_id)
                results.append(
                    {
                        "document_id": doc_id,
                        "title": title,
                        "result": r.get("success", False),
                        "sections": r.get("section_count", 0),
                        "findings": r.get("finding_count", 0),
                        "error": r.get("error"),
                    }
                )
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_to_doc = {
                    executor.submit(process_document, doc_id): (doc_id, title)
                    for doc_id, _url, title in docs
                }
                for future in as_completed(future_to_doc):
                    doc_id, title = future_to_doc[future]
                    try:
                        r = future.result()
                    except Exception as e:
                        logger.warning("document_processing doc_id=%s: %s", doc_id, e)
                        r = {"success": False, "error": str(e)}
                    results.append(
                        {
                            "document_id": doc_id,
                            "title": title,
                            "result": r.get("success", False),
                            "sections": r.get("section_count", 0),
                            "findings": r.get("finding_count", 0),
                            "error": r.get("error"),
                        }
                    )

        return {
            "success": True,
            "processed": len(results),
            "details": results,
        }
    except Exception as e:
        logger.warning("process_unprocessed_documents: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}
