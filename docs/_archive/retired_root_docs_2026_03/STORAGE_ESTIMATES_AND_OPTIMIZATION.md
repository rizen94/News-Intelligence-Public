# Storage Estimates and Optimization — Vector & Versioned Facts

Planning for growth of the intelligence layer: versioned facts, entity profiles, relationships, story states, and (future) vector embeddings. With proper optimization, **100–200 GB/year** for a medium-scale deployment is realistic rather than unbounded growth.

**Related:** [VECTOR_DATABASE_SCHEMA.md](VECTOR_DATABASE_SCHEMA.md), [RAG_ENHANCEMENT_ROADMAP.md](RAG_ENHANCEMENT_ROADMAP.md).

---

## 1. Core storage components

| Component | Base size (bytes) | Notes |
|-----------|-------------------|--------|
| Vector 768d (float32) | 3,072 | Per-fact or per-entity embedding |
| Vector 384d (float32) | 1,536 | Reduced dimension option |
| UUID / long id | 36 / 8 | References |
| Timestamp | 8 | valid_from, valid_to, created_at |
| Metadata (JSONB) | ~500 | sources, extraction_method, etc. |
| Fact text (avg) | ~200 | fact_text |

**Per versioned fact (with embedding):** ~4 KB (vector + text + metadata + indexes).  
**Per entity profile (with embedding):** ~5.5 KB (vector + profile data + relationship links).

---

## 2. Volume projections (example)

Assumptions for a production news-intelligence workload:

- **New articles processed:** ~10,000/day  
- **Facts per article:** ~5; **unique-fact ratio:** ~30% → ~15,000 new facts/day  
- **Entities per article:** ~3; **new-entity ratio:** ~5% → ~1,500 new entities/day  

Rough daily storage (before compression/dedup):

- Facts: ~60 MB/day  
- Entities: ~8 MB/day  
- Relationships (e.g. 30% of facts): ~9 MB/day  
- Story states (e.g. 100 stories × 10 KB): ~1 MB/day  
- **Total:** ~78 MB/day → **~28 GB/year** raw; with versioning and indexes, **~100–200 GB/year** is a reasonable target for planning.

---

## 3. Actual storage analysis (our schema)

Use this against the live DB to see current usage. Tables live in the `intelligence` schema.

```sql
-- Run against your DB (intelligence schema)
WITH storage_analysis AS (
    SELECT
        'intelligence.versioned_facts' AS table_name,
        COUNT(*) AS row_count,
        pg_total_relation_size('intelligence.versioned_facts') AS total_bytes
    FROM intelligence.versioned_facts
    UNION ALL
    SELECT
        'intelligence.entity_profiles',
        COUNT(*),
        pg_total_relation_size('intelligence.entity_profiles')
    FROM intelligence.entity_profiles
    UNION ALL
    SELECT
        'intelligence.entity_relationships',
        COUNT(*),
        pg_total_relation_size('intelligence.entity_relationships')
    FROM intelligence.entity_relationships
    UNION ALL
    SELECT
        'intelligence.storyline_states',
        COUNT(*),
        pg_total_relation_size('intelligence.storyline_states')
    FROM intelligence.storyline_states
    UNION ALL
    SELECT
        'intelligence.contexts',
        COUNT(*),
        pg_total_relation_size('intelligence.contexts')
    FROM intelligence.contexts
)
SELECT
    table_name,
    row_count,
    pg_size_pretty(total_bytes) AS total_size,
    CASE WHEN row_count > 0
        THEN pg_size_pretty((total_bytes / row_count)::bigint)
        ELSE NULL
    END AS avg_row_size
FROM storage_analysis
ORDER BY total_bytes DESC NULLS LAST;
```

---

## 4. Optimization strategies

### Compression

- **Vector quantization:** float32 → int8 (or similar) → ~4× reduction per vector.  
- **Product quantization (PQ):** e.g. 768d → 96 bytes for similarity search → ~32× reduction with some accuracy trade-off.  
- **Sparse vectors:** where applicable (e.g. text), store only non-zero dimensions.

### Tiered storage

- **Hot (e.g. last 30 days):** SSD, no or light compression, full indexes.  
- **Warm (e.g. 30–365 days):** SSD/HDD, Zstd, primary indexes only.  
- **Cold (>365 days):** archive (e.g. S3/Glacier), high compression, no vector indexes.

### Deduplication

- **Exact match:** hash of `fact_text` (and entity_profile_id) to avoid storing duplicates.  
- **Semantic near-duplicate:** vector similarity above a threshold (e.g. 0.95) within same entity → link to existing fact or merge.  
- **Fact consolidation:** multiple instances of the same “template” (e.g. “X appointed Y as Z”) stored as one fact + instance list (dates, source_ids).

### Pruning and retention

- **Superseded versions:** keep only every Nth or only “significant” versions (e.g. confidence > threshold).  
- **Fact-type retention:** e.g. keep all legal_decision / election_result; aggregate or drop low-value types after N months.  
- **Archive to cold:** move old rows to an archive table or external store; keep only references or aggregates in hot DB.

---

## 5. Realistic scale scenarios

| Scale | Monitored entities (order) | Facts/day (order) | Storage/year (with optimization) |
|-------|----------------------------|-------------------|-----------------------------------|
| Small | 10k | 5k | ~70 GB |
| Medium | 100k | 50k | ~100–200 GB |
| Large | 1M | 500k | ~700 GB – 1 TB+ |

Without optimization (full vectors, no dedup, no tiering), large deployments can reach multiple TB. With quantization, dedup, tiering, and retention, **100–200 GB/year** for a medium deployment is a reasonable target.

---

## 6. Recommendations summary

- **Expected storage (medium):** ~100–200 GB year 1; ~150–300 GB year 2; ~400–800 GB by year 5 (cumulative).  
- **Impact of measures:**  
  - Vector quantization: large reduction (e.g. 4×–32×).  
  - Deduplication: 30–40% reduction.  
  - Tiered storage: significant cost reduction (most data cold).  
  - Selective retention: 60%+ reduction for old, low-value data.  
- **Infrastructure (example):**  
  - Hot SSD: ~100 GB.  
  - Warm SSD: ~500 GB.  
  - Cold (e.g. S3): ~2 TB budget.  

Implement compression and dedup early; add tiering and retention policies as volume grows. Re-run the storage analysis query periodically to track growth and validate estimates.
