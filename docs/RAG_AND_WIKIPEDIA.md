# RAG retrieval and Wikipedia in News Intelligence

This is how the **application** (not MemPalace) pulls external context. MemPalace holds **operator/process** memory mined into drawers; RAG+Wikipedia runs inside the API services.

## Wikipedia

- **Service:** `api/services/rag/base.py` — **`(BaseRAGService`)**.
- **API:** Wikipedia **REST v1** at `https://en.wikipedia.org/api/rest_v1` (e.g. **`/page/summary/{title}`** with URL-encoded titles).
- **Flow:** Storyline enhancement **`enhance_storyline_context`** loads entities from **`article_entities`** / **`entity_canonical`** (includes **`wikipedia_page_id`** → **`wikipedia_url`**), falls back to extracted names from articles, derives **topics**, then **`_get_wikipedia_context`** fetches summaries. Results are merged with **GDELT** context and **saved** against the storyline (see **`_save_rag_context`** in the same module).
- **Caching:** Uses **`smart_cache_service`** when available (cache key namespace **`wikipedia`** per search term).
- **Local Kiwix mirror (Phase 2):** Set **`KIWIX_WIKIPEDIA_REST_URL`** to a Kiwix ZIM HTTP endpoint on Widow (e.g. `http://<WIDOW_HOST_IP>:8080/wikipedia_en_all_nopic/A`). Set **`KIWIX_ZIM_VINTAGE_DATE`** (ISO date of the ZIM dump) for citation vintage in the Citation Drawer. When unset, the service falls back to live Wikipedia REST v1.
- **Embeddings:** The **`embeddings_worker`** phase chunks Wikipedia summaries for reference-event titles into **`intelligence.embedding_chunks`** (`source_type='wikipedia'`) when pgvector is installed.
- **Related:** **`historical_context_service.py`** references a **`wikipedia_timeline`** module descriptor; entity seeds may use **Wikidata** via **`docs/EXTERNAL_ENTITY_SEEDS.md`** scripts (separate from REST summary RAG).

## “RAG” in this codebase

- **Not** a single Open WebUI-style vector chat file. It is **storyline-scoped enrichment**: Wikipedia + GDELT + extracted entities/topics, persisted for downstream narrative and monitoring flows.
- **Finance / evidence:** Routes can request optional RAG in evidence bundles (see e.g. **`api/domains/finance/routes/finance.py`** `include_rag` / `deep` analysis).
- **Embeddings / clustering:** Article and storyline embeddings live in **Postgres**-backed flows (e.g. consolidation service, topic clustering) — see **AGENTS.md** and **`docs/RESOURCE_BUDGETS_AND_LEAN_PIPELINE.md`**.

## MemPalace’s role

Use MemPalace to recall **how the team runs the pipeline** and **handoff notes**, not to replace Wikipedia HTTP calls.

- **Wing:** `News Intelligence` (see **AGENTS.md**).
- **Search:** MCP tool **`mempalace_search`** with `query` about RAG/Wikipedia and optional **`wing`**: `News Intelligence`.
