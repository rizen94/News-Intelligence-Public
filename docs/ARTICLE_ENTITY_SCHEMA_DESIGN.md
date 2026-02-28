# Article Entity & Event Schema Design

**Full-stack rebuild for parsed entity storage, intake processing, and storyline/event connectivity**

---

## Current State (What Exists)

| Component | Status |
|-----------|--------|
| **articles.entities** | JSONB blob – unstructured, mixed types |
| **articles.keywords** | JSONB array – used for topics |
| **entity_extractor** | Extracts PERSON, ORG, LOCATION, EVENT, DATE, etc. → dumps to entities JSONB |
| **story_entity_index** | Per-storyline entities (person, org, location, event) – populated from story continuation |
| **chronological_events** | Events with actual_event_date, actual_event_time, location – storyline-scoped |
| **topic_clustering** | Uses topic_keywords with types: general, entity, location, organization, person, concept |

**Problem**: Dates, times, and countries are mixed with topics. No structured article-level entity storage. No merge/condense for proper nouns across articles.

---

## Design Goals

1. **Article intake** → extract and store structured entities (headline + full text)
2. **Separate storage** for dates, times, countries → excluded from topic clustering
3. **Notable people & recurring events** → first-class entity types for storylines
4. **Storylines** → save entities per article, merge/condense when same entity appears across articles
5. **Search & connect** → fast lookup by entity type, link articles to storylines

---

## New Schema (Per-Domain)

### 1. `article_entities` – People, Orgs, Subjects, Recurring Events

Stores entities that are used for storyline building and topic context (NOT dates/times/countries).

```sql
-- In each domain schema (politics, finance, science_tech)
CREATE TABLE article_entities (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    
    entity_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN (
        'person', 'organization', 'subject', 'recurring_event'
    )),
    
    -- person: notable people; organization: companies, agencies; 
    -- subject: concepts, themes; recurring_event: hearings, earnings, summits
    
    mention_source VARCHAR(20) DEFAULT 'body' CHECK (mention_source IN ('headline', 'body', 'both')),
    -- headline mentions = higher salience for article
    
    confidence DECIMAL(3,2) DEFAULT 0.8 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    canonical_entity_id INTEGER REFERENCES entity_canonical(id) ON DELETE SET NULL,
    -- For merging: "Fed" -> canonical "Federal Reserve"
    
    source_text_snippet TEXT,  -- Short context where entity appeared
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(article_id, entity_name, entity_type)
);
```

**Indexes**: `(article_id)`, `(LOWER(entity_name), entity_type)`, `(canonical_entity_id)`, `(entity_type)`

---

### 2. `article_extracted_dates` – Dates Only (Excluded from Topics)

```sql
CREATE TABLE article_extracted_dates (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    
    raw_expression TEXT NOT NULL,       -- "last Tuesday", "March 15", "Q1 2024"
    normalized_date DATE,               -- Resolved date when possible
    expression_type VARCHAR(30) DEFAULT 'absolute' 
        CHECK (expression_type IN ('absolute', 'relative', 'period', 'range', 'unknown')),
    
    context_sentence TEXT,              -- Source text
    confidence DECIMAL(3,2) DEFAULT 0.7,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes**: `(article_id)`, `(normalized_date)`

---

### 3. `article_extracted_times` – Times Only

```sql
CREATE TABLE article_extracted_times (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    
    raw_expression TEXT NOT NULL,       -- "3:00 PM EST", "at noon", "morning"
    normalized_time TIME,
    timezone VARCHAR(50),                -- "EST", "UTC", etc.
    
    context_sentence TEXT,
    confidence DECIMAL(3,2) DEFAULT 0.7,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes**: `(article_id)`

---

### 4. `article_extracted_countries` – Countries Only (Excluded from Topics)

```sql
CREATE TABLE article_extracted_countries (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    
    country_name VARCHAR(255) NOT NULL,
    iso_code CHAR(2),                   -- ISO 3166-1 alpha-2 when known
    
    mention_context VARCHAR(20) DEFAULT 'body',  -- headline | body
    confidence DECIMAL(3,2) DEFAULT 0.8,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(article_id, country_name)
);
```

**Indexes**: `(article_id)`, `(LOWER(country_name))`, `(iso_code)`

---

### 5. `entity_canonical` – Merge/Alias Support (Domain-Level)

For condensing "Fed", "Federal Reserve", "the Fed" into one canonical entity.

```sql
CREATE TABLE entity_canonical (
    id SERIAL PRIMARY KEY,
    canonical_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(50) NOT NULL CHECK (entity_type IN (
        'person', 'organization', 'subject', 'recurring_event'
    )),
    aliases TEXT[] DEFAULT '{}',         -- ["Fed", "the Fed", "Federal Reserve"]
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(canonical_name, entity_type)
);
```

**Indexes**: `(LOWER(canonical_name))`, GIN on `aliases` for fast lookup

---

### 6. `article_keywords` – Search Keywords (Explicit, Excluded from Topic Clustering)

Simple keywords for search; topic_keywords stays for cluster-level. Article-level keywords are stored here and NOT fed into topic clustering as entity-like terms (dates/countries never go there).

```sql
CREATE TABLE article_keywords (
    id SERIAL PRIMARY KEY,
    article_id INTEGER NOT NULL REFERENCES articles(id) ON DELETE CASCADE,
    keyword VARCHAR(255) NOT NULL,
    keyword_type VARCHAR(30) DEFAULT 'general' 
        CHECK (keyword_type IN ('general', 'subject', 'product', 'technology')),
    -- NO: date, time, location, country, person, organization (those are separate tables)
    source VARCHAR(20) DEFAULT 'body' CHECK (source IN ('headline', 'body', 'both')),
    confidence DECIMAL(3,2) DEFAULT 0.7,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(article_id, keyword)
);
```

---

## Intake Pipeline Flow

```
RSS/Ingest → Article saved (pending)
    ↓
1. Content Analysis (word count, language, readability)
2. Entity Extraction (LLM on headline + full text):
   - article_entities (person, org, subject, recurring_event)
   - article_extracted_dates
   - article_extracted_times
   - article_extracted_countries
   - article_keywords (general subjects, products – no dates/times/countries)
3. Entity Resolution:
   - Match to entity_canonical or create new canonical
   - Set canonical_entity_id on article_entities
4. Summarization / Sentiment (existing)
5. Topic Clustering:
   - Use ONLY: article_entities (person, org, subject, recurring_event) + article_keywords
   - EXCLUDE: dates, times, countries from topic_keywords and cluster input
6. processing_stage = 'completed'
```

---

## Topic Clustering Exclusion Rules

When building `topic_keywords` or assigning articles to topics:

- **DO** use: `article_entities` (person, org, subject, recurring_event), `article_keywords`
- **DO NOT** use: `article_extracted_dates`, `article_extracted_times`, `article_extracted_countries`
- LLM topic extraction prompt: *"Extract thematic topics. Do not include dates, times, or country names as topic keywords."*

---

## Storyline Entity Merge Logic

When an article is added to a storyline:

1. Load `article_entities` for that article (with canonical resolution).
2. For each entity:
   - Look up `story_entity_index` for (storyline_id, entity_name, entity_type).
   - If canonical_entity_id is set, also check canonical form and aliases.
   - **If match found**: increment `mention_count`, update `last_seen_at`.
   - **If no match**: INSERT into `story_entity_index`.
3. Merge rule for proper nouns:
   - Before insert, check `entity_canonical` for alias match.
   - If "Fed" and "Federal Reserve" both map to same canonical → treat as one entity in story_entity_index.

---

## Search & Connectivity

| Use Case | Table(s) |
|----------|----------|
| Find articles about a person | `article_entities` WHERE entity_type='person' AND LOWER(entity_name) LIKE ... |
| Find articles in a country | `article_extracted_countries` |
| Find articles on a date | `article_extracted_dates` |
| Find articles for storyline (by entities) | Join story_entity_index ↔ article_entities on entity_name/canonical |
| Find recurring events | `article_entities` WHERE entity_type='recurring_event' |

---

## Migration Strategy

1. **Migration 138**: Create new tables in each domain schema.
2. **Backfill**: Script to run entity extraction on existing articles (optional batch job).
3. **Intake**: Update article processing service to call entity extraction and populate new tables.
4. **Topic clustering**: Update LLMTopicExtractor to exclude dates/times/countries.
5. **Storyline automation**: Update `storyline_automation_service` to use `article_entities` and merge logic.
6. **Deprecate**: Keep `articles.entities` temporarily for backward compatibility; migrate consumers to new tables.

---

## Entity Extraction Prompt Enhancements

The LLM prompt for article entity extraction should:

1. Extract **notable people** (politicians, executives, experts, public figures).
2. Extract **recurring events** (earnings calls, summits, hearings, trials, elections).
3. Output structured JSON:
   - `people`: [{name, confidence, in_headline}]
   - `organizations`: [{name, confidence, in_headline}]
   - `subjects`: [{name, confidence, in_headline}]
   - `recurring_events`: [{name, confidence, in_headline}]
   - `dates`: [{raw, normalized_iso, type}]
   - `times`: [{raw, normalized, timezone}]
   - `countries`: [{name, iso_code, in_headline}]
   - `keywords`: [{keyword, type, in_headline}] (thematic only – no dates/times/countries)

---

## Implementation Checklist

| Step | Component | Status |
|------|------------|--------|
| 1 | Migration 138 – create tables | Ready |
| 2 | `ArticleEntityExtractionService` – LLM extraction + DB writes | Done |
| 3 | Topic extraction queue worker – run entity extraction before topics | Done |
| 4 | `TopicClusteringService` prompt – exclude dates/times/countries | Done |
| 5 | `storyline_automation_service` – merge article_entities into story_entity_index on add | Done |
| 6 | Approve suggestion route – merge entities on add | Done |
| 7 | Backfill script for existing articles | Optional |
