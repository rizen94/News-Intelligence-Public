# Vector store graceful degradation patch

The file `api/domains/finance/data/vector_store.py` could not be edited from this environment (permission denied). Apply the following changes manually so that when ChromaDB is not installed, the finance vector store no-ops without repeated warnings.

## 1. Replace `get_client` and add cache

**Remove** the existing `get_client()` (the one that raises `ImportError`).

**Add** after the logger line:

```python
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
```

## 2. Update `get_collection`

- At the start of the function, call `client = _chromadb_client()` and `if client is None: return None`.
- Use `client` (not `get_client()`) and move `coll_name = _collection_name_for_model(model_name)` after the None check.
- In the `except` block, `return None` instead of `raise`.

## 3. Update `add`

- Call `coll = get_collection(model_name=model_name)` then `if coll is None: return False` before calling `coll.add(...)`.
- Keep the existing try/except for add; only log on real exceptions.

## 4. Update `query`

- Call `coll = get_collection()` then `if coll is None: return {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}` before querying.

## 5. Update `count`

- Call `coll = get_collection()` then `if coll is None: return 0` before `coll.count()`.

---

After applying: when chromadb is missing, you get one INFO log at first use and no repeated "Finance vector store add failed" messages. To enable the vector store, ensure the API runs in an environment where `uv sync` (or `pip install chromadb`) has been run—chromadb is already in `pyproject.toml`.
