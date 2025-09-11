# News Intelligence System v3.0 - Deployment Guide

**Version:** 3.0  
**Last Updated:** January 5, 2025

## 🚀 Quick Start

### Prerequisites
- Docker 20.10+
- Docker Compose 2.0+
- 4GB RAM minimum
- 10GB disk space

### 1. Clone and Setup
```bash
git clone <repository-url>
cd news-intelligence-system
```

### 2. Environment Configuration
```bash
# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env
```

### 3. Start Services
```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

### 4. Access Application
- **Frontend:** http://localhost:3001
- **API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## 🐳 Docker Services

### Service Overview
| Service | Port | Description |
|---------|------|-------------|
| `news-frontend` | 3001 | Nginx web server |
| `news-system-app` | 8000 | FastAPI backend |
| `news-system-postgres` | 5432 | PostgreSQL database |
| `news-system-redis` | 6379 | Redis cache |

### Service Details

#### Frontend Service (`news-frontend`)
```yaml
services:
  news-frontend:
    image: nginx:alpine
    ports:
      - "3001:80"
    volumes:
      - ./web:/usr/share/nginx/html
    depends_on:
      - news-system-app
```

#### Backend Service (`news-system-app`)
```yaml
services:
  news-system-app:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://newsint:Database%40NEWSINT2025@news-system-postgres:5432/newsintelligence
      - REDIS_URL=redis://news-system-redis:6379
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
    depends_on:
      - news-system-postgres
      - news-system-redis
```

#### Database Service (`news-system-postgres`)
```yaml
services:
  news-system-postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=newsintelligence
      - POSTGRES_USER=newsint
      - POSTGRES_PASSWORD=Database@NEWSINT2025
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
```

#### Redis Service (`news-system-redis`)
```yaml
services:
  news-system-redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
```

## 🔧 Configuration

### Environment Variables

#### Backend Configuration
```bash
# Database
DATABASE_URL=postgresql://newsint:Database%40NEWSINT2025@news-system-postgres:5432/newsintelligence

# Redis
REDIS_URL=redis://news-system-redis:6379

# AI Processing
OLLAMA_BASE_URL=http://host.docker.internal:11434

# API Settings
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=false

# Security
SECRET_KEY=your-secret-key-here
```

#### Frontend Configuration
```bash
# API Base URL
REACT_APP_API_URL=http://localhost:8000/api

# Environment
NODE_ENV=production
```

### Database Configuration

#### Connection String Format
```
postgresql://username:password@host:port/database
```

#### Password Encoding
- Special characters in passwords must be URL-encoded
- `@` becomes `%40`
- Example: `Database@NEWSINT2025` becomes `Database%40NEWSINT2025`

### AI Configuration

#### Ollama Setup
```bash
# Install Ollama (on host machine)
curl -fsSL https://ollama.ai/install.sh | sh

# Start Ollama service
ollama serve

# Pull required models
ollama pull llama3.1:70b-instruct-q4_K_M
ollama pull deepseek-coder:33b
```

#### Model Configuration
- **Primary Model:** `llama3.1:70b-instruct-q4_K_M`
- **Code Model:** `deepseek-coder:33b`
- **Fallback:** Graceful degradation if models unavailable

## 📊 Database Setup

### Initial Schema
```sql
-- Articles table
CREATE TABLE articles (
    id VARCHAR(255) PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT,
    url TEXT,
    published_at TIMESTAMP,
    source VARCHAR(255),
    tags JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sentiment_score FLOAT,
    entities JSONB,
    readability_score FLOAT,
    quality_score FLOAT,
    summary TEXT,
    ml_data JSONB,
    language VARCHAR(10),
    word_count INTEGER,
    reading_time INTEGER
);

-- Storylines table
CREATE TABLE storylines (
    id VARCHAR(255) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    master_summary TEXT
);

-- Storyline articles relationship
CREATE TABLE storyline_articles (
    id SERIAL PRIMARY KEY,
    storyline_id VARCHAR(255) REFERENCES storylines(id),
    article_id VARCHAR(255) REFERENCES articles(id),
    relevance_score FLOAT,
    importance_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(storyline_id, article_id)
);
```

### Indexes
```sql
-- Performance indexes
CREATE INDEX idx_articles_created_at ON articles(created_at DESC);
CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_published_at ON articles(published_at DESC);
CREATE INDEX idx_storyline_articles_storyline_id ON storyline_articles(storyline_id);
CREATE INDEX idx_storyline_articles_article_id ON storyline_articles(article_id);
```

## 🔄 Deployment Commands

### Development Deployment
```bash
# Start development environment
docker compose up -d

# View logs
docker compose logs -f

# Stop services
docker compose down

# Rebuild and restart
docker compose up -d --build
```

### Production Deployment
```bash
# Production build
docker compose -f docker-compose.prod.yml up -d

# Scale services
docker compose up -d --scale news-system-app=3

# Health check
docker compose ps
curl http://localhost:8000/api/health/
```

### Maintenance Commands
```bash
# Backup database
docker exec news-system-postgres pg_dump -U newsint newsintelligence > backup.sql

# Restore database
docker exec -i news-system-postgres psql -U newsint newsintelligence < backup.sql

# View container logs
docker logs news-system-app
docker logs news-frontend
docker logs news-system-postgres

# Execute commands in container
docker exec -it news-system-app bash
docker exec -it news-system-postgres psql -U newsint newsintelligence
```

## 🔍 Health Monitoring

### Health Check Endpoints
```bash
# API health
curl http://localhost:8000/api/health/

# Database connectivity
curl http://localhost:8000/api/health/database

# Redis connectivity
curl http://localhost:8000/api/health/redis

# AI processing
curl http://localhost:8000/api/health/ai
```

### Monitoring Scripts
```bash
#!/bin/bash
# health-check.sh

echo "=== News Intelligence System Health Check ==="

# Check API
if curl -s http://localhost:8000/api/health/ | grep -q "healthy"; then
    echo "✅ API: Healthy"
else
    echo "❌ API: Unhealthy"
fi

# Check Frontend
if curl -s http://localhost:3001/ | grep -q "News Intelligence"; then
    echo "✅ Frontend: Healthy"
else
    echo "❌ Frontend: Unhealthy"
fi

# Check Database
if docker exec news-system-postgres pg_isready -U newsint; then
    echo "✅ Database: Healthy"
else
    echo "❌ Database: Unhealthy"
fi

# Check Redis
if docker exec news-system-redis redis-cli ping | grep -q "PONG"; then
    echo "✅ Redis: Healthy"
else
    echo "❌ Redis: Unhealthy"
fi
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Database Connection Error
```bash
# Error: psycopg2.OperationalError
# Solution: Check password encoding
echo "Database%40NEWSINT2025" | python3 -c "import urllib.parse; print(urllib.parse.quote(input()))"
```

#### 2. Port Already in Use
```bash
# Find process using port
lsof -i :3001
lsof -i :8000

# Kill process
kill -9 <PID>
```

#### 3. Container Won't Start
```bash
# Check logs
docker logs news-system-app

# Check resource usage
docker stats

# Restart specific service
docker compose restart news-system-app
```

#### 4. AI Processing Not Working
```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Check model availability
ollama list

# Restart Ollama
pkill ollama
ollama serve
```

### Log Analysis
```bash
# View all logs
docker compose logs

# View specific service logs
docker compose logs news-system-app
docker compose logs news-frontend

# Follow logs in real-time
docker compose logs -f news-system-app

# View last 100 lines
docker compose logs --tail=100 news-system-app
```

## 🔒 Security Configuration

### SSL/TLS Setup
```bash
# Generate self-signed certificate
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes

# Update nginx configuration
# Add SSL configuration to nginx.conf
```

### Firewall Configuration
```bash
# Allow required ports
sudo ufw allow 3001
sudo ufw allow 8000
sudo ufw allow 5432
sudo ufw allow 6379

# Enable firewall
sudo ufw enable
```

### Environment Security
```bash
# Secure environment file
chmod 600 .env

# Use strong passwords
# Generate secure password
openssl rand -base64 32

# Rotate secrets regularly
# Update SECRET_KEY and database passwords
```

## 📈 Performance Optimization

### Database Optimization
```sql
-- Analyze query performance
EXPLAIN ANALYZE SELECT * FROM articles WHERE source = 'BBC News';

-- Update statistics
ANALYZE articles;

-- Vacuum database
VACUUM ANALYZE;
```

### Container Optimization
```bash
# Limit container resources
docker run --memory=2g --cpus=2 news-system-app

# Use multi-stage builds
# Optimize Dockerfile layers
```

### Caching Configuration
```bash
# Redis memory configuration
# Set maxmemory in redis.conf
maxmemory 256mb
maxmemory-policy allkeys-lru
```

## 🔄 Backup and Recovery

### Database Backup
```bash
#!/bin/bash
# backup-db.sh

BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
docker exec news-system-postgres pg_dump -U newsint newsintelligence > $BACKUP_DIR/newsintelligence_$DATE.sql

# Compress backup
gzip $BACKUP_DIR/newsintelligence_$DATE.sql

echo "Backup created: $BACKUP_DIR/newsintelligence_$DATE.sql.gz"
```

### Recovery Process
```bash
#!/bin/bash
# restore-db.sh

BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

# Decompress if needed
if [[ $BACKUP_FILE == *.gz ]]; then
    gunzip -c $BACKUP_FILE | docker exec -i news-system-postgres psql -U newsint newsintelligence
else
    docker exec -i news-system-postgres psql -U newsint newsintelligence < $BACKUP_FILE
fi

echo "Database restored from: $BACKUP_FILE"
```

## 📋 Maintenance Schedule

### Daily Tasks
- [ ] Check system health
- [ ] Monitor resource usage
- [ ] Review error logs
- [ ] Verify AI processing

### Weekly Tasks
- [ ] Database backup
- [ ] Log rotation
- [ ] Security updates
- [ ] Performance analysis

### Monthly Tasks
- [ ] Full system backup
- [ ] Security audit
- [ ] Dependency updates
- [ ] Capacity planning

---

**Deployment Guide Version:** 3.0  
**Last Updated:** January 5, 2025  
**Maintainer:** AI Assistant


