# 🎨 News Intelligence System v3.0 - Coding Style Guide

## 📋 **OVERVIEW**

This document establishes coding standards, conventions, and system requirements for the News Intelligence System to ensure consistency across all components, whether developed by AI agents or human developers.

---

## 🌐 **ENVIRONMENT VARIABLES**

### **Database Configuration**
```bash
# PostgreSQL Database
DB_HOST=postgres                    # Database host (Docker service name)
DB_NAME=news_system                 # Database name
DB_USER=newsapp                    # Database user
DB_PASSWORD=newsapp123             # Database password
DB_PORT=5432                       # Database port

# Redis Configuration
REDIS_HOST=redis                   # Redis host (Docker service name)
REDIS_PORT=6379                    # Redis port
REDIS_PASSWORD=                    # Redis password (empty for local)
```

### **API Configuration**
```bash
# FastAPI Backend
API_HOST=0.0.0.0                  # API host
API_PORT=8000                      # API port
API_WORKERS=4                      # Number of workers
API_RELOAD=false                   # Auto-reload (false for production)

# CORS Configuration
CORS_ORIGINS=http://localhost:3000,http://localhost:3001  # Allowed origins
```

### **ML/AI Configuration**
```bash
# Ollama Configuration
OLLAMA_HOST=localhost              # Ollama host
OLLAMA_PORT=11434                  # Ollama port
OLLAMA_MODEL=deepseek-coder:33b    # Default model for coding
OLLAMA_API_BASE=http://localhost:11434/v1  # API base URL

# ML Pipeline
ML_BATCH_SIZE=10                   # ML processing batch size
ML_MAX_WORKERS=2                   # Maximum ML workers
ML_CACHE_SIZE=1000                 # ML cache size
```

### **Monitoring & Logging**
```bash
# Logging Configuration
LOG_LEVEL=INFO                     # Log level (DEBUG, INFO, WARNING, ERROR)
LOG_FORMAT=json                    # Log format (json, text)
LOG_FILE=logs/app.log              # Log file path

# Monitoring
METRICS_ENABLED=true               # Enable metrics collection
METRICS_PORT=9090                  # Prometheus metrics port
HEALTH_CHECK_INTERVAL=30           # Health check interval (seconds)
```

### **RSS Collection**
```bash
# RSS Configuration
RSS_COLLECTION_INTERVAL=15         # Collection interval (minutes)
RSS_TIMEOUT=30                     # RSS request timeout (seconds)
RSS_MAX_ARTICLES_PER_FEED=50       # Max articles per feed per run
RSS_USER_AGENT=NewsIntelligence/3.0  # User agent for RSS requests
```

---

## 🔌 **PORT RESERVATIONS**

### **Reserved Ports**
```bash
# Backend Services
8000  - FastAPI Backend API        # Main API server
8001  - FastAPI Backend Admin      # Admin interface (reserved)
8002  - FastAPI Backend Metrics    # Metrics endpoint (reserved)

# Frontend Services
3000  - React Development Server   # Development frontend
3001  - React Production Server    # Production frontend (reserved)
3002  - React Admin Interface      # Admin frontend (reserved)

# Database Services
5432  - PostgreSQL Database        # Main database
5433  - PostgreSQL Admin           # Admin database (reserved)
5434  - PostgreSQL Backup          # Backup database (reserved)

# Cache Services
6379  - Redis Cache                # Main cache
6380  - Redis Admin                # Admin cache (reserved)
6381  - Redis Backup               # Backup cache (reserved)

# Monitoring Services
9090  - Prometheus Metrics         # Metrics collection
9091  - Prometheus Admin           # Prometheus admin (reserved)
3001  - Grafana Dashboard          # Monitoring dashboard
3002  - Grafana Admin              # Grafana admin (reserved)

# AI/ML Services
11434 - Ollama API                 # Local AI model server
11435 - Ollama Admin               # Ollama admin (reserved)
11436 - Ollama Backup              # Ollama backup (reserved)

# Development Tools
8080  - Development Tools           # General development
8081  - Testing Tools              # Testing utilities
8082  - Debugging Tools            # Debugging utilities
```

### **Port Usage Rules**
- **Never use reserved ports** for other services
- **Always document** new port assignments
- **Use port ranges** for related services (e.g., 8000-8009 for API services)
- **Test port availability** before assigning new ports

---

## 👥 **USER REQUIREMENTS & PERMISSIONS**

### **System Users**
```bash
# Docker Container Users
postgres:999:999                   # PostgreSQL user (UID:GID)
newsapp:1000:1000                  # Application user (UID:GID)
redis:1001:1001                    # Redis user (UID:GID)

# Host System Users
pete:1000:1000                     # Primary developer (UID:GID)
docker:999:999                     # Docker group
```

### **File Permissions**
```bash
# Application Files
/app/                              # 755 (rwxr-xr-x)
/app/logs/                         # 777 (rwxrwxrwx)
/app/data/                         # 755 (rwxr-xr-x)
/app/backups/                      # 755 (rwxr-xr-x)

# Database Files
/var/lib/postgresql/data/          # 700 (rwx------)
/var/log/postgresql/               # 755 (rwxr-xr-x)

# Configuration Files
*.conf                             # 644 (rw-r--r--)
*.env                              # 600 (rw-------)
*.key                              # 600 (rw-------)
```

### **Docker Volume Permissions**
```bash
# Named Volumes (Recommended)
postgres_data:/var/lib/postgresql/data
postgres_backups:/backups
postgres_logs:/var/log/postgresql
redis_data:/data

# Bind Mounts (Use with caution)
/mnt/terramaster-nas/docker-postgres-data/pgdata:/var/lib/postgresql/data
```

---

## 🐍 **PYTHON CODING STANDARDS**

### **Import Organization**
```python
# Standard library imports
import os
import sys
import logging
from datetime import datetime
from typing import Dict, List, Optional

# Third-party imports
import psycopg2
import feedparser
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Local imports
from config.database import get_db_connection
from modules.intelligence import IntelligenceOrchestrator
```

### **Function Naming**
```python
# Use snake_case for functions
def collect_rss_feeds() -> int:
    """Collect articles from RSS feeds"""
    pass

def process_article_content(article_id: int) -> bool:
    """Process article content through ML pipeline"""
    pass

# Use descriptive names
def get_active_stories() -> List[Dict]:
    """Get all active story threads"""
    pass
```

### **Class Naming**
```python
# Use PascalCase for classes
class RSSCollector:
    """RSS feed collection system"""
    pass

class IntelligenceOrchestrator:
    """Orchestrates intelligence processing pipeline"""
    pass

class StoryControlSystem:
    """Manages story expectations and targets"""
    pass
```

### **Variable Naming**
```python
# Use snake_case for variables
article_count = 0
feed_url = "https://example.com/rss"
processing_status = "pending"

# Use descriptive names
total_articles_collected = 0
last_successful_collection = datetime.now()
```

### **Constants**
```python
# Use UPPER_SNAKE_CASE for constants
MAX_ARTICLES_PER_FEED = 50
DEFAULT_TIMEOUT = 30
RSS_COLLECTION_INTERVAL = 15

# Database table names
ARTICLES_TABLE = "articles"
RSS_FEEDS_TABLE = "rss_feeds"
STORY_THREADS_TABLE = "story_threads"
```

---

## ⚛️ **REACT/JAVASCRIPT CODING STANDARDS**

### **Component Naming**
```javascript
// Use PascalCase for components
const Dashboard = () => { /* ... */ };
const ArticleList = () => { /* ... */ };
const StoryControlDashboard = () => { /* ... */ };

// Use descriptive names
const EnhancedArticles = () => { /* ... */ };
const IntelligenceInsights = () => { /* ... */ };
```

### **Function Naming**
```javascript
// Use camelCase for functions
const fetchArticles = async () => { /* ... */ };
const handleArticleClick = (articleId) => { /* ... */ };
const processStoryData = (storyData) => { /* ... */ };

// Use descriptive names
const fetchDashboardData = async (isManualRefresh = false) => { /* ... */ };
const handleRSSFeedRefresh = async (feedId) => { /* ... */ };
```

### **Variable Naming**
```javascript
// Use camelCase for variables
const articleCount = 0;
const isLoading = false;
const selectedStory = null;

// Use descriptive names
const totalArticlesCollected = 0;
const lastSuccessfulCollection = new Date();
const processingStatus = 'pending';
```

### **API Service Functions**
```javascript
// Use descriptive names for API calls
const getActiveStories = async () => { /* ... */ };
const createStoryExpectation = async (storyData) => { /* ... */ };
const evaluateArticleForStory = async (storyId, articleId) => { /* ... */ };
```

---

## 🗄️ **DATABASE STANDARDS**

### **Table Naming**
```sql
-- Use snake_case for table names
articles
rss_feeds
story_threads
article_clusters
content_priority_assignments
automation_logs
system_config
```

### **Column Naming**
```sql
-- Use snake_case for column names
id
title
content
published_date
created_at
updated_at
processing_status
content_hash
```

### **Index Naming**
```sql
-- Use descriptive index names
idx_articles_category
idx_articles_created_at
idx_articles_processing_status
idx_rss_feeds_is_active
idx_story_threads_status
```

### **Constraint Naming**
```sql
-- Use descriptive constraint names
unique_content_hash
unique_url
fk_articles_rss_feed_id
check_quality_score_range
```

---

## 📁 **FILE ORGANIZATION STANDARDS**

### **Directory Structure**
```
api/
├── routes/           # API endpoints
├── modules/          # Business logic
├── collectors/       # Data collection
├── config/           # Configuration
├── middleware/       # Middleware
├── scripts/          # Utility scripts
└── tests/            # Test files

web/
├── src/
│   ├── components/   # Reusable components
│   ├── pages/        # Page components
│   ├── services/     # API services
│   ├── hooks/        # Custom hooks
│   └── utils/        # Utility functions
```

### **File Naming**
```
# Python files
rss_collector.py
intelligence_orchestrator.py
story_control_system.py

# React files
Dashboard.js
ArticleList.jsx
StoryControlDashboard.js

# Configuration files
docker-compose.yml
requirements.txt
package.json
```

---

## 🔧 **CONFIGURATION STANDARDS**

### **Docker Compose**
```yaml
# Use consistent service naming
services:
  postgres:          # Database service
  redis:             # Cache service
  news-system:       # Main application
  nginx:             # Web server
  prometheus:        # Metrics
  grafana:           # Monitoring
```

### **Environment Files**
```bash
# Use .env.example as template
# Document all required variables
# Group related variables together
# Use consistent naming patterns
```

---

## 📝 **DOCUMENTATION STANDARDS**

### **Code Comments**
```python
def collect_rss_feeds() -> int:
    """
    Collect articles from RSS feeds with deduplication
    
    Returns:
        int: Number of articles added to database
        
    Raises:
        DatabaseError: If database connection fails
        RSSError: If RSS feed is inaccessible
    """
    pass
```

### **API Documentation**
```python
@router.get("/articles", response_model=ArticleList)
async def get_articles(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: Optional[str] = Query(None)
):
    """
    Get paginated list of articles
    
    Args:
        limit: Maximum number of articles to return
        offset: Number of articles to skip
        category: Filter by article category
        
    Returns:
        ArticleList: Paginated list of articles
    """
    pass
```

---

## 🧪 **TESTING STANDARDS**

### **Test File Naming**
```
test_basic.py
test_rss_collection.py
test_article_processing.py
test_story_management.py
```

### **Test Function Naming**
```python
def test_collect_rss_feeds_success():
    """Test successful RSS feed collection"""
    pass

def test_article_deduplication():
    """Test article deduplication logic"""
    pass

def test_story_creation():
    """Test story thread creation"""
    pass
```

---

## 🚀 **DEPLOYMENT STANDARDS**

### **Version Control**
- Use semantic versioning (v3.0.0)
- Tag releases with version numbers
- Document breaking changes
- Maintain changelog

### **Environment Separation**
- Development: `docker-compose.yml`
- Production: `docker-compose.prod.yml`
- Testing: `docker-compose.test.yml`

---

## ✅ **COMPLIANCE CHECKLIST**

Before committing code, ensure:
- [ ] Environment variables are documented
- [ ] Port assignments follow the reserved list
- [ ] User permissions are correctly set
- [ ] Python code follows snake_case conventions
- [ ] React code follows camelCase conventions
- [ ] Database tables use snake_case naming
- [ ] File names are descriptive and consistent
- [ ] Comments explain complex logic
- [ ] Error handling is implemented
- [ ] Logging is appropriate for the context

---

## 🔄 **AI AGENT GUIDELINES**

When using AI agents (Claude Sonnet, GPT-5):
1. **Always reference this style guide**
2. **Maintain consistency** with existing code patterns
3. **Use established naming conventions**
4. **Follow the port reservation list**
5. **Respect environment variable standards**
6. **Update documentation** when adding new features
7. **Test changes** before committing

---

*This style guide ensures consistency across all components of the News Intelligence System, whether developed by AI agents or human developers.*