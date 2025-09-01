# 🚀 Deployment Guide - News Intelligence System v3.0

## 🎯 **COMPLETE DEPLOYMENT INSTRUCTIONS**

This guide covers all deployment scenarios for the News Intelligence System, from local development to production with NAS storage and monitoring.

---

## 🏠 **DEPLOYMENT SCENARIOS**

### **1. Local Development**
- **Storage**: Local Docker volumes
- **Monitoring**: Basic system health
- **Use Case**: Development, testing, small workloads

### **2. NAS Deployment**
- **Storage**: TerraMaster NAS with persistent data
- **Monitoring**: Full monitoring stack (Prometheus + Grafana)
- **Use Case**: Medium workloads, data persistence

### **3. Production Deployment**
- **Storage**: NAS with production optimizations
- **Monitoring**: Enterprise-grade monitoring and alerting
- **Use Case**: Production workloads, high availability

---

## 🐳 **PREREQUISITES**

### **System Requirements**
- **OS**: Linux (Ubuntu 20.04+, Pop!_OS 20.04+)
- **Docker**: Docker Engine 20.10+ and Docker Compose 2.0+
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB minimum (local) or NAS access
- **Network**: Stable internet connection

### **Hardware Recommendations**
- **CPU**: 4+ cores for optimal performance
- **RAM**: 8GB+ for production workloads
- **Storage**: SSD for local, NAS for production
- **Network**: Gigabit Ethernet for NAS deployments

---

## 🚀 **SCENARIO 1: LOCAL DEVELOPMENT DEPLOYMENT**

### **Quick Start**
```bash
# 1. Clone the repository
git clone https://github.com/your-username/news-intelligence-system.git
cd news-intelligence-system

# 2. Verify configuration
cat .env | grep -E "ENVIRONMENT|STORAGE_TYPE|ENABLE_MONITORING"

# Expected output:
# ENVIRONMENT=local
# STORAGE_TYPE=local
# ENABLE_MONITORING=false

# 3. Deploy the system
chmod +x scripts/deployment/deploy.sh
./scripts/deployment/deploy.sh local
```

### **What Gets Deployed**
- ✅ **PostgreSQL Database**: Local Docker volume storage
- ✅ **Flask Backend**: All API endpoints and services
- ✅ **React Frontend**: Professional web interface
- ✅ **Database Schema**: Automatic initialization
- ✅ **Sample Data**: Test content for validation

### **Access Points**
- **Main Application**: http://localhost:8000
- **Database**: localhost:5432
- **API Health**: http://localhost:8000/health

---

## 🗄️ **SCENARIO 2: NAS DEPLOYMENT**

### **NAS Preparation**
```bash
# 1. Mount TerraMaster NAS
sudo mkdir -p /mnt/terramaster-nas
sudo mount -t cifs //192.168.93.100/public /mnt/terramaster-nas \
  -o username=YOUR_USERNAME,password=YOUR_PASSWORD,uid=$(id -u),gid=$(id -g),vers=3.0

# 2. Create directory structure
sudo mkdir -p /mnt/terramaster-nas/docker-postgres-data/{pgdata,logs,backups,ml-models,data-archives,prometheus-data,grafana-data,temp,data}

# 3. Set permissions
sudo chown -R $(id -u):$(id -g) /mnt/terramaster-nas/docker-postgres-data
sudo chmod -R 755 /mnt/terramaster-nas/docker-postgres-data
```

### **Environment Configuration**
```bash
# Edit .env file for NAS deployment
nano .env

# Update these settings:
ENVIRONMENT=nas
STORAGE_TYPE=nas
ENABLE_MONITORING=true
```

### **Deploy with NAS Storage**
```bash
# Deploy with NAS storage and monitoring
./scripts/deployment/deploy.sh nas --clean
```

### **What Gets Deployed**
- ✅ **PostgreSQL Database**: NAS storage with persistence
- ✅ **Flask Backend**: All services with NAS data
- ✅ **React Frontend**: Professional interface
- ✅ **Prometheus**: Metrics collection and storage
- ✅ **Grafana**: Monitoring dashboards
- ✅ **Node Exporter**: System metrics
- ✅ **PostgreSQL Exporter**: Database metrics
- ✅ **NVIDIA GPU Exporter**: GPU monitoring (if available)

### **Access Points**
- **Main Application**: http://localhost:8000
- **Grafana Dashboards**: http://localhost:3001 (admin/Database@NEWSINT2025)
- **Prometheus**: http://localhost:9090
- **System Metrics**: http://localhost:9100

---

## 🏭 **SCENARIO 3: PRODUCTION DEPLOYMENT**

### **Production Preparation**
```bash
# 1. Security hardening
# Update default passwords in .env
nano .env

# 2. SSL/TLS configuration (if using reverse proxy)
# Configure nginx or traefik for SSL termination

# 3. Backup configuration
# Set up automated backup procedures
# Configure backup retention policies
```

### **Environment Configuration**
```bash
# Edit .env for production
nano .env

# Production settings:
ENVIRONMENT=production
STORAGE_TYPE=nas
ENABLE_MONITORING=true
LOG_LEVEL=WARNING
```

### **Deploy Production System**
```bash
# Deploy production with full monitoring
./scripts/deployment/deploy.sh production --clean --build
```

### **Production Features**
- ✅ **High Availability**: Health checks and auto-restart
- ✅ **Resource Limits**: CPU and memory constraints
- ✅ **Security**: Rate limiting and input validation
- ✅ **Monitoring**: Comprehensive system oversight
- ✅ **Logging**: Structured logging and error tracking
- ✅ **Backup**: Automated data protection

---

## 🔧 **DEPLOYMENT CONFIGURATION**

### **Docker Compose Profiles**

#### **Local Profile**
```yaml
# Uses local storage, basic functionality
docker compose --profile local up -d
```

#### **NAS Profile**
```yaml
# Uses NAS storage, full monitoring
docker compose --profile nas --profile monitoring up -d
```

#### **Production Profile**
```yaml
# Uses NAS storage, production settings, full monitoring
docker compose --profile production --profile monitoring up -d
```

### **Environment Variables**
Key configuration options in `.env`:

```bash
# Deployment Type
ENVIRONMENT=local|nas|production
STORAGE_TYPE=local|nas
ENABLE_MONITORING=true|false

# Database Configuration
DB_HOST=postgres
DB_NAME=news_system
DB_USER=NewsInt_DB
DB_PASSWORD=Database@NEWSINT2025

# Performance Tuning
RSS_INTERVAL_MINUTES=60
MAX_CONCURRENT_ARTICLES=100
DATABASE_POOL_SIZE=10

# Monitoring Configuration
GRAFANA_PASSWORD=Database@NEWSINT2025
PROMETHEUS_RETENTION_DAYS=30
```

---

## 📊 **MONITORING SETUP**

### **Grafana Dashboards**
Pre-configured dashboards include:

- **System Overview**: CPU, memory, disk usage
- **Application Metrics**: API response times, error rates
- **Database Performance**: Query performance, connections
- **Content Processing**: RSS collection, article processing
- **Custom Metrics**: Business-specific KPIs

### **Alert Configuration**
```yaml
# Example alert rules
groups:
  - name: system_alerts
    rules:
      - alert: HighCPUUsage
        expr: cpu_usage > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: High CPU usage detected
```

### **Log Aggregation**
- **Structured Logging**: JSON format for easy parsing
- **Log Levels**: DEBUG, INFO, WARNING, ERROR
- **Log Rotation**: Automatic log management
- **Centralized Logging**: Optional ELK stack integration

---

## 🔒 **SECURITY CONFIGURATION**

### **Network Security**
```yaml
# Docker network configuration
networks:
  news-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### **Access Control**
- **Rate Limiting**: API request throttling
- **CORS Configuration**: Cross-origin resource sharing
- **Input Validation**: SQL injection protection
- **Authentication**: User access control (future feature)

### **Data Protection**
- **Encryption**: Data at rest and in transit
- **Backup Encryption**: Secure backup storage
- **Access Logging**: Complete audit trail
- **Data Retention**: Configurable retention policies

---

## 📈 **PERFORMANCE OPTIMIZATION**

### **Database Tuning**
```sql
-- PostgreSQL performance settings
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET effective_cache_size = '1GB';
ALTER SYSTEM SET work_mem = '4MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
```

### **Application Optimization**
- **Connection Pooling**: Database connection management
- **Caching**: Redis integration for performance
- **Async Processing**: Background task processing
- **Resource Limits**: Container resource constraints

### **Monitoring Performance**
- **Response Times**: API endpoint performance
- **Throughput**: Requests per second
- **Resource Usage**: CPU, memory, disk utilization
- **Bottleneck Detection**: Performance analysis tools

---

## 🔄 **BACKUP & RECOVERY**

### **Automated Backups**
```bash
# Database backup script
#!/bin/bash
BACKUP_DIR="/mnt/terramaster-nas/docker-postgres-data/backups"
DATE=$(date +%Y%m%d_%H%M%S)
docker compose exec -T postgres-nas pg_dump -U newsapp news_system > "$BACKUP_DIR/backup_$DATE.sql"
```

### **Backup Schedule**
- **Daily**: Full database backup
- **Weekly**: Complete system backup
- **Monthly**: Archive and retention management
- **On-Demand**: Manual backup triggers

### **Recovery Procedures**
```bash
# Database recovery
docker compose exec -T postgres-nas psql -U newsapp news_system < backup_20240901_120000.sql

# System recovery
docker compose down
docker volume prune
docker compose up -d
```

---

## 🚨 **TROUBLESHOOTING**

### **Common Deployment Issues**

#### **Port Conflicts**
```bash
# Check port usage
sudo lsof -i :8000
sudo lsof -i :5432

# Stop conflicting services
sudo systemctl stop apache2 nginx
```

#### **Permission Issues**
```bash
# Fix NAS mount permissions
sudo chown -R $(id -u):$(id -g) /mnt/terramaster-nas/docker-postgres-data
sudo chmod -R 755 /mnt/terramaster-nas/docker-postgres-data
```

#### **Database Connection Failures**
```bash
# Check database status
docker compose ps postgres-local
docker compose logs postgres-local

# Restart database
docker compose restart postgres-local
```

### **Debug Commands**
```bash
# View all logs
docker compose logs -f

# Check service status
docker compose ps

# Inspect containers
docker compose exec postgres-local psql -U newsapp -d news_system -c "SELECT version();"

# Monitor resources
docker stats
```

---

## 📋 **DEPLOYMENT CHECKLIST**

### **Pre-Deployment**
- [ ] **System Requirements**: Verify hardware and software
- [ ] **Docker Installation**: Confirm Docker and Compose
- [ ] **Network Access**: Test internet connectivity
- [ ] **Storage Preparation**: Local volumes or NAS setup
- [ ] **Environment Configuration**: Update .env file

### **Deployment**
- [ ] **Database Initialization**: Schema creation and data population
- [ ] **Service Startup**: All containers running
- [ ] **Health Checks**: Service status verification
- [ ] **Frontend Access**: Web interface loading
- [ ] **API Testing**: Endpoint functionality validation

### **Post-Deployment**
- [ ] **Monitoring Setup**: Grafana dashboards and alerts
- [ ] **Backup Configuration**: Automated backup procedures
- [ ] **Performance Testing**: Load testing and optimization
- [ ] **Documentation**: Update deployment records
- [ ] **Team Training**: User and admin training

---

## 🔮 **SCALING & FUTURE ENHANCEMENTS**

### **Horizontal Scaling**
- **Load Balancing**: Multiple backend instances
- **Database Clustering**: PostgreSQL read replicas
- **Microservices**: Service decomposition
- **Kubernetes**: Container orchestration

### **ML Integration (v4.0)**
- **Content Summarization**: AI-powered summaries
- **Sentiment Analysis**: Content sentiment scoring
- **Trend Prediction**: Predictive analytics
- **Custom Models**: Domain-specific ML models

### **Enterprise Features**
- **Multi-tenancy**: Multiple organization support
- **Advanced Analytics**: Business intelligence dashboards
- **API Management**: Rate limiting and authentication
- **Integration Hub**: Third-party system connections

---

## 📞 **SUPPORT & MAINTENANCE**

### **Regular Maintenance**
- **Weekly**: System health review
- **Monthly**: Performance optimization
- **Quarterly**: Security updates and patches
- **Annually**: Architecture review and planning

### **Support Resources**
- **Documentation**: Complete system documentation
- **Community**: GitHub discussions and issues
- **Professional Support**: Enterprise support options
- **Training**: User and administrator training

---

## 🎉 **CONCLUSION**

The News Intelligence System v3.0 provides a robust, scalable platform for automated news collection and analysis. With comprehensive deployment options from local development to production enterprise, you have everything needed to:

- **Deploy quickly** with automated scripts
- **Scale efficiently** from development to production
- **Monitor comprehensively** with professional tools
- **Maintain reliably** with automated procedures
- **Grow sustainably** with future-ready architecture

**Your deployment is now professional-grade and production-ready!** 🚀

---

## 🔗 **RELATED DOCUMENTATION**

- **[Quick Start Guide](QUICK_START.md)** - Get started quickly
- **[User Manual](USER_MANUAL.md)** - Complete feature guide
- **[Architecture Guide](ARCHITECTURE.md)** - System design details
- **[Monitoring Guide](MONITORING.md)** - System monitoring setup

