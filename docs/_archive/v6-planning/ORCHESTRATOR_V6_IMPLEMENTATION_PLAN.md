# Newsroom Orchestrator v6 — Implementation Plan

> **Source:** Parsed from upgrade plan document (Untitled document 8.txt)  
> **Goal:** Complement existing AutomationManager with event-driven, role-based newsroom orchestration.

---

## 1. Parsed To-Do List

### Phase 1: Foundation (Start Here)

| # | Task | Details |
|---|------|---------|
| 1.1 | **Event System** | Create event types enum; build Redis pub/sub wrapper; implement priority queue |
| 1.2 | **Base Orchestrator Class** | Plugin loading system; configuration management; state persistence |
| 1.3 | **Reporter Module** | Refactor existing RSS collector; add DataSource plugin interface; implement breaking news detection |

### Phase 2: Intelligence Layer

| # | Task | Details |
|---|------|---------|
| 2.1 | **Journalist Module** | Pattern detection algorithms; entity relationship builder; investigation state machine |
| 2.2 | **Editor Module** | Quality scoring pipeline; narrative synthesis; publishing decisions |
| 2.3 | **Cross-Domain Linking** | Shared entity detection; temporal correlation; impact chain mapping |

### Phase 3: Advanced Features

| # | Task | Details |
|---|------|---------|
| 3.1 | **Archivist Module** | Historical pattern matching; knowledge graph building; semantic search enhancement |
| 3.2 | **Chief Editor AI** | Resource optimization; strategic planning; adaptive learning |

### Database & Config

| # | Task | Details |
|---|------|---------|
| 4.1 | **Orchestration schema** | `orchestration.events`, `orchestration.investigations`, `orchestration.workflows`, `orchestration.task_queue`, `orchestration.source_plugins`, `orchestration.processing_state` |
| 4.2 | **Intelligence schema** | `intelligence.patterns`, `intelligence.entity_relationships`, `intelligence.narrative_threads`, `intelligence.cross_domain_links`, `intelligence.investigation_notes` |
| 4.3 | **Configuration** | YAML config for newsroom roles (reporter, journalist, editor); breaking_news_keywords; investigation triggers |

---

## 2. Architecture Overview

### Newsroom Roles (Modular Components)

| Role | Responsibilities |
|------|------------------|
| **Chief Editor** | Strategic decisions, resource allocation, priority management, cross-domain coordination, quality gates |
| **Reporter** | RSS monitoring, source discovery, breaking news detection, raw data collection, source reliability |
| **Journalist** | Deep investigation, pattern recognition, entity relationship mapping, story development tracking |
| **Editor** | Content curation, narrative synthesis, quality scoring, relevance filtering, publishing decisions |
| **Archivist** | Historical context, search optimization, data lifecycle, knowledge preservation, reference linking |

### Technical Patterns

- **Event-Driven Message Bus:** Redis pub/sub for events; priority queue for tasks
- **Event Types:** `BREAKING_NEWS`, `PATTERN_DETECTED`, `INVESTIGATION_NEEDED`, etc.
- **Plugin Architecture:** `DataSource` interface with `authenticate`, `fetch_latest`, `validate_data`, `transform_to_standard`, `get_rate_limits`
- **Pipeline Stages:** Ingestion → Analysis → Investigation → Synthesis → Publishing

---

## 3. Implementation Strategy (Detailed)

### Phase 1: Foundation

#### 1.1 Event System
- [ ] Define `EventType` enum (BREAKING_NEWS, PATTERN_DETECTED, INVESTIGATION_NEEDED, ARTICLE_INGESTED, etc.)
- [ ] Create Redis pub/sub wrapper (`api/orchestration/events/redis_bus.py`)
- [ ] Implement priority queue (Redis list or sorted set) for task ordering
- [ ] Event payload schema (event_type, payload, priority, timestamp, domain)

#### 1.2 Base Orchestrator Class
- [ ] Create `BaseOrchestrator` with plugin discovery/loading
- [ ] Configuration management (from YAML/env)
- [ ] State persistence (Redis for volatile, PostgreSQL for durable)
- [ ] Lifecycle: `start()`, `stop()`, `get_status()`

#### 1.3 Reporter Module
- [ ] Define `DataSource` abstract interface
- [ ] Implement `RSSDataSource` (wrap existing `rss_collector.py`)
- [ ] Breaking news detection (keyword matching, velocity checks)
- [ ] Emit `ARTICLE_INGESTED` / `BREAKING_NEWS` events

### Phase 2: Intelligence Layer

#### 2.1 Journalist Module
- [ ] Pattern detection (simple rules first, e.g., multiple entity mentions ≥3)
- [ ] Entity relationship builder (link entities across articles)
- [ ] Investigation state machine (triggered, investigating, completed, deferred)
- [ ] Emit `PATTERN_DETECTED`, `INVESTIGATION_NEEDED`

#### 2.2 Editor Module
- [ ] Quality scoring pipeline (reuse existing quality_scoring)
- [ ] Narrative synthesis (briefings, summaries)
- [ ] Publishing decisions (dashboard updates, alerts)

#### 2.3 Cross-Domain Linking
- [ ] Shared entity detection (entity appears in politics → check finance)
- [ ] Temporal correlation (events within time window)
- [ ] Impact chain mapping (market pattern → regulatory news)

### Phase 3: Advanced Features (Defer if Needed)

- Archivist: historical pattern matching, knowledge graph
- Chief Editor AI: resource optimization, adaptive learning

---

## 4. Database Schema Additions (Draft)

```sql
-- Schema: orchestration
CREATE SCHEMA IF NOT EXISTS orchestration;

CREATE TABLE orchestration.events (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    priority INTEGER DEFAULT 3,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE orchestration.investigations (
    id SERIAL PRIMARY KEY,
    trigger_event_id INTEGER REFERENCES orchestration.events(id),
    status VARCHAR(50) DEFAULT 'open',  -- open, investigating, completed, deferred
    domain_key VARCHAR(50),
    entity_ids INTEGER[],
    pattern_confidence DECIMAL(3,2),
    notes JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orchestration.workflows (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE orchestration.task_queue (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    priority INTEGER DEFAULT 3,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE orchestration.source_plugins (
    id SERIAL PRIMARY KEY,
    plugin_type VARCHAR(50) NOT NULL,  -- rss, web_scraper, api, file_watcher, email_digest
    config JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    last_fetched_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE orchestration.processing_state (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Schema: intelligence
CREATE SCHEMA IF NOT EXISTS intelligence;

CREATE TABLE intelligence.patterns (
    id SERIAL PRIMARY KEY,
    pattern_type VARCHAR(50),
    domain_key VARCHAR(50),
    confidence DECIMAL(3,2),
    data JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE intelligence.entity_relationships (
    id SERIAL PRIMARY KEY,
    entity_a_id INTEGER,
    entity_b_id INTEGER,
    relationship_type VARCHAR(50),
    source_article_ids INTEGER[],
    confidence DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE intelligence.narrative_threads (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER,
    domain_key VARCHAR(50),
    summary TEXT,
    linked_article_ids INTEGER[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE intelligence.cross_domain_links (
    id SERIAL PRIMARY KEY,
    source_domain VARCHAR(50),
    target_domain VARCHAR(50),
    entity_name VARCHAR(255),
    link_type VARCHAR(50),
    source_article_ids INTEGER[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE intelligence.investigation_notes (
    id SERIAL PRIMARY KEY,
    investigation_id INTEGER REFERENCES orchestration.investigations(id),
    note_type VARCHAR(50),
    content TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

---

## 5. Configuration Example (YAML)

```yaml
newsroom:
  roles:
    reporter:
      sources:
        - type: rss
          check_interval: 300
        # - type: web_scraper
        #   targets: [configured_sites]
      breaking_news_keywords: []  # populate from config
      priority_entities: []

    journalist:
      investigation_triggers:
        - multiple_entity_mentions: 3
        - pattern_confidence: 0.8
        - user_watchlist_hit: true
      max_concurrent_investigations: 5

    editor:
      quality_threshold: 0.7
      narrative_update_frequency: 3600
      publishing_rules: []
```

---

## 6. Migration Path from v5

1. **Run parallel:** New orchestrator runs alongside AutomationManager
2. **Migrate incrementally:** One workflow at a time (e.g., RSS first)
3. **Validate:** Compare outputs before full handoff
4. **Gradual takeover:** Increase orchestrator responsibilities
5. **Deprecate:** Remove AutomationManager once stable

---

## 7. Practical Constraints (from Doc)

| Build First | Defer |
|-------------|-------|
| Event system + basic orchestrator | Complex ML patterns |
| Refactored RSS reporter with plugin support | Real-time streaming sources |
| Simple investigation workflows | External API integrations (costs) |
| Cross-domain entity linking | Distributed processing |

**Resource limits:** LLM 500–1000 calls/day; use materialized views; stream large datasets; batch network ops.

---

## 8. Proposed Directory Structure

```
api/
  orchestration/
    __init__.py
    base.py              # BaseOrchestrator
    events/
      __init__.py
      types.py           # EventType enum
      redis_bus.py       # Redis pub/sub + priority queue
    roles/
      __init__.py
      reporter.py        # ReporterModule
      journalist.py      # JournalistModule
      editor.py          # EditorModule
      archivist.py       # ArchivistModule (Phase 3)
    plugins/
      __init__.py
      base.py            # DataSource interface
      rss_source.py      # RSSDataSource
    config.py
```

---

## 9. Next Steps

1. Create `api/orchestration/` directory structure
2. Implement Event System (1.1)
3. Implement Base Orchestrator (1.2)
4. Add database migrations for `orchestration` and `intelligence` schemas
5. Implement Reporter Module with DataSource interface (1.3)
6. Wire orchestrator to run parallel to AutomationManager in `main.py` lifespan
