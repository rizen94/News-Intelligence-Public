# 📝 News Intelligence System v3.0 - Coding Style Guide

## 📋 **OVERVIEW**

This document establishes coding standards, naming conventions, and architectural patterns for the News Intelligence System to ensure consistency, maintainability, and prevent configuration fragmentation.

**Last Updated**: 2025-09-11  
**Version**: 3.0  
**Status**: Active

---

## 🎯 **CORE PRINCIPLES**

### **1. Consistency Over Cleverness**
- Use established patterns consistently
- Prefer readability over brevity
- Follow existing conventions

### **2. Single Source of Truth**
- One configuration file per concern
- Centralized environment management
- No duplicate functionality

### **3. Explicit Over Implicit**
- Clear naming conventions
- Explicit imports and dependencies
- Obvious code structure

---

## 🐍 **PYTHON CODING STANDARDS**

### **File Naming Conventions**
```python
# ✅ CORRECT - Use snake_case for files
api/config/database.py
api/routes/articles.py
api/services/health_service.py

# ❌ WRONG - Don't use camelCase or kebab-case
api/config/databaseConfig.py
api/routes/article-routes.py
```

### **Class Naming Conventions**
```python
# ✅ CORRECT - Use PascalCase for classes
class DatabaseManager:
    pass

class HealthService:
    pass

class ArticleProcessor:
    pass

# ❌ WRONG - Don't use snake_case for classes
class database_manager:
    pass
```

### **Function and Variable Naming**
```python
# ✅ CORRECT - Use snake_case for functions and variables
def get_database_connection():
    connection_pool = create_pool()
    return connection_pool

# ❌ WRONG - Don't use camelCase
def getDatabaseConnection():
    connectionPool = createPool()
    return connectionPool
```

### **Constant Naming**
```python
# ✅ CORRECT - Use UPPER_SNAKE_CASE for constants
DATABASE_CONFIG = {
    'host': 'news-intelligence-postgres',
    'port': 5432
}

MAX_RETRIES = 5
DEFAULT_TIMEOUT = 30

# ❌ WRONG - Don't use lowercase for constants
database_config = {...}
max_retries = 5
```

### **Import Organization**
```python
# ✅ CORRECT - Organize imports in this order
# 1. Standard library imports
import os
import sys
import logging
from pathlib import Path

# 2. Third-party imports
import psycopg2
from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

# 3. Local application imports
from config.database import get_db
from schemas.robust_schemas import APIResponse
from services.health_service import HealthService
```

---

## 🐳 **DOCKER STANDARDS**

### **Service Naming Convention**
```yaml
# ✅ CORRECT - Use news-intelligence-{service} pattern
services:
  postgres:
    container_name: news-intelligence-postgres
  redis:
    container_name: news-intelligence-redis
  api:
    container_name: news-intelligence-api
  frontend:
    container_name: news-intelligence-frontend
  monitoring:
    container_name: news-intelligence-monitoring

# ❌ WRONG - Don't use inconsistent naming
services:
  postgres:
    container_name: postgres
  redis:
    container_name: redis
  api:
    container_name: news-api
```

### **Environment Variable Standards**
```yaml
# ✅ CORRECT - Use consistent environment variable names
environment:
  # Database Configuration
  DB_HOST: news-intelligence-postgres
  DB_NAME: news_intelligence
  DB_USER: newsapp
  DB_PASSWORD: newsapp_password
  DB_PORT: 5432
  DATABASE_URL: postgresql://newsapp:newsapp_password@news-intelligence-postgres:5432/news_intelligence
  
  # Redis Configuration
  REDIS_URL: redis://news-intelligence-redis:6379/0
  
  # Application Configuration
  ENVIRONMENT: production
  LOG_LEVEL: info
  PYTHONPATH: /app
```

### **Volume Naming Convention**
```yaml
# ✅ CORRECT - Use {service}_data pattern
volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  prometheus_data:
    driver: local

# ❌ WRONG - Don't use inconsistent volume names
volumes:
  postgres_storage:
    driver: local
  redis_cache:
    driver: local
  monitoring_data:
    driver: local
```

---

## 🗄️ **DATABASE STANDARDS**

### **Table Naming Convention**
```sql
-- ✅ CORRECT - Use snake_case for table names
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rss_feeds (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL
);

-- ❌ WRONG - Don't use camelCase or PascalCase
CREATE TABLE Articles (
    id SERIAL PRIMARY KEY,
    Title TEXT NOT NULL
);
```

### **Column Naming Convention**
```sql
-- ✅ CORRECT - Use snake_case for column names
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    published_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ❌ WRONG - Don't use camelCase
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    publishedDate TIMESTAMP,
    createdAt TIMESTAMP
);
```

### **Index Naming Convention**
```sql
-- ✅ CORRECT - Use idx_{table}_{column} pattern
CREATE INDEX idx_articles_published_date ON articles(published_date);
CREATE INDEX idx_articles_category ON articles(category);
CREATE INDEX idx_rss_feeds_status ON rss_feeds(status);

-- ❌ WRONG - Don't use inconsistent index names
CREATE INDEX articles_published_date ON articles(published_date);
CREATE INDEX idx_articles_category_idx ON articles(category);
```

---

## 🌐 **API STANDARDS**

### **Route Naming Convention**
```python
# ✅ CORRECT - Use snake_case for route paths
@router.get("/articles/")
@router.get("/rss_feeds/")
@router.get("/health/")
@router.post("/articles/")
@router.put("/articles/{article_id}")
@router.delete("/articles/{article_id}")

# ❌ WRONG - Don't use camelCase or kebab-case
@router.get("/articles-list/")
@router.get("/rssFeeds/")
@router.get("/health-check/")
```

### **Response Model Naming**
```python
# ✅ CORRECT - Use descriptive response model names
@router.get("/articles/", response_model=APIResponse)
@router.get("/health/", response_model=HealthResponse)
@router.get("/dashboard/", response_model=DashboardResponse)

# ❌ WRONG - Don't use generic names
@router.get("/articles/", response_model=Response)
@router.get("/health/", response_model=Data)
```

### **Error Handling Standards**
```python
# ✅ CORRECT - Use consistent error handling
@router.get("/articles/")
async def get_articles():
    try:
        # Business logic here
        return APIResponse(
            success=True,
            data=articles,
            message="Articles retrieved successfully"
        )
    except Exception as e:
        logger.error(f"Error getting articles: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve articles"
        )

# ❌ WRONG - Don't use inconsistent error handling
@router.get("/articles/")
async def get_articles():
    # No error handling
    return articles
```

---

## 📁 **FILE STRUCTURE STANDARDS**

### **Project Structure**
```
News Intelligence/
├── api/                          # Backend API
│   ├── config/
│   │   ├── database.py           # ✅ SINGLE database config
│   │   └── paths.py              # Path management
│   ├── routes/                   # API routes
│   │   ├── articles.py
│   │   ├── health.py
│   │   └── storylines.py
│   ├── services/                 # Business logic
│   │   ├── health_service.py
│   │   └── article_service.py
│   ├── schemas/                  # Data models
│   │   ├── robust_schemas.py
│   │   └── response_schemas.py
│   └── main.py                   # Application entry point
├── web/                          # Frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── services/
│   └── package.json
├── docker-compose.yml            # ✅ SINGLE compose file
├── docs/                         # Documentation
│   ├── ARCHITECTURAL_STANDARDS.md
│   ├── CODING_STYLE_GUIDE.md
│   └── API_DOCUMENTATION.md
└── scripts/                      # Utility scripts
    ├── test_database_connection.py
    └── validate_architecture.py
```

### **Configuration File Standards**
```python
# ✅ CORRECT - Single configuration file per concern
api/config/database.py          # Database configuration
api/config/paths.py             # Path management
docker-compose.yml              # Container orchestration

# ❌ WRONG - Multiple configuration files
api/config/database.py
api/config/robust_database.py
api/config/unified_database.py
api/database/connection.py
```

---

## 🔧 **ENVIRONMENT VARIABLE STANDARDS**

### **Naming Convention**
```bash
# ✅ CORRECT - Use UPPER_SNAKE_CASE
DB_HOST=news-intelligence-postgres
DB_NAME=news_intelligence
DB_USER=newsapp
DB_PASSWORD=newsapp_password
REDIS_URL=redis://news-intelligence-redis:6379/0
API_V1_STR=/api
PROJECT_NAME=News Intelligence System

# ❌ WRONG - Don't use camelCase or lowercase
dbHost=news-intelligence-postgres
db_name=news_intelligence
redisUrl=redis://news-intelligence-redis:6379/0
```

### **Environment File Organization**
```bash
# ✅ CORRECT - Use .env in project root
.env

# ❌ WRONG - Don't create multiple env files
.env.local
.env.production
.env.development
configs/.env
```

---

## 📝 **DOCUMENTATION STANDARDS**

### **File Naming Convention**
```markdown
# ✅ CORRECT - Use UPPER_SNAKE_CASE for documentation files
ARCHITECTURAL_STANDARDS.md
CODING_STYLE_GUIDE.md
API_DOCUMENTATION.md
DATABASE_SCHEMA_DOCUMENTATION.md

# ❌ WRONG - Don't use camelCase or kebab-case
architectural-standards.md
codingStyleGuide.md
api-documentation.md
```

### **Documentation Structure**
```markdown
# 📝 Document Title

## 📋 **OVERVIEW**
Brief description of the document's purpose.

## 🎯 **CORE PRINCIPLES**
Key principles and guidelines.

## 📊 **DETAILED SECTIONS**
Specific implementation details.

## ✅ **COMPLIANCE CHECKLIST**
Items to verify compliance.

---

*Last Updated: YYYY-MM-DD*
*Version: X.X*
*Status: Active*
```

---

## 🚫 **ANTI-PATTERNS TO AVOID**

### **Configuration Fragmentation**
```python
# ❌ WRONG - Multiple database config files
from config.database import get_db
from config.robust_database import get_robust_db
from config.unified_database import get_unified_db
from database.connection import get_connection

# ✅ CORRECT - Single database config file
from config.database import get_db
```

### **Inconsistent Naming**
```python
# ❌ WRONG - Inconsistent naming
class database_manager:
    def getDatabaseConnection():
        pass

# ✅ CORRECT - Consistent naming
class DatabaseManager:
    def get_database_connection():
        pass
```

### **Multiple Docker Compose Files**
```bash
# ❌ WRONG - Multiple compose files
docker-compose.yml
docker-compose.dev.yml
docker-compose.prod.yml
configs/docker-compose.backend.yml

# ✅ CORRECT - Single compose file
docker-compose.yml
```

---

## 🔍 **VALIDATION TOOLS**

### **Code Style Validation**
```bash
# Run linting
python3 -m flake8 api/
python3 -m black api/
python3 -m isort api/
```

### **Architecture Validation**
```bash
# Validate configuration consistency
python3 api/scripts/validate_architecture.py

# Test database connectivity
python3 api/scripts/test_database_connection.py
```

### **Docker Validation**
```bash
# Validate Docker configuration
docker-compose config

# Check container naming
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"
```

---

## 📋 **IMPLEMENTATION CHECKLIST**

### **Before Writing New Code**
- [ ] Follow established naming conventions
- [ ] Use single source of truth for configuration
- [ ] Follow error handling patterns
- [ ] Add appropriate logging
- [ ] Write clear documentation

### **Before Adding New Features**
- [ ] Check if existing functionality can be extended
- [ ] Follow architectural standards
- [ ] Update documentation
- [ ] Add validation tests
- [ ] Follow naming conventions

### **Before Production Deployment**
- [ ] All code follows style guide
- [ ] No configuration fragmentation
- [ ] All services use consistent naming
- [ ] Documentation is updated
- [ ] Validation tests pass

---

## 📚 **REFERENCE DOCUMENTATION**

### **Related Documents**
- [ARCHITECTURAL_STANDARDS.md](./ARCHITECTURAL_STANDARDS.md) - Architecture standards
- [DATABASE_SCHEMA_DOCUMENTATION.md](./DATABASE_SCHEMA_DOCUMENTATION.md) - Database schema
- [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) - API endpoints

### **External References**
- [PEP 8 - Python Style Guide](https://pep8.org/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

*This coding style guide is the single source of truth for News Intelligence System code standards and should be referenced before any code changes.*
