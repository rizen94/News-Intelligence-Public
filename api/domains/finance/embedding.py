"""
Finance domain — embedding pipeline for evidence chunks.
Uses bge-large-en-v1.5 (1024-dim) when available; optional Ollama fallback.
"""

import logging

try:
    from config.logging_config import get_component_logger

    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import (
    CHUNK_OVERLAP_TOKENS,
    CHUNK_SIZE_TOKENS,
    FINANCE_MODELS,
    OLLAMA_HOST,
)

# Approximate: 1 token ~ 4 chars for English
CHARS_PER_TOKEN = 4
CHUNK_SIZE_CHARS = CHUNK_SIZE_TOKENS * CHARS_PER_TOKEN
CHUNK_OVERLAP_CHARS = CHUNK_OVERLAP_TOKENS * CHARS_PER_TOKEN


def chunk_text(
    text: str, chunk_size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS
) -> list[str]:
    """Split text into overlapping chunks. Simple word-boundary aware."""
    if not text or not text.strip():
        return []
    text = text.strip()
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        # Try to break at word boundary
        if end < len(text):
            for sep in ("\n\n", "\n", ". ", " "):
                last = text.rfind(sep, start, end + 1)
                if last > start:
                    end = last + len(sep)
                    break
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end - overlap
        if start >= len(text):
            break
    return chunks


def _get_sentence_transformer_model():
    """Lazy load bge-large. Returns None if unavailable."""
    try:
        from sentence_transformers import SentenceTransformer

        model_name = FINANCE_MODELS.get("embedding", "BAAI/bge-large-en-v1.5")
        return SentenceTransformer(model_name)
    except ImportError:
        logger.warning("sentence-transformers not available for finance embeddings")
        return None
    except Exception as e:
        logger.warning("Finance embedding model load failed: %s", e)
        return None


_model = None


def get_embedding_model():
    """Singleton embedding model for finance."""
    global _model
    if _model is None:
        _model = _get_sentence_transformer_model()
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts. Returns 1024-dim vectors or [] on failure."""
    model = get_embedding_model()
    if not model or not texts:
        return []

    try:
        embeddings = model.encode(texts, convert_to_numpy=True)
        if hasattr(embeddings, "tolist"):
            return [e.tolist() for e in embeddings]
        return list(embeddings)
    except Exception as e:
        logger.warning("Finance embed_texts failed: %s", e)
        return []


def embed_text(text: str) -> list[float] | None:
    """Generate embedding for single text."""
    result = embed_texts([text])
    return result[0] if result else None


def ingest_evidence_chunks(
    chunks: list,
    record_ledger: bool = True,
) -> tuple[int, list[str]]:
    """
    Embed EvidenceChunk list, upsert to ChromaDB, optionally record in ledger.
    Returns (count_embedded, list of chunk_ids that were stored).
    """
    if not chunks:
        return 0, []
    try:
        from domains.finance.data.evidence_ledger import record as ledger_record
        from domains.finance.data.vector_store import add as vs_add
    except ImportError as e:
        logger.warning("Evidence ingestion unavailable: %s", e)
        return 0, []

    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)
    if not embeddings or len(embeddings) != len(chunks):
        logger.warning(
            "Embedding count mismatch: %d chunks, %d embeddings", len(chunks), len(embeddings) or 0
        )
        return 0, []

    ids = [c.chunk_id() for c in chunks]
    metadatas = [
        {
            "source": c.source,
            "document_id": c.document_id,
            "chunk_index": c.chunk_index,
            **(c.metadata or {}),
        }
        for c in chunks
    ]
    docs = [c.text for c in chunks]

    if not vs_add(ids=ids, embeddings=embeddings, documents=docs, metadatas=metadatas):
        return 0, []

    if record_ledger:
        from datetime import datetime, timezone

        report_id = f"evidence_ingest_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        for c in chunks:
            ledger_record(
                report_id=report_id,
                source_type="evidence_chunk",
                source_id=c.source,
                evidence_data={
                    "chunk_id": c.chunk_id(),
                    "document_id": c.document_id,
                    "chunk_index": c.chunk_index,
                    **c.metadata,
                },
            )

    return len(chunks), ids


def embed_with_ollama_fallback(text: str) -> tuple[list[float], str] | None:
    """Try sentence-transformers first; fallback to Ollama nomic-embed-text (768-dim).
    Returns (embedding, model_name) so vector store can use the correct collection.
    Ollama produces 768-dim → use finance_evidence_nomic_embed collection."""
    vec = embed_text(text)
    if vec:
        model = FINANCE_MODELS.get("embedding", "BAAI/bge-large-en-v1.5")
        return (vec, model)
    try:
        import requests

        r = requests.post(
            f"{OLLAMA_HOST}/api/embeddings",
            json={"model": "nomic-embed-text", "prompt": text[:4000]},
            timeout=60,
        )
        if r.status_code == 200:
            emb = r.json().get("embedding")
            if emb:
                return (emb, "nomic-embed-text")
    except Exception as e:
        logger.debug("Ollama embedding fallback failed: %s", e)
    return None
