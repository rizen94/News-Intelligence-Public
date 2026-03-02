# News Intelligence System v4.0 - Domain Silo Architecture

## Date: 2025-12-07
## Status: 🏗️ **ARCHITECTURE DESIGN**

---

## 🎯 **v4.0 Vision: Multi-Domain News Intelligence Platform**

Transform the News Intelligence System into a **newspaper-style multi-domain platform** with isolated silos for different news categories, while maintaining a unified, topic-agnostic API architecture.

---

## 📰 **Domain Structure**

### **Master Domains (Newspaper Sections)**

1. **Politics** (Existing - to be siloed)
   - Political news and analysis
   - Government announcements
   - Election coverage
   - Policy analysis

2. **Finance** (New)
   - Corporate financial announcements
   - Market research and analysis
   - Earnings reports
   - Market pattern analysis
   - Stock market news

3. **Science & Technology** (Existing - to be organized)
   - Scientific research
   - Technology news
   - Innovation and breakthroughs
   - Tech industry analysis

### **Future Domains** (Extensible)
- Health & Medicine
- Sports
- Entertainment
- Business & Economy
- International News

---

## 🏗️ **Architecture Principles**

### **1. Topic-Agnostic API**
- Single API structure that works for all domains
- Domain passed as parameter/context
- Shared services with domain-specific data isolation
- No redundant microservices

### **2. Data Isolation**
- Each domain has isolated data storage
- Shared schema, domain-specific tables/partitions
- Cross-domain queries when needed
- Domain-specific configurations

### **3. Unified Infrastructure**
- Single API server
- Single frontend application
- Shared authentication and authorization
- Domain-aware routing

---

## 🗄️ **Database Architecture**

### **Domain Isolation Strategy**

#### **Option 1: Schema-Based Isolation** (Recommended)
```sql
-- Domain-specific schemas
CREATE SCHEMA politics;
CREATE SCHEMA finance;
CREATE SCHEMA science_tech;

-- Shared tables in public schema
-- Domain-specific tables in domain schemas
```

#### **Option 2: Domain Column Partitioning**
```sql
-- Add domain column to all tables
ALTER TABLE articles ADD COLUMN domain VARCHAR(50);
ALTER TABLE topics ADD COLUMN domain VARCHAR(50);
ALTER TABLE storylines ADD COLUMN domain VARCHAR(50);

-- Partition tables by domain
CREATE TABLE articles_politics PARTITION OF articles 
  FOR VALUES IN ('politics');
CREATE TABLE articles_finance PARTITION OF articles 
  FOR VALUES IN ('finance');
```

#### **Option 3: Domain Prefix Tables**
```sql
-- Domain-specific tables
CREATE TABLE politics_articles (...);
CREATE TABLE finance_articles (...);
CREATE TABLE science_tech_articles (...);
```

**Recommendation**: **Option 1 (Schema-Based)** - Cleanest isolation, easiest to manage, supports future microservice split.

---

## 🔌 **API Architecture**

### **Topic-Agnostic Endpoint Structure**

#### **Current Structure** (v3.0)
```
/api/v4/news-aggregation/articles
/api/v4/content-analysis/topics
/api/v4/storyline-management/storylines
```

#### **New Structure** (v4.0)
```
/api/v4/{domain}/articles
/api/v4/{domain}/topics
/api/v4/{domain}/storylines
/api/v4/{domain}/feeds
/api/v4/{domain}/analysis
```

**Examples**:
- `/api/v4/politics/articles`
- `/api/v4/finance/articles`
- `/api/v4/science-tech/articles`

### **Shared Endpoints** (Cross-Domain)
```
/api/v4/domains                    # List all domains
/api/v4/search?domain=politics     # Domain-specific search
/api/v4/analytics/cross-domain     # Cross-domain analytics
```

---

## 📊 **Database Schema Design**

### **Domain Configuration Table**
```sql
CREATE TABLE domains (
    id SERIAL PRIMARY KEY,
    domain_key VARCHAR(50) UNIQUE NOT NULL,  -- 'politics', 'finance', 'science-tech'
    name VARCHAR(100) NOT NULL,              -- 'Politics', 'Finance', 'Science & Technology'
    description TEXT,
    schema_name VARCHAR(50) NOT NULL,         -- 'politics', 'finance', 'science_tech'
    is_active BOOLEAN DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Default domains
INSERT INTO domains (domain_key, name, schema_name, display_order) VALUES
('politics', 'Politics', 'politics', 1),
('finance', 'Finance', 'finance', 2),
('science-tech', 'Science & Technology', 'science_tech', 3);
```

### **Domain-Specific Schema Structure**
```sql
-- Each domain schema contains:
CREATE SCHEMA politics;
CREATE SCHEMA finance;
CREATE SCHEMA science_tech;

-- Domain-specific tables in each schema
politics.articles
politics.topics
politics.storylines
politics.feeds
politics.analysis

finance.articles
finance.topics
finance.storylines
finance.feeds
finance.analysis
finance.market_patterns      -- Finance-specific
finance.corporate_announcements -- Finance-specific

science_tech.articles
science_tech.topics
science_tech.storylines
science_tech.feeds
science_tech.analysis
```

### **Shared Tables** (Public Schema)
```sql
-- Cross-domain tables
public.domains
public.users
public.user_preferences
public.system_config
public.analytics
```

---

## 🔄 **API Service Layer**

### **Domain-Aware Service Pattern**

```python
class DomainAwareService:
    """Base class for domain-aware services"""
    
    def __init__(self, domain: str):
        self.domain = domain
        self.schema = self._get_domain_schema(domain)
        self.db_config = self._get_domain_db_config(domain)
    
    def _get_domain_schema(self, domain: str) -> str:
        """Get schema name for domain"""
        return domain.replace('-', '_')
    
    def _get_domain_db_config(self, domain: str) -> dict:
        """Get database config with schema"""
        config = get_base_db_config()
        config['schema'] = self.schema
        return config

class ArticleService(DomainAwareService):
    """Article service that works for any domain"""
    
    def get_articles(self, limit: int = 50, offset: int = 0):
        """Get articles from current domain"""
        query = f"""
            SELECT * FROM {self.schema}.articles
            ORDER BY published_at DESC
            LIMIT %s OFFSET %s
        """
        # Execute with domain-specific schema
```

### **Router Pattern**

```python
@router.get("/{domain}/articles")
async def get_domain_articles(
    domain: str = Path(..., regex="^(politics|finance|science-tech)$"),
    limit: int = Query(50),
    offset: int = Query(0)
):
    """Get articles for specific domain"""
    service = ArticleService(domain=domain)
    return await service.get_articles(limit=limit, offset=offset)
```

---

## 🎨 **Frontend Architecture**

### **Navigation Structure**

```
News Intelligence
├── Politics
│   ├── Articles
│   ├── Topics
│   ├── Storylines
│   └── Analysis
├── Finance
│   ├── Articles
│   ├── Market Research
│   ├── Corporate Announcements
│   ├── Market Patterns
│   └── Analysis
└── Science & Technology
    ├── Articles
    ├── Topics
    ├── Storylines
    └── Analysis
```

### **Component Structure**

```
src/
├── domains/
│   ├── Politics/
│   │   ├── Articles/
│   │   ├── Topics/
│   │   └── Storylines/
│   ├── Finance/
│   │   ├── Articles/
│   │   ├── MarketResearch/
│   │   ├── CorporateAnnouncements/
│   │   └── MarketPatterns/
│   └── ScienceTech/
│       ├── Articles/
│       ├── Topics/
│       └── Storylines/
├── shared/
│   ├── Navigation/
│   ├── DomainSelector/
│   └── CrossDomainSearch/
```

---

## 📈 **Finance Domain Specific Features**

### **Corporate Announcements**
- Earnings reports
- Product launches
- Mergers & acquisitions
- Executive changes
- Regulatory filings

### **Market Pattern Analysis**
- Price trend analysis
- Volume pattern detection
- Correlation analysis
- Market sentiment tracking
- Predictive modeling

### **Data Sources**
- SEC filings (EDGAR)
- Corporate press releases
- Financial news feeds
- Stock exchange announcements
- Analyst reports

---

## 🔄 **Migration Strategy**

### **Phase 1: Database Preparation**
1. Create domain configuration table
2. Create domain schemas
3. Migrate existing data to politics schema
4. Set up finance schema
5. Set up science-tech schema

### **Phase 2: API Refactoring**
1. Create domain-aware base services
2. Refactor existing endpoints to accept domain parameter
3. Implement domain routing
4. Add domain validation
5. Update API documentation

### **Phase 3: Feed Categorization**
1. Categorize existing feeds by domain
2. Set up finance-specific feeds
3. Update feed collection to route by domain
4. Test feed processing per domain

### **Phase 4: Frontend Reorganization**
1. Create domain navigation structure
2. Build domain selector component
3. Update routing for domain-based pages
4. Create finance-specific pages
5. Update existing pages for domain context

### **Phase 5: Finance Features**
1. Implement corporate announcement collection
2. Build market pattern analysis
3. Create finance-specific visualizations
4. Add financial data processing

---

## 📋 **Implementation Checklist**

### **Database**
- [ ] Create domains table
- [ ] Create domain schemas (politics, finance, science_tech)
- [ ] Migrate existing articles to politics schema
- [ ] Create finance-specific tables (market_patterns, corporate_announcements)
- [ ] Set up domain-specific indexes
- [ ] Create migration scripts

### **API**
- [ ] Create DomainAwareService base class
- [ ] Refactor ArticleService for domain awareness
- [ ] Refactor TopicService for domain awareness
- [ ] Refactor StorylineService for domain awareness
- [ ] Update all routers to accept domain parameter
- [ ] Add domain validation middleware
- [ ] Create finance-specific endpoints
- [ ] Update API documentation

### **Feed Management**
- [ ] Add domain column to feeds table
- [ ] Categorize existing feeds
- [ ] Set up finance feeds (SEC, corporate, financial news)
- [ ] Update RSS collector for domain routing
- [ ] Test feed processing per domain

### **Frontend**
- [ ] Create domain navigation structure
- [ ] Build DomainSelector component
- [ ] Update routing for domain context
- [ ] Create Finance domain pages
- [ ] Update existing pages for domain awareness
- [ ] Create finance-specific components
- [ ] Add market pattern visualizations

### **Finance Features**
- [ ] Corporate announcement collector
- [ ] Market pattern analysis engine
- [ ] Financial data processing pipeline
- [ ] Pattern detection algorithms
- [ ] Finance-specific visualizations

---

## 🎯 **Success Criteria**

### **Functional**
- [ ] All domains operate independently
- [ ] No data leakage between domains
- [ ] Finance domain fully functional
- [ ] Existing politics domain works unchanged
- [ ] Science-tech domain organized

### **Technical**
- [ ] Single API codebase (no microservice duplication)
- [ ] Domain-agnostic service layer
- [ ] Clean schema isolation
- [ ] Efficient cross-domain queries when needed
- [ ] Scalable architecture

### **User Experience**
- [ ] Clear domain navigation
- [ ] Easy domain switching
- [ ] Domain-specific features accessible
- [ ] Consistent UI across domains
- [ ] Fast page loads

---

## 📚 **Next Steps**

1. **Review and Approve Architecture** - Confirm approach
2. **Create Detailed Database Migration** - Schema design
3. **Design API Contracts** - Endpoint specifications
4. **Plan Feed Categorization** - Feed assignment strategy
5. **Design Finance Features** - Market analysis requirements

---

*Architecture Design Date: 2025-12-07*
*Target Implementation: Q1 2026*

