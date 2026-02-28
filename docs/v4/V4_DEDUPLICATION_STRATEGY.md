# News Intelligence System v4.0 - Deduplication Strategy

## Date: 2025-01-XX
## Status: 📋 **STRATEGY DEFINED**

---

## 🎯 **Design Intent**

Articles can be tagged for multiple domains, but we don't need to save originals more than once. Once an article is pulled into a storyline, it needs to be isolated into that domain's storyline and kept distinct from the original.

---

## 📊 **Architecture**

### **Article Storage Strategy**

#### **Option A: Shared Article Storage** (Recommended)
- Articles stored in a shared location (e.g., `public.articles` or cross-domain table)
- Articles can have multiple domain tags/assignments
- Single source of truth for article content
- Domain-specific storylines reference shared articles

#### **Option B: Domain-Specific Article Storage**
- Articles stored in domain schemas (`politics.articles`, `finance.articles`)
- Articles duplicated across domains if needed in multiple domains
- Each domain has its own copy

**Recommendation**: **Option A** - Shared storage with domain tagging

---

## 🔄 **Article Lifecycle**

### **1. Article Ingestion**
```
RSS Feed → Article Collected → Stored in Shared Location
                                    ↓
                            Domain Tagged (can be multiple)
```

### **2. Article → Storyline**
```
Shared Article → Added to Domain Storyline
                        ↓
            Creates Domain-Specific Reference
            (storyline_articles table in domain schema)
```

### **3. Storyline Isolation**
- When article is added to a storyline:
  - Article content remains in shared location
  - Domain-specific reference created in `{domain}.storyline_articles`
  - Storyline context is domain-specific
  - Article can be in multiple storylines across domains

---

## 🗄️ **Database Design**

### **Shared Article Storage**
```sql
-- Option: Store in public schema or cross-domain table
CREATE TABLE public.articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    url TEXT UNIQUE,
    -- ... other article fields
    domain_tags TEXT[],  -- Array of domain keys: ['politics', 'finance']
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### **Domain-Specific Storyline References**
```sql
-- In each domain schema (politics, finance, science_tech)
CREATE TABLE {domain}.storyline_articles (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER REFERENCES {domain}.storylines(id),
    article_id INTEGER REFERENCES public.articles(id),  -- Reference to shared article
    added_at TIMESTAMP,
    relevance_score DECIMAL,
    -- Domain-specific context
    domain_context JSONB,  -- Domain-specific metadata
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### **Domain Tagging**
```sql
-- Junction table for article-domain relationships
CREATE TABLE public.article_domain_tags (
    article_id INTEGER REFERENCES public.articles(id),
    domain_key VARCHAR(50) REFERENCES public.domains(domain_key),
    tagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    tagged_by VARCHAR(100),
    confidence DECIMAL(3,2),  -- How confident we are this article belongs to this domain
    PRIMARY KEY (article_id, domain_key)
);
```

---

## 🔍 **Deduplication Logic**

### **Current Implementation**
- Deduplication happens at ingestion time
- Checks for duplicate URLs
- Checks for similar content (content hash)
- Prevents duplicate articles from being inserted

### **Multi-Domain Considerations**
1. **URL Deduplication**: 
   - Same URL = same article (regardless of domain)
   - Store once, tag with multiple domains

2. **Content Deduplication**:
   - Similar content = potential duplicate
   - If same article appears in multiple domain feeds, tag with all relevant domains

3. **Storyline Isolation**:
   - Article can be in multiple storylines
   - Each storyline reference is domain-specific
   - Storyline context is isolated per domain

---

## 📋 **Implementation Plan**

### **Phase 1: Update Article Storage**
- [ ] Decide on shared storage location (public schema vs cross-domain table)
- [ ] Add `domain_tags` column to articles table
- [ ] Create `article_domain_tags` junction table
- [ ] Update article ingestion to tag domains

### **Phase 2: Update Storyline References**
- [ ] Ensure `storyline_articles` references shared articles
- [ ] Add domain-specific context to storyline_articles
- [ ] Update storyline article addition logic

### **Phase 3: Update Deduplication**
- [ ] Update deduplication to work with shared articles
- [ ] Add domain tagging during deduplication
- [ ] Ensure deduplication doesn't prevent multi-domain tagging

### **Phase 4: Update API**
- [ ] Update article endpoints to handle domain tags
- [ ] Update storyline endpoints to use shared article references
- [ ] Add domain tagging endpoints

---

## 🎯 **Key Principles**

1. **Single Source of Truth**: Article content stored once
2. **Multi-Domain Tagging**: Articles can belong to multiple domains
3. **Storyline Isolation**: Storylines are domain-specific, even if they reference shared articles
4. **Domain Context**: When article is in a storyline, it has domain-specific context

---

## ⚠️ **Considerations**

### **Cross-Domain Queries**
- Need to query shared articles with domain filters
- Need to aggregate across domains when needed
- Need to maintain performance with shared storage

### **Article Updates**
- If article is updated, all domains see the update
- Need to handle domain-specific metadata separately

### **Deletion**
- If article is deleted, need to handle domain tags
- Need to handle storyline references

---

*Strategy Document Date: 2025-01-XX*



