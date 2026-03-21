# 🗄️ News Intelligence System v3.0 - Database Schema Documentation

> **Status:** Legacy snapshot (v3-era naming, e.g. `news_system`). **Canonical reference for current work:** [DATABASE.md](./DATABASE.md). Do not treat this file as the live schema contract.

## 📋 **OVERVIEW**

This document provides comprehensive documentation of the News Intelligence System database schema, following the standards established in [CODING_STYLE_GUIDE.md](./CODING_STYLE_GUIDE.md).

**Database Name**: `news_system`  
**Default User**: `newsapp`  
**Port**: `5432`  
**Host**: `postgres` (Docker service name)

---

## 🏗️ **SCHEMA ARCHITECTURE**

### **Core Tables**
- **Content Management**: `articles`, `rss_feeds`, `content_hashes`
- **Story Management**: `story_expectations`, `story_threads`, `story_targets`
- **ML Processing**: `article_clusters`, `entities`, `similarity_scores`
- **Timeline Features**: `timeline_events`, `timeline_periods`, `timeline_milestones`
- **System Management**: `system_config`, `automation_logs`, `performance_metrics`

---

## 📊 **CORE CONTENT TABLES**

### **articles**
Primary table for storing news articles and their processed data.

```sql
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    summary TEXT,
    url TEXT,
    source VARCHAR(255),
    published_date TIMESTAMP,
    category VARCHAR(100),
    language VARCHAR(10) DEFAULT 'en',
    quality_score NUMERIC(3,2) DEFAULT 0.0,
    processing_status VARCHAR(50) DEFAULT 'raw',
    content_hash VARCHAR(64),
    deduplication_status VARCHAR(50) DEFAULT 'pending',
    content_similarity_score NUMERIC(3,2),
    normalized_content TEXT,
    ml_data JSONB,
    rag_keep_longer BOOLEAN DEFAULT false,
    rag_context_needed BOOLEAN DEFAULT false,
    rag_priority INTEGER DEFAULT 0,
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sentiment_score NUMERIC(3,2) DEFAULT 0.0,
    key_points TEXT[],
    entities_extracted JSONB,
    topics_extracted TEXT[],
    readability_score NUMERIC(3,2) DEFAULT 0.0,
    engagement_score NUMERIC(3,2) DEFAULT 0.0,
    -- Timeline-specific columns
    timeline_relevance_score NUMERIC(3,2) DEFAULT 0.0,
    timeline_processed BOOLEAN DEFAULT false,
    timeline_events_generated INTEGER DEFAULT 0
);
```

**Key Indexes**:
- `idx_articles_category` - Category filtering
- `idx_articles_published_date` - Date-based queries
- `idx_articles_processing_status` - Processing state
- `idx_articles_timeline_relevance` - Timeline relevance scoring

### **rss_feeds**
Configuration and monitoring for RSS feed sources.

```sql
CREATE TABLE rss_feeds (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_fetched TIMESTAMP,
    success_rate NUMERIC(3,2) DEFAULT 0.0,
    avg_response_time INTEGER DEFAULT 0,
    articles_today INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 📖 **STORY MANAGEMENT TABLES**

### **story_expectations**
Core storyline configuration and tracking.

```sql
CREATE TABLE story_expectations (
    story_id VARCHAR(255) PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    priority_level INTEGER CHECK (priority_level >= 1 AND priority_level <= 10),
    keywords JSONB DEFAULT '[]'::jsonb,
    entities JSONB DEFAULT '[]'::jsonb,
    geographic_regions JSONB DEFAULT '[]'::jsonb,
    quality_threshold NUMERIC(3,2) DEFAULT 0.7,
    max_articles_per_day INTEGER DEFAULT 50,
    auto_enhance BOOLEAN DEFAULT true,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Timeline-specific columns
    timeline_enabled BOOLEAN DEFAULT true,
    timeline_auto_generate BOOLEAN DEFAULT true,
    timeline_min_importance NUMERIC(3,2) DEFAULT 0.3,
    timeline_max_events_per_day INTEGER DEFAULT 10,
    timeline_last_generated TIMESTAMP
);
```

**Key Indexes**:
- `idx_story_expectations_is_active` - Active storylines
- `idx_story_expectations_priority_level` - Priority filtering

---

## ⏰ **TIMELINE FEATURES TABLES**

### **timeline_events**
ML-generated timeline events for storylines.

```sql
CREATE TABLE timeline_events (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR(255) UNIQUE NOT NULL,
    storyline_id VARCHAR(255) NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    event_date DATE NOT NULL,
    event_time TIME,
    source VARCHAR(255),
    url TEXT,
    importance_score NUMERIC(3,2) DEFAULT 0.0,
    event_type VARCHAR(100) DEFAULT 'general',
    location VARCHAR(255),
    entities JSONB DEFAULT '[]'::jsonb,
    tags TEXT[] DEFAULT '{}',
    ml_generated BOOLEAN DEFAULT true,
    confidence_score NUMERIC(3,2) DEFAULT 0.0,
    source_article_ids INTEGER[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_importance_score CHECK (importance_score >= 0.0 AND importance_score <= 1.0),
    CONSTRAINT chk_confidence_score CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0)
);
```

**Key Indexes**:
- `idx_timeline_events_storyline_id` - Storyline filtering
- `idx_timeline_events_event_date` - Date-based queries
- `idx_timeline_events_importance_score` - Importance ranking
- `idx_timeline_events_event_type` - Event type filtering

### **timeline_periods**
Grouped timeline events by time periods.

```sql
CREATE TABLE timeline_periods (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) NOT NULL,
    period VARCHAR(50) NOT NULL, -- e.g., '2024-01', '2024-Q1'
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    event_count INTEGER DEFAULT 0,
    key_events JSONB DEFAULT '[]'::jsonb,
    summary TEXT,
    ml_generated BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(storyline_id, period)
);
```

### **timeline_milestones**
Key milestone events in storylines.

```sql
CREATE TABLE timeline_milestones (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) NOT NULL,
    event_id VARCHAR(255) NOT NULL,
    milestone_type VARCHAR(100) NOT NULL, -- 'major', 'turning_point', 'crisis', 'resolution'
    significance_score NUMERIC(3,2) DEFAULT 0.0,
    impact_description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES timeline_events(event_id) ON DELETE CASCADE
);
```

### **timeline_analysis**
ML analysis results for storylines.

```sql
CREATE TABLE timeline_analysis (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) NOT NULL,
    analysis_date DATE NOT NULL,
    total_events INTEGER DEFAULT 0,
    high_importance_events INTEGER DEFAULT 0,
    event_types JSONB DEFAULT '{}'::jsonb,
    key_entities JSONB DEFAULT '[]'::jsonb,
    geographic_coverage JSONB DEFAULT '[]'::jsonb,
    sentiment_trend NUMERIC(3,2) DEFAULT 0.0,
    complexity_score NUMERIC(3,2) DEFAULT 0.0,
    narrative_coherence NUMERIC(3,2) DEFAULT 0.0,
    ml_insights JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(storyline_id, analysis_date)
);
```

---

## 🤖 **ML PROCESSING TABLES**

### **article_clusters**
Article clustering for content organization.

```sql
CREATE TABLE article_clusters (
    id SERIAL PRIMARY KEY,
    main_article_id INTEGER NOT NULL,
    cluster_size INTEGER DEFAULT 1,
    cluster_theme TEXT,
    similarity_threshold NUMERIC(3,2) DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (main_article_id) REFERENCES articles(id) ON DELETE CASCADE
);
```

### **entities**
Extracted entities from articles.

```sql
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    entity_name VARCHAR(255) NOT NULL,
    entity_type VARCHAR(100) NOT NULL, -- 'person', 'organization', 'location', 'event'
    confidence_score NUMERIC(3,2) DEFAULT 0.0,
    source_article_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_article_id) REFERENCES articles(id) ON DELETE CASCADE
);
```

---

## ⚙️ **SYSTEM MANAGEMENT TABLES**

### **system_config**
System configuration parameters.

```sql
CREATE TABLE system_config (
    id SERIAL PRIMARY KEY,
    key VARCHAR(255) UNIQUE NOT NULL,
    value TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Configuration Values**:
- `timeline_ml_enabled` - Enable ML timeline generation
- `timeline_ollama_url` - Ollama API URL
- `timeline_model_name` - Default ML model
- `timeline_max_events_per_storyline` - Event limits
- `timeline_min_confidence_score` - Quality thresholds

### **automation_logs**
System automation and processing logs.

```sql
CREATE TABLE automation_logs (
    id SERIAL PRIMARY KEY,
    process_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL, -- 'running', 'completed', 'failed'
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    records_processed INTEGER DEFAULT 0,
    execution_time_seconds INTEGER DEFAULT 0
);
```

---

## 🔗 **RELATIONSHIP DIAGRAM**

```
story_expectations (1) ──→ (N) timeline_events
timeline_events (1) ──→ (N) timeline_milestones
timeline_events (1) ──→ (N) timeline_event_sources
articles (1) ──→ (N) timeline_event_sources
story_expectations (1) ──→ (N) timeline_periods
story_expectations (1) ──→ (N) timeline_analysis
articles (1) ──→ (N) article_clusters
articles (1) ──→ (N) entities
```

---

## 📏 **DATA TYPES & CONSTRAINTS**

### **Numeric Constraints**
- `NUMERIC(3,2)` - Scores and percentages (0.00 to 9.99)
- `INTEGER` - Counts and IDs
- `SERIAL` - Auto-incrementing primary keys

### **Text Constraints**
- `TEXT` - Variable-length text (unlimited)
- `VARCHAR(n)` - Fixed-length text with limits
- `JSONB` - Structured JSON data with indexing

### **Date/Time Constraints**
- `TIMESTAMP` - Full date and time
- `DATE` - Date only (YYYY-MM-DD)
- `TIME` - Time only (HH:MM:SS)

---

## 🔍 **QUERY PATTERNS**

### **Common Queries**

#### Get Timeline Events for Storyline
```sql
SELECT te.*, se.name as storyline_name
FROM timeline_events te
JOIN story_expectations se ON te.storyline_id = se.story_id
WHERE te.storyline_id = $1
  AND te.event_date BETWEEN $2 AND $3
  AND te.importance_score >= $4
ORDER BY te.event_date DESC, te.importance_score DESC;
```

#### Get High-Importance Milestones
```sql
SELECT tm.*, te.title, te.description, te.event_date
FROM timeline_milestones tm
JOIN timeline_events te ON tm.event_id = te.event_id
WHERE tm.storyline_id = $1
  AND tm.significance_score >= 0.8
ORDER BY te.event_date DESC;
```

#### Get Articles for Timeline Generation
```sql
SELECT a.*, se.keywords, se.entities
FROM articles a
CROSS JOIN story_expectations se
WHERE se.story_id = $1
  AND a.processing_status = 'completed'
  AND a.timeline_processed = false
  AND (
    a.title ILIKE ANY(se.keywords) OR
    a.content ILIKE ANY(se.keywords) OR
    a.entities_extracted ?| se.entities
  )
ORDER BY a.published_date DESC;
```

---

## 🚀 **PERFORMANCE OPTIMIZATION**

### **Indexing Strategy**
- **Primary Keys**: All tables have `id SERIAL PRIMARY KEY`
- **Foreign Keys**: Indexed for join performance
- **Query Patterns**: Indexes on frequently queried columns
- **Composite Indexes**: For multi-column queries

### **Partitioning Strategy**
- **Timeline Events**: Consider partitioning by `event_date` for large datasets
- **Articles**: Consider partitioning by `published_date` for historical data

### **Maintenance**
- **VACUUM**: Regular vacuuming for JSONB columns
- **ANALYZE**: Regular statistics updates
- **REINDEX**: Periodic index rebuilding

---

## 🔒 **SECURITY CONSIDERATIONS**

### **Access Control**
- **Database User**: `newsapp` with limited privileges
- **Connection Security**: Internal Docker network only
- **Data Encryption**: At rest and in transit

### **Data Privacy**
- **Content Hashing**: Unique content identification
- **Source Attribution**: Proper source tracking
- **Audit Trails**: Creation and update timestamps

---

## 📚 **REFERENCE DOCUMENTATION**

### **Related Documents**
- [CODING_STYLE_GUIDE.md](./CODING_STYLE_GUIDE.md) - Coding standards and conventions
- [DEVELOPER_QUICK_REFERENCE.md](./DEVELOPER_QUICK_REFERENCE.md) - Quick reference for developers
- [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) - API endpoint documentation

### **Migration Files**
- `001_initial_schema.sql` - Initial database setup
- `002_ml_features.sql` - ML processing features
- `003_story_management.sql` - Story management features
- `004_timeline_features.sql` - Timeline and ML features
- `005_performance_optimization.sql` - Performance improvements
- `006_security_enhancements.sql` - Security features
- `007_timeline_features.sql` - Latest timeline ML features

---

## ✅ **SCHEMA VALIDATION CHECKLIST**

Before deploying schema changes:
- [ ] All table names follow `snake_case` convention
- [ ] All column names follow `snake_case` convention
- [ ] All indexes have descriptive names starting with `idx_`
- [ ] All constraints have descriptive names
- [ ] Foreign key relationships are properly defined
- [ ] JSONB columns have appropriate default values
- [ ] Timestamp columns have proper defaults
- [ ] Numeric constraints are within valid ranges
- [ ] Documentation is updated for new tables/columns
- [ ] Migration scripts are tested

---

*This schema documentation follows the standards established in the News Intelligence System Coding Style Guide and should be referenced before any database modifications.*
