# RAG System: Current Implementation, Rationale, and Improvement Directions

This document describes the News Intelligence RAG (Retrieval-Augmented Generation) system in detail, why it was built this way, and concrete ways to improve **story-detail identification** and **continual pull of relevant details and historical context**.

---

## 1. Current Architecture Overview

RAG in this project is **not** a single pipeline. It is used in several places with different backends and goals:

| Use case | Location | What it does |
|----------|----------|--------------|
| **Intelligence Hub RAG queries** | `services/rag/` + `domains/intelligence_hub/routes/rag_queries.py` | User asks a question; system retrieves domain articles + domain knowledge, builds a prompt, LLM answers. Returns answer + citations. |
| **Storyline context enhancement** | `services/rag/base.py` | For a storyline, extract entities/topics from articles → fetch Wikipedia + GDELT context → save to `storyline_rag_context`. |
| **Storyline automation (discovery)** | `services/storyline_automation_service.py` | Find new articles for a storyline: **entity-first** (DB search on storyline entities) then **RAG fallback** (hybrid/semantic retrieval via `RAGService.retrieval`). |
| **Storyline RAG analysis** | `domains/storyline_management/services/rag_analysis_service.py` | Build context from storyline + articles, optionally related storylines; LLM generates “comprehensive” analysis. |
| **Finance evidence** | `domains/finance/` (ChromaDB + `embedding.py`) | EDGAR and other finance docs chunked, embedded with BGE, stored in ChromaDB; used for evidence retrieval in analysis (separate from the main RAG service). |

So “the” RAG system is really **several subsystems** that share some building blocks (embeddings, domain knowledge, LLM) but differ in data source, schema, and how they identify “what to look up.”

---

## 2. Current Implementation in Detail

### 2.1 Core RAG service (`api/services/rag/`)

- **Base (`base.py`)**
  - **Wikipedia**: For a list of topics/entities, calls Wikipedia REST API (`/page/summary/{term}`), caches via `smart_cache_service`.
  - **GDELT**: For same terms, calls GDELT doc API with date range (e.g. last 30 days), caches.
  - **Entity/topic extraction**: From storyline articles, uses **regex and keyword lists** (e.g. capitalized phrases, quoted strings, fixed topic list like “AI”, “blockchain”, “regulation”). No NER or embedding-based extraction here.
  - **Storyline context**: Combines Wikipedia + GDELT + extracted entities/topics, saves to `storyline_rag_context` (if that table exists in the schema in use).

- **Domain module (`domain.py`)**
  - **Article retrieval**: Runs in **per-domain schema** (`politics`, `finance`, `science_tech`). Selects articles from `{schema}.articles` with `published_at >= NOW() - interval`, optional `embedding_vector`. If `query_embedding` and article `embedding_vector` exist, relevance = **cosine similarity**; else **keyword overlap** (query words vs title/content/summary).
  - **Domain knowledge**: Uses `DomainKnowledgeService` (in-memory knowledge bases per domain: entities, terminology, historical context templates). Enriches RAG context with “who/what” and definitions; used in Intelligence Hub RAG and topic context.

- **Generation module (`generation.py`)**
  - **Embeddings**: Via **Ollama** `POST /api/embeddings` with `RAG_EMBEDDING_MODEL` (default `nomic-embed-text`). Cached in memory by hash of text.
  - **LLM**: Ollama `POST /api/generate` with `RAG_LLM_MODEL` (e.g. `llama3.1:8b`). Builds a single prompt from domain context + article chunks + terminology + question; no multi-step or iterative retrieval.
  - **Prompt**: Structured sections (domain context, relevant articles, entities, terms, question, instructions). Confidence is heuristic (length, presence of “[Source” or “according to”).

- **Retrieval module (`retrieval.py`)**
  - **Optional sentence-transformers**: If available, uses `all-MiniLM-L6-v2` for **local** embeddings (used only inside this module for semantic/hybrid search).
  - **Flow**: Query expansion (simple synonym map + plural/singular) → **keyword** (SQL `LIKE` on title/content/excerpt) and/or **semantic** (encode query + candidates, cosine similarity) → **hybrid** merge (weighted combination) → **re-rank** (relevance + quality + recency + title match + credibility).
  - **Important**: Keyword search runs against a single `articles` table with **no explicit schema** (relies on connection `search_path`). So when used from storyline automation, it may not be domain-scoped unless the caller sets schema.

### 2.2 Storyline automation discovery

- **Entity-first**: Builds a list of “storyline entities” from:
  - `story_entity_index` (if present) for the storyline
  - `key_entities` JSONB on the storyline
  - `search_entities`, `search_keywords`
  - Title words (capitalized / all-caps)
- **DB search**: Articles where title/content/summary **ILIKE** any of those entities, within `date_range_days`, excluding already-linked articles. Ranked by entity matches (title weighted) and recency.
- **RAG fallback**: Only if entity search returns fewer than half of `max_results`. Calls `RAGService().retrieval.retrieve_relevant_articles(query, ...)` with a query built from title + keywords + entities + description snippet. No schema is passed into retrieval, so this is effectively **single-schema** (e.g. public or default).

### 2.3 Storyline RAG analysis

- Fetches storyline + articles from the **domain schema**.
- Builds text context (title, description, article titles/sources/summaries).
- **Historical context**: Optional related storylines via **keyword overlap** on title/description (LIKE on a few title words).
- Sends one big prompt to `llm_service.generate_storyline_analysis`; no retrieval over a larger corpus or external APIs.

### 2.4 Finance evidence (ChromaDB)

- **Separate from** the main RAG service: uses `domains/finance/embedding.py` (BGE-large-en-v1.5 when available), chunks EDGAR (and similar) text with overlap, stores in **ChromaDB**.
- Evidence collector and analysis use this for “find supporting chunks” for finance analysis. So “RAG” in finance = vector search over pre-chunked documents + LLM over selected chunks.

### 2.5 Where embeddings live

- **Domain articles**: Some code paths expect `embedding_vector` (or `embedding` in pgvector migrations) on `articles`. Migration 134 adds pgvector `embedding vector(768)`. Populating these is done in places like `ai_storyline_discovery` and possibly ML pipeline; **not all article flows** necessarily write embeddings.
- **Intelligence Hub / domain RAG**: Domain module uses `embedding_vector` from `{schema}.articles` when present for similarity; otherwise keyword only.
- **Retrieval module**: Uses its own sentence-transformers model to **encode on the fly** for candidate articles (from keyword search); it does **not** use stored article embeddings. So we have two embedding paths: stored (domain) vs on-the-fly (retrieval).

---

## 3. Why This Design?

Reasonable inferences from the code and structure:

1. **Local-first and control**  
   Ollama for embeddings and LLM keeps everything on your hardware; no external API keys for RAG inference. Sentence-transformers in retrieval give a fallback when Ollama isn’t used for that path.

2. **Domain silos**  
   Politics, finance, science-tech are separated at the DB and API level. Domain RAG (domain.py) is schema-aware so that Intelligence Hub and topic/timeline features stay per-domain. Entity-first discovery fits “story = set of entities + events.”

3. **Reuse of existing structure**  
   Storylines already have titles, descriptions, analysis_summary, and (where present) key_entities and story_entity_index. Using those for “what to look up” avoids building a separate “story representation” from scratch.

4. **Wikipedia + GDELT as external context**  
   They provide (a) definitions and background (Wikipedia) and (b) recent events and media (GDELT) without maintaining your own knowledge graph. Caching and rate limiting keep external calls bounded.

5. **Hybrid and re-ranking**  
   Keyword + semantic and then multi-signal re-rank (relevance, quality, recency, credibility) improve over pure keyword or pure semantic, especially when article embeddings are missing or sparse.

6. **Finance treated differently**  
   EDGAR and evidence need chunk-level retrieval and provenance; ChromaDB + BGE is a better fit than overloading the article-centric RAG with another schema.

What we **didn’t** do (and where improvements live):

- No **single “story embedding” or “story expansion”** that drives both what we look up and what we pull in.
- No **continual background process** that, for each active storyline, periodically decides “what new entities/facts to look up” and “what new data to pull in.”
- Limited **historical and narrative structure**: related storylines are simple keyword overlap; no timeline of “story states” or “story facets” used to target retrieval.
- **Entity/topic extraction** in base RAG is regex/keyword; we don’t use NER or embedding-based clustering there to identify story details.

---

## 4. Improvement 1: Better Identification of “What to Look Up” (Story Details)

Today we identify “what to look up” from: title, description, analysis_summary, key_entities, search_entities, search_keywords, and (if present) story_entity_index. Extraction in base RAG is shallow (regex + fixed topic list). Improvements:

### 4.1 Structured “story facets” and lookup targets

- **Represent a storyline as facets**: e.g. entities (people, orgs, places), events, time range, themes, questions (e.g. “What did X say about Y?”).
- **Persist lookup targets**: e.g. `storyline_lookup_targets` table: `storyline_id`, `target_type` (entity | event | theme | question), `value`, `source` (title | analysis | user | extraction), `last_looked_up_at`, `priority`.
- **Refresh targets** when the storyline changes (new articles, new analysis, or user edits). Use **LLM (or NER)** to extract entities and “open questions” from the latest summary and new articles, and merge into `storyline_lookup_targets` with priorities (e.g. core entities higher than tangential).

This gives a single place that drives both “what we search for” and “what we fetch from external sources.”

### 4.2 Stronger entity and theme extraction

- **Replace or augment** regex entity extraction in `base.py` with:
  - **NER**: Use your existing entity extraction pipeline (or a small Ollama/sentence-transformers NER) to get persons, orgs, locations, and (if supported) events from storyline articles and analysis.
  - **Embedding-based themes**: Cluster article snippets (or summary sentences) with your existing embedding model; take cluster centroids or labels as “themes” and add them as lookup targets (e.g. for Wikipedia/GDELT or for internal search).
- **Deduplicate and normalize**: Map extracted strings to canonical entities (e.g. “White House” / “administration” → one entity). Reuse or extend `DomainKnowledgeService` so that “what to look up” uses the same canonical list that enriches RAG context.

### 4.3 “Open questions” and missing pieces

- From analysis_summary or from the last N articles, use the **LLM** to generate a short list of “open questions” or “missing pieces” (e.g. “What is the current status of X?”, “What has Y said about Z?”).
- Store these as lookup targets with type `question` and use them to:
  - **Drive retrieval**: e.g. turn each question into a query for domain RAG or for entity-first search.
  - **Drive external pull**: e.g. GDELT or future APIs keyed by entity + time window.

### 4.4 Domain knowledge and entity service as source of truth

- **Expand** `DomainKnowledgeService` (or a separate “storyline entity index”) so that for each storyline we maintain:
  - Canonical entities and their roles (e.g. “main actor”, “organization”, “location”).
  - Which of those we have “enough” context for vs which we should look up again (e.g. “last_looked_up_at” or “coverage” score).
- Use this to **prioritize** what to look up in Wikipedia/GDELT and what to request from internal retrieval (e.g. “find more about entity X in the last 7 days”).

---

## 5. Improvement 2: Continually Pulling in More Relevant Details and Historical Context

Today, “pull” is mostly **on-demand**: user runs RAG query, or triggers storyline discovery, or requests analysis. There is no background loop that, per storyline, “refreshes context” and “pulls new data.” Improvements:

### 5.1 Scheduled “storyline context refresh”

- **Background job** (e.g. from OrchestratorCoordinator or a dedicated scheduler) that, on a schedule (e.g. daily or when automation runs):
  - For each **active** (or watched) storyline, load its **lookup targets** (entities, themes, questions).
  - For each target:
    - **Internal**: Run domain-scoped article retrieval (entity-first + optional RAG) for the last N days; attach only **new** articles (or new snippets) to the storyline’s “context cache” or suggest them to the suggestion queue.
    - **External**: Call Wikipedia (and GDELT if available) for entities/events; **store** results in a dedicated table (e.g. `storyline_external_context`: storyline_id, source, term, content, fetched_at) so that the next RAG or analysis run doesn’t re-fetch the same thing.
  - Optionally **re-run** a lightweight “context summary” (e.g. one LLM call that summarizes new context) and store it for the storyline so the main RAG/analysis can use “latest context” without re-retrieving every time.

### 5.2 Historical context layer

- **Structured history** per storyline:
  - **Timeline of “story states”**: e.g. “As of date D, the story was about X, key entities were E1,E2, key fact was F.” This can be generated periodically from analysis_summary + new articles and stored in a `storyline_timeline` or `storyline_states` table.
  - **Use in retrieval**: When building the RAG prompt or when deciding “what to look up,” include “last known state” and “what happened since” so the model and retrieval can focus on **delta** and **recency**.
- **Related storylines** beyond keyword overlap:
  - Use **embeddings** of storyline title + summary (and maybe key entities) to find similar storylines; or use a small graph of “related” (e.g. shared entities, or editor-defined links). Then pull **their** summaries or key events as “historical context” for the current storyline.

### 5.3 External data pull and caching

- **Wikipedia**: Already cached. Add **refresh policy** (e.g. re-fetch if older than 7 days) and **coverage**: for each storyline, record which entities we already have Wikipedia context for, so the refresh job only requests missing or stale ones.
- **GDELT**: Same idea: cache keyed by (entity/theme, time window). Background job fills in missing windows (e.g. “last 7 days” for each high-priority entity) and stores in `storyline_external_context` or a generic “external_events” table.
- **Future sources**: Any new “pull” (e.g. press releases, official statements) can follow the same pattern: **lookup targets** drive what we request; **results** are stored with storyline_id and source so RAG and analysis can reuse them.

### 5.4 Domain-scoped and embedding-consistent retrieval

- **Retrieval module**: Today its keyword (and thus hybrid) path uses a single `articles` table. Change it to accept a **domain/schema** (or connection with the right `search_path`) so that storyline automation’s RAG fallback is **domain-scoped** (e.g. only politics articles for a politics storyline).
- **Article embeddings**: Ensure at least one pipeline (e.g. after article processing or ML) **writes** `embedding_vector` (or pgvector `embedding`) for domain articles, using the **same** model that the domain RAG (or retrieval) uses for the query. That way “continual pull” can use fast vector search (e.g. pgvector HNSW) instead of only keyword or on-the-fly encoding.

### 5.5 Orchestrator-driven “what to do next”

- **ProcessingGovernor / coordinator**: Extend so that, besides “run RSS” or “run topic clustering,” it can suggest “refresh storyline context for storyline_id=42” or “pull external context for entity X.” Priorities can come from watchlist, recency of last refresh, and “coverage” of lookup targets.
- **Event bus**: When new articles are linked to a storyline, emit an event so that a listener can:
  - Update **lookup targets** (new entities from the article).
  - Trigger a **lightweight context refresh** (e.g. one retrieval + one small LLM summary) and attach it to the storyline.

---

## 6. Summary Table: Current vs Improved

| Aspect | Current | Improved direction |
|--------|--------|--------------------|
| **What we look up** | Title, keywords, entities from key_entities/search_entities/story_entity_index; base RAG uses regex + fixed topic list | Structured “story facets” and lookup targets; NER/embedding-based extraction; “open questions”; domain entity service as source of truth |
| **Where we pull from** | On-demand: domain articles, Wikipedia, GDELT; finance ChromaDB for evidence | Same sources, but **scheduled** refresh per storyline; external results **stored** (storyline_external_context) and reused |
| **Historical context** | Optional related storylines by keyword overlap; no timeline of “story states” | Timeline of story states; related storylines by embedding or graph; “delta since last state” in prompts |
| **Continual pull** | Only when user or automation runs discovery/analysis | Background “storyline context refresh” driven by lookup targets and governor; event-driven updates when new articles are added |
| **Retrieval scope** | Domain module is schema-aware; retrieval module is not (single articles table) | Make retrieval domain-aware; ensure article embeddings are populated and used consistently |

---

## 7. Suggested Implementation Order

1. **Domain-scoped retrieval** and **article embeddings**  
   So that RAG and discovery use the right data and vector search where available.

2. **Structured lookup targets** and **periodic refresh**  
   One table and one job that “for each active storyline, refresh lookup targets from analysis + new articles, then pull internal + external context and store it.”

3. **Stronger extraction**  
   NER or LLM-based entity/theme/question extraction feeding into lookup targets.

4. **Historical layer**  
   Story states and related-storyline context so that “continual pull” and RAG prompts can use “what we knew then” and “what’s new.”

5. **Orchestrator integration**  
   Governor and events so that “refresh storyline context” and “pull external context” are first-class, scheduled or event-driven actions.

This keeps the current design (local LLM, domain silos, Wikipedia/GDELT, hybrid retrieval) while making **what we identify** and **how we keep pulling** more systematic and automatic.
