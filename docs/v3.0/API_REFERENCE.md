# News Intelligence System v3.0 - API Reference

**Version:** 3.0  
**Base URL:** `http://localhost:8000/api`  
**Last Updated:** September 7, 2025

## 🔗 Base Information

- **API Version:** 3.0
- **Protocol:** HTTP/HTTPS
- **Content Type:** `application/json`
- **Authentication:** None (development mode)
- **Rate Limiting:** None (development mode)

## 📊 Response Format

All API responses follow this standard format:

```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response data here
  },
  "error": null
}
```

### Error Response Format

```json
{
  "success": false,
  "message": "Operation failed",
  "data": null,
  "error": "Detailed error message"
}
```

## 📰 Articles API

### Get Articles
**Endpoint:** `GET /articles/`

**Description:** Retrieve articles with pagination, search, and filtering

**Parameters:**
- `limit` (integer, optional): Number of articles per page (default: 20)
- `page` (integer, optional): Page number (default: 1)
- `search` (string, optional): Search term for article titles
- `source` (string, optional): Filter by news source

**Example Request:**
```bash
curl "http://localhost:8000/api/articles/?limit=20&page=1&search=ukraine&source=bbc"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "articles": [
      {
        "id": "article_123",
        "title": "Article Title",
        "content": "Article content...",
        "url": "https://example.com/article",
        "published_at": "2025-01-05T10:30:00Z",
        "source": "BBC News",
        "tags": ["politics", "international"],
        "created_at": "2025-01-05T10:35:00Z",
        "sentiment_score": 0.2,
        "entities": {"people": ["John Doe"], "places": ["Ukraine"]},
        "readability_score": 12.5,
        "quality_score": 0.85,
        "summary": "AI-generated summary...",
        "ml_data": {"analysis": "detailed_analysis"},
        "language": "en",
        "word_count": 450,
        "reading_time": 3
      }
    ],
    "total_count": 103,
    "limit": 20,
    "page": 1,
    "total_pages": 6
  }
}
```

### Delete Article
**Endpoint:** `DELETE /articles/{article_id}`

**Description:** Delete a specific article

**Parameters:**
- `article_id` (string, required): Article ID

**Example Request:**
```bash
curl -X DELETE "http://localhost:8000/api/articles/article_123"
```

**Response:**
```json
{
  "success": true,
  "message": "Article deleted successfully",
  "data": {
    "article_id": "article_123",
    "status": "deleted"
  }
}
```

## 📚 Storylines API

### Get All Storylines
**Endpoint:** `GET /storylines/`

**Description:** Retrieve all storylines with pagination

**Parameters:**
- `limit` (integer, optional): Number of storylines per page (default: 20)
- `offset` (integer, optional): Number of storylines to skip (default: 0)

**Example Request:**
```bash
curl "http://localhost:8000/api/storylines/"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "storylines": [
      {
        "id": "storyline_20250105_123456_1234",
        "title": "Ukraine Conflict Updates",
        "description": "Latest developments in the Ukraine conflict",
        "status": "active",
        "created_at": "2025-01-05T10:00:00Z",
        "updated_at": "2025-01-05T15:30:00Z",
        "master_summary": "AI-generated storyline summary...",
        "article_count": 15
      }
    ],
    "total_count": 5,
    "limit": 20,
    "offset": 0
  }
}
```

### Create Storyline
**Endpoint:** `POST /storylines/`

**Description:** Create a new storyline

**Request Body:**
```json
{
  "title": "Storyline Title",
  "description": "Optional description"
}
```

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/storylines/" \
  -H "Content-Type: application/json" \
  -d '{"title": "New Storyline", "description": "Description here"}'
```

**Response:**
```json
{
  "success": true,
  "message": "Storyline created successfully",
  "data": {
    "id": "storyline_20250105_123456_1234",
    "title": "New Storyline",
    "description": "Description here",
    "status": "active",
    "article_count": 0,
    "created_at": "2025-01-05T10:00:00Z"
  }
}
```

### Add Article to Storyline
**Endpoint:** `POST /storylines/{storyline_id}/add-article/`

**Description:** Add an article to a storyline

**Parameters:**
- `storyline_id` (string, required): Storyline ID

**Request Body:**
```json
{
  "article_id": "article_123",
  "relevance_score": 0.8,
  "importance_score": 0.9
}
```

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/storylines/storyline_123/add-article/" \
  -H "Content-Type: application/json" \
  -d '{"article_id": "article_123"}'
```

**Response:**
```json
{
  "success": true,
  "message": "Article added to storyline successfully",
  "data": {
    "storyline_id": "storyline_123",
    "article_id": "article_123",
    "status": "added"
  }
}
```

### Remove Article from Storyline
**Endpoint:** `DELETE /storylines/{storyline_id}/articles/{article_id}/`

**Description:** Remove an article from a storyline

**Parameters:**
- `storyline_id` (string, required): Storyline ID
- `article_id` (string, required): Article ID

**Example Request:**
```bash
curl -X DELETE "http://localhost:8000/api/storylines/storyline_123/articles/article_123/"
```

**Response:**
```json
{
  "success": true,
  "message": "Article removed from storyline successfully",
  "data": {
    "storyline_id": "storyline_123",
    "article_id": "article_123",
    "status": "removed"
  }
}
```

### Generate Storyline Summary
**Endpoint:** `POST /storylines/{storyline_id}/generate-summary/`

**Description:** Generate AI-powered summary for a storyline

**Parameters:**
- `storyline_id` (string, required): Storyline ID

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/storylines/storyline_123/generate-summary/"
```

**Response:**
```json
{
  "success": true,
  "message": "Storyline summary generated successfully",
  "data": {
    "storyline_id": "storyline_123",
    "summary": "AI-generated comprehensive summary...",
    "generated_at": "2025-01-05T10:00:00Z"
  }
}
```

## 🔄 Processing API

### Process Article
**Endpoint:** `POST /processing/process-article/`

**Description:** Process a single article for content extraction and cleaning

**Request Body:**
```json
{
  "url": "https://example.com/article"
}
```

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/processing/process-article/" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article"}'
```

**Response:**
```json
{
  "success": true,
  "message": "Article processed successfully",
  "data": {
    "url": "https://example.com/article",
    "title": "Extracted Title",
    "content": "Cleaned article content...",
    "word_count": 450,
    "reading_time": 3
  }
}
```

### Process Default Feeds
**Endpoint:** `POST /processing/process-default-feeds/`

**Description:** Process all configured RSS feeds

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/processing/process-default-feeds/"
```

**Response:**
```json
{
  "success": true,
  "message": "RSS feeds processed successfully",
  "data": {
    "articles_processed": 25,
    "feeds_processed": 5,
    "processing_time": "2.5s"
  }
}
```

## 📊 Clusters API

### Get Topic Clusters
**Endpoint:** `GET /clusters/`

**Description:** Get topic clusters based on recent articles

**Example Request:**
```bash
curl "http://localhost:8000/api/clusters/"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "clusters": [
      {
        "id": "cluster_1",
        "topic": "Ukraine Conflict",
        "article_count": 15,
        "keywords": ["ukraine", "russia", "war", "conflict"],
        "relevance_score": 0.95
      }
    ],
    "total_clusters": 8,
    "generated_at": "2025-01-05T10:00:00Z"
  }
}
```

### Get Word Cloud Data
**Endpoint:** `GET /clusters/word-cloud/`

**Description:** Get word cloud data for visualization

**Example Request:**
```bash
curl "http://localhost:8000/api/clusters/word-cloud/"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "words": [
      {"text": "ukraine", "weight": 45},
      {"text": "russia", "weight": 38},
      {"text": "war", "weight": 32},
      {"text": "conflict", "weight": 28}
    ],
    "total_words": 50,
    "generated_at": "2025-01-05T10:00:00Z"
  }
}
```

## 📈 Dashboard API

### Get Dashboard Data
**Endpoint:** `GET /dashboard/`

**Description:** Get dashboard statistics and overview data

**Example Request:**
```bash
curl "http://localhost:8000/api/dashboard/"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "total_articles": 103,
    "total_storylines": 5,
    "recent_articles": 25,
    "system_health": "healthy",
    "last_updated": "2025-01-05T10:00:00Z"
  }
}
```

## 🏥 Health API

### Health Check
**Endpoint:** `GET /health/`

**Description:** Check system health status

**Example Request:**
```bash
curl "http://localhost:8000/api/health/"
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-01-05T10:00:00Z",
  "services": {
    "database": "healthy",
    "redis": "healthy",
    "ai_processing": "healthy"
  }
}
```

## 🔧 Error Codes

### HTTP Status Codes
- `200` - Success
- `400` - Bad Request
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

### Common Error Messages
- `"Article not found"` - Article ID doesn't exist
- `"Storyline not found"` - Storyline ID doesn't exist
- `"Invalid parameters"` - Request parameters are invalid
- `"Database connection error"` - Database connectivity issue
- `"AI processing failed"` - AI model processing error

## 📝 Usage Examples

### Frontend Integration

#### Load Articles with Pagination
```javascript
async function loadArticles(page = 1, limit = 20, search = '', source = '') {
  const params = new URLSearchParams({
    page: page,
    limit: limit
  });
  
  if (search) params.append('search', search);
  if (source) params.append('source', source);
  
  const response = await fetch(`http://localhost:8000/api/articles/?${params}`);
  const data = await response.json();
  
  if (data.success) {
    displayArticles(data.data.articles);
    updatePagination(data.data);
  }
}
```

#### Add Article to Storyline
```javascript
async function addToStoryline(storylineId, articleId) {
  const response = await fetch(`http://localhost:8000/api/storylines/${storylineId}/add-article/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      article_id: articleId
    })
  });
  
  const result = await response.json();
  
  if (result.success) {
    console.log('Article added to storyline');
  } else {
    console.error('Error:', result.error);
  }
}
```

#### Search Articles
```javascript
async function searchArticles(searchTerm) {
  const response = await fetch(`http://localhost:8000/api/articles/?search=${encodeURIComponent(searchTerm)}`);
  const data = await response.json();
  
  if (data.success) {
    displaySearchResults(data.data.articles);
  }
}
```

## 🤖 Progressive Enhancement API

### Create Storyline with Auto Summary
**Endpoint:** `POST /progressive/storylines/create-with-auto-summary`

**Description:** Create a new storyline with automatic basic summary generation

**Request Body:**
```json
{
  "title": "Storyline Title",
  "description": "Optional description",
  "status": "active",
  "created_by": "user"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "storyline_id": "storyline_20250907_140051_6428",
    "message": "Storyline created with automatic basic summary"
  }
}
```

### Generate Basic Summary
**Endpoint:** `POST /progressive/storylines/{storyline_id}/generate-basic-summary`

**Description:** Generate a basic summary for an existing storyline

**Response:**
```json
{
  "success": true,
  "data": {
    "summary_type": "basic",
    "version": 1,
    "message": "Basic summary generated successfully"
  }
}
```

### Enhance with RAG
**Endpoint:** `POST /progressive/storylines/{storyline_id}/enhance-with-rag`

**Description:** Enhance storyline summary with RAG context

**Parameters:**
- `force` (boolean, optional): Force enhancement even if not needed (default: false)

**Response:**
```json
{
  "success": true,
  "data": {
    "summary_type": "rag_enhanced",
    "version": 2,
    "message": "RAG enhancement completed successfully"
  }
}
```

### Get Summary History
**Endpoint:** `GET /progressive/storylines/{storyline_id}/summary-history`

**Description:** Get summary version history for a storyline

**Response:**
```json
{
  "success": true,
  "data": {
    "storyline_id": "storyline_20250907_140051_6428",
    "summary_history": [
      {
        "version_number": 1,
        "summary_type": "basic",
        "summary_content": "Basic summary content...",
        "created_at": "2025-09-07T14:00:51.165690+00:00",
        "created_by": "system"
      },
      {
        "version_number": 2,
        "summary_type": "rag_enhanced",
        "summary_content": "Enhanced summary with RAG context...",
        "rag_context": {...},
        "created_at": "2025-09-07T14:30:23.608135+00:00",
        "created_by": "system"
      }
    ],
    "total_versions": 2
  }
}
```

### API Usage Statistics
**Endpoint:** `GET /progressive/api-usage/stats`

**Description:** Get API usage statistics and monitoring data

**Parameters:**
- `service` (string, optional): Filter by specific service
- `days` (integer, optional): Number of days to include (default: 7)

**Response:**
```json
{
  "success": true,
  "data": {
    "usage_stats": [
      {
        "service": "wikipedia",
        "total_requests": 15,
        "successful_requests": 15,
        "failed_requests": 0,
        "avg_response_size": 2048,
        "avg_processing_time": 120,
        "usage_percentage": 0.15,
        "remaining_requests": 9985
      }
    ],
    "daily_limits": {
      "wikipedia": 10000,
      "gdelt": 10000,
      "newsapi": 1000,
      "rag_context": 1000
    },
    "rate_limits": {
      "wikipedia": 60,
      "gdelt": 30,
      "newsapi": 30,
      "rag_context": 10
    }
  }
}
```

### Service Status
**Endpoint:** `GET /progressive/api-usage/service/{service_name}/status`

**Description:** Get current status of a specific service

**Response:**
```json
{
  "success": true,
  "data": {
    "service": "wikipedia",
    "rate_limit_ok": true,
    "daily_limit_ok": true,
    "status": "healthy",
    "today_usage": {
      "total_requests": 15,
      "successful_requests": 15,
      "failed_requests": 0
    },
    "daily_limit": 10000,
    "rate_limit": 60
  }
}
```

### Cache Statistics
**Endpoint:** `GET /progressive/cache/stats`

**Description:** Get cache statistics and performance data

**Response:**
```json
{
  "success": true,
  "data": {
    "cache_stats": [
      {
        "service": "wikipedia",
        "total_entries": 25,
        "recent_entries": 5,
        "avg_response_size": 2048,
        "last_cached": "2025-09-07T14:30:23.608135+00:00"
      }
    ],
    "cache_durations": {
      "wikipedia": 86400,
      "gdelt": 3600,
      "newsapi": 1800,
      "rag_context": 21600
    },
    "total_services": 4
  }
}
```

### Cache Cleanup
**Endpoint:** `POST /progressive/cache/cleanup`

**Description:** Clean up expired cache entries

**Response:**
```json
{
  "success": true,
  "data": {
    "cleared_entries": 12,
    "message": "Cleared 12 expired cache entries"
  }
}
```

## 🚀 Rate Limiting

Currently, no rate limiting is implemented in development mode. For production deployment, consider implementing:

- **Per-IP Rate Limiting:** 100 requests per minute
- **Per-Endpoint Limits:** 50 requests per minute for heavy operations
- **Burst Allowance:** 10 requests per second

## 🔒 Security Considerations

### Current Security Measures
- **Input Validation:** All parameters validated
- **SQL Injection Prevention:** Parameterized queries
- **CORS Configuration:** Configured for localhost development

### Production Recommendations
- **Authentication:** Implement JWT or OAuth2
- **HTTPS:** Use SSL certificates
- **Rate Limiting:** Implement request throttling
- **Input Sanitization:** Enhanced input cleaning
- **API Keys:** Implement API key authentication

## 📚 Additional Resources

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **OpenAPI Spec:** http://localhost:8000/openapi.json
- **Project Documentation:** PROJECT_STATUS_v3.0.md

---

**API Version:** 3.0  
**Last Updated:** January 5, 2025  
**Maintainer:** AI Assistant
