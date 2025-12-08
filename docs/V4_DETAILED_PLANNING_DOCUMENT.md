# News Intelligence System v4.0 - Detailed Planning Document

## Date: 2025-12-07
## Status: 📋 **COMPREHENSIVE PLANNING**
## Purpose: Detailed design and migration strategy before implementation

---

## 🎯 **Design Intent for v4.0**

### **Core Philosophy**

v4.0 transforms the News Intelligence System from a **single-domain news aggregator** into a **multi-domain intelligence platform** organized like a newspaper, where each section (domain) operates independently while sharing common infrastructure.

### **Key Design Principles**

1. **Domain Isolation with Shared Infrastructure**
   - Each domain (Politics, Finance, Science & Tech) has isolated data storage
   - Shared API codebase that works for all domains
   - No redundant microservices - single codebase, domain-aware routing
   - Common authentication, monitoring, and infrastructure

2. **Topic-Agnostic Architecture**
   - API endpoints accept domain as a parameter: `/api/v4/{domain}/articles`
   - Services are domain-aware but code is shared
   - Database queries automatically scoped to domain schema
   - Frontend components work across all domains

3. **Newspaper-Style Organization**
   - Master navigation: Politics | Finance | Science & Technology
   - Each section has its own articles, topics, storylines
   - Domain-specific features (e.g., Finance has market patterns)
   - Cross-domain search and analytics when needed

4. **Extensibility**
   - Easy to add new domains (Health, Sports, etc.)
   - Domain-specific features don't pollute other domains
   - Shared infrastructure scales with new domains
   - Configuration-driven domain management

---

## 🏗️ **Database Architecture Design**

### **Current State (v3.0)**

```
public schema
├── articles (all articles)
├── topics (all topics)
├── storylines (all storylines)
├── rss_feeds (all feeds)
├── article_topic_assignments
├── storyline_articles
└── ... (other tables)
```

**Issues:**
- All data mixed together
- No domain separation
- Hard to scale per domain
- Cannot isolate domain-specific features

### **Target State (v4.0)**

```
public schema (shared)
├── domains (domain configuration)
├── users (shared users)
├── user_preferences (cross-domain)
├── system_config (shared config)
└── analytics (cross-domain)

politics schema (domain-specific)
├── articles
├── topics
├── storylines
├── rss_feeds
├── article_topic_assignments
├── storyline_articles
└── ... (politics-specific tables)

finance schema (domain-specific)
├── articles
├── topics
├── storylines
├── rss_feeds
├── article_topic_assignments
├── storyline_articles
├── market_patterns (finance-specific)
├── corporate_announcements (finance-specific)
├── financial_indicators (finance-specific)
└── ... (finance-specific tables)

science_tech schema (domain-specific)
├── articles
├── topics
├── storylines
├── rss_feeds
├── article_topic_assignments
├── storyline_articles
└── ... (science-tech-specific tables)
```

---

## 📊 **Detailed Database Migration Strategy**

### **Phase 1: Domain Infrastructure Setup**

#### **Step 1.1: Create Domains Configuration Table**

```sql
-- Migration: 122_domain_silo_infrastructure.sql

-- Domains configuration table (in public schema)
CREATE TABLE IF NOT EXISTS domains (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) UNIQUE NOT NULL,  -- 'politics', 'finance', 'science-tech'
    name VARCHAR(100) NOT NULL,              -- 'Politics', 'Finance', 'Science & Technology'
    description TEXT,
    schema_name VARCHAR(50) NOT NULL,         -- 'politics', 'finance', 'science_tech'
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    config JSONB DEFAULT '{}',                -- Domain-specific configuration
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT valid_domain_key CHECK (domain_key ~ '^[a-z0-9-]+$'),
    CONSTRAINT valid_schema_name CHECK (schema_name ~ '^[a-z0-9_]+$')
);

-- Indexes
CREATE INDEX idx_domains_key ON domains(domain_key);
CREATE INDEX idx_domains_active ON domains(is_active);

-- Insert default domains
INSERT INTO domains (domain_key, name, schema_name, display_order, description) VALUES
('politics', 'Politics', 'politics', 1, 'Political news, government, elections, and policy analysis'),
('finance', 'Finance', 'finance', 2, 'Financial markets, corporate announcements, market research, and economic analysis'),
('science-tech', 'Science & Technology', 'science_tech', 3, 'Scientific research, technology news, innovation, and industry analysis')
ON CONFLICT (domain_key) DO NOTHING;

-- Domain metadata table for tracking domain statistics
CREATE TABLE IF NOT EXISTS domain_metadata (
    domain_id INTEGER PRIMARY KEY REFERENCES domains(id) ON DELETE CASCADE,
    article_count INTEGER DEFAULT 0,
    topic_count INTEGER DEFAULT 0,
    storyline_count INTEGER DEFAULT 0,
    feed_count INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**Design Intent:**
- Centralized domain configuration
- Easy to add/disable domains
- Domain-specific settings in JSONB config
- Metadata tracking for each domain

**Cascading Issues:**
- Need to update all services to check domains table
- Domain validation required in all API endpoints
- Frontend needs domain list for navigation

---

#### **Step 1.2: Create Domain Schemas**

```sql
-- Create schemas for each domain
CREATE SCHEMA IF NOT EXISTS politics;
CREATE SCHEMA IF NOT EXISTS finance;
CREATE SCHEMA IF NOT EXISTS science_tech;

-- Grant permissions
GRANT USAGE ON SCHEMA politics TO newsapp;
GRANT USAGE ON SCHEMA finance TO newsapp;
GRANT USAGE ON SCHEMA science_tech TO newsapp;

-- Grant create privileges for future migrations
GRANT CREATE ON SCHEMA politics TO newsapp;
GRANT CREATE ON SCHEMA finance TO newsapp;
GRANT CREATE ON SCHEMA science_tech TO newsapp;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA politics GRANT ALL ON TABLES TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA finance GRANT ALL ON TABLES TO newsapp;
ALTER DEFAULT PRIVILEGES IN SCHEMA science_tech GRANT ALL ON TABLES TO newsapp;
```

**Design Intent:**
- Clean namespace separation
- Easy to backup/restore per domain
- Can eventually split to separate databases if needed
- Permissions scoped per domain

**Cascading Issues:**
- All queries must specify schema
- Connection pooling needs schema context
- Migrations must run per schema
- Backup/restore scripts need schema awareness

---

#### **Step 1.3: Create Domain-Specific Table Structures**

```sql
-- Politics schema tables (migrate from public)
-- We'll create empty tables with same structure first

-- Articles table
CREATE TABLE politics.articles (
    LIKE public.articles INCLUDING ALL
);

-- Topics table
CREATE TABLE politics.topics (
    LIKE public.topics INCLUDING ALL
);

-- Storylines table
CREATE TABLE politics.storylines (
    LIKE public.storylines INCLUDING ALL
);

-- RSS Feeds table
CREATE TABLE politics.rss_feeds (
    LIKE public.rss_feeds INCLUDING ALL
);

-- Article-Topic Assignments
CREATE TABLE politics.article_topic_assignments (
    LIKE public.article_topic_assignments INCLUDING ALL
);

-- Storyline Articles
CREATE TABLE politics.storyline_articles (
    LIKE public.storyline_articles INCLUDING ALL
);

-- Topic Clusters
CREATE TABLE politics.topic_clusters (
    LIKE public.topic_clusters INCLUDING ALL
);

-- Topic Learning History
CREATE TABLE politics.topic_learning_history (
    LIKE public.topic_learning_history INCLUDING ALL
);

-- Repeat for finance schema
CREATE TABLE finance.articles (
    LIKE public.articles INCLUDING ALL
);
-- ... (all same tables)

-- Finance-specific tables
CREATE TABLE finance.market_patterns (
    id SERIAL PRIMARY KEY,
    pattern_type VARCHAR(50) NOT NULL,  -- 'price_trend', 'volume_spike', 'correlation', etc.
    pattern_name VARCHAR(200) NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    time_window_days INTEGER NOT NULL,
    confidence_score DECIMAL(3,2) CHECK (confidence_score >= 0.0 AND confidence_score <= 1.0),
    pattern_data JSONB DEFAULT '{}',  -- Pattern-specific data
    affected_companies TEXT[],        -- Array of company names
    affected_articles INTEGER[],       -- Array of article IDs
    market_impact DECIMAL(5,2),       -- Percentage impact
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE finance.corporate_announcements (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(200) NOT NULL,
    ticker_symbol VARCHAR(10),
    announcement_type VARCHAR(50) NOT NULL,  -- 'earnings', 'merger', 'product', 'executive', 'regulatory'
    announcement_date DATE NOT NULL,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    source_url TEXT,
    source_type VARCHAR(50),  -- 'sec_filing', 'press_release', 'news_article'
    filing_type VARCHAR(50),   -- For SEC filings: '10-K', '10-Q', '8-K', etc.
    sentiment_score DECIMAL(3,2),  -- -1.0 to 1.0
    market_impact DECIMAL(5,2),   -- Percentage price change
    article_id INTEGER,             -- Link to finance.articles if from news
    raw_data JSONB,                 -- Original announcement data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE finance.financial_indicators (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(200),
    ticker_symbol VARCHAR(10),
    indicator_type VARCHAR(50) NOT NULL,  -- 'revenue', 'profit', 'market_cap', etc.
    value DECIMAL(15,2),
    currency VARCHAR(10) DEFAULT 'USD',
    period_start DATE,
    period_end DATE,
    reported_at TIMESTAMP WITH TIME ZONE,
    source VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Science & Tech schema (same base tables)
CREATE TABLE science_tech.articles (
    LIKE public.articles INCLUDING ALL
);
-- ... (all same tables)
```

**Design Intent:**
- Same structure across domains for consistency
- Domain-specific tables only where needed
- Easy to query across domains when needed
- Finance gets specialized tables for market analysis

**Cascading Issues:**
- Foreign key constraints need schema qualification
- Triggers must be recreated per schema
- Indexes must be created per schema
- Sequences need schema qualification

---

### **Phase 2: Data Migration**

#### **Step 2.1: Categorize Existing Data**

**Challenge:** We need to determine which existing articles/feeds belong to which domain.

**Strategy:**
1. **Feeds First** - Categorize feeds by domain
2. **Articles Follow Feeds** - Articles inherit domain from their feed
3. **Manual Review** - Flag ambiguous items for review

```sql
-- Add domain column to existing rss_feeds (temporary, for migration)
ALTER TABLE public.rss_feeds ADD COLUMN IF NOT EXISTS domain_key VARCHAR(50);

-- Categorize feeds based on existing category field
UPDATE public.rss_feeds 
SET domain_key = CASE
    WHEN category IN ('politics', 'government', 'election') THEN 'politics'
    WHEN category IN ('economy', 'business', 'finance', 'markets') THEN 'finance'
    WHEN category IN ('tech', 'science', 'innovation', 'technology') THEN 'science-tech'
    ELSE 'politics'  -- Default to politics for now
END
WHERE domain_key IS NULL;

-- Add domain to articles based on feed
ALTER TABLE public.articles ADD COLUMN IF NOT EXISTS domain_key VARCHAR(50);

UPDATE public.articles a
SET domain_key = f.domain_key
FROM public.rss_feeds f
WHERE a.source_domain = f.name OR a.url LIKE '%' || f.url || '%'
AND a.domain_key IS NULL;

-- For articles without matching feed, use content analysis
-- This is a placeholder - actual implementation would use ML
UPDATE public.articles
SET domain_key = 'politics'  -- Default, to be refined
WHERE domain_key IS NULL;
```

**Design Intent:**
- Preserve all existing data
- Automatic categorization where possible
- Manual review for edge cases
- Audit trail of categorization

**Cascading Issues:**
- Some articles may be miscategorized
- Need review process for ambiguous items
- May need to split articles that span multiple domains
- Feed categorization may need refinement

---

#### **Step 2.2: Migrate Data to Domain Schemas**

```sql
-- Migration script: Migrate politics data
INSERT INTO politics.articles 
SELECT * FROM public.articles 
WHERE domain_key = 'politics';

INSERT INTO politics.topics
SELECT * FROM public.topics
WHERE id IN (
    SELECT DISTINCT topic_id 
    FROM public.article_topic_assignments ata
    JOIN public.articles a ON ata.article_id = a.id
    WHERE a.domain_key = 'politics'
);

INSERT INTO politics.article_topic_assignments
SELECT ata.* 
FROM public.article_topic_assignments ata
JOIN public.articles a ON ata.article_id = a.id
WHERE a.domain_key = 'politics';

INSERT INTO politics.storylines
SELECT s.* 
FROM public.storylines s
WHERE s.id IN (
    SELECT DISTINCT storyline_id
    FROM public.storyline_articles sa
    JOIN public.articles a ON sa.article_id = a.id
    WHERE a.domain_key = 'politics'
);

INSERT INTO politics.storyline_articles
SELECT sa.*
FROM public.storyline_articles sa
JOIN public.articles a ON sa.article_id = a.id
WHERE a.domain_key = 'politics';

INSERT INTO politics.rss_feeds
SELECT * FROM public.rss_feeds
WHERE domain_key = 'politics';

-- Repeat for finance and science-tech domains
-- (Similar INSERT statements with appropriate domain_key filter)
```

**Design Intent:**
- Complete data migration
- Preserve all relationships
- Maintain referential integrity
- Audit migration success

**Cascading Issues:**
- **ID Conflicts**: Article IDs may conflict when inserting into domain schemas
- **Foreign Key Issues**: Need to remap IDs to maintain relationships
- **Orphaned Data**: Some relationships may break if data is split
- **Migration Time**: Large datasets may take significant time
- **Rollback Complexity**: Need to preserve original data during migration

---

#### **Step 2.3: Handle ID Remapping**

**Critical Issue:** When moving articles from public.articles to politics.articles, the IDs change, breaking foreign key relationships.

**Solution Options:**

**Option A: Preserve Original IDs (Recommended)**
```sql
-- Use SERIAL but set sequence to continue from max ID
SELECT setval('politics.articles_id_seq', 
    (SELECT COALESCE(MAX(id), 0) FROM politics.articles));

-- Or use explicit IDs during migration
INSERT INTO politics.articles (id, title, content, ...)
SELECT id, title, content, ...
FROM public.articles 
WHERE domain_key = 'politics';
```

**Option B: ID Mapping Table**
```sql
-- Create mapping tables
CREATE TABLE politics.id_mapping_articles (
    old_id INTEGER,
    new_id INTEGER PRIMARY KEY
);

-- Migrate with mapping
INSERT INTO politics.articles (title, content, ...)
SELECT title, content, ...
FROM public.articles 
WHERE domain_key = 'politics'
RETURNING id INTO mapping table;

-- Update foreign keys using mapping
UPDATE politics.article_topic_assignments
SET article_id = (
    SELECT new_id FROM politics.id_mapping_articles 
    WHERE old_id = article_id
);
```

**Recommendation:** **Option A** - Preserve IDs to avoid remapping complexity.

**Design Intent:**
- Maintain referential integrity
- Avoid complex ID remapping
- Preserve existing relationships
- Simplify rollback if needed

**Cascading Issues:**
- Sequence management across schemas
- Need to coordinate ID ranges
- Future cross-domain queries need schema qualification
- ID uniqueness only within schema (not across schemas)

---

### **Phase 3: Foreign Key and Constraint Management**

#### **Step 3.1: Update Foreign Key Constraints**

**Issue:** Foreign keys in domain schemas reference tables in the same schema, but some may reference public schema.

```sql
-- Example: article_topic_assignments references articles
-- In politics schema:
ALTER TABLE politics.article_topic_assignments
DROP CONSTRAINT IF EXISTS article_topic_assignments_article_id_fkey;

ALTER TABLE politics.article_topic_assignments
ADD CONSTRAINT article_topic_assignments_article_id_fkey
FOREIGN KEY (article_id) 
REFERENCES politics.articles(id) 
ON DELETE CASCADE;

-- Repeat for all foreign keys in each domain schema
```

**Design Intent:**
- Maintain referential integrity within domains
- Isolate domains from each other
- Enable cascade deletes within domain
- Prevent cross-domain foreign keys

**Cascading Issues:**
- **Cross-Domain References**: Some data may legitimately reference other domains
- **Shared Resources**: Users, system config may need cross-domain access
- **Cascade Behavior**: Need to define cascade rules per domain
- **Constraint Validation**: All constraints must be recreated per schema

---

#### **Step 3.2: Recreate Indexes and Triggers**

```sql
-- Recreate all indexes per schema
CREATE INDEX idx_politics_articles_published_at 
ON politics.articles(published_at DESC);

CREATE INDEX idx_politics_articles_source_domain 
ON politics.articles(source_domain);

CREATE INDEX idx_politics_article_topic_assignments_article_id 
ON politics.article_topic_assignments(article_id);

CREATE INDEX idx_politics_article_topic_assignments_topic_id 
ON politics.article_topic_assignments(topic_id);

-- Repeat for all indexes in each domain schema

-- Recreate triggers
CREATE TRIGGER update_politics_articles_updated_at
BEFORE UPDATE ON politics.articles
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Repeat for all triggers in each domain schema
```

**Design Intent:**
- Maintain performance characteristics
- Preserve automatic timestamp updates
- Keep data integrity checks
- Ensure consistent behavior across domains

**Cascading Issues:**
- **Trigger Functions**: Must be in public schema or recreated per schema
- **Function Dependencies**: Functions may need schema qualification
- **Performance**: Index creation on large tables is slow
- **Maintenance**: Future schema changes need to be applied to all domains

---

### **Phase 4: API Service Layer Changes**

#### **Step 4.1: Domain-Aware Service Base Class**

```python
# api/shared/services/domain_aware_service.py

from typing import Optional
from shared.database.connection import get_db_connection
import logging

logger = logging.getLogger(__name__)

class DomainAwareService:
    """
    Base class for all domain-aware services.
    Provides domain context and schema management.
    """
    
    def __init__(self, domain: str):
        """
        Initialize service with domain context.
        
        Args:
            domain: Domain key (e.g., 'politics', 'finance', 'science-tech')
        """
        self.domain = domain
        self.schema = self._normalize_schema_name(domain)
        self._validate_domain()
    
    def _normalize_schema_name(self, domain: str) -> str:
        """Convert domain key to schema name."""
        return domain.replace('-', '_')
    
    def _validate_domain(self):
        """Validate that domain exists and is active."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, schema_name, is_active 
                    FROM domains 
                    WHERE domain_key = %s
                """, (self.domain,))
                result = cur.fetchone()
                
                if not result:
                    raise ValueError(f"Domain '{self.domain}' not found")
                
                if not result[2]:  # is_active
                    raise ValueError(f"Domain '{self.domain}' is not active")
                
                self.domain_id = result[0]
                self.schema = result[1]  # Use schema from database
        finally:
            conn.close()
    
    def get_db_connection(self):
        """
        Get database connection with domain schema context.
        Sets search_path to domain schema + public.
        """
        conn = get_db_connection()
        with conn.cursor() as cur:
            # Set search path to domain schema first, then public
            cur.execute(f"SET search_path TO {self.schema}, public")
        return conn
    
    def execute_in_domain_schema(self, query: str, params: tuple = None):
        """
        Execute query in domain schema context.
        Automatically prefixes table names with schema if needed.
        """
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cur:
                # Replace table references with schema-qualified names
                qualified_query = self._qualify_table_names(query)
                cur.execute(qualified_query, params)
                return cur.fetchall()
        finally:
            conn.close()
    
    def _qualify_table_names(self, query: str) -> str:
        """
        Qualify table names with schema.
        This is a simplified version - may need more sophisticated parsing.
        """
        # List of tables that should be schema-qualified
        domain_tables = ['articles', 'topics', 'storylines', 'rss_feeds', 
                        'article_topic_assignments', 'storyline_articles']
        
        qualified_query = query
        for table in domain_tables:
            # Replace unqualified table references
            pattern = f'\\b{table}\\b'
            replacement = f'{self.schema}.{table}'
            qualified_query = re.sub(pattern, replacement, qualified_query)
        
        return qualified_query
```

**Design Intent:**
- Single base class for all domain services
- Automatic schema management
- Domain validation
- Consistent query execution

**Cascading Issues:**
- **Query Parsing**: Table name qualification is complex
- **Performance**: Setting search_path per connection may impact pooling
- **Error Handling**: Need clear errors for invalid domains
- **Testing**: Need to test with all domains

---

#### **Step 4.2: Refactor Existing Services**

**Example: ArticleService**

```python
# api/domains/news_aggregation/services/article_service.py

from shared.services.domain_aware_service import DomainAwareService

class ArticleService(DomainAwareService):
    """Article service that works for any domain."""
    
    def __init__(self, domain: str = 'politics'):
        super().__init__(domain)
    
    def get_articles(self, limit: int = 50, offset: int = 0, filters: dict = None):
        """Get articles from current domain."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cur:
                query = f"""
                    SELECT * FROM {self.schema}.articles
                    WHERE 1=1
                """
                params = []
                
                # Add filters
                if filters:
                    if filters.get('source_domain'):
                        query += " AND source_domain = %s"
                        params.append(filters['source_domain'])
                    # ... more filters
                
                query += " ORDER BY published_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                
                cur.execute(query, params)
                return cur.fetchall()
        finally:
            conn.close()
    
    def create_article(self, article_data: dict):
        """Create article in current domain."""
        conn = self.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO {self.schema}.articles 
                    (title, content, url, source_domain, published_at, ...)
                    VALUES (%s, %s, %s, %s, %s, ...)
                    RETURNING id
                """, (article_data['title'], ...))
                return cur.fetchone()[0]
        finally:
            conn.close()
```

**Design Intent:**
- Services work for any domain
- Domain passed at initialization
- All queries scoped to domain schema
- Consistent interface across domains

**Cascading Issues:**
- **Service Instantiation**: Need domain context everywhere
- **Caching**: Cache keys must include domain
- **Background Jobs**: Need domain context in async tasks
- **API Endpoints**: Must extract domain from request

---

#### **Step 4.3: Update API Routers**

```python
# api/domains/news_aggregation/routes/news_aggregation.py

from fastapi import APIRouter, Path, Query
from shared.services.domain_aware_service import DomainAwareService
from domains.news_aggregation.services.article_service import ArticleService

router = APIRouter(
    prefix="/api/v4",
    tags=["News Aggregation"]
)

@router.get("/{domain}/articles")
async def get_domain_articles(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """Get articles for specific domain."""
    try:
        service = ArticleService(domain=domain)
        articles = service.get_articles(limit=limit, offset=offset)
        return {
            "success": True,
            "data": {
                "articles": articles,
                "domain": domain,
                "count": len(articles)
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

**Design Intent:**
- Domain as path parameter
- Automatic domain validation
- Consistent response format
- Error handling for invalid domains

**Cascading Issues:**
- **Route Conflicts**: Need to ensure domain doesn't conflict with other routes
- **Validation**: Regex validation may need updating as domains are added
- **Documentation**: OpenAPI docs need domain examples
- **Testing**: Need to test all domains

---

### **Phase 5: Feed Management Changes**

#### **Step 5.1: Domain-Aware Feed Collection**

```python
# api/collectors/rss_collector.py

class RSSCollector:
    def collect_from_feed(self, feed_id: int):
        """Collect articles from feed and route to domain."""
        # Get feed with domain
        feed = self.get_feed(feed_id)
        domain = feed.domain_key
        
        if not domain:
            raise ValueError(f"Feed {feed_id} has no domain assigned")
        
        # Fetch articles
        articles = self.fetch_articles(feed)
        
        # Save to domain-specific schema
        article_service = ArticleService(domain=domain)
        for article in articles:
            article_service.create_article(article)
```

**Design Intent:**
- Feeds have domain assignment
- Articles automatically routed to correct domain
- No manual domain assignment needed
- Consistent with feed categorization

**Cascading Issues:**
- **Feed Categorization**: Need to categorize all existing feeds
- **Multi-Domain Feeds**: Some feeds may span multiple domains
- **Feed Updates**: Domain changes require data migration
- **Collection Jobs**: Need domain context in background jobs

---

## ⚠️ **Critical Cascading Issues to Plan For**

### **1. ID Management Across Schemas**

**Issue:** Article IDs are unique within a schema but not across schemas. This affects:
- Cross-domain queries
- URL generation
- Caching keys
- Analytics aggregation

**Solutions:**
- Use composite keys: `{domain}:{id}` for cross-domain references
- Add domain prefix to all external IDs
- Update all ID-based lookups to include domain
- Modify URL structure: `/politics/articles/123` vs `/finance/articles/123`

**Impact:** High - affects all ID-based operations

---

### **2. Foreign Key Constraints**

**Issue:** Foreign keys within a domain are fine, but cross-domain references break.

**Examples:**
- User preferences may reference articles from multiple domains
- Analytics may aggregate across domains
- Search may span domains

**Solutions:**
- Keep cross-domain references in public schema
- Use domain-qualified IDs for cross-domain references
- Create junction tables in public schema for cross-domain relationships
- Use application-level referential integrity for cross-domain

**Impact:** High - requires careful design of cross-domain features

---

### **3. Sequence Management**

**Issue:** Each schema has its own sequences. Need to coordinate to avoid conflicts if ever merging.

**Solutions:**
- Use different ID ranges per domain (e.g., politics: 1-10M, finance: 10M-20M)
- Or accept that IDs are only unique within domain
- Document that IDs are domain-scoped

**Impact:** Medium - mainly affects future cross-domain operations

---

### **4. Query Performance**

**Issue:** Schema-qualified queries may have different performance characteristics.

**Solutions:**
- Ensure indexes are created in each schema
- Monitor query performance per domain
- Use connection pooling with schema context
- Consider materialized views for cross-domain analytics

**Impact:** Medium - needs monitoring and optimization

---

### **5. Migration Rollback**

**Issue:** If migration fails, need to rollback without data loss.

**Solutions:**
- Keep original public schema data until migration verified
- Create backup before migration
- Test migration on staging first
- Have rollback scripts ready
- Use transactions for atomic migration steps

**Impact:** Critical - must have rollback plan

---

### **6. Background Jobs and Automation**

**Issue:** Background jobs need domain context.

**Examples:**
- RSS collection jobs
- Topic clustering jobs
- Daily batch processing
- ML processing

**Solutions:**
- Pass domain to all background jobs
- Create domain-specific job queues
- Update AutomationManager to be domain-aware
- Schedule jobs per domain

**Impact:** High - affects all automation

---

### **7. Caching Strategy**

**Issue:** Cache keys must include domain to avoid collisions.

**Solutions:**
- Prefix all cache keys with domain: `politics:article:123`
- Update all cache operations
- Clear cache per domain when needed
- Monitor cache hit rates per domain

**Impact:** Medium - requires cache key updates

---

### **8. Search and Analytics**

**Issue:** Cross-domain search and analytics need special handling.

**Solutions:**
- Create unified search view across schemas
- Use UNION queries for cross-domain searches
- Create materialized views for analytics
- Consider Elasticsearch for cross-domain search

**Impact:** High - affects user experience

---

### **9. Feed Categorization Accuracy**

**Issue:** Some feeds/articles may be miscategorized.

**Solutions:**
- Manual review process
- ML-based categorization
- User feedback mechanism
- Easy recategorization process
- Audit log of categorizations

**Impact:** Medium - affects data quality

---

### **10. Finance-Specific Data Sources**

**Issue:** Finance domain needs different data sources (SEC filings, corporate announcements).

**Solutions:**
- Create finance-specific collectors
- Parse SEC EDGAR data
- Integrate financial data APIs
- Build corporate announcement parser
- Create market data connectors

**Impact:** High - new functionality required

---

### **11. Frontend Routing**

**Issue:** Frontend needs domain-aware routing.

**Solutions:**
- Update all routes to include domain
- Create domain selector component
- Update navigation structure
- Handle domain switching
- Preserve domain context in URLs

**Impact:** High - affects all frontend pages

---

### **12. API Versioning and Backward Compatibility**

**Issue:** Existing API clients expect old endpoints.

**Solutions:**
- Maintain v3 endpoints during transition
- Redirect v3 to politics domain
- Deprecation timeline
- Client migration guide
- Version negotiation

**Impact:** Medium - affects API consumers

---

## 📋 **Implementation Checklist**

### **Pre-Implementation**
- [ ] Review and approve architecture
- [ ] Create detailed test plan
- [ ] Set up staging environment
- [ ] Create database backup
- [ ] Document rollback procedures

### **Database Migration**
- [ ] Create domains table
- [ ] Create domain schemas
- [ ] Create domain-specific tables
- [ ] Categorize existing feeds
- [ ] Migrate data to domains
- [ ] Verify data integrity
- [ ] Create indexes per schema
- [ ] Recreate triggers per schema
- [ ] Update foreign keys

### **API Refactoring**
- [ ] Create DomainAwareService base
- [ ] Refactor ArticleService
- [ ] Refactor TopicService
- [ ] Refactor StorylineService
- [ ] Update all routers
- [ ] Add domain validation
- [ ] Update API documentation
- [ ] Test all endpoints

### **Feed Management**
- [ ] Add domain to feeds table
- [ ] Categorize existing feeds
- [ ] Set up finance feeds
- [ ] Update RSS collector
- [ ] Test feed routing

### **Frontend**
- [ ] Create domain navigation
- [ ] Update routing
- [ ] Create domain context
- [ ] Update API service calls
- [ ] Create finance pages
- [ ] Test domain switching

### **Finance Features**
- [ ] Corporate announcement collector
- [ ] Market pattern analyzer
- [ ] Finance visualizations
- [ ] Integration testing

### **Testing**
- [ ] Unit tests for domain services
- [ ] Integration tests per domain
- [ ] Cross-domain tests
- [ ] Performance tests
- [ ] Migration tests
- [ ] Rollback tests

---

## 🎯 **Success Criteria**

- [ ] All domains operate independently
- [ ] No data leakage between domains
- [ ] Finance domain fully functional
- [ ] Existing politics data works unchanged
- [ ] API response times maintained
- [ ] Zero data loss during migration
- [ ] Rollback tested and verified
- [ ] All tests passing

---

*Planning Document Date: 2025-12-07*
*Status: Ready for Review and Approval*

