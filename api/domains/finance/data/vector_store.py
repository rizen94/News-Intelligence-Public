"""
Finance domain — ChromaDB vector store for evidence chunks.
Collection name embeds model (bge_large vs nomic_embed) to avoid dimension mismatch.
"""

import logging

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)

from config.settings import (
    FINANCE_CHROMA_DIR,
    EMBEDDING_DIMENSION,
    FINANCE_MODELS,
)

# Collection name suffix by model — prevents 768-dim (nomic) in 1024-dim (bge) collection
_EMBEDDING_MODEL_TO_SUFFIX = {
    "BAAI/bge-large-en-v1.5": "bge_large",
    "bge-large-en-v1.5": "bge_large",
    "nomic-embed-text": "nomic_embed",
}
_DEFAULT_SUFFIX = "bge_large"
FINANCE_CHROMA_COLLECTION = "finance_evidence"


def _collection_name_for_model(model_name: str | None = None) -> str:
    """Collection name with model suffix."""
    name = model_name or FINANCE_MODELS.get("embedding", "BAAI/bge-large-en-v1.5")
    suffix = _EMBEDDING_MODEL_TO_SUFFIX.get(name, _DEFAULT_SUFFIX)
    return f"{FINANCE_CHROMA_COLLECTION}_{suffix}"


def get_embedding_collection_info() -> tuple[str, str]:
    """Return (model_name, collection_name) for startup logging. No ChromaDB connection."""
    model = FINANCE_MODELS.get("embedding", "BAAI/bge-large-en-v1.5")
    coll = _collection_name_for_model(model)
    return (model, coll)


_chromadb_available: bool | None = None


def _chromadb_client():
    """Lazy ChromaDB client. Returns None if chromadb not installed."""
    global _chromadb_available
    if _chromadb_available is False:
        return None
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
    except ImportError:
        _chromadb_available = False
        logger.info(
            "ChromaDB not installed; finance vector store disabled. "
            "Install with: uv sync (chromadb is in pyproject.toml)"
        )
        return None
    try:
        client = chromadb.PersistentClient(
            path=str(FINANCE_CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _chromadb_available = True
        return client
    except Exception as e:
        logger.warning("Finance vector store client init failed: %s", e)
        return None


def get_client():
    """Return ChromaDB client or None if chromadb unavailable."""
    return _chromadb_client()


def get_collection(embedding_dimension: int | None = None, model_name: str | None = None):
    """Get or create finance evidence collection. Returns None if ChromaDB unavailable."""
    client = _chromadb_client()
    if client is None:
        return None
    coll_name = _collection_name_for_model(model_name)
    try:
        coll = client.get_or_create_collection(
            name=coll_name,
            metadata={"description": "Finance evidence chunks", "embedding_model": model_name or "bge-large"},
        )
        logger.info("Finance vector store: collection=%s, embedding_model=%s", coll_name, model_name or "bge-large")
        return coll
    except Exception as e:
        logger.warning("Finance vector store get_collection failed: %s", e)
        return None


def add(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str] | None = None,
    metadatas: list[dict] | None = None,
    model_name: str | None = None,
) -> bool:
    """Add documents to finance collection. Returns False if ChromaDB unavailable (no error log)."""
    coll = get_collection(model_name=model_name)
    if coll is None:
        return False
    try:
        coll.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents or [""] * len(ids),
            metadatas=metadatas or [{}] * len(ids),
        )
        return True
    except Exception as e:
        logger.warning("Finance vector store add failed: %s", e)
        return False


def query(
    query_embeddings: list[list[float]],
    n_results: int = 5,
    where: dict | None = None,
) -> dict:
    """Query finance collection by embedding. Returns empty result if ChromaDB unavailable."""
    coll = get_collection()
    if coll is None:
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    try:
        return coll.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
            where=where,
        )
    except Exception as e:
        logger.warning("Finance vector store query failed: %s", e)
        return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}


def count() -> int:
    """Return number of documents in finance collection. Returns 0 if ChromaDB unavailable."""
    coll = get_collection()
    if coll is None:
        return 0
    try:
        return coll.count()
    except Exception:
        return 0
