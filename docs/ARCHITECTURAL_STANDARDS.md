# 🏗️ News Intelligence System v3.0 - Architectural Standards

## 📋 **OVERVIEW**

This document establishes the architectural standards and naming conventions for the News Intelligence System to prevent configuration fragmentation and ensure consistency across all components.

**Last Updated**: 2025-09-11  
**Version**: 3.0  
**Status**: Active

---

## 🎯 **CORE PRINCIPLES**

### **1. Single Source of Truth**
- **One configuration file per concern** (database, Docker, etc.)
- **No duplicate configuration files**
- **Centralized environment variable management**

### **2. Consistent Naming Conventions**
- **Service Names**: `news-intelligence-{service}`
- **Container Names**: `news-intelligence-{service}`
- **Network Names**: `news-network`
- **Volume Names**: `{service}_data`

### **3. Standardized Ports**
- **API**: 8000
- **PostgreSQL**: 5432
- **Redis**: 6379
- **Frontend**: 80, 443
- **Monitoring**: 9090

---

## 🐳 **DOCKER ARCHITECTURE STANDARDS**

### **Service Naming Convention**
```yaml
# ✅ CORRECT - Use this pattern
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
```

### **Network Configuration**
```yaml
# ✅ CORRECT - Single network for all services
networks:
  news-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
    labels:
      - "news-intelligence.network=main"
```

### **Volume Configuration**
```yaml
# ✅ CORRECT - Named volumes with consistent naming
volumes:
  postgres_data:
    driver: local
  redis_data:
    driver: local
  prometheus_data:
    driver: local
```

### **Environment Variables**
```yaml
# ✅ CORRECT - Standardized environment variables
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
```

---

## 🗄️ **DATABASE ARCHITECTURE STANDARDS**

### **Single Database Configuration File**
```python
# ✅ CORRECT - Use api/config/database.py ONLY
from config.database import get_db, get_db_config, check_database_health

# ❌ WRONG - Don't create multiple database config files
# from config.robust_database import ...
# from config.unified_database import ...
# from database.connection import ...
```

### **Database Connection Standards**
```python
# ✅ CORRECT - Use these functions
def get_db_connection():
    """Get psycopg2 connection"""
    return db_manager.get_psycopg2_connection()

def get_db():
    """Get SQLAlchemy session for FastAPI"""
    return db_manager.get_sqlalchemy_session()

@contextmanager
def get_db_cursor():
    """Context manager for database operations"""
    with db_manager.get_psycopg2_cursor() as cursor:
        yield cursor
```

### **Database Configuration Standards**
```python
# ✅ CORRECT - Standardized configuration
DATABASE_CONFIG = {
    'host': 'news-intelligence-postgres',
    'database': 'news_intelligence',
    'user': 'newsapp',
    'password': 'newsapp_password',
    'port': 5432
}
```

---

## 📁 **FILE STRUCTURE STANDARDS**

### **Configuration Files**
```
api/
├── config/
│   ├── database.py          # ✅ SINGLE database config
│   ├── paths.py             # ✅ Path management
│   └── __init__.py
├── routes/                  # ✅ API routes
├── services/                # ✅ Business logic
└── schemas/                 # ✅ Data models
```

### **Docker Files**
```
├── docker-compose.yml       # ✅ SINGLE compose file
├── Dockerfile.frontend      # ✅ Frontend container
└── api/
    └── Dockerfile.production # ✅ API container
```

### **Documentation Files**
```
docs/
├── ARCHITECTURAL_STANDARDS.md    # ✅ This file
├── CODING_STYLE_GUIDE.md         # ✅ Code standards
├── DATABASE_SCHEMA_DOCUMENTATION.md
└── API_DOCUMENTATION.md
```

---

## 🔧 **ENVIRONMENT VARIABLE STANDARDS**

### **Required Environment Variables**
```bash
# Database Configuration
DB_HOST=news-intelligence-postgres
DB_NAME=news_intelligence
DB_USER=newsapp
DB_PASSWORD=newsapp_password
DB_PORT=5432
DATABASE_URL=postgresql://newsapp:newsapp_password@news-intelligence-postgres:5432/news_intelligence

# Redis Configuration
REDIS_URL=redis://news-intelligence-redis:6379/0

# Application Configuration
ENVIRONMENT=production
LOG_LEVEL=info
PYTHONPATH=/app
SECRET_KEY=news-intelligence-secret-key-2025
```

### **Environment File Location**
```bash
# ✅ CORRECT - Use .env in project root
.env

# ❌ WRONG - Don't create multiple env files
# .env.local
# .env.production
# .env.development
```

---

## 🚫 **ANTI-PATTERNS TO AVOID**

### **Configuration Fragmentation**
```python
# ❌ WRONG - Multiple database config files
api/config/database.py
api/config/robust_database.py
api/config/unified_database.py
api/database/connection.py

# ✅ CORRECT - Single database config file
api/config/database.py
```

### **Inconsistent Service Naming**
```yaml
# ❌ WRONG - Inconsistent naming
services:
  postgres:
    container_name: postgres
  redis:
    container_name: redis
  api:
    container_name: news-api

# ✅ CORRECT - Consistent naming
services:
  postgres:
    container_name: news-intelligence-postgres
  redis:
    container_name: news-intelligence-redis
  api:
    container_name: news-intelligence-api
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

## 📋 **IMPLEMENTATION CHECKLIST**

### **Before Adding New Configuration**
- [ ] Check if existing configuration can be extended
- [ ] Ensure naming follows established conventions
- [ ] Verify no duplicate functionality exists
- [ ] Update this documentation if changes are made

### **Before Adding New Services**
- [ ] Use `news-intelligence-{service}` naming pattern
- [ ] Add to single `docker-compose.yml` file
- [ ] Use `news-network` for networking
- [ ] Follow established volume naming pattern

### **Before Adding New Database Features**
- [ ] Extend `api/config/database.py` only
- [ ] Use established connection functions
- [ ] Follow database naming conventions
- [ ] Update schema documentation

---

## 🔍 **VALIDATION TOOLS**

### **Configuration Validation Script**
```bash
# Run this to validate configuration consistency
python3 api/scripts/validate_architecture.py
```

### **Docker Configuration Check**
```bash
# Validate Docker configuration
docker-compose config
```

### **Database Connection Test**
```bash
# Test database connectivity
python3 api/scripts/test_database_connection.py
```

---

## 📚 **REFERENCE DOCUMENTATION**

### **Related Documents**
- [CODING_STYLE_GUIDE.md](./CODING_STYLE_GUIDE.md) - Code style standards
- [DATABASE_SCHEMA_DOCUMENTATION.md](./DATABASE_SCHEMA_DOCUMENTATION.md) - Database schema
- [API_DOCUMENTATION.md](./API_DOCUMENTATION.md) - API endpoints

### **External References**
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## ✅ **COMPLIANCE VERIFICATION**

### **Monthly Architecture Review**
- [ ] No duplicate configuration files exist
- [ ] All services follow naming conventions
- [ ] Single docker-compose.yml file is used
- [ ] Database configuration is centralized
- [ ] Environment variables are standardized

### **Before Production Deployment**
- [ ] All services use `news-intelligence-` prefix
- [ ] Database connections use unified configuration
- [ ] No configuration fragmentation exists
- [ ] All documentation is updated

---

*This architectural standards document is the single source of truth for News Intelligence System configuration and should be referenced before any architectural changes.*
