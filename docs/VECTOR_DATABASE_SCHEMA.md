# Vector Database Schema — Versioned Facts and Entity Relationships

Design for a vector-backed schema that supports **temporal evolution** and **entity relationships** in the news intelligence system. Complements the [RAG Enhancement Roadmap](RAG_ENHANCEMENT_ROADMAP.md) and [RAG System Deep Dive](RAG_SYSTEM_DEEP_DIVE_AND_IMPROVEMENTS.md).

---

## Current stack alignment

| Aspect | In this project |
|--------|------------------|
| **Primary DB** | PostgreSQL (Widow); single source in `api/shared/database/connection.py` |
| **Vector extension** | pgvector (migration `134_pgvector_event_embeddings.sql`): `vector(768)`, cosine, HNSW |
| **Embedding model** | nomic-embed-text (768d) for events/articles; RAG also uses SentenceTransformer `all-MiniLM-L6-v2` (384d) in some paths — **standardise on 768d** for new entity/fact/story collections to match migration 134 |
| **Domains** | `politics`, `finance`, `science_tech` (snake_case) |
| **Optional** | ChromaDB (or similar) for dedicated RAG collections if you want separate stores from PostgreSQL |

New entity/fact/relationship/story-state collections should use **768-dimensional** embeddings and **cosine** similarity for consistency with existing event/article embeddings.

---

## 1. Core collections structure

### 1.1 Entity profiles

```python
# Collection: entity_profiles
{
    "collection_name": "entity_profiles",
    "schema": {
        "id": "entity_{uuid}",
        "canonical_name": "Donald Trump",
        "entity_type": "PERSON",  # PERSON, ORGANIZATION, EVENT, PLACE
        "domain": "politics",     # politics, finance, science_tech

        # Vector representation of the entity (768d)
        "embedding": [0.123, -0.456, ...],

        "metadata": {
            "created_at": "2024-01-01T00:00:00Z",
            "last_updated": "2024-03-15T12:00:00Z",
            "version": 42,
            "confidence_score": 0.95,
            "enrichment_count": 15,
            "primary_domain": "politics",
            "cross_domain_relevance": ["finance", "science_tech"],
            "aliases": ["Trump", "Donald J. Trump", "President Trump"],
            "active": true
        }
    },
    "vector_config": {
        "dimension": 768,
        "metric": "cosine",
        "index_type": "hnsw",
        "hnsw_config": {"m": 16, "ef_construction": 200}
    }
}
```

### 1.2 Versioned facts

```python
# Collection: versioned_facts
{
    "collection_name": "versioned_facts",
    "schema": {
        "id": "fact_{uuid}_v{version}",
        "entity_id": "entity_123",
        "fact_type": "POSITION",  # POSITION, STATEMENT, ACTION, RELATIONSHIP
        "fact_text": "Donald Trump served as 45th President of the United States",

        "embedding": [0.234, -0.567, ...],  # 768d

        "metadata": {
            "version": 1,
            "valid_from": "2017-01-20T00:00:00Z",
            "valid_to": "2021-01-20T00:00:00Z",  # null if current
            "confidence": 1.0,
            "sources": [
                {
                    "source_id": "article_789",
                    "source_type": "news_article",
                    "published_at": "2017-01-20T12:00:00Z",
                    "credibility_score": 0.95
                }
            ],
            "superseded_by": "fact_124_v2",
            "extraction_method": "llm_extraction",
            "verification_status": "verified",
            "domain_relevance": {"politics": 1.0, "finance": 0.3}
        }
    }
}
```

### 1.3 Entity relationships

```python
# Collection: entity_relationships
{
    "collection_name": "entity_relationships",
    "schema": {
        "id": "rel_{uuid}_v{version}",
        "source_entity_id": "entity_123",
        "target_entity_id": "entity_456",
        "relationship_type": "APPOINTED",
        "relationship_description": "Donald Trump appointed Jerome Powell as Fed Chair",

        "embedding": [0.345, -0.678, ...],  # 768d

        "metadata": {
            "version": 1,
            "valid_from": "2017-11-02T00:00:00Z",
            "valid_to": null,
            "confidence": 0.95,
            "bidirectional": false,
            "strength": 0.8,
            "domains": ["politics", "finance"],
            "temporal_context": {
                "is_current": true,
                "duration_days": 2500,
                "recency_score": 0.7
            },
            "supporting_facts": ["fact_789_v1", "fact_790_v1"]
        }
    }
}
```

### 1.4 Story states

```python
# Collection: story_states
{
    "collection_name": "story_states",
    "schema": {
        "id": "story_state_{story_id}_v{version}",
        "story_id": "story_001",
        "state_summary": "Trump presidency enters second year with tax reform focus",

        "embedding": [0.456, -0.789, ...],  # 768d

        "metadata": {
            "version": 15,
            "timestamp": "2018-01-20T00:00:00Z",
            "maturity_score": 0.75,
            "key_entities": ["entity_123", "entity_456"],
            "key_facts": ["fact_100_v1", "fact_101_v1"],
            "active_relationships": ["rel_200_v1", "rel_201_v1"],
            "knowledge_gaps": [
                "Cabinet appointment outcomes",
                "Legislative agenda progress"
            ],
            "watch_patterns_matched": ["cabinet_change", "policy_announcement"],
            "significant_change": true,
            "change_summary": "Major cabinet reshuffling announced"
        }
    }
}
```

---

## 2. Hybrid search (ChromaDB-style)

If using ChromaDB (or similar) for dedicated RAG collections:

```python
# Conceptual — for ChromaDB or equivalent
class EnhancedRAGVectorStore:
    def __init__(self):
        self.client = chromadb.PersistentClient(path="./data/enhanced_rag")

        self.collections = {
            "entities": self._create_entity_collection(),
            "facts": self._create_fact_collection(),
            "relationships": self._create_relationship_collection(),
            "story_states": self._create_story_state_collection(),
            "temporal_facts": self._create_temporal_fact_collection(),
        }

    def _create_entity_collection(self):
        return self.client.create_collection(
            name="entity_profiles",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.embedding_function,  # 768d
        )
```

Use **one** embedding model (e.g. nomic-embed-text) for all these collections so dimensions and similarity behaviour are consistent.

---

## 3. Versioning strategy

```python
class VersionedFactManager:
    def add_fact_version(
        self,
        entity_id: str,
        fact: dict,
        previous_version_id: str | None = None,
    ) -> None:
        """Add a new version of a fact, maintaining history."""
        version = self.get_next_version(entity_id, fact["fact_type"])

        if previous_version_id:
            self.update_metadata(
                collection="versioned_facts",
                id=previous_version_id,
                metadata_update={
                    "valid_to": datetime.utcnow().isoformat(),
                    "superseded_by": f"fact_{entity_id}_v{version}",
                },
            )

        fact_doc = {
            "id": f"fact_{entity_id}_v{version}",
            "entity_id": entity_id,
            "version": version,
            "valid_from": datetime.utcnow().isoformat(),
            "valid_to": None,
            **fact,
        }
        embedding = self.generate_fact_embedding(fact)
        self.collections["facts"].add(
            ids=[fact_doc["id"]],
            embeddings=[embedding],
            metadatas=[fact_doc["metadata"]],
            documents=[fact["fact_text"]],
        )
```

---

## 4. Relationship indexing (PostgreSQL)

For graph-style traversal and temporal queries, keep a relational table in PostgreSQL and point to the vector store by id:

```sql
-- Optional: PostgreSQL table for relationship graph (indexes created separately)
CREATE TABLE IF NOT EXISTS entity_relationship_graph (
    id SERIAL PRIMARY KEY,
    source_entity_id VARCHAR(100),
    target_entity_id VARCHAR(100),
    relationship_type VARCHAR(50),
    vector_store_id VARCHAR(100),
    valid_from TIMESTAMP,
    valid_to TIMESTAMP,
    is_current BOOLEAN DEFAULT true
);

CREATE INDEX IF NOT EXISTS idx_rel_source_current
ON entity_relationship_graph (source_entity_id, is_current);
CREATE INDEX IF NOT EXISTS idx_rel_target_current
ON entity_relationship_graph (target_entity_id, is_current);
CREATE INDEX IF NOT EXISTS idx_rel_temporal
ON entity_relationship_graph (valid_from, valid_to);

-- Materialized view for current relationship network
CREATE MATERIALIZED VIEW IF NOT EXISTS current_entity_network AS
SELECT source_entity_id, target_entity_id, relationship_type, vector_store_id
FROM entity_relationship_graph
WHERE is_current = true;
```

---

## 5. Temporal query support

```python
class TemporalVectorQuery:
    def get_facts_at_time(self, entity_id: str, timestamp: datetime):
        """Facts valid at a specific point in time."""
        results = self.collections["facts"].query(
            query_embeddings=None,
            where={
                "$and": [
                    {"entity_id": entity_id},
                    {"valid_from": {"$lte": timestamp.isoformat()}},
                    {
                        "$or": [
                            {"valid_to": {"$gte": timestamp.isoformat()}},
                            {"valid_to": None},
                        ]
                    },
                ]
            },
            n_results=100,
        )
        return results

    def get_relationship_evolution(self, entity1: str, entity2: str):
        """Track how a relationship changed over time."""
        results = self.collections["relationships"].query(
            where={
                "$and": [
                    {"source_entity_id": entity1},
                    {"target_entity_id": entity2},
                ]
            },
            n_results=1000,
        )
        return sorted(results["metadatas"], key=lambda x: x["version"])
```

---

## 6. PGVector (PostgreSQL-native) option

If you keep everything in PostgreSQL with pgvector (no ChromaDB), add tables and a temporal search function:

```sql
-- Example: entity embeddings table (new migration)
CREATE TABLE IF NOT EXISTS entity_embeddings (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(100) UNIQUE,
    embedding vector(768),
    metadata JSONB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_entity_embeddings_entity_id ON entity_embeddings (entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_embeddings_metadata_gin ON entity_embeddings USING gin (metadata jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_entity_embeddings_hnsw ON entity_embeddings
USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- Temporal similarity search for versioned_facts (if stored in PG)
CREATE OR REPLACE FUNCTION search_facts_temporal(
    query_embedding vector(768),
    at_timestamp TIMESTAMP,
    limit_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    fact_id VARCHAR,
    similarity FLOAT,
    fact_text TEXT,
    valid_from TIMESTAMP,
    valid_to TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        f.id::VARCHAR,
        (1 - (f.embedding <=> query_embedding))::FLOAT AS similarity,
        f.fact_text,
        f.valid_from,
        f.valid_to
    FROM versioned_facts f
    WHERE
        f.valid_from <= at_timestamp
        AND (f.valid_to IS NULL OR f.valid_to >= at_timestamp)
    ORDER BY f.embedding <=> query_embedding
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;
```

---

## 7. Story-specific index hints

For recurring use cases (e.g. Trump presidency, 2026 elections, gold/China):

```python
story_indexes = {
    "trump_presidency": {
        "primary_entity": "entity_trump_001",
        "time_bounds": ["2017-01-20", "2021-01-20"],
        "key_relationships": ["president_of", "appointed", "signed"],
        "watch_entities": ["entity_cabinet_*", "entity_congress_*"],
    },
    "2026_elections": {
        "event_type": "election",
        "geographic_scope": "usa",
        "watch_patterns": ["candidate_announcement", "poll_result", "debate"],
        "entity_roles": {
            "candidates": [],
            "parties": ["entity_gop", "entity_dem"],
            "states": ["entity_state_*"],
        },
    },
    "gold_standard_china": {
        "trigger_entities": ["entity_china", "entity_pboc"],
        "watch_facts": ["monetary_policy", "gold_reserve", "currency_decision"],
        "impact_entities": ["entity_gold", "entity_usd", "entity_markets"],
        "correlation_window": "7d",
    },
}
```

---

## 8. Performance optimizations (optional)

- **Hot/warm/cold**: Separate collections or partitions by recency (e.g. hot_facts_90d, warm_facts_1y, cold_facts_archive) and move documents on a schedule.
- **Smaller index for current state**: Use 384d embeddings only for a dedicated “entity current state” index if you need faster lookups and can afford a second embedding path.
- **Relationship cache**: In-memory or Redis cache for current_entity_network with TTL (e.g. 1h) to avoid repeated graph queries.

---

## 9. What this schema provides

| Need | How |
|------|-----|
| **Temporal versioning** | `valid_from` / `valid_to`, `version`, `superseded_by` on facts and relationships |
| **Relationship mapping** | Vector space (semantic) plus PostgreSQL graph table for traversal |
| **Point-in-time queries** | Filter by timestamp so only facts/relationships valid at that time are returned |
| **Scalability** | Separate collections by type; optional partitioning by time or recency |
| **Hybrid search** | Vector similarity + metadata filters (domain, entity_id, valid_from/to) |

Implement in phases: start with **entity_profiles** and **versioned_facts** (and one store: pgvector or ChromaDB), then add **entity_relationships** and **story_states** as the [RAG Enhancement Roadmap](RAG_ENHANCEMENT_ROADMAP.md) phases roll out.
