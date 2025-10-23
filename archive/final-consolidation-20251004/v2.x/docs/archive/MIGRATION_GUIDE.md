# News Intelligence System v2.0.0 - Migration Guide

## 🚀 **Hardware Migration & Scalability Guide**

This guide covers migrating your News Intelligence System to new hardware, scaling up, and preparing for ML features.

## 📋 **Migration Prerequisites**

### **Current System Requirements**
- **CPU**: 2+ cores (current: basic processing)
- **RAM**: 4GB+ (current: RSS + basic operations)
- **Storage**: 20GB+ (current: articles + database)
- **GPU**: None (current: CPU-only operations)

### **Future ML System Requirements**
- **CPU**: 8+ cores (recommended: 16+ cores)
- **RAM**: 32GB+ (recommended: 64GB+)
- **Storage**: 100GB+ SSD (recommended: 500GB+ NVMe)
- **GPU**: NVIDIA RTX 3080+ or Tesla T4+ (for ML features)

## 🔄 **Migration Process**

### **Phase 1: Preparation (Current System)**

1. **Create Full Backup**
   ```bash
   ./deploy.sh backup
   ```

2. **Export Configuration**
   ```bash
   cp .env .env.backup
   cp -r api/config api/config.backup
   ```

3. **Document Current Setup**
   ```bash
   ./deploy.sh status
   docker-compose ps
   ```

### **Phase 2: New Hardware Setup**

1. **Install Dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install -y docker.io docker-compose git curl
   
   # Enable Docker service
   sudo systemctl enable docker
   sudo systemctl start docker
   ```

2. **Clone Repository**
   ```bash
   git clone https://github.com/your-repo/news-system.git
   cd news-system
   ```

3. **Restore Configuration**
   ```bash
   cp .env.backup .env
   # Edit .env for new hardware specifications
   ```

### **Phase 3: Data Migration**

1. **Transfer Backup Files**
   ```bash
   # Copy backup files to new system
   scp backups/* user@new-server:/path/to/news-system/backups/
   ```

2. **Restore Database**
   ```bash
   ./deploy.sh deploy
   ./deploy.sh restore backups/backup_YYYYMMDD_HHMMSS.sql
   ```

3. **Verify Migration**
   ```bash
   ./deploy.sh status
   # Check article count, RSS feeds, etc.
   ```

## 🐳 **Container Migration Options**

### **Option 1: Full Container Migration (Recommended)**
```bash
# Export entire system
docker-compose export > news-system-export.tar

# Transfer to new system
scp news-system-export.tar user@new-server:/path/to/

# Import on new system
docker-compose import < news-system-export.tar
```

### **Option 2: Volume Migration**
```bash
# Export volumes
docker run --rm -v news-system_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/postgres-data.tar.gz -C /data .

# Transfer and restore on new system
docker run --rm -v news-system_postgres_data:/data -v $(pwd):/backup alpine tar xzf /backup/postgres-data.tar.gz -C /data
```

### **Option 3: Database-Only Migration**
```bash
# Create full database dump
./deploy.sh backup

# Transfer backup file
scp backups/* user@new-server:/path/to/news-system/backups/

# Restore on new system
./deploy.sh restore backups/backup_YYYYMMDD_HHMMSS.sql
```

## 🔧 **Hardware-Specific Configurations**

### **High-Performance CPU Configuration**
```yaml
# docker-compose.yml - CPU optimization
services:
  news-system:
    environment:
      - MAX_CONCURRENT_RSS_FEEDS=20
      - MAX_CONCURRENT_ARTICLES=200
      - DATABASE_POOL_SIZE=20
    deploy:
      resources:
        limits:
          cpus: '8.0'
          memory: 16G
        reservations:
          cpus: '4.0'
          memory: 8G
```

### **GPU-Enabled Configuration (Future v3.0)**
```yaml
# docker-compose.yml - GPU support
services:
  news-system-ml:
    build: 
      context: .
      dockerfile: Dockerfile.gpu
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - NVIDIA_DRIVER_CAPABILITIES=compute,utility
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### **High-Memory Configuration**
```yaml
# docker-compose.yml - Memory optimization
services:
  postgres:
    environment:
      - POSTGRES_SHARED_BUFFERS=4GB
      - POSTGRES_EFFECTIVE_CACHE_SIZE=12GB
      - POSTGRES_WORK_MEM=256MB
      - POSTGRES_MAINTENANCE_WORK_MEM=1GB
    deploy:
      resources:
        limits:
          memory: 8G
        reservations:
          memory: 4G
```

## 📊 **Scaling Strategies**

### **Horizontal Scaling (Multiple Instances)**
```yaml
# docker-compose.yml - Multi-instance scaling
services:
  news-system:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
    environment:
      - INSTANCE_ID=${HOSTNAME}
      - REDIS_HOST=redis
```

### **Load Balancing with Nginx**
```nginx
# docker/nginx/conf.d/load-balancer.conf
upstream news_app {
    server news-system-1:8000;
    server news-system-2:8000;
    server news-system-3:8000;
    keepalive 32;
}
```

### **Database Scaling**
```yaml
# docker-compose.yml - Read replicas
services:
  postgres-read:
    image: pgvector/pgvector:pg15
    environment:
      POSTGRES_DB: news_aggregator
      POSTGRES_USER: dockside_admin
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    command: >
      postgres
      -c hot_standby=on
      -c primary_conninfo=host=postgres user=dockside_admin password=${DB_PASSWORD}
```

## 🔒 **Security Considerations**

### **Production Hardening**
```bash
# Generate strong passwords
openssl rand -base64 32 > .env.production

# SSL certificates
mkdir -p docker/nginx/ssl
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout docker/nginx/ssl/key.pem \
  -out docker/nginx/ssl/cert.pem
```

### **Network Security**
```yaml
# docker-compose.yml - Network isolation
networks:
  news-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
    driver_opts:
      com.docker.network.bridge.enable_icc: "false"
```

## 📈 **Performance Monitoring**

### **Resource Monitoring**
```yaml
# docker-compose.yml - Monitoring stack
services:
  node-exporter:
    image: prom/node-exporter:latest
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.ignored-mount-points=^/(sys|proc|dev|host|etc)($$|/)'
```

### **Custom Metrics**
```python
# api/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge

# RSS collection metrics
rss_collection_total = Counter('rss_collection_total', 'Total RSS collections')
rss_articles_collected = Counter('rss_articles_collected', 'Total articles collected')
rss_collection_duration = Histogram('rss_collection_duration_seconds', 'RSS collection duration')

# Article processing metrics
articles_processed = Counter('articles_processed_total', 'Total articles processed')
processing_duration = Histogram('article_processing_duration_seconds', 'Article processing duration')
```

## 🚀 **Future ML Integration Preparation**

### **GPU-Enabled Dockerfile**
```dockerfile
# Dockerfile.gpu - For future ML features
FROM nvidia/cuda:11.8-devel-ubuntu20.04

# Install Python and dependencies
RUN apt-get update && apt-get install -y \
    python3.11 python3.11-dev python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install ML dependencies
COPY api/requirements_ml.txt .
RUN pip3 install -r requirements_ml.txt

# Copy application
COPY api/ ./api/

# Set environment for GPU
ENV CUDA_VISIBLE_DEVICES=0
ENV TF_FORCE_GPU_ALLOW_GROWTH=true
```

### **ML Service Configuration**
```yaml
# docker-compose.ml.yml - ML services
services:
  news-system-ml:
    build:
      context: .
      dockerfile: Dockerfile.gpu
    runtime: nvidia
    environment:
      - MODEL_CACHE_DIR=/app/models
      - GPU_MEMORY_LIMIT=8GB
    volumes:
      - ml_models:/app/models
      - ./api/models:/app/api/models
```

## 📝 **Migration Checklist**

### **Pre-Migration**
- [ ] Full system backup created
- [ ] Configuration exported
- [ ] Current performance baseline documented
- [ ] New hardware specifications confirmed
- [ ] Network connectivity verified

### **Migration Day**
- [ ] Old system stopped gracefully
- [ ] Data transferred to new system
- [ ] New system deployed and tested
- [ ] All services verified operational
- [ ] Performance benchmarks run

### **Post-Migration**
- [ ] Monitoring alerts configured
- [ ] Backup schedule verified
- [ ] Performance compared to baseline
- [ ] Documentation updated
- [ ] Team training completed

## 🆘 **Troubleshooting**

### **Common Migration Issues**

1. **Database Connection Failures**
   ```bash
   # Check PostgreSQL status
   docker-compose exec postgres pg_isready -U dockside_admin
   
   # Verify network connectivity
   docker-compose exec news-system ping postgres
   ```

2. **Performance Degradation**
   ```bash
   # Check resource usage
   docker stats
   
   # Monitor logs
   ./deploy.sh logs
   ```

3. **Data Corruption**
   ```bash
   # Verify data integrity
   docker-compose exec postgres psql -U dockside_admin -d news_aggregator -c "SELECT COUNT(*) FROM articles;"
   
   # Restore from backup if needed
   ./deploy.sh restore backups/backup_YYYYMMDD_HHMMSS.sql
   ```

## 📞 **Support & Resources**

- **Documentation**: [VERSION_2_DOCUMENTATION.md](VERSION_2_DOCUMENTATION.md)
- **Setup Guide**: [SETUP_GUIDE_v2.md](SETUP_GUIDE_v2.md)
- **Issues**: GitHub Issues page
- **Community**: GitHub Discussions

---

**🎯 Goal**: Seamless migration to new hardware with zero downtime and improved performance for future ML features.
