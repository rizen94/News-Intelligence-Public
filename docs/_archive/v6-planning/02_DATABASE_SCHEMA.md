# Database Schema — v6 Planning Reference

> **Purpose:** Consolidated schema summary in Claude-readable format for v6 project planning.  
> **Database:** `news_intel` on PostgreSQL 16 (Widow: <WIDOW_HOST_IP>)  
> **User:** `newsapp`

---

## 1. Schema Architecture Overview

The system uses **schema-based domain isolation**. Each content domain has its own PostgreSQL schema with replicated table structures. Public schema holds cross-domain configuration.

| Schema | Purpose |
|--------|---------|
| `public` | Domains config, domain_metadata, shared/cross-domain tables |
| `politics` | Politics domain — articles, topics, storylines, rss_feeds, entities, etc. |
| `finance` | Finance domain — same base tables + market_patterns, corporate_announcements, financial_indicators |
| `science_tech` | Science & technology domain — same base tables as politics |

---

## 2. Public Schema (Cross-Domain)

### domains

```sql
CREATE TABLE domains (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) UNIQUE NOT NULL,   -- 'politics', 'finance', 'science-tech'
    name VARCHAR(100) NOT NULL,
    description TEXT,
    schema_name VARCHAR(50) NOT NULL,         -- 'politics', 'finance', 'science_tech'
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- Default rows: politics, finance, science-tech
```

### domain_metadata

```sql
CREATE TABLE domain_metadata (
    domain_id INTEGER PRIMARY KEY REFERENCES domains(id) ON DELETE CASCADE,
    article_count INTEGER DEFAULT 0,
    topic_count INTEGER DEFAULT 0,
    storyline_count INTEGER DEFAULT 0,
    feed_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### Extensions

- `uuid-ossp`, `pg_trgm`, `btree_gin`, `vector` (pgvector for embeddings)

---

## 3. Per-Domain Tables (politics, finance, science_tech)

Each domain schema contains the following tables. Finance adds three extra tables (see section 4).

### articles

Core article storage with pipeline state and analysis results.

```sql
-- Key columns (from migration 100, 102)
id SERIAL PRIMARY KEY,
article_uuid UUID,
title VARCHAR(500) NOT NULL,
content TEXT,
excerpt TEXT,
url VARCHAR(1000),
canonical_url VARCHAR(1000),
published_at TIMESTAMP WITH TIME ZONE,
discovered_at TIMESTAMP WITH TIME ZONE,
author, publisher, source_domain VARCHAR(255),
language_code VARCHAR(10) DEFAULT 'en',
word_count, reading_time_minutes INTEGER,
content_hash VARCHAR(64),
processing_status VARCHAR(50) DEFAULT 'pending',  -- pending, ingesting, analyzing, summarizing, clustering, completed, failed, archived
processing_stage VARCHAR(50),
processing_started_at, processing_completed_at, processing_error_message TIMESTAMP/TEXT,
quality_score, readability_score, bias_score, credibility_score DECIMAL(3,2),
summary TEXT,
sentiment_label VARCHAR(20), sentiment_score, sentiment_confidence DECIMAL(3,2),
entities, topics, keywords, categories, tags, metadata, analysis_results JSONB,
rss_feed_id INTEGER REFERENCES rss_feeds(id),
created_at, updated_at TIMESTAMP WITH TIME ZONE
```

### rss_feeds

```sql
id SERIAL PRIMARY KEY,
feed_name VARCHAR(200) NOT NULL,
feed_url VARCHAR(1000) NOT NULL,
feed_description TEXT,
is_active BOOLEAN DEFAULT TRUE,
fetch_interval_seconds INTEGER DEFAULT 300,
last_fetched_at, last_successful_fetch_at TIMESTAMP WITH TIME ZONE,
error_count INTEGER DEFAULT 0,
last_error_message TEXT,
success_rate DECIMAL(5,2),
average_response_time_ms INTEGER,
metadata, tags JSONB,
quality_score DECIMAL(3,2),
created_at, updated_at TIMESTAMP WITH TIME ZONE
```

### topics

```sql
id SERIAL PRIMARY KEY,
topic_uuid UUID,
name VARCHAR(200) NOT NULL UNIQUE,
description TEXT,
category VARCHAR(100),
keywords TEXT[],
confidence_score, accuracy_score DECIMAL(3,2),
review_count, correct_assignments, incorrect_assignments INTEGER,
learning_data JSONB,
last_improved_at TIMESTAMP,
improvement_trend DECIMAL(3,2),
status VARCHAR(50) DEFAULT 'active',  -- active, reviewed, archived, merged
is_auto_generated BOOLEAN DEFAULT TRUE,
created_at, updated_at TIMESTAMP WITH TIME ZONE,
created_by VARCHAR(100)
```

### storylines

```sql
id SERIAL PRIMARY KEY,
storyline_uuid UUID,
title VARCHAR(300) NOT NULL,
description, summary TEXT,
status VARCHAR(50) DEFAULT 'active',  -- draft, active, archived, completed, failed
processing_status VARCHAR(50),
quality_score, completeness_score, coherence_score DECIMAL(3,2),
created_at, updated_at TIMESTAMP WITH TIME ZONE,
created_by VARCHAR(100)
```

### article_topic_assignments

```sql
id SERIAL PRIMARY KEY,
assignment_uuid UUID,
article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE,
confidence_score, relevance_score DECIMAL(3,2),
is_validated BOOLEAN DEFAULT FALSE,
is_correct BOOLEAN,
feedback_notes TEXT, feedback_source VARCHAR(50),
assignment_method VARCHAR(50) DEFAULT 'auto',  -- auto, manual, learned, hybrid
model_version VARCHAR(50),
assignment_context JSONB,
created_at, updated_at, validated_at TIMESTAMP WITH TIME ZONE,
validated_by VARCHAR(100),
UNIQUE(article_id, topic_id)
```

### topic_clusters

```sql
id SERIAL PRIMARY KEY,
cluster_uuid UUID,
cluster_name VARCHAR(200) NOT NULL,
description TEXT,
category VARCHAR(100),
topic_count, article_count INTEGER,
average_confidence DECIMAL(3,2),
cluster_patterns, learning_data JSONB,
status VARCHAR(50) DEFAULT 'active',
created_at, updated_at TIMESTAMP WITH TIME ZONE
```

### topic_cluster_memberships

```sql
id SERIAL PRIMARY KEY,
topic_id INTEGER REFERENCES topics(id),
cluster_id INTEGER REFERENCES topic_clusters(id),
membership_confidence DECIMAL(3,2),
created_at TIMESTAMP WITH TIME ZONE,
UNIQUE(topic_id, cluster_id)
```

### topic_learning_history

```sql
id SERIAL PRIMARY KEY,
topic_id INTEGER REFERENCES topics(id),
event_type VARCHAR(50),  -- review, correction, validation, improvement
event_data JSONB,
accuracy_before, accuracy_after, confidence_before, confidence_after DECIMAL(3,2),
created_at TIMESTAMP WITH TIME ZONE,
created_by VARCHAR(100)
```

### storyline_articles

Links storylines to articles.

```sql
id SERIAL PRIMARY KEY,
storyline_id INTEGER REFERENCES storylines(id),
article_id INTEGER REFERENCES articles(id),
created_at TIMESTAMP WITH TIME ZONE,
UNIQUE(storyline_id, article_id)
```

---

## 4. Entity Extraction Tables (per domain, migration 138)

### entity_canonical

```sql
id SERIAL PRIMARY KEY,
canonical_name VARCHAR(255) NOT NULL,
entity_type VARCHAR(50) CHECK (entity_type IN ('person','organization','subject','recurring_event')),
aliases TEXT[],
created_at, updated_at TIMESTAMP WITH TIME ZONE,
UNIQUE(canonical_name, entity_type)
```

### article_entities

```sql
id SERIAL PRIMARY KEY,
article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
entity_name VARCHAR(255) NOT NULL,
entity_type VARCHAR(50) CHECK (entity_type IN ('person','organization','subject','recurring_event')),
mention_source VARCHAR(20) DEFAULT 'body',  -- headline, body, both
confidence DECIMAL(3,2),
canonical_entity_id INTEGER REFERENCES entity_canonical(id),
source_text_snippet TEXT,
created_at TIMESTAMP WITH TIME ZONE,
UNIQUE(article_id, entity_name, entity_type)
```

### article_extracted_dates

```sql
id SERIAL PRIMARY KEY,
article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
raw_expression TEXT NOT NULL,
normalized_date DATE,
expression_type VARCHAR(30),  -- absolute, relative, period, range, unknown
context_sentence TEXT,
confidence DECIMAL(3,2),
created_at TIMESTAMP WITH TIME ZONE
```

### article_extracted_times

```sql
id SERIAL PRIMARY KEY,
article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
raw_expression TEXT NOT NULL,
normalized_time TIME,
timezone VARCHAR(50),
context_sentence TEXT,
confidence DECIMAL(3,2),
created_at TIMESTAMP WITH TIME ZONE
```

### article_extracted_countries

```sql
id SERIAL PRIMARY KEY,
article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
country_name VARCHAR(100) NOT NULL,
country_code VARCHAR(5),
context_sentence TEXT,
confidence DECIMAL(3,2),
created_at TIMESTAMP WITH TIME ZONE
```

### article_keywords

```sql
id SERIAL PRIMARY KEY,
article_id INTEGER REFERENCES articles(id) ON DELETE CASCADE,
keyword VARCHAR(255) NOT NULL,
confidence DECIMAL(3,2),
created_at TIMESTAMP WITH TIME ZONE
```

---

## 5. Finance-Only Tables (finance schema)

### market_patterns

```sql
id SERIAL PRIMARY KEY,
pattern_uuid UUID,
pattern_type, pattern_name VARCHAR(50/200),
description TEXT,
detected_at TIMESTAMP WITH TIME ZONE,
time_window_days INTEGER,
confidence_score DECIMAL(3,2),
pattern_data JSONB,
affected_companies TEXT[],
affected_articles INTEGER[],
market_impact DECIMAL(5,2),
pattern_strength, pattern_duration_days,
predicted_outcome, actual_outcome TEXT,
created_at, updated_at TIMESTAMP WITH TIME ZONE,
created_by VARCHAR(100)
```

### corporate_announcements

```sql
id SERIAL PRIMARY KEY,
announcement_uuid UUID,
company_name VARCHAR(200),
ticker_symbol VARCHAR(10),
company_sector, company_industry VARCHAR(100),
announcement_type VARCHAR(50),  -- earnings, merger, product, executive, regulatory, guidance
announcement_date DATE,
title VARCHAR(500),
content, summary TEXT,
source_url, source_type, filing_type, filing_date,
sentiment_score, sentiment_label, market_impact, impact_duration_days,
article_id INTEGER REFERENCES finance.articles(id),
related_announcements INTEGER[],
raw_data JSONB,
created_at, updated_at, processed_at TIMESTAMP WITH TIME ZONE
```

### financial_indicators

```sql
id SERIAL PRIMARY KEY,
indicator_uuid UUID,
company_name, ticker_symbol VARCHAR(200/10),
indicator_type VARCHAR(50),
value DECIMAL(15,2),
currency VARCHAR(10) DEFAULT 'USD',
unit VARCHAR(20),
period_start, period_end DATE,
period_type VARCHAR(20),
fiscal_year, fiscal_quarter INTEGER,
reported_at TIMESTAMP WITH TIME ZONE,
report_source, report_url VARCHAR(100)/TEXT,
previous_value, change_percentage, consensus_estimate DECIMAL,
created_at, updated_at TIMESTAMP WITH TIME ZONE
```

---

## 6. Cross-Domain / Public Tables (from later migrations)

### watchlist (migration 136)

User watchlist for storylines (public or per-domain; check migration for exact schema).

### topic_extraction_queue (migration 130)

Queue for topic extraction processing.

### story_entity_index (migration 135)

Entity index for storyline merge/cross-article entity tracking.

### event_embeddings (migration 134, pgvector)

Embeddings for events (if used).

### banned_topics (migration 137)

Topics excluded from processing.

### log_archive (migration 139)

Log archival tables.

### api_cache (migration 011, 132)

API response caching.

---

## 7. Migration Order Reference

Key migrations (apply in order):

1. **100** — v4.0 complete schema overhaul (rss_feeds, articles, storylines, topics, etc.)
2. **101, 102, 103** — Schema enhancements and naming fixes
3. **121** — Topic clustering system (topics, article_topic_assignments, topic_clusters, topic_cluster_memberships, topic_learning_history)
4. **122** — Domain silo infrastructure (domains, domain_metadata, create politics/finance/science_tech schemas and tables)
5. **123** — Fix domain foreign keys
6. **125** — Data migration to domains
7. **130** — Topic extraction queue
8. **133** — Event extraction v5
9. **134** — pgvector event embeddings
10. **135** — Story entity index
11. **136** — Watchlist tables
12. **137** — Banned topics
13. **138** — Article entities full system (entity_canonical, article_entities, article_extracted_dates/times/countries, article_keywords)
14. **139** — Log archive tables

---

## 8. Query Hints for Claude

- Domain schemas are referenced as `politics.articles`, `finance.articles`, etc.
- Use `domains` and `domain_metadata` for cross-domain queries.
- Entity extraction is per-domain; `article_entities` links to `entity_canonical`.
- Topic clustering uses `topics`, `article_topic_assignments`, `topic_clusters`, `topic_cluster_memberships`.
