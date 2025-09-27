# API Reference - News Intelligence System v3.0

**Base URL**: `http://localhost:8000`  
**API Version**: v3.0  
**Last Updated**: September 26, 2025

## 🎯 Overview

The News Intelligence System API provides comprehensive endpoints for news aggregation, analysis, and storyline management. All endpoints return JSON responses with a consistent structure.

## 📋 Response Format

All API responses follow this structure:
```json
{
  "success": boolean,
  "data": object|array,
  "message": string,
  "timestamp": string
}
```

## 🔗 Core Endpoints

### **Health & Status**

#### `GET /api/health/`
**Description**: System health check  
**Response**: System status and component health

```bash
curl http://localhost:8000/api/health/
```

**Response**:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "timestamp": "2025-09-26T14:00:00Z",
    "components": {
      "database": "healthy",
      "redis": "healthy",
      "api": "healthy"
    }
  },
  "message": "System is healthy"
}
```

## 📰 Article Management

### **Get Articles**
#### `GET /api/articles/`
**Description**: Retrieve paginated list of articles  
**Parameters**:
- `page` (int, optional): Page number (default: 1)
- `limit` (int, optional): Items per page (default: 20, max: 100)
- `search` (string, optional): Search in title and content
- `source` (string, optional): Filter by source
- `category` (string, optional): Filter by category
- `status` (string, optional): Filter by status
- `sort` (string, optional): Sort field (default: created_at)
- `sort_order` (string, optional): Sort order asc/desc (default: desc)

```bash
curl "http://localhost:8000/api/articles/?page=1&limit=10&source=CNN"
```

### **Get Article by ID**
#### `GET /api/articles/{article_id}`
**Description**: Retrieve specific article by ID

```bash
curl http://localhost:8000/api/articles/1
```

### **Article Statistics**
#### `GET /api/articles/stats/overview`
**Description**: Get comprehensive article statistics

```bash
curl http://localhost:8000/api/articles/stats/overview
```

**Response**:
```json
{
  "success": true,
  "data": {
    "total_articles": 150,
    "sources": {
      "CNN": 45,
      "BBC": 38,
      "Reuters": 32,
      "Fox News": 25,
      "MSNBC": 10
    },
    "categories": {
      "Politics": 89,
      "Technology": 34,
      "Business": 27
    },
    "status_distribution": {
      "processed": 120,
      "pending": 25,
      "failed": 5
    }
  }
}
```

### **Article Sources**
#### `GET /api/articles/sources`
**Description**: Get list of article sources

```bash
curl http://localhost:8000/api/articles/sources
```

### **Article Categories**
#### `GET /api/articles/categories`
**Description**: Get list of article categories

```bash
curl http://localhost:8000/api/articles/categories
```

## 📡 RSS Feed Management

### **Get RSS Feeds**
#### `GET /api/rss/feeds/`
**Description**: Retrieve all RSS feeds

```bash
curl http://localhost:8000/api/rss/feeds/
```

### **RSS Feed Statistics**
#### `GET /api/rss/feeds/stats/overview`
**Description**: Get RSS feed statistics

```bash
curl http://localhost:8000/api/rss/feeds/stats/overview
```

**Response**:
```json
{
  "success": true,
  "data": {
    "total_feeds": 5,
    "active_feeds": 5,
    "inactive_feeds": 0,
    "total_articles": 150,
    "feeds": [
      {
        "name": "CNN Politics",
        "url": "http://rss.cnn.com/rss/edition_politics.rss",
        "is_active": true,
        "last_fetched": "2025-09-26T13:45:00Z",
        "article_count": 45
      }
    ]
  }
}
```

## 📚 Storyline Management

### **Get Storylines**
#### `GET /api/storylines/`
**Description**: Retrieve all storylines

```bash
curl http://localhost:8000/api/storylines/
```

**Response**:
```json
{
  "success": true,
  "data": {
    "total_storylines": 12,
    "storylines": [
      {
        "id": 1,
        "title": "2024 Election Coverage",
        "description": "Comprehensive coverage of 2024 election",
        "created_at": "2025-09-26T10:00:00Z",
        "article_count": 25,
        "status": "active"
      }
    ]
  }
}
```

### **Get Storyline by ID**
#### `GET /api/storylines/{storyline_id}`
**Description**: Retrieve specific storyline with articles

```bash
curl http://localhost:8000/api/storylines/1
```

## 🔍 Intelligence & Analytics

### **Deduplication Statistics**
#### `GET /api/deduplication/statistics`
**Description**: Get duplicate detection statistics

```bash
curl http://localhost:8000/api/deduplication/statistics
```

**Response**:
```json
{
  "success": true,
  "data": {
    "total_articles": 150,
    "unique_articles": 120,
    "duplicates_found": 30,
    "clusters": 8,
    "deduplication_rate": 0.2
  }
}
```

### **Intelligence Analytics**
#### `GET /api/intelligence/analytics/summary`
**Description**: Get intelligence analytics summary

```bash
curl http://localhost:8000/api/intelligence/analytics/summary
```

## 🚨 Error Handling

### **Error Response Format**
```json
{
  "success": false,
  "data": null,
  "message": "Error description",
  "error_code": "ERROR_CODE",
  "timestamp": "2025-09-26T14:00:00Z"
}
```

### **Common HTTP Status Codes**
- `200` - Success
- `400` - Bad Request
- `404` - Not Found
- `500` - Internal Server Error

### **Error Examples**
```json
{
  "success": false,
  "data": null,
  "message": "Article not found",
  "error_code": "ARTICLE_NOT_FOUND",
  "timestamp": "2025-09-26T14:00:00Z"
}
```

## 🔧 Authentication

Currently, the API does not require authentication. All endpoints are publicly accessible.

## 📊 Rate Limiting

No rate limiting is currently implemented. Monitor system performance and implement if needed.

## 🧪 Testing

### **Test All Endpoints**
```bash
# Health check
curl http://localhost:8000/api/health/

# Articles
curl http://localhost:8000/api/articles/
curl http://localhost:8000/api/articles/stats/overview

# RSS Feeds
curl http://localhost:8000/api/rss/feeds/
curl http://localhost:8000/api/rss/feeds/stats/overview

# Storylines
curl http://localhost:8000/api/storylines/

# Analytics
curl http://localhost:8000/api/deduplication/statistics
curl http://localhost:8000/api/intelligence/analytics/summary
```

### **Integration Test**
```bash
# Run full integration test
python3 scripts/simple_integration.py
```

## 📚 OpenAPI Documentation

Interactive API documentation is available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 🔄 API Versioning

Current API version: v3.0
- All endpoints are under `/api/` prefix
- Version information in response headers
- Backward compatibility maintained

---

**API Status**: 🟢 **FULLY OPERATIONAL**  
**Last Updated**: September 26, 2025  
**Next Review**: Recommended monthly
