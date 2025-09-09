# 🔌 News Intelligence System v3.0 - API Documentation

## 📋 **OVERVIEW**

This document provides comprehensive API documentation for the News Intelligence System, following the standards established in [CODING_STYLE_GUIDE.md](./CODING_STYLE_GUIDE.md).

**Base URL**: `http://localhost:8000`  
**API Version**: `v3.0`  
**Content Type**: `application/json`

---

## 🏗️ **API ARCHITECTURE**

### **Core Endpoints**
- **Articles**: `/api/articles` - Article management and retrieval
- **Storylines**: `/api/story-management/stories` - Storyline management
- **Timeline**: `/api/storyline-timeline` - ML-powered timeline generation
- **Health**: `/api/health` - System health monitoring
- **RSS**: `/api/rss` - RSS feed management
- **Intelligence**: `/api/intelligence` - ML processing and analysis

---

## 📰 **ARTICLES API**

### **GET /api/articles**
Retrieve paginated list of articles with filtering options.

**Query Parameters**:
- `per_page` (int, optional): Number of articles per page (1-100, default: 10)
- `page` (int, optional): Page number (default: 1)
- `category` (string, optional): Filter by article category
- `search` (string, optional): Search in title and content
- `sort_by` (string, optional): Sort field (`published_date`, `created_at`, `engagement_score`)
- `sort_order` (string, optional): Sort order (`asc`, `desc`)

**Response Format**:
```json
{
  "success": true,
  "data": {
    "articles": [
      {
        "id": 1,
        "title": "Article Title",
        "content": "Article content...",
        "summary": "Article summary...",
        "source": "News Source",
        "url": "https://example.com/article",
        "published_date": "2024-01-15T10:30:00Z",
        "category": "politics",
        "sentiment_score": 0.7,
        "engagement_score": 0.8,
        "entities_extracted": ["Entity1", "Entity2"],
        "topics_extracted": ["topic1", "topic2"],
        "timeline_relevance_score": 0.6,
        "timeline_processed": false
      }
    ],
    "total": 150,
    "page": 1,
    "per_page": 10,
    "total_pages": 15
  },
  "message": "Articles retrieved successfully"
}
```

### **GET /api/articles/{id}**
Retrieve a specific article by ID.

**Path Parameters**:
- `id` (int, required): Article ID

**Response Format**:
```json
{
  "success": true,
  "data": {
    "id": 1,
    "title": "Article Title",
    "content": "Full article content...",
    "summary": "Article summary...",
    "source": "News Source",
    "url": "https://example.com/article",
    "published_date": "2024-01-15T10:30:00Z",
    "category": "politics",
    "sentiment_score": 0.7,
    "engagement_score": 0.8,
    "entities_extracted": ["Entity1", "Entity2"],
    "topics_extracted": ["topic1", "topic2"],
    "key_points": ["Point 1", "Point 2"],
    "readability_score": 0.6,
    "timeline_relevance_score": 0.6,
    "timeline_processed": false,
    "timeline_events_generated": 0
  },
  "message": "Article retrieved successfully"
}
```

---

## 📖 **STORYLINES API**

### **GET /api/story-management/stories**
Retrieve all active storylines.

**Response Format**:
```json
{
  "success": true,
  "data": [
    {
      "story_id": "ukraine_russia_conflict_2024",
      "name": "Ukraine-Russia Conflict 2024",
      "description": "Comprehensive tracking of the ongoing conflict...",
      "priority_level": 7,
      "keywords": ["ukraine", "russia", "conflict", "war"],
      "entities": ["Volodymyr Zelensky", "Vladimir Putin", "Ukraine", "Russia"],
      "geographic_regions": ["Ukraine", "Russia", "Eastern Europe"],
      "quality_threshold": 0.8,
      "max_articles_per_day": 200,
      "auto_enhance": true,
      "is_active": true,
      "timeline_enabled": true,
      "timeline_auto_generate": true,
      "timeline_min_importance": 0.3,
      "timeline_max_events_per_day": 10,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "message": "Storylines retrieved successfully"
}
```

### **POST /api/story-management/stories**
Create a new storyline.

**Request Body**:
```json
{
  "name": "New Storyline",
  "description": "Description of the storyline",
  "priority_level": 5,
  "keywords": ["keyword1", "keyword2"],
  "entities": ["Entity1", "Entity2"],
  "geographic_regions": ["Region1", "Region2"],
  "quality_threshold": 0.7,
  "max_articles_per_day": 50,
  "auto_enhance": true,
  "is_active": true,
  "timeline_enabled": true,
  "timeline_auto_generate": true,
  "timeline_min_importance": 0.3,
  "timeline_max_events_per_day": 10
}
```

### **PUT /api/story-management/stories/{story_id}**
Update an existing storyline.

**Path Parameters**:
- `story_id` (string, required): Storyline ID

**Request Body**: Same as POST, but all fields are optional.

### **DELETE /api/story-management/stories/{story_id}**
Delete (deactivate) a storyline.

**Path Parameters**:
- `story_id` (string, required): Storyline ID

---

## ⏰ **TIMELINE API**

### **GET /api/storyline-timeline/{storyline_id}**
Get comprehensive timeline for a storyline using ML analysis.

**Path Parameters**:
- `storyline_id` (string, required): Storyline ID

**Query Parameters**:
- `start_date` (string, optional): Start date (YYYY-MM-DD)
- `end_date` (string, optional): End date (YYYY-MM-DD)
- `event_types` (string, optional): Comma-separated event types
- `min_importance` (float, optional): Minimum importance score (0.0-1.0)

**Response Format**:
```json
{
  "success": true,
  "data": {
    "storyline_id": "ukraine_russia_conflict_2024",
    "storyline_name": "Ukraine-Russia Conflict 2024",
    "total_events": 25,
    "time_range": {
      "start": "2024-01-01",
      "end": "2024-01-31"
    },
    "periods": [
      {
        "period": "2024-01",
        "start_date": "2024-01-01",
        "end_date": "2024-01-31",
        "event_count": 15,
        "key_events": [...],
        "summary": "High activity period with major developments"
      }
    ],
    "key_milestones": [
      {
        "event_id": "2024-01-15_0_123",
        "title": "Major Military Operation",
        "description": "Significant military development...",
        "event_date": "2024-01-15",
        "event_time": "14:30",
        "source": "BBC News",
        "importance_score": 0.9,
        "event_type": "military",
        "location": "Eastern Ukraine",
        "entities": ["Ukrainian Army", "Russian Forces"],
        "tags": ["military", "conflict", "eastern-ukraine"]
      }
    ],
    "recent_events": [...],
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  },
  "message": "Timeline generated successfully"
}
```

### **GET /api/storyline-timeline/{storyline_id}/events**
Get paginated list of timeline events.

**Path Parameters**:
- `storyline_id` (string, required): Storyline ID

**Query Parameters**:
- `limit` (int, optional): Maximum events to return (1-500, default: 50)
- `offset` (int, optional): Number of events to skip (default: 0)
- `sort_by` (string, optional): Sort field (`event_date`, `importance_score`)
- `sort_order` (string, optional): Sort order (`asc`, `desc`)
- `event_types` (string, optional): Comma-separated event types
- `min_importance` (float, optional): Minimum importance score (0.0-1.0)

**Response Format**:
```json
{
  "success": true,
  "data": [
    {
      "event_id": "2024-01-15_0_123",
      "title": "Event Title",
      "description": "Event description...",
      "event_date": "2024-01-15",
      "event_time": "14:30",
      "source": "News Source",
      "url": "https://example.com/article",
      "importance_score": 0.8,
      "event_type": "military",
      "location": "Location",
      "entities": ["Entity1", "Entity2"],
      "tags": ["tag1", "tag2"],
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "message": "Timeline events retrieved successfully"
}
```

### **GET /api/storyline-timeline/{storyline_id}/milestones**
Get key milestone events for a storyline.

**Path Parameters**:
- `storyline_id` (string, required): Storyline ID

**Query Parameters**:
- `limit` (int, optional): Maximum milestones to return (1-100, default: 20)

---

## 🏥 **HEALTH API**

### **GET /api/health**
Get system health status.

**Response Format**:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "version": "3.0.0",
    "uptime_seconds": 3600,
    "services": {
      "database": {
        "status": "healthy",
        "message": "Database connection successful",
        "response_time_ms": 10.5
      },
      "ml_pipeline": {
        "status": "healthy",
        "message": "ML pipeline operational",
        "response_time_ms": 0.02
      },
      "timeline_generator": {
        "status": "healthy",
        "message": "Timeline generation operational",
        "response_time_ms": 5.2
      }
    }
  },
  "message": "System is healthy"
}
```

---

## 🔧 **RSS API**

### **GET /api/rss/feeds**
Get RSS feed configuration and status.

**Response Format**:
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "BBC News",
      "url": "http://feeds.bbci.co.uk/news/rss.xml",
      "is_active": true,
      "last_fetched": "2024-01-15T10:30:00Z",
      "success_rate": 0.95,
      "avg_response_time": 1200,
      "articles_today": 25,
      "last_error": null
    }
  ],
  "message": "RSS feeds retrieved successfully"
}
```

---

## 🤖 **INTELLIGENCE API**

### **GET /api/intelligence/status**
Get ML processing status and metrics.

**Response Format**:
```json
{
  "success": true,
  "data": {
    "ml_pipeline_status": "running",
    "articles_processed_today": 150,
    "timeline_events_generated": 25,
    "active_storylines": 5,
    "processing_queue_size": 10,
    "last_processing_time": "2024-01-15T10:30:00Z"
  },
  "message": "Intelligence status retrieved successfully"
}
```

---

## 📊 **ERROR HANDLING**

### **Error Response Format**
```json
{
  "success": false,
  "data": null,
  "message": "Error description",
  "error": "Detailed error information",
  "error_code": "VALIDATION_ERROR",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### **Common Error Codes**
- `VALIDATION_ERROR` - Request validation failed
- `NOT_FOUND` - Resource not found
- `UNAUTHORIZED` - Authentication required
- `FORBIDDEN` - Access denied
- `RATE_LIMITED` - Too many requests
- `INTERNAL_ERROR` - Server error
- `SERVICE_UNAVAILABLE` - Service temporarily unavailable

### **HTTP Status Codes**
- `200` - Success
- `201` - Created
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `422` - Validation Error
- `429` - Too Many Requests
- `500` - Internal Server Error
- `503` - Service Unavailable

---

## 🔐 **AUTHENTICATION & SECURITY**

### **CORS Configuration**
- **Allowed Origins**: `http://localhost:3000`, `http://localhost:3001`
- **Allowed Methods**: `GET`, `POST`, `PUT`, `DELETE`, `OPTIONS`
- **Allowed Headers**: `Content-Type`, `Authorization`

### **Rate Limiting**
- **Default**: 100 requests per minute per IP
- **Timeline Generation**: 10 requests per minute per storyline
- **ML Processing**: 5 requests per minute per user

---

## 📚 **REFERENCE DOCUMENTATION**

### **Related Documents**
- [CODING_STYLE_GUIDE.md](./CODING_STYLE_GUIDE.md) - Coding standards and conventions
- [DATABASE_SCHEMA_DOCUMENTATION.md](./DATABASE_SCHEMA_DOCUMENTATION.md) - Database schema reference
- [DEVELOPER_QUICK_REFERENCE.md](./DEVELOPER_QUICK_REFERENCE.md) - Quick reference for developers

### **API Testing**
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Spec**: `http://localhost:8000/openapi.json`

---

## ✅ **API COMPLIANCE CHECKLIST**

Before implementing API changes:
- [ ] Follow RESTful conventions
- [ ] Use consistent response format
- [ ] Include proper error handling
- [ ] Add input validation
- [ ] Update documentation
- [ ] Test all endpoints
- [ ] Verify CORS configuration
- [ ] Check rate limiting
- [ ] Validate JSON schemas
- [ ] Test error scenarios

---

*This API documentation follows the standards established in the News Intelligence System Coding Style Guide and should be referenced before any API modifications.*
