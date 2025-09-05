# 🔌 API & Web Interface Mapping - News Intelligence System v3.0

## 📋 **OVERVIEW**

This document provides a comprehensive mapping between the backend API endpoints and frontend web interface components, ensuring proper data flow and functionality across the entire system.

---

## 🏗️ **SYSTEM ARCHITECTURE**

### **Backend (FastAPI)**
- **Port**: 8000
- **Base URL**: `http://localhost:8000`
- **API Documentation**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc`

### **Frontend (React + Nginx)**
- **Port**: 3001 (Production)
- **Base URL**: `http://localhost:3001`
- **Development**: `http://localhost:3000`

### **Database (PostgreSQL)**
- **Port**: 5432
- **Database**: `news_system`
- **User**: `newsapp`

---

## 🔌 **API ENDPOINT MAPPING**

### **1. System Health & Monitoring**

#### **Backend Endpoints**
```python
# Health Check
GET /api/health/                    # Overall system health
GET /api/health/metrics             # System metrics
GET /api/health/rss                 # RSS collection health
GET /api/health/database            # Database health
```

#### **Frontend Service Calls**
```javascript
// newsSystemService.js
getHealth()                         // → GET /api/health/
getSystemMetrics()                  // → GET /api/health/metrics
```

#### **Frontend Components**
- `pages/Dashboard/EnhancedDashboard.js` - Uses health data for system status
- `components/SystemStatus/SystemStatus.js` - Displays health indicators

---

### **2. Articles Management**

#### **Backend Endpoints**
```python
# Articles API
GET /api/articles/                  # List articles with pagination
GET /api/articles/{article_id}      # Get specific article
GET /api/articles/sources           # Get article sources
GET /api/articles/categories        # Get article categories
GET /api/articles/stats/overview    # Article statistics
```

#### **Frontend Service Calls**
```javascript
// newsSystemService.js
getArticles(params)                 // → GET /api/articles/
getArticle(id)                      // → GET /api/articles/{id}
getArticleSources()                 // → GET /api/articles/sources
getArticleCategories()              // → GET /api/articles/categories
```

#### **Frontend Components**
- `pages/Articles/Articles.js` - Main articles listing
- `pages/Articles/ArticleDetail.js` - Individual article view
- `components/ArticleCard/ArticleCard.js` - Article display component

#### **Data Flow**
```
Database (articles table) → FastAPI → React Components → Material-UI Display
```

---

### **3. Storylines Management**

#### **Backend Endpoints**
```python
# Story Management API
GET /api/story-management/stories   # Get active storylines
POST /api/story-management/stories  # Create new storyline
PUT /api/story-management/stories/{id}  # Update storyline
DELETE /api/story-management/stories/{id}  # Delete storyline
```

#### **Frontend Service Calls**
```javascript
// newsSystemService.js
getActiveStories()                  // → GET /api/story-management/stories
createStoryExpectation(data)        // → POST /api/story-management/stories
updateStoryline(id, data)           // → PUT /api/story-management/stories/{id}
deleteStoryline(id)                 // → DELETE /api/story-management/stories/{id}
```

#### **Frontend Components**
- `pages/Storylines/Storylines.js` - Main storylines listing
- `pages/Storylines/StorylineDetail.js` - Individual storyline view
- `components/EditStorylineDialog/EditStorylineDialog.js` - Edit storyline
- `components/AddToStorylineDialog/AddToStorylineDialog.js` - Add articles to storyline

#### **Data Flow**
```
Database (story_expectations table) → FastAPI → React Components → Material-UI Display
```

---

### **4. Timeline Management**

#### **Backend Endpoints**
```python
# Timeline API
GET /api/storyline-timeline/{storyline_id}  # Get storyline timeline
GET /api/storyline-timeline/{storyline_id}/events  # Get timeline events
GET /api/storyline-timeline/{storyline_id}/milestones  # Get milestones
```

#### **Frontend Service Calls**
```javascript
// newsSystemService.js
getStorylineTimeline(storylineId)   // → GET /api/storyline-timeline/{storyline_id}
```

#### **Frontend Components**
- `pages/Timeline/StorylineTimeline.js` - Timeline visualization
- `pages/Storylines/StorylineDetail.js` - Timeline integration

#### **Data Flow**
```
Database (timeline_events, timeline_periods, timeline_milestones) → FastAPI → React Components → Timeline Visualization
```

---

### **5. RSS Feed Management**

#### **Backend Endpoints**
```python
# RSS Management API
GET /api/rss/feeds                  # List RSS feeds
POST /api/rss/feeds                 # Add new RSS feed
PUT /api/rss/feeds/{id}             # Update RSS feed
DELETE /api/rss/feeds/{id}          # Delete RSS feed
POST /api/rss/feeds/{id}/refresh    # Refresh RSS feed
GET /api/rss/stats                  # RSS collection statistics
```

#### **Frontend Service Calls**
```javascript
// newsSystemService.js
getRSSFeeds()                       // → GET /api/rss/feeds
addRSSFeed(data)                    // → POST /api/rss/feeds
updateRSSFeed(id, data)             // → PUT /api/rss/feeds/{id}
deleteRSSFeed(id)                   // → DELETE /api/rss/feeds/{id}
refreshRSSFeed(id)                  // → POST /api/rss/feeds/{id}/refresh
getRSSStats()                       // → GET /api/rss/stats
```

#### **Frontend Components**
- `pages/Sources/Sources.js` - RSS feed management
- `components/RSSFeedCard/RSSFeedCard.js` - RSS feed display

---

### **6. Dashboard & Analytics**

#### **Backend Endpoints**
```python
# Dashboard API
GET /api/dashboard/                 # Main dashboard data
GET /api/dashboard/stats            # Dashboard statistics
GET /api/dashboard/ingestion        # Ingestion statistics
GET /api/dashboard/ml-pipeline      # ML pipeline statistics
GET /api/dashboard/story-evolution  # Story evolution statistics
GET /api/dashboard/system-alerts    # System alerts
GET /api/dashboard/recent-activity  # Recent activity
```

#### **Frontend Service Calls**
```javascript
// newsSystemService.js
getDashboardStats()                 // → GET /api/dashboard/
getIngestionStats()                 // → GET /api/dashboard/ingestion
getMLPipelineStats()                // → GET /api/dashboard/ml-pipeline
getStoryEvolutionStats()            // → GET /api/dashboard/story-evolution
getSystemAlerts()                   // → GET /api/dashboard/system-alerts
getRecentActivity()                 // → GET /api/dashboard/recent-activity
```

#### **Frontend Components**
- `pages/Dashboard/EnhancedDashboard.js` - Main dashboard
- `components/Dashboard/StatsCard.js` - Statistics display
- `components/Dashboard/ChartComponent.js` - Data visualization

---

## 🔄 **DATA FLOW ARCHITECTURE**

### **1. Article Collection Flow**
```
RSS Feeds → RSS Collector → Database (articles) → FastAPI → React → Material-UI
```

### **2. Storyline Management Flow**
```
User Input → React Form → FastAPI → Database (story_expectations) → React Display
```

### **3. Timeline Generation Flow**
```
Articles → ML Pipeline → Timeline Events → Database → FastAPI → React Timeline
```

### **4. Dashboard Data Flow**
```
Database Queries → FastAPI Aggregation → React Components → Charts & Statistics
```

---

## 📊 **DATABASE TABLE MAPPING**

### **Core Tables**
```sql
-- Articles
articles                    → /api/articles/
├── id                     → article.id
├── title                  → article.title
├── content                → article.content
├── source                 → article.source
├── published_date         → article.published_date
└── created_at             → article.created_at

-- Storylines
story_expectations         → /api/story-management/stories
├── story_id               → storyline.story_id
├── name                   → storyline.name
├── description            → storyline.description
├── priority_level         → storyline.priority_level
├── keywords               → storyline.keywords
├── entities               → storyline.entities
└── geographic_regions     → storyline.geographic_regions

-- Timeline
timeline_events            → /api/storyline-timeline/{id}
├── event_id               → event.event_id
├── storyline_id           → event.storyline_id
├── event_title            → event.event_title
├── event_date             → event.event_date
├── importance_score       → event.importance_score
└── entities               → event.entities

-- RSS Feeds
rss_feeds                  → /api/rss/feeds
├── id                     → feed.id
├── name                   → feed.name
├── url                    → feed.url
├── is_active              → feed.is_active
└── last_fetched           → feed.last_fetched
```

---

## 🎯 **COMPONENT RESPONSIBILITIES**

### **Frontend Components**

#### **Pages**
- **Dashboard**: System overview, statistics, health monitoring
- **Articles**: Article listing, filtering, detailed view
- **Storylines**: Storyline management, creation, editing
- **Timeline**: Timeline visualization, event display
- **Sources**: RSS feed management
- **Discover**: Content discovery and trending topics

#### **Components**
- **ArticleCard**: Individual article display
- **StorylineCard**: Individual storyline display
- **TimelineComponent**: Timeline visualization
- **StatsCard**: Statistics display
- **ChartComponent**: Data visualization
- **Dialog Components**: Forms and modals

### **Backend Services**

#### **API Routes**
- **Health**: System monitoring and status
- **Articles**: Article management and retrieval
- **Story Management**: Storyline CRUD operations
- **Timeline**: Timeline data and events
- **RSS**: Feed management and collection
- **Dashboard**: Analytics and statistics

#### **Data Processing**
- **RSS Collector**: Automated news collection
- **ML Pipeline**: Content analysis and processing
- **Timeline Generator**: Event extraction and timeline creation
- **Deduplication**: Content similarity detection

---

## 🔧 **API RESPONSE FORMATS**

### **Standard Response Format**
```javascript
{
  "success": boolean,
  "data": any,           // Actual response data
  "message": string,     // Optional success/error message
  "error": string        // Optional error details
}
```

### **Pagination Format**
```javascript
{
  "success": true,
  "data": {
    "items": [...],      // Array of items
    "total": number,     // Total count
    "page": number,      // Current page
    "per_page": number,  // Items per page
    "pages": number      // Total pages
  },
  "message": "Data retrieved successfully"
}
```

### **Error Response Format**
```javascript
{
  "success": false,
  "data": null,
  "message": "Error description",
  "error": "Detailed error information"
}
```

---

## 🚨 **CRITICAL FIELD MAPPINGS**

### **Storyline Field Mapping**
```javascript
// Frontend → Backend
const STORYLINE_MAPPING = {
  'title' → 'name',                    // Storyline title
  'description' → 'description',       // Storyline description
  'priority' → 'priority_level',       // Priority (1-10)
  'status' → 'is_active',              // Active status
  'targets' → 'keywords',              // Target keywords
  'category' → 'geographic_regions',   // Geographic regions
  'quality_filters' → 'quality_threshold' // Quality threshold
};

// Backend → Frontend
const DISPLAY_MAPPING = {
  'story_id' → 'id',                   // Unique identifier
  'name' → 'title',                    // Display title
  'priority_level' → 'priority',       // Display priority
  'is_active' → 'status',              // Display status
  'keywords' → 'targets',              // Display targets
  'geographic_regions' → 'category',   // Display category
  'quality_threshold' → 'quality_filters' // Display quality filters
};
```

### **ID Field Consistency**
```javascript
// CRITICAL: Use correct ID fields
const ID_FIELDS = {
  'storylines': 'story_id',           // NOT 'id'
  'articles': 'id',                   // Use 'id'
  'rss_feeds': 'id',                  // Use 'id'
  'timeline_events': 'event_id'       // Use 'event_id'
};
```

---

## 🧪 **TESTING CHECKLIST**

### **Pre-Deployment Testing**
- [ ] All API endpoints return expected data format
- [ ] Frontend components render without errors
- [ ] Data flows correctly from database to UI
- [ ] Error handling displays appropriate messages
- [ ] Loading states work properly
- [ ] Navigation between pages functions
- [ ] Forms submit and validate correctly
- [ ] ID fields are correctly mapped
- [ ] Button handlers are functional

### **API Testing**
- [ ] Health endpoints return system status
- [ ] Articles API returns paginated data
- [ ] Storylines API handles CRUD operations
- [ ] Timeline API returns structured data
- [ ] RSS API manages feed operations
- [ ] Dashboard API provides statistics

### **Frontend Testing**
- [ ] All pages load without JavaScript errors
- [ ] Components display data correctly
- [ ] Forms validate input properly
- [ ] Navigation works between all routes
- [ ] Error states are handled gracefully
- [ ] Loading indicators appear during API calls

---

## 🔄 **DEPLOYMENT CONSIDERATIONS**

### **Environment Variables**
```bash
# Frontend
REACT_APP_API_URL=http://localhost:8000

# Backend
DB_HOST=postgres
DB_NAME=news_system
DB_USER=newsapp
DB_PASSWORD=newsapp123
API_HOST=0.0.0.0
API_PORT=8000
```

### **CORS Configuration**
```python
# Backend CORS settings
CORS_ORIGINS = [
    "http://localhost:3000",  # Development
    "http://localhost:3001",  # Production
]
```

### **Port Configuration**
- **Backend API**: 8000
- **Frontend (Production)**: 3001
- **Frontend (Development)**: 3000
- **Database**: 5432
- **Redis**: 6379

---

## 📚 **REFERENCE DOCUMENTS**

- **Project Overview**: `PROJECT_OVERVIEW.md`
- **Coding Style Guide**: `CODING_STYLE_GUIDE.md`
- **Database Schema**: `DATABASE_SCHEMA_DOCUMENTATION.md`
- **Web Interface Assessment**: `docs/WEB_INTERFACE_ASSESSMENT.md`
- **API Documentation**: `http://localhost:8000/docs`

---

**This mapping ensures seamless integration between the backend API and frontend web interface, providing a robust foundation for the News Intelligence System.**
