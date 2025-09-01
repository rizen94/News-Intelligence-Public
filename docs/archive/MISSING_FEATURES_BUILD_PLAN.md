# Missing Features Build Plan for ML Summarizer Readiness

## Overview

This document outlines the missing features from the enhancement plan that must be implemented before adding the ML summarizer. These features ensure data quality, proper deduplication, and comprehensive monitoring.

## Priority 1: Deduplication System (Critical)

### **1.1 Content Hash Deduplication**
- **Implementation**: Extend `ArticleProcessor` with deduplication methods
- **Features**:
  - SHA256 content hash generation (already exists)
  - Hash-based duplicate detection
  - Duplicate marking with `duplicate_of` reference
  - Batch deduplication for performance
- **Database Changes**:
  ```sql
  ALTER TABLE articles ADD COLUMN duplicate_of INTEGER REFERENCES articles(id);
  ALTER TABLE articles ADD COLUMN is_duplicate BOOLEAN DEFAULT FALSE;
  CREATE INDEX idx_articles_content_hash ON articles(content_hash);
  CREATE INDEX idx_articles_duplicate_of ON articles(duplicate_of);
  ```

### **1.2 URL-Based Deduplication**
- **Implementation**: URL normalization and comparison
- **Features**:
  - URL canonicalization (remove tracking parameters, normalize protocols)
  - Domain-based duplicate detection
  - URL similarity scoring
- **Database Changes**:
  ```sql
  ALTER TABLE articles ADD COLUMN canonical_url VARCHAR(500);
  ALTER TABLE articles ADD COLUMN url_hash VARCHAR(64);
  CREATE INDEX idx_articles_canonical_url ON articles(canonical_url);
  CREATE INDEX idx_articles_url_hash ON articles(url_hash);
  ```

### **1.3 Semantic Similarity Deduplication**
- **Implementation**: Text similarity using sentence-transformers
- **Features**:
  - Embedding-based similarity detection
  - Configurable similarity thresholds
  - Batch processing for efficiency
- **Dependencies**: `sentence-transformers`, `torch`

## Priority 2: Metadata Enrichment (High)

### **2.1 Language Detection & Storage**
- **Implementation**: Extend `ArticleProcessor` with language detection
- **Features**:
  - Language detection using `langdetect` or `fasttext`
  - Language confidence scoring
  - Language-specific text processing
- **Database Changes**:
  ```sql
  ALTER TABLE articles ADD COLUMN detected_language VARCHAR(10);
  ALTER TABLE articles ADD COLUMN language_confidence DECIMAL(5,2);
  CREATE INDEX idx_articles_language ON articles(detected_language);
  ```

### **2.2 Content Metrics & Quality Scoring**
- **Implementation**: Enhanced content analysis in `ArticleProcessor`
- **Features**:
  - Word count, sentence count, character count
  - Reading time estimation
  - Content completeness scoring
  - Quality heuristics (length, structure, readability)
- **Database Changes**:
  ```sql
  ALTER TABLE articles ADD COLUMN word_count INTEGER;
  ALTER TABLE articles ADD COLUMN sentence_count INTEGER;
  ALTER TABLE articles ADD COLUMN content_completeness_score DECIMAL(5,2);
  ALTER TABLE articles ADD COLUMN readability_score DECIMAL(5,2);
  ```

### **2.3 Keyword Extraction**
- **Implementation**: TF-IDF and RAKE keyword extraction
- **Features**:
  - TF-IDF keyword extraction
  - RAKE (Rapid Automatic Keyword Extraction)
  - Keyword ranking and scoring
  - Multi-language keyword support
- **Dependencies**: `scikit-learn`, `rake-nltk`, `nltk`

### **2.4 Source Metadata Consistency**
- **Implementation**: Source validation and enrichment
- **Features**:
  - Source name normalization
  - Source credibility scoring
  - Source category classification
  - Source health monitoring

## Priority 3: Monitoring & Reporting (Medium)

### **3.1 Ingestion Statistics Dashboard**
- **Implementation**: Real-time ingestion monitoring
- **Features**:
  - Articles processed per hour/day
  - Duplicates detected and removed
  - Processing success/failure rates
  - Source performance metrics
- **Tools**: Grafana + Prometheus integration

### **3.2 Entity Frequency Reports**
- **Implementation**: Entity analytics and reporting
- **Features**:
  - Top entities by frequency (24h, 7d, 30d)
  - Entity trend analysis
  - Entity relationship networks
  - Export capabilities for analysis
- **Database Views**:
  ```sql
  CREATE VIEW entity_frequency_24h AS
  SELECT entity_text, entity_type, COUNT(*) as frequency
  FROM articles, jsonb_array_elements(person_entities) as entity_text
  WHERE created_at >= NOW() - INTERVAL '24 hours'
  GROUP BY entity_text, entity_type
  ORDER BY frequency DESC;
  ```

### **3.3 Feed Health Metrics**
- **Implementation**: RSS feed monitoring system
- **Features**:
  - Last fetch time per feed
  - Success/failure rates
  - Response time monitoring
  - Feed quality scoring
- **Database Changes**:
  ```sql
  CREATE TABLE feed_health_metrics (
      feed_id SERIAL PRIMARY KEY,
      feed_url VARCHAR(500),
      last_fetch_time TIMESTAMP,
      last_success_time TIMESTAMP,
      success_rate DECIMAL(5,2),
      avg_response_time_ms INTEGER,
      error_count INTEGER DEFAULT 0,
      created_at TIMESTAMP DEFAULT NOW()
  );
  ```

### **3.4 Daily Data Hygiene Reports**
- **Implementation**: Automated quality reporting
- **Features**:
  - Daily summary of ingestion quality
  - Duplicate detection statistics
  - Entity extraction quality metrics
  - Processing pipeline health
  - Email/notification system

## Priority 4: Staging Area & Quality Control (Medium)

### **4.1 Raw Article Staging**
- **Implementation**: Two-tier article storage system
- **Features**:
  - Raw articles stored in staging table
  - Quality verification before promotion
  - Batch promotion to production
  - Staging cleanup and maintenance
- **Database Changes**:
  ```sql
  CREATE TABLE raw_articles_staging (
      staging_id SERIAL PRIMARY KEY,
      title TEXT,
      content TEXT,
      url VARCHAR(500),
      source VARCHAR(255),
      published_date TIMESTAMP,
      raw_data JSONB,
      quality_score DECIMAL(5,2),
      processing_status VARCHAR(50) DEFAULT 'pending',
      created_at TIMESTAMP DEFAULT NOW()
  );
  ```

### **4.2 Quality Verification System**
- **Implementation**: Automated quality checks
- **Features**:
  - Content length validation
  - Language detection verification
  - Duplicate content checking
  - Source credibility assessment
  - Manual review queue for borderline cases

### **4.3 Archiving System**
- **Implementation**: Automated article archiving
- **Features**:
  - Age-based archiving (90+ days)
  - Importance-based retention
  - Cold storage management
  - Archive retrieval system
- **Database Changes**:
  ```sql
  CREATE TABLE archived_articles (
      archive_id SERIAL PRIMARY KEY,
      original_article_id INTEGER,
      archived_at TIMESTAMP DEFAULT NOW(),
      archive_reason VARCHAR(100),
      storage_location VARCHAR(255)
  );
  ```

## Implementation Timeline

### **Week 1: Deduplication System**
- Day 1-2: Content hash and URL deduplication
- Day 3-4: Semantic similarity deduplication
- Day 5: Testing and optimization

### **Week 2: Metadata Enrichment**
- Day 1-2: Language detection and content metrics
- Day 3-4: Keyword extraction and quality scoring
- Day 5: Source metadata consistency

### **Week 3: Monitoring & Reporting**
- Day 1-2: Ingestion statistics dashboard
- Day 3-4: Entity frequency reports and feed health
- Day 5: Daily data hygiene reports

### **Week 4: Staging & Quality Control**
- Day 1-2: Raw article staging system
- Day 3-4: Quality verification and archiving
- Day 5: Integration testing and optimization

## Dependencies to Install

```bash
# Core NLP and ML libraries
pip install spacy sentence-transformers torch transformers

# Text processing and analysis
pip install nltk scikit-learn rake-nltk fasttext

# Language detection
pip install langdetect

# Text similarity
pip install fuzzywuzzy python-Levenshtein

# Monitoring and metrics
pip install prometheus-client grafana-api

# Additional utilities
pip install textstat readability
```

## Database Schema Updates Required

### **Articles Table Extensions**
```sql
-- Deduplication
ALTER TABLE articles ADD COLUMN duplicate_of INTEGER REFERENCES articles(id);
ALTER TABLE articles ADD COLUMN is_duplicate BOOLEAN DEFAULT FALSE;
ALTER TABLE articles ADD COLUMN canonical_url VARCHAR(500);
ALTER TABLE articles ADD COLUMN url_hash VARCHAR(64);

-- Content metrics
ALTER TABLE articles ADD COLUMN detected_language VARCHAR(10);
ALTER TABLE articles ADD COLUMN language_confidence DECIMAL(5,2);
ALTER TABLE articles ADD COLUMN word_count INTEGER;
ALTER TABLE articles ADD COLUMN sentence_count INTEGER;
ALTER TABLE articles ADD COLUMN content_completeness_score DECIMAL(5,2);
ALTER TABLE articles ADD COLUMN readability_score DECIMAL(5,2);

-- Keywords
ALTER TABLE articles ADD COLUMN extracted_keywords TEXT[];
ALTER TABLE articles ADD COLUMN keyword_scores JSONB;
```

### **New Tables**
```sql
-- Feed health monitoring
CREATE TABLE feed_health_metrics (...);

-- Raw article staging
CREATE TABLE raw_articles_staging (...);

-- Archived articles
CREATE TABLE archived_articles (...);

-- Deduplication tracking
CREATE TABLE duplicate_groups (
    group_id SERIAL PRIMARY KEY,
    original_article_id INTEGER REFERENCES articles(id),
    duplicate_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Success Criteria

### **Deduplication System**
- [ ] 95%+ duplicate detection accuracy
- [ ] <100ms duplicate check performance
- [ ] Zero false positive rate for content hashes
- [ ] Configurable similarity thresholds

### **Metadata Enrichment**
- [ ] 99%+ language detection accuracy
- [ ] Complete content metrics for all articles
- [ ] Keyword extraction for 95%+ articles
- [ ] Quality scores with clear validation

### **Monitoring & Reporting**
- [ ] Real-time dashboard updates
- [ ] Daily automated reports
- [ ] Alert system for anomalies
- [ ] Export capabilities for all metrics

### **Quality Control**
- [ ] Staging system processes 1000+ articles/hour
- [ ] Quality verification <5% false positive rate
- [ ] Automated archiving with 99%+ accuracy
- [ ] Manual review queue <24h turnaround

## Next Steps After Completion

Once these missing features are implemented:

1. **Data Quality Validation**: Run comprehensive quality checks
2. **Performance Testing**: Ensure system handles target load
3. **ML Model Preparation**: Create training datasets from processed articles
4. **Summarization Implementation**: Begin ML summarizer development

This build plan ensures the system has a rock-solid foundation for ML summarization with high-quality, well-organized, and properly deduplicated data.
