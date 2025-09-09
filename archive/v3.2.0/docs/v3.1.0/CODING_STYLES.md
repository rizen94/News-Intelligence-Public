# News Intelligence System v3.1.0 - Coding Styles & Standards

**Version:** 3.1.0  
**Last Updated:** September 7, 2025  
**Scope:** Progressive Enhancement System & Full Stack Development

## 📋 Table of Contents

1. [General Principles](#general-principles)
2. [Python Backend Standards](#python-backend-standards)
3. [JavaScript Frontend Standards](#javascript-frontend-standards)
4. [Database Standards](#database-standards)
5. [API Design Patterns](#api-design-patterns)
6. [Progressive Enhancement Patterns](#progressive-enhancement-patterns)
7. [Error Handling](#error-handling)
8. [Documentation Standards](#documentation-standards)
9. [Testing Standards](#testing-standards)
10. [Deployment Standards](#deployment-standards)

---

## 🎯 General Principles

### Code Quality Standards
- **Readability First**: Code should be self-documenting
- **Consistency**: Follow established patterns throughout the codebase
- **Modularity**: Break functionality into logical, reusable components
- **Performance**: Optimize for both speed and resource usage
- **Maintainability**: Write code that's easy to modify and extend

### Progressive Enhancement Philosophy
- **Graceful Degradation**: System works without advanced features
- **Layered Intelligence**: Basic → Enhanced → Advanced functionality
- **Cost Optimization**: Minimize external API usage through caching
- **Self-Sufficiency**: System operates independently with minimal intervention

---

## 🐍 Python Backend Standards

### File Structure
```
api/
├── services/
│   ├── progressive_enhancement_service.py
│   ├── api_cache_service.py
│   ├── api_usage_monitor.py
│   └── storyline_service.py
├── routes/
│   ├── progressive_enhancement.py
│   └── storylines.py
└── database/
    └── migrations/
        └── 011_api_cache.sql
```

### Service Layer Patterns

#### Service Class Structure
```python
"""
Service Name for News Intelligence System
Brief description of service purpose
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import json

logger = logging.getLogger(__name__)

class ServiceName:
    """Service class with clear purpose"""
    
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        # Initialize service-specific attributes
        
    def _get_db_connection(self):
        """Get database connection - private method"""
        return psycopg2.connect(**self.db_config)
    
    async def public_method(self, param: str) -> Dict[str, Any]:
        """Public method with clear purpose and return type"""
        try:
            # Implementation here
            return {'success': True, 'data': result}
        except Exception as e:
            logger.error(f"Error in public_method: {e}")
            return {'success': False, 'error': str(e)}

# Global instance pattern
_service_instance = None

def get_service_instance() -> ServiceName:
    """Get global service instance"""
    global _service_instance
    if _service_instance is None:
        db_config = {
            'host': os.getenv('DB_HOST', 'news-system-postgres'),
            'database': os.getenv('DB_NAME', 'newsintelligence'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'Database@NEWSINT2025'),
            'port': os.getenv('DB_PORT', '5432')
        }
        _service_instance = ServiceName(db_config)
    return _service_instance
```

#### Progressive Enhancement Service Patterns
```python
class ProgressiveEnhancementService:
    """Service for progressive enhancement of storyline summaries"""
    
    async def create_storyline_with_auto_summary(self, storyline_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create storyline and automatically generate basic summary"""
        try:
            # 1. Create storyline first
            storyline_id = storyline_data.get('id')
            if not storyline_id:
                storyline_id = self._generate_storyline_id(storyline_data)
                storyline_data['id'] = storyline_id
            
            # 2. Save to database
            await self._save_storyline_to_db(storyline_data)
            
            # 3. Generate basic summary immediately
            await self.generate_basic_summary(storyline_id)
            
            return {
                'success': True,
                'storyline_id': storyline_id,
                'message': 'Storyline created with automatic basic summary'
            }
            
        except Exception as e:
            logger.error(f"Error creating storyline with auto summary: {e}")
            return {'success': False, 'error': str(e)}
    
    async def enhance_with_rag(self, storyline_id: str, force: bool = False) -> Dict[str, Any]:
        """Enhance storyline summary with RAG context"""
        try:
            # 1. Check if enhancement is needed
            if not force:
                enhancement_needed = await self._should_enhance_storyline(storyline_id)
                if not enhancement_needed:
                    return {
                        'success': True,
                        'message': 'Enhancement not needed at this time',
                        'skipped': True
                    }
            
            # 2. Get RAG context with monitoring
            rag_context = await self._get_rag_context_with_monitoring(storyline_id)
            
            # 3. Generate enhanced summary
            enhanced_summary = await self._generate_enhanced_summary(storyline_id, rag_context)
            
            # 4. Save as new version
            await self._save_summary_version(storyline_id, enhanced_summary, rag_context)
            
            return {
                'success': True,
                'summary_type': 'rag_enhanced',
                'version': await self._get_current_summary_version(storyline_id),
                'message': 'RAG enhancement completed successfully'
            }
            
        except Exception as e:
            logger.error(f"Error enhancing with RAG: {e}")
            return {'success': False, 'error': str(e)}
```

### Database Patterns

#### Migration Structure
```sql
-- Migration: 011_api_cache.sql
-- Description: Add API caching and progressive enhancement support
-- Date: 2025-09-07

-- Create API cache table
CREATE TABLE IF NOT EXISTS api_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(64) NOT NULL,
    service VARCHAR(50) NOT NULL,
    query TEXT NOT NULL,
    response_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(cache_key, service)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_api_cache_service_key 
ON api_cache (service, cache_key);

CREATE INDEX IF NOT EXISTS idx_api_cache_created_at 
ON api_cache (created_at DESC);
```

#### Query Patterns
```python
async def get_cached_response(self, service: str, query: str) -> Optional[Dict[str, Any]]:
    """Get cached API response if available and not expired"""
    try:
        cache_key = self._get_cache_key(service, query)
        conn = self._get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT response_data, created_at 
            FROM api_cache 
            WHERE cache_key = %s AND service = %s
            ORDER BY created_at DESC 
            LIMIT 1
        """, (cache_key, service))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            # Check if cache is still valid
            cache_age = time.time() - result['created_at'].timestamp()
            max_age = self.cache_durations.get(service, 3600)
            
            if cache_age < max_age:
                logger.info(f"Cache hit for {service}: {query[:50]}...")
                return json.loads(result['response_data'])
            else:
                logger.info(f"Cache expired for {service}: {query[:50]}...")
                return None
        else:
            logger.info(f"Cache miss for {service}: {query[:50]}...")
            return None
            
    except Exception as e:
        logger.error(f"Error getting cached response: {e}")
        return None
```

---

## 🌐 JavaScript Frontend Standards

### File Structure
```
web/
├── index.html (main application)
├── storyline-detail.html (storyline detail page)
└── styles/ (if using separate CSS files)
```

### Progressive Enhancement Frontend Patterns

#### API Call Patterns
```javascript
// Base API configuration
const API_BASE = 'http://localhost:8000/api';

// Progressive enhancement API calls
async function createStorylineWithAutoSummary(storylineData) {
    try {
        const response = await fetch(`${API_BASE}/progressive/storylines/create-with-auto-summary`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(storylineData)
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Handle success - storyline created with auto summary
            displaySuccessMessage(result.message);
            await loadStorylines(); // Refresh the list
        } else {
            throw new Error(result.error || 'Failed to create storyline');
        }
        
    } catch (error) {
        console.error('Error creating storyline:', error);
        displayErrorMessage('Failed to create storyline: ' + error.message);
    }
}

// RAG enhancement with progress tracking
async function enhanceStorylineWithRAG(storylineId) {
    const button = event.target;
    const storylineCard = button.closest('.storyline-card');
    
    try {
        // Set loading state
        button.disabled = true;
        button.innerHTML = `
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" id="progress-${storylineId}"></div>
                </div>
                <span class="progress-text" id="progress-text-${storylineId}">Enhancing with RAG...</span>
            </div>
        `;
        
        // Start progress tracking
        updateProgress(storylineId, 10, 'Starting RAG enhancement...');
        
        // Call RAG enhancement API
        const response = await fetch(`${API_BASE}/progressive/storylines/${storylineId}/enhance-with-rag`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        updateProgress(storylineId, 50, 'Processing with RAG...');
        
        const result = await response.json();
        
        if (result.success) {
            updateProgress(storylineId, 100, 'Enhancement complete!');
            
            // Update the storyline display
            await loadStorylines();
            
            // Reset button
            setTimeout(() => {
                button.disabled = false;
                button.innerHTML = 'Regenerate Summary';
            }, 2000);
            
        } else {
            throw new Error(result.error || 'RAG enhancement failed');
        }
        
    } catch (error) {
        console.error('Error enhancing storyline:', error);
        displayErrorMessage('RAG enhancement failed: ' + error.message);
        
        // Reset button
        button.disabled = false;
        button.innerHTML = 'Enhance with RAG';
    }
}
```

#### UI Component Patterns
```javascript
// RAG status indicator component
function displayRAGStatus(storyline) {
    const ragStatus = storyline.rag_enhanced_at ? `
        <span class="rag-status" title="RAG Enhanced: ${new Date(storyline.rag_enhanced_at).toLocaleString()}">
            🤖 RAG Enhanced
        </span>
    ` : `
        <span class="rag-status pending" title="Not RAG enhanced">
            🤖 Pending
        </span>
    `;
    
    return ragStatus;
}

// AI summary formatting component
function formatAISummary(text) {
    if (!text) return '';
    
    return text
        // Convert headers
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^#### (.+)$/gm, '<h4>$1</h4>')
        // Convert bold text
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        // Convert italic text
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Convert bullet points
        .replace(/^- (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
        // Convert numbered lists
        .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
        .replace(/(<li>.*<\/li>)/s, '<ol>$1</ol>')
        // Convert line breaks to paragraphs
        .replace(/\n\n/g, '</p><p>')
        .replace(/^(.+)$/gm, '<p>$1</p>')
        // Clean up empty paragraphs
        .replace(/<p><\/p>/g, '')
        .replace(/<p>\s*<\/p>/g, '');
}
```

---

## 🗄️ Database Standards

### Table Naming Conventions
- **Snake case**: `storyline_summary_versions`
- **Descriptive names**: `api_usage_tracking`
- **Consistent prefixes**: `idx_` for indexes, `fk_` for foreign keys

### Column Standards
```sql
-- Standard column patterns
id SERIAL PRIMARY KEY,                    -- Auto-incrementing primary key
created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,  -- Creation timestamp
updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,  -- Update timestamp
status VARCHAR(50) DEFAULT 'active',      -- Status field with default
metadata JSONB,                          -- Flexible metadata storage
```

### Index Patterns
```sql
-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_table_name_column 
ON table_name (column_name);

-- Composite indexes for common queries
CREATE INDEX IF NOT EXISTS idx_table_name_composite 
ON table_name (column1, column2, created_at DESC);

-- Unique constraints
CREATE UNIQUE INDEX IF NOT EXISTS idx_table_name_unique 
ON table_name (unique_column1, unique_column2);
```

---

## 🔌 API Design Patterns

### Response Format Standards
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response data here
  },
  "error": null,
  "meta": {
    "timestamp": "2025-09-07T14:30:23.608135+00:00",
    "version": "3.1.0"
  }
}
```

### Error Response Standards
```json
{
  "success": false,
  "message": "Operation failed",
  "data": null,
  "error": "Detailed error message",
  "meta": {
    "timestamp": "2025-09-07T14:30:23.608135+00:00",
    "version": "3.1.0"
  }
}
```

### Endpoint Naming Conventions
- **RESTful**: `/api/storylines/` (GET, POST)
- **Resource-based**: `/api/storylines/{id}/` (GET, PUT, DELETE)
- **Action-based**: `/api/storylines/{id}/generate-summary/` (POST)
- **Progressive enhancement**: `/api/progressive/storylines/{id}/enhance-with-rag` (POST)

---

## 🤖 Progressive Enhancement Patterns

### Layered Intelligence Architecture
```python
# Layer 1: Basic Summary (Fast, Local AI)
async def generate_basic_summary(storyline_id: str) -> Dict[str, Any]:
    """Generate basic summary using local AI only"""
    # Uses only storyline articles
    # Fast processing (2-3 minutes)
    # No external API calls
    # Immediate availability

# Layer 2: RAG Enhancement (External Context)
async def enhance_with_rag(storyline_id: str) -> Dict[str, Any]:
    """Enhance with external context (Wikipedia, GDELT)"""
    # Uses external APIs with caching
    # Moderate processing (5-10 minutes)
    # Builds upon basic summary
    # Enhanced context and accuracy

# Layer 3: Timeline Generation (Temporal Analysis)
async def generate_timeline(storyline_id: str) -> Dict[str, Any]:
    """Generate temporal timeline of events"""
    # Uses RAG-enhanced summary
    # Advanced processing (10-15 minutes)
    # Creates chronological narrative
    # Professional journalistic output
```

### Caching Strategy
```python
# Cache durations by service
CACHE_DURATIONS = {
    'wikipedia': 24 * 60 * 60,  # 24 hours (FREE)
    'gdelt': 60 * 60,           # 1 hour (FREE)
    'newsapi': 30 * 60,         # 30 minutes (PAID)
    'rag_context': 6 * 60 * 60  # 6 hours (CUSTOM)
}

# Cache key generation
def _get_cache_key(self, service: str, query: str) -> str:
    """Generate consistent cache key"""
    return hashlib.md5(f"{service}:{query}".encode()).hexdigest()
```

### Usage Monitoring
```python
# Rate limiting per service
RATE_LIMITS = {
    'wikipedia': 60,     # 1 per second
    'gdelt': 30,         # 1 per 2 seconds
    'newsapi': 30,       # 1 per 2 seconds
    'rag_context': 10    # 1 per 6 seconds
}

# Daily limits
DAILY_LIMITS = {
    'wikipedia': 10000,  # Very generous
    'gdelt': 10000,      # Very generous
    'newsapi': 1000,     # Actual free tier
    'rag_context': 1000  # Custom limit
}
```

---

## ⚠️ Error Handling

### Service Layer Error Handling
```python
async def service_method(self, param: str) -> Dict[str, Any]:
    """Service method with comprehensive error handling"""
    try:
        # Validate input
        if not param or not isinstance(param, str):
            return {
                'success': False,
                'error': 'Invalid parameter: param must be a non-empty string'
            }
        
        # Main logic
        result = await self._perform_operation(param)
        
        # Validate result
        if not result:
            return {
                'success': False,
                'error': 'Operation completed but returned no result'
            }
        
        return {
            'success': True,
            'data': result,
            'message': 'Operation completed successfully'
        }
        
    except ValueError as e:
        logger.warning(f"Validation error in service_method: {e}")
        return {
            'success': False,
            'error': f'Validation error: {str(e)}'
        }
    except ConnectionError as e:
        logger.error(f"Connection error in service_method: {e}")
        return {
            'success': False,
            'error': 'Database connection failed. Please try again later.'
        }
    except Exception as e:
        logger.error(f"Unexpected error in service_method: {e}")
        return {
            'success': False,
            'error': 'An unexpected error occurred. Please contact support.'
        }
```

### Frontend Error Handling
```javascript
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(endpoint, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'API call failed');
        }
        
        return data;
        
    } catch (error) {
        console.error(`API call failed for ${endpoint}:`, error);
        
        // Display user-friendly error message
        displayErrorMessage(`Operation failed: ${error.message}`);
        
        // Return error structure for consistent handling
        return {
            success: false,
            error: error.message
        };
    }
}
```

---

## 📚 Documentation Standards

### Code Documentation
```python
"""
Service Name for News Intelligence System
Brief description of service purpose and functionality
"""

class ServiceName:
    """
    Service class with clear purpose
    
    This service handles [specific functionality] for the News Intelligence System.
    It provides [key features] and integrates with [other components].
    
    Attributes:
        db_config (Dict[str, str]): Database configuration
        cache_service (CacheService): Caching service instance
        usage_monitor (UsageMonitor): API usage monitoring instance
    """
    
    async def method_name(self, param: str, optional_param: Optional[int] = None) -> Dict[str, Any]:
        """
        Method description
        
        This method performs [specific operation] with [specific behavior].
        It handles [error conditions] and returns [response format].
        
        Args:
            param (str): Description of required parameter
            optional_param (Optional[int]): Description of optional parameter
            
        Returns:
            Dict[str, Any]: Response dictionary with success/error status
            
        Raises:
            ValueError: When param is invalid
            ConnectionError: When database connection fails
            
        Example:
            >>> service = ServiceName(db_config)
            >>> result = await service.method_name("test")
            >>> print(result['success'])
            True
        """
```

### API Documentation
```markdown
### Endpoint Name
**Endpoint:** `POST /api/progressive/storylines/{storyline_id}/enhance-with-rag`

**Description:** Enhance storyline summary with RAG context

**Parameters:**
- `storyline_id` (path, required): Unique identifier for the storyline
- `force` (query, optional): Force enhancement even if not needed (default: false)

**Request Body:** None

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

**Error Responses:**
- `400 Bad Request`: Invalid storyline ID or parameters
- `404 Not Found`: Storyline not found
- `500 Internal Server Error`: Server error during processing

**Example Usage:**
```javascript
const response = await fetch('/api/progressive/storylines/123/enhance-with-rag?force=true', {
    method: 'POST'
});
const result = await response.json();
```
```

---

## 🧪 Testing Standards

### Unit Testing Patterns
```python
import pytest
from unittest.mock import Mock, patch
from services.progressive_enhancement_service import ProgressiveEnhancementService

class TestProgressiveEnhancementService:
    """Test suite for ProgressiveEnhancementService"""
    
    @pytest.fixture
    def service(self):
        """Create service instance for testing"""
        db_config = {
            'host': 'test-host',
            'database': 'test-db',
            'user': 'test-user',
            'password': 'test-password',
            'port': '5432'
        }
        return ProgressiveEnhancementService(db_config)
    
    @pytest.mark.asyncio
    async def test_create_storyline_with_auto_summary_success(self, service):
        """Test successful storyline creation with auto summary"""
        # Arrange
        storyline_data = {
            'title': 'Test Storyline',
            'description': 'Test description',
            'status': 'active'
        }
        
        # Mock database operations
        with patch.object(service, '_save_storyline_to_db') as mock_save, \
             patch.object(service, 'generate_basic_summary') as mock_generate:
            
            mock_save.return_value = None
            mock_generate.return_value = {'success': True}
            
            # Act
            result = await service.create_storyline_with_auto_summary(storyline_data)
            
            # Assert
            assert result['success'] is True
            assert 'storyline_id' in result
            assert result['message'] == 'Storyline created with automatic basic summary'
            mock_save.assert_called_once()
            mock_generate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_storyline_with_auto_summary_error(self, service):
        """Test storyline creation with error handling"""
        # Arrange
        storyline_data = {'title': 'Test'}
        
        with patch.object(service, '_save_storyline_to_db') as mock_save:
            mock_save.side_effect = Exception("Database error")
            
            # Act
            result = await service.create_storyline_with_auto_summary(storyline_data)
            
            # Assert
            assert result['success'] is False
            assert 'error' in result
            assert 'Database error' in result['error']
```

### Integration Testing
```python
@pytest.mark.integration
async def test_progressive_enhancement_workflow():
    """Test complete progressive enhancement workflow"""
    # 1. Create storyline with auto summary
    storyline_data = {
        'title': 'Integration Test Storyline',
        'description': 'Test description'
    }
    
    create_response = await client.post(
        '/api/progressive/storylines/create-with-auto-summary',
        json=storyline_data
    )
    assert create_response.status_code == 200
    
    storyline_id = create_response.json()['data']['storyline_id']
    
    # 2. Verify basic summary was created
    summary_response = await client.get(
        f'/api/progressive/storylines/{storyline_id}/summary-history'
    )
    assert summary_response.status_code == 200
    
    history = summary_response.json()['data']['summary_history']
    assert len(history) >= 1
    assert history[0]['summary_type'] == 'basic'
    
    # 3. Enhance with RAG
    enhance_response = await client.post(
        f'/api/progressive/storylines/{storyline_id}/enhance-with-rag'
    )
    assert enhance_response.status_code == 200
    
    # 4. Verify RAG enhancement was created
    updated_history = await client.get(
        f'/api/progressive/storylines/{storyline_id}/summary-history'
    )
    history = updated_history.json()['data']['summary_history']
    assert len(history) >= 2
    assert any(version['summary_type'] == 'rag_enhanced' for version in history)
```

---

## 🚀 Deployment Standards

### Docker Configuration
```dockerfile
# Dockerfile.optimized
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Start application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Configuration
```bash
# .env.production
# Database Configuration
DB_HOST=news-system-postgres
DB_NAME=newsintelligence
DB_USER=newsapp
DB_PASSWORD=Database@NEWSINT2025
DB_PORT=5432

# API Configuration
API_BASE_URL=http://localhost:8000/api
CORS_ORIGINS=http://localhost:3001,https://yourdomain.com

# Progressive Enhancement Configuration
CACHE_ENABLED=true
RAG_ENHANCEMENT_ENABLED=true
AUTO_SUMMARY_GENERATION=true

# Rate Limiting
WIKIPEDIA_DAILY_LIMIT=10000
GDELT_DAILY_LIMIT=10000
NEWSAPI_DAILY_LIMIT=1000

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true
```

### Migration Standards
```sql
-- Migration: 011_api_cache.sql
-- Version: 3.1.0
-- Date: 2025-09-07
-- Description: Add API caching and progressive enhancement support

-- Create API cache table
CREATE TABLE IF NOT EXISTS api_cache (
    id SERIAL PRIMARY KEY,
    cache_key VARCHAR(64) NOT NULL,
    service VARCHAR(50) NOT NULL,
    query TEXT NOT NULL,
    response_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(cache_key, service)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_api_cache_service_key 
ON api_cache (service, cache_key);

CREATE INDEX IF NOT EXISTS idx_api_cache_created_at 
ON api_cache (created_at DESC);

-- Add summary versioning table
CREATE TABLE IF NOT EXISTS storyline_summary_versions (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) NOT NULL,
    version_number INTEGER NOT NULL,
    summary_type VARCHAR(50) NOT NULL,
    summary_content TEXT NOT NULL,
    rag_context JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50) DEFAULT 'system',
    
    FOREIGN KEY (storyline_id) REFERENCES storylines(id) ON DELETE CASCADE
);

-- Create indexes for summary versions
CREATE INDEX IF NOT EXISTS idx_storyline_summary_versions_storyline_id 
ON storyline_summary_versions (storyline_id);

CREATE INDEX IF NOT EXISTS idx_storyline_summary_versions_created_at 
ON storyline_summary_versions (created_at DESC);
```

---

## 📊 Performance Standards

### Database Performance
- **Query Timeout**: 30 seconds maximum
- **Connection Pool**: 10-20 connections
- **Index Coverage**: All frequently queried columns
- **Query Optimization**: Use EXPLAIN ANALYZE for complex queries

### API Performance
- **Response Time**: < 2 seconds for basic operations
- **RAG Enhancement**: < 10 minutes for complex storylines
- **Cache Hit Rate**: > 80% for external API calls
- **Memory Usage**: < 512MB per service instance

### Frontend Performance
- **Page Load Time**: < 3 seconds
- **API Call Timeout**: 30 seconds
- **Progress Updates**: Every 2-3 seconds during long operations
- **Error Recovery**: Graceful fallback for failed operations

---

## 🔒 Security Standards

### Input Validation
```python
def validate_storyline_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate storyline data with security checks"""
    if not isinstance(data, dict):
        raise ValueError("Data must be a dictionary")
    
    # Validate title
    title = data.get('title', '').strip()
    if not title or len(title) > 255:
        raise ValueError("Title must be 1-255 characters")
    
    # Sanitize description
    description = data.get('description', '').strip()
    if len(description) > 1000:
        raise ValueError("Description must be less than 1000 characters")
    
    # Validate status
    status = data.get('status', 'active')
    if status not in ['active', 'inactive', 'archived']:
        raise ValueError("Status must be active, inactive, or archived")
    
    return {
        'title': title,
        'description': description,
        'status': status
    }
```

### SQL Injection Prevention
```python
# Always use parameterized queries
cursor.execute("""
    SELECT * FROM storylines 
    WHERE id = %s AND status = %s
""", (storyline_id, status))

# Never use string formatting for SQL
# BAD: cursor.execute(f"SELECT * FROM storylines WHERE id = '{storyline_id}'")
# GOOD: cursor.execute("SELECT * FROM storylines WHERE id = %s", (storyline_id,))
```

### CORS Configuration
```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

---

## 📈 Monitoring Standards

### Logging Configuration
```python
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('logs/application.log')
    ]
)

# Service-specific logging
logger = logging.getLogger(__name__)

# Log levels by importance
logger.debug("Detailed debugging information")
logger.info("General information about program execution")
logger.warning("Something unexpected happened")
logger.error("A serious error occurred")
logger.critical("A very serious error occurred")
```

### Metrics Collection
```python
# Track API usage
async def record_api_call(service: str, endpoint: str, success: bool, duration_ms: int):
    """Record API call metrics"""
    metrics = {
        'service': service,
        'endpoint': endpoint,
        'success': success,
        'duration_ms': duration_ms,
        'timestamp': datetime.now().isoformat()
    }
    
    # Store in database
    await store_metrics(metrics)
    
    # Log for monitoring
    logger.info(f"API call: {service}/{endpoint} - {duration_ms}ms - {'SUCCESS' if success else 'FAILED'}")
```

---

## 🎯 Best Practices Summary

### Code Quality
1. **Write self-documenting code** with clear variable and function names
2. **Use type hints** for all function parameters and return values
3. **Follow the single responsibility principle** - one function, one purpose
4. **Handle errors gracefully** with appropriate user feedback
5. **Write tests** for all new functionality

### Progressive Enhancement
1. **Start with basic functionality** that works without external dependencies
2. **Layer enhancements** on top of the basic functionality
3. **Cache aggressively** to minimize external API usage
4. **Monitor usage** to stay within free tier limits
5. **Provide fallbacks** when external services are unavailable

### Performance
1. **Optimize database queries** with proper indexing
2. **Use connection pooling** for database connections
3. **Implement caching** for frequently accessed data
4. **Monitor resource usage** and optimize accordingly
5. **Use async/await** for I/O operations

### Security
1. **Validate all inputs** before processing
2. **Use parameterized queries** to prevent SQL injection
3. **Implement proper CORS** configuration
4. **Log security events** for monitoring
5. **Keep dependencies updated** to avoid vulnerabilities

This coding styles document should be followed by all developers working on the News Intelligence System v3.1.0 to ensure consistency, maintainability, and quality across the entire codebase.


