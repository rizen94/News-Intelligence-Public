# News Intelligence System v4.0 - Migration Plan

## Date: 2025-12-07
## Status: 📋 **PLANNING**

---

## 🎯 **Migration Overview**

Migrate from single-domain system to multi-domain silo architecture while maintaining zero downtime and backward compatibility during transition.

---

## 📅 **Migration Phases**

### **Phase 1: Database Foundation** (Week 1)

#### **1.1 Create Domain Infrastructure**
```sql
-- Create domains table
CREATE TABLE domains (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    schema_name VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Insert default domains
INSERT INTO domains (domain_key, name, schema_name, display_order) VALUES
('politics', 'Politics', 'politics', 1),
('finance', 'Finance', 'finance', 2),
('science-tech', 'Science & Technology', 'science_tech', 3);
```

#### **1.2 Create Domain Schemas**
```sql
-- Create schemas for each domain
CREATE SCHEMA IF NOT EXISTS politics;
CREATE SCHEMA IF NOT EXISTS finance;
CREATE SCHEMA IF NOT EXISTS science_tech;

-- Grant permissions
GRANT USAGE ON SCHEMA politics TO newsapp;
GRANT USAGE ON SCHEMA finance TO newsapp;
GRANT USAGE ON SCHEMA science_tech TO newsapp;
```

#### **1.3 Create Domain-Specific Tables**
```sql
-- Politics schema (migrate existing tables)
CREATE TABLE politics.articles AS SELECT * FROM public.articles WHERE 1=0;
CREATE TABLE politics.topics AS SELECT * FROM public.topics WHERE 1=0;
CREATE TABLE politics.storylines AS SELECT * FROM public.storylines WHERE 1=0;
-- ... etc

-- Finance schema (new tables)
CREATE TABLE finance.articles (LIKE public.articles INCLUDING ALL);
CREATE TABLE finance.topics (LIKE public.topics INCLUDING ALL);
CREATE TABLE finance.storylines (LIKE public.storylines INCLUDING ALL);
CREATE TABLE finance.market_patterns (
    id SERIAL PRIMARY KEY,
    pattern_type VARCHAR(50) NOT NULL,
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    confidence_score DECIMAL(3,2),
    pattern_data JSONB,
    -- ... finance-specific fields
);
CREATE TABLE finance.corporate_announcements (
    id SERIAL PRIMARY KEY,
    company_name VARCHAR(200),
    announcement_type VARCHAR(50),
    announcement_date DATE,
    content TEXT,
    source_url TEXT,
    -- ... finance-specific fields
);

-- Science & Tech schema
CREATE TABLE science_tech.articles (LIKE public.articles INCLUDING ALL);
CREATE TABLE science_tech.topics (LIKE public.topics INCLUDING ALL);
CREATE TABLE science_tech.storylines (LIKE public.storylines INCLUDING ALL);
```

#### **1.4 Migrate Existing Data**
```sql
-- Migrate existing articles to politics (assuming they're political)
INSERT INTO politics.articles SELECT * FROM public.articles;
INSERT INTO politics.topics SELECT * FROM public.topics;
INSERT INTO politics.storylines SELECT * FROM public.storylines;
-- ... etc

-- Keep public schema for shared tables only
```

---

### **Phase 2: API Refactoring** (Week 2-3)

#### **2.1 Create Domain-Aware Base Classes**
```python
# api/shared/services/domain_aware_service.py
class DomainAwareService:
    """Base service for domain-aware operations"""
    
    def __init__(self, domain: str):
        self.domain = domain
        self.schema = self._normalize_schema_name(domain)
        self.validate_domain()
    
    def _normalize_schema_name(self, domain: str) -> str:
        """Convert domain key to schema name"""
        return domain.replace('-', '_')
    
    def validate_domain(self):
        """Validate domain exists"""
        # Check domains table
        pass
    
    def get_db_connection(self):
        """Get connection with schema context"""
        conn = get_db_connection()
        # Set search_path to domain schema
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {self.schema}, public")
        return conn
```

#### **2.2 Refactor Existing Services**
```python
# api/domains/content_analysis/services/article_service.py
class ArticleService(DomainAwareService):
    def __init__(self, domain: str = 'politics'):
        super().__init__(domain)
    
    def get_articles(self, limit: int = 50, offset: int = 0):
        conn = self.get_db_connection()
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT * FROM {self.schema}.articles
                ORDER BY published_at DESC
                LIMIT %s OFFSET %s
            """, (limit, offset))
            return cur.fetchall()
```

#### **2.3 Update Routers**
```python
# api/domains/news_aggregation/routes/news_aggregation.py
@router.get("/{domain}/articles")
async def get_domain_articles(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    limit: int = Query(50),
    offset: int = Query(0)
):
    service = ArticleService(domain=domain)
    articles = service.get_articles(limit=limit, offset=offset)
    return {"success": True, "data": articles}
```

#### **2.4 Add Domain Validation Middleware**
```python
# api/middleware/domain_validation.py
async def validate_domain(request: Request, call_next):
    """Validate domain parameter in requests"""
    # Check if domain exists in domains table
    # Set domain context for request
    pass
```

---

### **Phase 3: Feed Categorization** (Week 4)

#### **3.1 Add Domain to Feeds**
```sql
-- Add domain column to feeds table
ALTER TABLE rss_feeds ADD COLUMN domain VARCHAR(50);
ALTER TABLE rss_feeds ADD CONSTRAINT fk_domain 
    FOREIGN KEY (domain) REFERENCES domains(domain_key);

-- Categorize existing feeds
UPDATE rss_feeds SET domain = 'politics' WHERE category LIKE '%politics%';
UPDATE rss_feeds SET domain = 'science-tech' WHERE category LIKE '%tech%' OR category LIKE '%science%';
```

#### **3.2 Set Up Finance Feeds**
```sql
-- Add finance feeds
INSERT INTO rss_feeds (name, url, domain, is_active) VALUES
('SEC EDGAR Filings', 'https://www.sec.gov/cgi-bin/browse-edgar', 'finance', true),
('Financial Times', 'https://www.ft.com/rss', 'finance', true),
('Bloomberg Finance', 'https://www.bloomberg.com/feeds', 'finance', true),
-- ... more finance feeds
```

#### **3.3 Update RSS Collector**
```python
# api/collectors/rss_collector.py
class RSSCollector:
    def collect_from_feed(self, feed_id: int):
        # Get feed domain
        feed = get_feed(feed_id)
        domain = feed.domain
        
        # Route articles to domain-specific schema
        articles = self.fetch_articles(feed)
        self.save_articles(articles, domain=domain)
    
    def save_articles(self, articles, domain: str):
        """Save articles to domain-specific schema"""
        schema = domain.replace('-', '_')
        # Insert into {schema}.articles
```

---

### **Phase 4: Frontend Reorganization** (Week 5-6)

#### **4.1 Create Domain Navigation**
```typescript
// web/src/config/domains.ts
export const domains = [
  { key: 'politics', name: 'Politics', icon: 'AccountBalance' },
  { key: 'finance', name: 'Finance', icon: 'TrendingUp' },
  { key: 'science-tech', name: 'Science & Technology', icon: 'Science' },
];

// web/src/components/Navigation/DomainNavigation.tsx
export const DomainNavigation = () => {
  return (
    <Tabs value={currentDomain}>
      {domains.map(domain => (
        <Tab 
          key={domain.key}
          label={domain.name}
          onClick={() => navigate(`/${domain.key}`)}
        />
      ))}
    </Tabs>
  );
};
```

#### **4.2 Update Routing**
```typescript
// web/src/App.tsx
<Routes>
  <Route path="/:domain/articles" element={<Articles />} />
  <Route path="/:domain/topics" element={<Topics />} />
  <Route path="/:domain/storylines" element={<Storylines />} />
  <Route path="/finance/market-research" element={<MarketResearch />} />
  <Route path="/finance/corporate-announcements" element={<CorporateAnnouncements />} />
  {/* ... */}
</Routes>
```

#### **4.3 Create Domain Context**
```typescript
// web/src/contexts/DomainContext.tsx
export const DomainContext = createContext<{
  domain: string;
  setDomain: (domain: string) => void;
}>({
  domain: 'politics',
  setDomain: () => {},
});
```

#### **4.4 Update API Service**
```typescript
// web/src/services/apiService.ts
export const apiService = {
  getArticles: async(domain: string, params: any) => {
    const response = await api.get(`/api/v4/${domain}/articles`, { params });
    return response.data;
  },
  // ... other domain-aware methods
};
```

---

### **Phase 5: Finance Features** (Week 7-8)

#### **5.1 Corporate Announcement Collector**
```python
# api/domains/finance/collectors/corporate_announcements.py
class CorporateAnnouncementCollector:
    def collect_sec_filings(self):
        """Collect SEC EDGAR filings"""
        # Parse SEC RSS feeds
        # Extract corporate announcements
        # Save to finance.corporate_announcements
        pass
    
    def collect_press_releases(self):
        """Collect corporate press releases"""
        # Parse corporate RSS feeds
        # Extract announcements
        # Save to finance.corporate_announcements
        pass
```

#### **5.2 Market Pattern Analysis**
```python
# api/domains/finance/services/market_pattern_analyzer.py
class MarketPatternAnalyzer:
    def detect_patterns(self, time_window: int = 30):
        """Detect market patterns from announcements"""
        # Analyze corporate announcements
        # Detect price correlations
        # Identify volume patterns
        # Save patterns to finance.market_patterns
        pass
    
    def analyze_sentiment_impact(self):
        """Analyze sentiment impact on market"""
        # Correlate announcement sentiment with market movement
        # Build predictive models
        pass
```

#### **5.3 Finance-Specific UI**
```typescript
// web/src/pages/Finance/MarketResearch.tsx
export const MarketResearch = () => {
  // Market pattern visualizations
  // Corporate announcement timeline
  // Sentiment analysis charts
  // Pattern detection results
};
```

---

## 🔄 **Backward Compatibility**

### **Legacy Endpoint Support**
```python
# Maintain v3.0 endpoints during transition
@router.get("/api/v3/articles")
async def legacy_get_articles():
    """Legacy endpoint - redirects to politics domain"""
    return await get_domain_articles(domain='politics')
```

### **Gradual Migration**
- Phase 1-2: Both old and new endpoints work
- Phase 3: Redirect old endpoints to new
- Phase 4: Deprecate old endpoints
- Phase 5: Remove old endpoints

---

## ✅ **Migration Checklist**

### **Database**
- [ ] Create domains table
- [ ] Create domain schemas
- [ ] Create domain-specific tables
- [ ] Migrate existing data to politics
- [ ] Set up finance tables
- [ ] Set up science-tech tables
- [ ] Create indexes per domain
- [ ] Test data isolation

### **API**
- [ ] Create DomainAwareService base
- [ ] Refactor all services for domain awareness
- [ ] Update all routers for domain parameter
- [ ] Add domain validation
- [ ] Create finance-specific endpoints
- [ ] Update API documentation
- [ ] Test backward compatibility

### **Feeds**
- [ ] Add domain column to feeds
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
- [ ] Update existing pages
- [ ] Test domain switching

### **Finance Features**
- [ ] Corporate announcement collector
- [ ] Market pattern analyzer
- [ ] Finance visualizations
- [ ] Pattern detection UI
- [ ] Integration testing

---

## 🎯 **Success Metrics**

- [ ] Zero downtime during migration
- [ ] All existing features work in politics domain
- [ ] Finance domain fully functional
- [ ] No data leakage between domains
- [ ] API response times maintained
- [ ] Frontend navigation intuitive
- [ ] Finance features operational

---

*Migration Plan Date: 2025-12-07*
*Estimated Duration: 8 weeks*

