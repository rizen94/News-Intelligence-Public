# Entity Profile Schema Graph — entity_profiles, Migration 199–229, Builder Service

*Date created: 2026-10-22*
*Source: `api/database/migrations/199*, 200*, 226*, 227*, 228*, 229*`, `api/services/entity_profile_builder_service.py`*

---

## 1. Overview

Entity profiles represent real-world entities (persons, organizations, subjects, events, families) that appear across articles and storylines. The system builds, enriches, and cross-links these profiles over time to create a knowledge graph of "who did what, where, when."

---

## 2. Entity Types (CHECK Constraint)

```sql
-- Enforced via Migration 199:
entity_type IN ('person', 'organization', 'subject', 'recurring_event', 'family')
```

### Entity Type Semantics

| Type | Example | Notes |
|------|---------|-------|
| **person** | "Donald Trump" | Individual with canonical name + aliases |
| **organization** | "White House" | Institutions, companies, agencies |
| **subject** | "Climate Change" | Abstract topics/themes as entity nodes |
| **recurring_event** | "US Elections" | Events that recur across time periods |
| **family** | "Trump family" | Surname umbrella linking distinct persons (added in M199) |

---

## 3. Migration History

### Migration 199 — `entity_family_type`
- Adds `family` to CHECK constraint on both `entity_canonical` and `article_entities` tables.
- Drops old constraints dynamically, recreates with widened type list.
- Domain-scoped: iterates all schemas containing these tables.

### Migration 200 — `entity_profiles_core`
Creates the core entity profiles table:
```sql
CREATE TABLE entity_profiles (
    id              SERIAL PRIMARY KEY,
    entity_id       INT NOT NULL,           -- FK to entity_canonical.id
    canonical_name  VARCHAR(255) NOT NULL,
    aliases         TEXT[],                 -- alternative names
    description     TEXT,                   -- free-text summary
    attributes      JSONB,                  -- structured metadata (birth_date, HQ_location, etc.)
    metadata_json   JSONB,                  -- raw LLM response + processing info
    source_domain   VARCHAR(32),            -- which domain extracted this profile
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(entity_id)
);
```

### Migrations 226–229 — Auxiliary Entity Extraction Tables

| Migration | Purpose |
|-----------|---------|
| **226** | `article_extracted_dates` per domain schema (parallel to politics) |
| **227** | `article_extracted_times` per domain schema |
| **228** | `article_extracted_countries` per domain schema |
| **229** | `article_keywords`, cross-entity linking tables, profile enrichment pipeline |

All four migrations follow the same pattern: for each active domain (legal, medicine, artificial_intelligence), check if the target table exists; if not, clone from politics schema.

---

## 4. Entity Profile Builder Service

### 4.1 Architecture Overview

The `EntityProfileBuilderService` runs in two tiers:

```
┌──────────────────────┐     ┌──────────────────────┐
│   Fast Tier          │     │   Full Tier          │
│   (Metadata Only)    │     │   (LLM Extraction)   │
│                      │     │                      │
│ • Article title      │     │ • Context bundles    │
│ • Author             │────►│ • Article body       │
│ • Publish date       │     │ • Entity candidates  │
│ • Tags/categories    │     │ • Prior profile data │
│                      │     │                      │
│ ~10ms per article    │     │ ~3–30s per article   │
└──────────────────────┘     └──────────────────────┘
```

### 4.2 Fast Tier (Default)

Triggered when:
- Article has sufficient metadata (title, author, date)
- Storyline already has an existing entity profile to compare against
- `ENTITY_BUILD_MODE` env var is not set to "full"

**Process:**
1. Extract entities from article title + lead paragraph only.
2. Match against existing entity_canonical entries (fuzzy name match).
3. If no match → lightweight fallback entry with metadata-derived attributes.
4. No LLM call; response cached indefinitely.

### 4.3 Full Tier

Triggered when:
- `ENTITY_BUILD_MODE=full` env var is set
- An entity profile is >7 days stale (updated_at threshold)
- Materiality gate classifies change as "material"

**Process:**
1. Build **context bundles** — the system packs all relevant context for each entity candidate:
   - Prior canonical narrative fragments
   - Existing alias list
   - Cross-domain mentions of same entity (from `article_entities`)
   - Time window: articles within last 30 days
2. Send to LLM with structured prompt:
   ```
   "Based on the following evidence, update the entity profile for {name}:
    Priors: {existing_profile}
    Evidence: {context_bundles[entity_id]}
    Return: canonical_name, aliases[], description, attributes{}"
   ```
3. Parse response → upsert into `entity_profiles`.
4. Cross-link via `article_entities` → update entity graph edges.

### 4.4 Batched Parallel Building

The builder processes entities in parallel batches:

```python
# Pseudocode from entity_profile_builder_service.py
async def build_profiles_batch(
    article_ids: List[int],
    max_concurrent: int = 5  # configurable via ENTITY_BUILD_PARALLELISM
) -> List[EntityProfile]:
    """
    For each article in the batch:
    1. Extract entity candidates
    2. Build context bundle for each candidate
    3. Dispatch LLM calls (parallel, up to max_concurrent)
    4. Merge results into entity_profiles table
    """
```

Key design decisions:
- **Parallelism cap** prevents Ollama model pool exhaustion.
- **Context bundles are deduplicated** across entities in the same batch — if two articles mention "Donald Trump" and "Biden family", their shared context is loaded once.
- **Failure isolation**: a failed LLM call for one entity doesn't block other entities in the batch.

---

## 5. Context Bundle Pipeline

### 5.1 What Is a Context Bundle?

A context bundle is a scoped snapshot of all information relevant to a single entity candidate, used as input to the LLM during profile enrichment:

```python
ContextBundle = {
    "entity_id": int,
    "canonical_name": str,
    "existing_aliases": [str],
    "prior_description": str | None,
    "existing_attributes": JSONB,  # partial or full prior data
    "related_articles": [
        {
            "article_id": int,
            "title": str,
            "published_at": datetime,
            "mention_context": str,  # surrounding text of entity mention
            "domain": str           # politics | finance | science-tech
        }
    ],
    "cross_domain_mentions": [
        {
            "entity_type": str,
            "domain": str,
            "confidence": float      # from entity extraction confidence
        }
    ]
}
```

### 5.2 Bundle Construction (SQL)

```sql
-- Pseudocode for context bundle query
SELECT e.id, e.canonical_name, e.aliases, ep.description,
       ar.title, ar.published_at, ar.domain
FROM entity_canonical e
LEFT JOIN entity_profiles ep ON ep.entity_id = e.id
JOIN article_entities ae ON ae.entity_id = e.id
JOIN articles ar ON ar.id = ae.article_id
WHERE e.canonical_name ILIKE :candidate_name
  AND ar.published_at > now() - interval '30 days'
ORDER BY ar.published_at DESC;
```

---

## 6. Entity Graph Cross-Linking

### 6.1 article_entities Table

The cross-domain linking is maintained via `article_entities`:

```sql
CREATE TABLE article_entities (
    article_id    INT REFERENCES articles(id),
    entity_id     INT REFERENCES entity_canonical(id),
    entity_type   VARCHAR(32) CHECK (entity_type IN ('person','organization','subject','recurring_event','family')),
    mention_text  TEXT,            -- how the entity is referenced in this article
    confidence    FLOAT DEFAULT 0.0,
    domain        VARCHAR(32),     -- which domain extracted this link
    created_at    TIMESTAMPTZ
);
```

### 6.2 Cross-Entity Resolution

When a new entity candidate appears:
1. Check `article_entities` for existing entity IDs with same canonical_name (fuzzy match).
2. If confidence > 0.85 → **merge** into existing profile.
3. If no match → create new `entity_canonical` + `entity_profiles` entry.
4. Update graph edges via cross-domain joins (politics entity mentions in finance articles, etc.).

---

## 7. Key Files

- `api/database/migrations/199_entity_family_type.sql` — Adds family type to CHECK constraint
- `api/database/migrations/200_entity_profiles_core.sql` — Core profiles table schema
- `api/database/migrations/226_article_extracted_dates.sql` — Dates aux tables per domain
- `api/database/migrations/227_article_extracted_times.sql` — Times aux tables per domain
- `api/database/migrations/228_article_extracted_countries.sql` — Countries aux tables per domain
- `api/database/migrations/229_entity_extraction_aux_tables.sql` — Keywords + cross-entity linking
- `api/services/entity_profile_builder_service.py` — Builder service (fast/full tiering)
