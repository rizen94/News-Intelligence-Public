# 🔌 News Intelligence System v3.1.0 - API Analysis Report

**Date:** September 8, 2025  
**Reviewer:** AI Assistant  
**Scope:** Complete API architecture review and schema alignment analysis

---

## 📊 **API ARCHITECTURE OVERVIEW**

### **API Structure Summary**
- **Total Routes:** 37+ route files
- **Primary Framework:** FastAPI with Pydantic validation
- **Response Standard:** `APIResponse` schema (standardized)
- **Authentication:** None currently implemented
- **Versioning:** v3.1.0 with production/development splits

### **Core API Categories**
1. **Content Management** - Articles, RSS feeds, sources
2. **Intelligence Processing** - ML, AI, clustering, entities
3. **Story Management** - Storylines, timelines, consolidation
4. **System Monitoring** - Health, metrics, performance
5. **Data Processing** - Deduplication, enrichment, filtering

---

## 🏗️ **API ROUTE ANALYSIS**

### **1. 📰 CONTENT MANAGEMENT APIs**

#### **Articles Production API** (`/api/articles`)
**Endpoints:**
- `GET /` - Paginated article list with filters
- `GET /sources` - Article sources list
- `GET /categories` - Article categories
- `GET /stats/overview` - Article statistics
- `GET /{article_id}` - Single article by ID
- `POST /` - Create new article
- `PUT /{article_id}` - Update article
- `DELETE /{article_id}` - Delete article

**Data Requirements:**
```python
# Expected Article Schema
{
  "id": "string",
  "title": "string",
  "content": "string",
  "url": "string",
  "source": "string",
  "published_at": "datetime",
  "category": "string",
  "tags": ["string"],
  "language": "string",
  "status": "string",
  "sentiment_score": "float",
  "entities": "object",
  "readability_score": "float",
  "quality_score": "float",
  "processing_status": "string",
  "created_at": "datetime",      # ⚠️ MISSING IN SCHEMA
  "updated_at": "datetime",      # ⚠️ MISSING IN SCHEMA
  "summary": "string",
  "ml_data": "object",
  "word_count": "integer",
  "reading_time": "integer"
}
```

**⚠️ CRITICAL SCHEMA MISMATCHES:**
1. **Missing Timestamps** - API expects `created_at`/`updated_at` but schema doesn't have them
2. **Field Name Mismatch** - API uses `published_at` but schema has `published_date`
3. **Missing Processing Fields** - API expects `processing_status` but schema has different field names

#### **RSS Management API** (`/api/rss`)
**Endpoints:**
- `GET /feeds` - RSS feeds with filtering
- `POST /feeds` - Create new feed
- `PUT /feeds/{feed_id}` - Update feed
- `DELETE /feeds/{feed_id}` - Delete feed
- `GET /feeds/{feed_id}/stats` - Feed statistics
- `POST /feeds/fetch` - Trigger feed fetching
- `GET /articles` - Articles with advanced filtering
- `POST /deduplication/detect` - Trigger duplicate detection
- `POST /enrichment/batch` - Batch metadata enrichment

**Data Requirements:**
```python
# Expected RSS Feed Schema
{
  "id": "integer",
  "name": "string",
  "url": "string",
  "description": "string",
  "tier": "integer",
  "priority": "integer",
  "language": "string",
  "country": "string",
  "category": "string",
  "subcategory": "string",
  "is_active": "boolean",
  "status": "string",
  "update_frequency": "integer",
  "max_articles_per_update": "integer",
  "success_rate": "float",
  "avg_response_time": "integer",
  "reliability_score": "float",
  "created_at": "datetime",      # ⚠️ MISSING IN SCHEMA
  "updated_at": "datetime"       # ⚠️ MISSING IN SCHEMA
}
```

**⚠️ CRITICAL SCHEMA MISMATCHES:**
1. **Missing Timestamps** - API expects audit trail
2. **No Article-Feed Relationship** - Articles reference feeds by `source` string, not foreign key
3. **Missing Performance Tracking** - API expects `success_rate`, `avg_response_time` but schema has them

### **2. 🧵 STORY MANAGEMENT APIs**

#### **Storylines API** (`/api/storylines`)
**Endpoints:**
- `GET /` - Get all storylines
- `POST /` - Create new storyline
- `GET /{storyline_id}/` - Get specific storyline
- `POST /{storyline_id}/add-article/` - Add article to storyline
- `DELETE /{storyline_id}/articles/{article_id}/` - Remove article
- `POST /{storyline_id}/generate-summary/` - Generate AI summary
- `GET /{storyline_id}/suggestions/` - Get suggestions
- `DELETE /{storyline_id}/` - Delete storyline

**Data Requirements:**
```python
# Expected Storyline Schema
{
  "id": "string",
  "title": "string",
  "description": "string",
  "status": "string",
  "created_at": "datetime",      # ⚠️ MISSING IN SCHEMA
  "updated_at": "datetime",      # ⚠️ MISSING IN SCHEMA
  "articles": [
    {
      "article_id": "string",
      "relevance_score": "float",
      "importance_score": "float"
    }
  ]
}
```

**⚠️ CRITICAL SCHEMA MISMATCHES:**
1. **Missing Timestamps** - Story threads table has them, but API doesn't use them consistently
2. **No Direct Article Association** - Missing junction table for storyline-article relationships
3. **Missing Priority Integration** - API expects priority levels but schema connection is incomplete

### **3. 📊 MONITORING & HEALTH APIs**

#### **Health Production API** (`/api/health`)
**Endpoints:**
- `GET /` - Overall system health
- `GET /database` - Database health
- `GET /ready` - Readiness status
- `GET /live` - Liveness status

#### **Dashboard API** (`/api/dashboard`)
**Endpoints:**
- `GET /` - Comprehensive dashboard data
- `GET /stats` - Dashboard statistics

**Data Requirements:**
```python
# Expected Dashboard Schema
{
  "article_stats": {
    "total_articles": "integer",
    "articles_today": "integer",
    "processing_status": "object"
  },
  "rss_stats": {
    "total_feeds": "integer",
    "active_feeds": "integer",
    "success_rate": "float"
  },
  "system_health": {
    "database_status": "string",
    "services_status": "object",
    "performance_metrics": "object"
  }
}
```

### **4. 🤖 INTELLIGENCE PROCESSING APIs**

#### **Clusters API** (`/api/clusters`)
**Endpoints:**
- `GET /` - Get article clusters
- `POST /` - Create new cluster
- `GET /{cluster_id}` - Get specific cluster
- `PUT /{cluster_id}` - Update cluster
- `DELETE /{cluster_id}` - Delete cluster
- `POST /{cluster_id}/articles` - Add articles to cluster
- `GET /{cluster_id}/articles` - Get cluster articles

#### **Entities API** (`/api/entities`)
**Endpoints:**
- `POST /extract` - Extract entities from text
- `GET /stats` - Entity extraction statistics
- `GET /types` - Available entity types

---

## ⚠️ **CRITICAL API-SCHEMA MISMATCHES**

### **1. Missing Audit Timestamps**
**Issue:** APIs expect `created_at`/`updated_at` but many tables lack them
**Impact:** 
- No audit trail for data changes
- API responses missing timestamp data
- Frontend can't display creation/update times

**Tables Affected:**
- `articles` (CRITICAL)
- `rss_feeds` (CRITICAL)
- `entities`
- `content_hashes`
- `similarity_scores`

### **2. Field Name Inconsistencies**
**Issue:** API field names don't match database column names
**Examples:**
- API: `published_at` → Schema: `published_date`
- API: `processing_status` → Schema: `processing_status` (exists but different structure)
- API: `word_count` → Schema: Not in articles table

### **3. Missing Foreign Key Relationships**
**Issue:** APIs expect relational data but schema has loose coupling
**Examples:**
- Articles reference feeds by `source` string instead of `feed_id`
- Storylines don't have direct article associations
- ML tasks not linked to articles

### **4. Incomplete Data Structures**
**Issue:** APIs expect fields that don't exist in schema
**Examples:**
- Article schema missing `word_count`, `reading_time`
- RSS feeds missing performance tracking fields
- Storylines missing article relationship table

---

## 🔄 **DATA FLOW ANALYSIS**

### **Content Ingestion Flow**
```
RSS Feeds → RSS Fetcher → Articles → ML Processing → Clusters → Storylines
```

**Current Issues:**
1. **RSS → Articles** - No foreign key relationship
2. **Articles → ML** - No task tracking
3. **Articles → Clusters** - Missing cluster_id in articles
4. **Clusters → Storylines** - No direct relationship

### **API Response Flow**
```
Database → Service Layer → API Route → Pydantic Schema → JSON Response
```

**Current Issues:**
1. **Service Layer** - Expects fields not in database
2. **Pydantic Schemas** - Don't match database structure
3. **JSON Responses** - Missing required fields

---

## 🎯 **COORDINATED UPDATE PLAN**

### **Phase 1: Critical Schema Fixes**
1. **Add Missing Timestamps**
   ```sql
   ALTER TABLE articles ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
   ALTER TABLE articles ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
   ALTER TABLE rss_feeds ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
   ALTER TABLE rss_feeds ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
   ```

2. **Fix Field Name Mismatches**
   ```sql
   ALTER TABLE articles RENAME COLUMN published_date TO published_at;
   ```

3. **Add Missing Fields**
   ```sql
   ALTER TABLE articles ADD COLUMN word_count INTEGER DEFAULT 0;
   ALTER TABLE articles ADD COLUMN reading_time INTEGER DEFAULT 0;
   ```

### **Phase 2: Relationship Fixes**
1. **Add Article-Feed Relationship**
   ```sql
   ALTER TABLE articles ADD COLUMN feed_id INTEGER REFERENCES rss_feeds(id);
   ```

2. **Create Storyline-Article Junction Table**
   ```sql
   CREATE TABLE storyline_articles (
     id SERIAL PRIMARY KEY,
     storyline_id INTEGER REFERENCES story_threads(id),
     article_id INTEGER REFERENCES articles(id),
     relevance_score FLOAT,
     importance_score FLOAT,
     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
   );
   ```

### **Phase 3: API Schema Updates**
1. **Update Pydantic Models** - Align with database schema
2. **Update Service Layer** - Use correct field names
3. **Update API Responses** - Include all required fields

### **Phase 4: Data Migration**
1. **Populate Missing Fields** - Calculate word_count, reading_time
2. **Create Feed Relationships** - Link articles to feeds
3. **Update Existing Data** - Fix field name mismatches

---

## 📋 **API READINESS ASSESSMENT**

| Component | Status | Issues | Priority |
|-----------|--------|--------|----------|
| **Articles API** | ⚠️ Partial | Missing timestamps, field mismatches | HIGH |
| **RSS API** | ⚠️ Partial | Missing timestamps, no relationships | HIGH |
| **Storylines API** | ⚠️ Partial | Missing article relationships | MEDIUM |
| **Health API** | ✅ Good | Minor schema issues | LOW |
| **Dashboard API** | ⚠️ Partial | Missing data relationships | MEDIUM |
| **Clusters API** | ⚠️ Partial | Missing article relationships | MEDIUM |
| **Entities API** | ✅ Good | Works with current schema | LOW |

**Overall API Readiness:** ⚠️ **60% - Needs Schema Updates**

---

## 🚀 **RECOMMENDED IMPLEMENTATION ORDER**

1. **Fix Critical Schema Issues** (Phase 1)
2. **Update Pydantic Models** (Phase 3)
3. **Test API Endpoints** (Validation)
4. **Fix Relationships** (Phase 2)
5. **Data Migration** (Phase 4)
6. **Full System Testing** (Integration)

**Estimated Time:** 2-3 hours for critical fixes, 4-6 hours for complete alignment

---

## 📝 **NEXT STEPS**

1. **Implement Phase 1 fixes** - Add missing timestamps and fields
2. **Update API schemas** - Align Pydantic models with database
3. **Test critical endpoints** - Validate articles and RSS APIs
4. **Implement relationships** - Add foreign keys and junction tables
5. **Full integration testing** - End-to-end API validation

**Ready to proceed with Phase 1 implementation?**
