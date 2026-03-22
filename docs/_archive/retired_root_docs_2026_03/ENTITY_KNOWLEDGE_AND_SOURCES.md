# Entity knowledge and external sources

How the system connects entity names to descriptions and links (Wikipedia, Knowledge Graph, optional vector DB and other sources), and when to add more.

---

## High-level method: entity knowledge connector

Use **one entry point** for “resolve this entity name to a description and link” so callers don’t touch Wikipedia/KG (or future sources) directly.

- **Module:** `api/services/entity_knowledge_connector.py`
- **Single resolution:** `resolve_entity_knowledge(name, entity_type=None, sources=(...))`
- **Batch:** `resolve_entity_knowledge_batch(names, sources=(...))`

Returns a common shape: `description`, `url`, `title`, `source` (`"wikipedia"` | `"knowledge_graph"`), and when from Wikipedia, `wikipedia_page_id`. Tries each requested source in order and returns the first usable result.

**Current sources (in order):**

1. **Wikipedia** — Local `intelligence.wikipedia_knowledge` (exact → alias → prefix → full-text), then Wikipedia API search. No key required. Improves with local dump + `scripts/populate_wikipedia_aliases.py`.
2. **Knowledge Graph** — Google Knowledge Graph API. Set `KG_API_KEY` or `GOOGLE_KNOWLEDGE_GRAPH_API_KEY` to enable. Gives short, structured descriptions and is a good fallback when Wikipedia has no article.

**Who uses it:** Entity enrichment (`entity_enrichment_service`) uses the connector with `sources=("wikipedia", "knowledge_graph")`. Backfill and dossier code can call it too for a single place to add or reorder sources.

---

## Do you need a vector database?

**Current behaviour:** Entity–knowledge resolution is **key/alias/full-text**, not vector similarity. We match by:

- Exact and prefix title in local Wikipedia
- Alias arrays (e.g. redirects)
- Full-text search on title + abstract

So **you do not need a vector DB** for basic “entity name → description” resolution. Existing Postgres FTS and the connector are enough for that.

**When a vector DB (or pgvector) helps:**

- **Semantic matching** — e.g. “Fed” → “Federal Reserve”, or nicknames/phrases that don’t appear as titles or aliases. You’d embed entity names and/or descriptions and do nearest-neighbour search.
- **Very large alias sets** — If you have hundreds of thousands of entities and want “find similar entity” or “disambiguate among many candidates”, vector similarity over an entity index can help.
- **Cross-lingual or fuzzy names** — Embeddings can improve matching across spelling variants and languages.

**What we already use vectors for:** pgvector is used for **events** (`chronological_events.embedding`) and **articles** (embedding columns) for dedup and storyline discovery. **ChromaDB** is used in the finance domain for EDGAR evidence. None of these are used for entity–knowledge resolution today. Adding an **entity description vector index** (e.g. pgvector table over `entity_canonical` + descriptions, or a small Chroma collection of entity names + descriptions) is optional and only needed when you need semantic or “similar entity” behaviour above.

---

## Other data sources (beyond Wikipedia and Knowledge Graph)

| Source | Role | Notes |
|--------|------|--------|
| **Wikipedia** | Primary: descriptions, redirects, FTS | Local dump + aliases script recommended. |
| **Knowledge Graph** | Fallback: short descriptions, types | Requires API key; already in connector. |
| **Wikidata** | Structured facts, types, disambiguation | Free API; good for “is this a person/org?” and IDs. Can be added as another source in the connector. |
| **DBpedia** | Structured extract from Wikipedia | Alternative to raw Wikipedia for triples/types. |
| **Your own content** | Entity profiles, versioned_facts | Already in `intelligence.entity_profiles`; enrichment writes back here. |

To add a new source (e.g. Wikidata): implement a `_resolve_wikidata(name)` in `entity_knowledge_connector.py` that returns the same shape as `_resolve_wikipedia` / `_resolve_knowledge_graph`, then add `"wikidata"` to the `sources` tuple in `resolve_entity_knowledge` (or make it configurable). No need for a new vector DB unless you want semantic or similarity search as above.

---

## Summary

- **High-level method:** Use `resolve_entity_knowledge` / `resolve_entity_knowledge_batch` from `entity_knowledge_connector` for all entity–knowledge resolution.
- **Vector DB:** Not required for basic resolution; consider it only for semantic/fuzzy matching or large-scale “similar entity” use cases.
- **Other sources:** Wikipedia + Knowledge Graph are wired in; add Wikidata or DBpedia in the connector when you want more coverage or structure.
