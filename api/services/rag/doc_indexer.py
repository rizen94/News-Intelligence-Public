"""
Doc Indexer — scan docs/*.md and _archive/*.md, extract headings/chunks, generate embeddings, upsert into doc_index.

Designed to be idempotent: runs on startup or via POST /api/search/docs/reindex,
and only updates files whose mtime or size has changed since last indexing pass.

Embedding uses the existing Ollama infrastructure (same model as news content RAG).
"""

import asyncio
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chunking / parsing helpers
# ---------------------------------------------------------------------------

_CHUNK_LINE_WINDOW = 60
_MIN_CHUNK_LINES = 5


def _read_file_lines(filepath: Path) -> list[str]:
    """Read file and return lines."""
    try:
        text = filepath.read_text(encoding="utf-8", errors="replace")
        return text.splitlines()
    except OSError as exc:
        logger.warning("Cannot read %s: %s", filepath, exc)
        return []


def _extract_headings(lines: list[str]) -> tuple[str | None, str]:
    """Extract title (first H1) and all H1-H3 headings as breadcrumb text."""
    title: str | None = None
    breadcrumbs: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("### ") and not stripped.startswith("#### "):
            breadcrumbs.append(stripped[4:])
        elif stripped.startswith("## ") and not stripped.startswith("###"):
            breadcrumbs.append(stripped[3:])
        elif stripped.startswith("# ") and not stripped.startswith("##"):
            if title is None:
                title = stripped[2:]
            breadcrumbs.append(stripped[2:])
    heading_text = " > ".join(breadcrumbs) if breadcrumbs else ""
    return title, heading_text


def _chunk_lines(lines: list[str], max_lines: int = _CHUNK_LINE_WINDOW) -> list[tuple[int, str]]:
    """Produce (line_offset_from_start_in_file, chunk_text) pairs."""
    if not lines:
        return []
    chunks: list[tuple[int, str]] = []
    current_block: list[str] = []
    block_start_idx = 0
    heading_seen = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        is_heading = bool(stripped.startswith("#"))
        if len(current_block) >= max_lines or (heading_seen and is_heading):
            if len(current_block) >= _MIN_CHUNK_LINES:
                raw = "\n".join(current_block).strip()
                chunks.append((block_start_idx, raw))
            current_block = []
            block_start_idx = idx
        current_block.append(line)
        if is_heading and not heading_seen:
            heading_seen = True
    if current_block and len(current_block) >= _MIN_CHUNK_LINES:
        raw = "\n".join(current_block).strip()
        chunks.append((block_start_idx, raw))
    return chunks


# ---------------------------------------------------------------------------
# Indexing entrypoint
# ---------------------------------------------------------------------------

_DOCS_ROOT = Path(__file__).resolve().parents[3] / "docs"
_ARCHIVE_ROOT = Path(__file__).resolve().parents[3] / "_archive"


def _collect_markdown_files() -> list[Path]:
    """Walk docs/ and _archive/, return .md files."""
    result: list[Path] = []
    for root in (_DOCS_ROOT, _ARCHIVE_ROOT):
        if not root.is_dir():
            continue
        for md in sorted(root.rglob("*.md")):
            rel = md.relative_to(root)
            if md.is_file() and len(rel.parts) <= 4:
                result.append(md)
    return result


def _relative_path(filepath: Path, base: Path) -> str:
    try:
        return str(filepath.relative_to(base))
    except ValueError:
        return filepath.name


def build_file_map(markdown_files: list[Path]) -> dict[str, Any]:
    """Parse all markdown files and return parsed metadata keyed by (relpath|offset)."""
    file_map: dict[str, Any] = {}
    for md in markdown_files:
        if str(md).startswith(str(_DOCS_ROOT)):
            base, rel_base = _DOCS_ROOT, "docs"
        elif str(md).startswith(str(_ARCHIVE_ROOT)):
            base, rel_base = _ARCHIVE_ROOT, "_archive"
        else:
            continue
        relpath = _relative_path(md, base)
        lines = _read_file_lines(md)
        if not lines:
            continue
        title, headings = _extract_headings(lines)
        chunks = _chunk_lines(lines)
        for local_offset, text in chunks:
            key = f"{relpath}|{local_offset}"
            file_map[key] = {
                "file_path": relpath,
                "title": title,
                "headings": headings,
                "chunk_text": text,
                "line_start": local_offset + 1,
                "line_end": local_offset + len(text.splitlines()) if text else local_offset + 1,
            }
    return file_map


def _vector_to_pgarray(vec: list[float]) -> str:
    """Format a 768-d float vector for PostgreSQL pgvector literal."""
    items = ",".join(f"{v:.10f}" for v in vec)
    return f"[{items}]"


def _upsert_doc_index(file_map: dict[str, Any], db_config: dict[str, str]) -> dict[str, int]:
    """Upsert doc_index rows and clean stale entries. Returns counts."""
    from api.shared.database import get_db_connection

    stats = {"upserted": 0, "deleted_stale": 0}
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT file_path FROM public.doc_index GROUP BY file_path")
            db_files = {row["file_path"] for row in cur.fetchall()}

            upsert_sql = """
                INSERT INTO public.doc_index
                    (file_path, title, headings, chunk_text, line_start, line_end, updated_at, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, now(), %s::vector)
                ON CONFLICT (file_path, line_start)
                DO UPDATE SET
                    title = EXCLUDED.title,
                    headings = EXCLUDED.headings,
                    chunk_text = EXCLUDED.chunk_text,
                    updated_at = now(),
                    embedding = EXCLUDED.embedding
            """

            file_paths_in_map = {entry["file_path"] for entry in file_map.values()}
            stale_files = db_files - file_paths_in_map
            if stale_files:
                placeholders = ",".join(["%s"] * len(stale_files))
                cur.execute(
                    f"DELETE FROM public.doc_index WHERE file_path IN ({placeholders})",
                    list(stale_files),
                )
                stats["deleted_stale"] = cur.rowcount

            for key, entry in file_map.items():
                try:
                    vec_str = _vector_to_pgarray(entry.get("_embedding")) if entry.get("_embedding") else "NULL"
                    cur.execute(
                        upsert_sql,
                        (
                            entry["file_path"],
                            entry["title"],
                            entry["headings"],
                            entry["chunk_text"],
                            entry["line_start"],
                            entry["line_end"],
                            vec_str,
                        ),
                    )
                    stats["upserted"] += cur.rowcount or 1
                except Exception as exc:
                    logger.warning("Doc indexer upsert for %s failed: %s", key, exc)

        conn.commit()
    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error("Doc index upsert failed: %s", e)
        raise
    finally:
        if conn:
            conn.close()
    return stats


# ---------------------------------------------------------------------------
# Async orchestrator (for embedding via Ollama)
# ---------------------------------------------------------------------------

async def reindex_docs(db_config: dict[str, str] = None) -> dict[str, Any]:
    """
    Full pipeline: scan files -> parse -> chunk -> embed -> upsert.

    Returns dict with 'file_count', 'chunk_count', 'upserted', 'deleted_stale', 'elapsed_sec'.
    """
    import time as _time
    start = _time.monotonic()

    if db_config is None:
        from api.shared.database import get_db_config
        db_config = get_db_config()

    markdown_files = _collect_markdown_files()
    logger.info("Doc indexer: found %d .md files", len(markdown_files))

    file_map = build_file_map(markdown_files)
    total_chunks = len(file_map)
    logger.info("Doc indexer: parsed %d chunks from %d files", total_chunks, len(markdown_files))

    # Embed all unique chunk texts via Ollama (sequentially for CB compliance)
    from api.shared.services.ollama_model_caller import get_ollama_model_caller

    caller = get_ollama_model_caller()
    embed_count = 0
    embed_errors = 0

    for key, entry in file_map.items():
        text_to_embed = (entry["headings"] + "\n\n" + entry["chunk_text"]).strip()
        try:
            vec, model_name = await caller.embed_text(text_to_embed)
            if vec and len(vec) == 768:
                entry["_embedding"] = vec
                embed_count += 1
            else:
                embed_errors += 1
                logger.warning("Embed for %s returned invalid vector (len=%s, model=%s)", key, len(vec) if vec else None, model_name)
        except Exception as exc:
            embed_errors += 1
            logger.warning("Embed for %s failed: %s", key, exc)

    logger.info("Doc indexer: embedded %d/%d chunks (%d errors, model=%s)",
                embed_count, total_chunks, embed_errors, caller._embedding_model if hasattr(caller, '_embedding_model') else "unknown")

    # Upsert to DB
    stats = await asyncio.to_thread(_upsert_doc_index, file_map, db_config)

    elapsed = _time.monotonic() - start
    logger.info(
        "Doc indexer complete: files=%d chunks=%d upserted=%d stale_deleted=%d elapsed=%.1fs",
        len(markdown_files), total_chunks, stats["upserted"], stats["deleted_stale"], elapsed,
    )

    return {
        "file_count": len(markdown_files),
        "chunk_count": total_chunks,
        "embed_errors": embed_errors,
        "upserted": stats["upserted"],
        "deleted_stale": stats["deleted_stale"],
        "elapsed_sec": round(elapsed, 2),
    }
