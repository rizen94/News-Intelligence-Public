# 🚀 News Intelligence System v3.0 - Deployment Guide

## **System Overview**
The News Intelligence System is a comprehensive news aggregation, analysis, and prioritization platform that combines:
- **React Frontend** for user interaction
- **Flask Backend** for API services
- **PostgreSQL Database** with vector extensions
- **Content Prioritization Engine** with RAG capabilities
- **Advanced Deduplication System**
- **Story Thread Management**

## **System Requirements**

### **Hardware Requirements**
- **CPU**: 4+ cores (8+ recommended for production)
- **RAM**: 8GB minimum (16GB+ recommended)
- **Storage**: 50GB+ SSD storage
- **Network**: Stable internet connection for RSS feeds

### **Software Requirements**
- **OS**: Linux (Ubuntu 20.04+ recommended)
- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Git**: Latest version

## **Quick Start Deployment**

### **1. Clone & Setup**
```bash
# Clone the repository
git clone <repository-url>
cd news-system

# Set environment variables
cp .env.example .env
# Edit .env with your configuration
```

### **2. Environment Configuration**
```bash
# Required environment variables
DB_HOST=localhost
DB_NAME=news_system
DB_USER=newsapp
DB_PASSWORD=your_secure_password
DB_PORT=5432
SECRET_KEY=your_secret_key_here
ALLOWED_ORIGINS=http://localhost:8000
```

### **3. Launch System**
```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### **4. Access System**
- **Frontend**: http://localhost:8000
- **API**: http://localhost:8000/api/
- **Database**: localhost:5432

## **Production Deployment**

### **1. Production Environment Setup**
```bash
# Create production environment file
cp .env.example .env.production

# Set production values
DB_HOST=your_db_host
DB_NAME=news_system_prod
DB_USER=newsapp_prod
DB_PASSWORD=very_secure_password
SECRET_KEY=very_long_random_secret_key
ALLOWED_ORIGINS=https://yourdomain.com
```

### **2. Production Docker Compose**
```bash
# Use production compose file
docker-compose -f docker-compose.production.yml up -d
```

### **3. SSL/HTTPS Setup**
```bash
# Install Certbot
sudo apt install certbot

# Generate SSL certificate
sudo certbot certonly --standalone -d yourdomain.com

# Configure Nginx reverse proxy (see nginx.conf.example)
```

## **Database Migration**

### **1. Export Existing Data**
```bash
# Export database schema and data
docker exec news-system-postgres pg_dump -U newsapp -d news_system > backup.sql

# Export specific tables
docker exec news-system-postgres pg_dump -U newsapp -d news_system -t articles > articles_backup.sql
```

### **2. Import to New System**
```bash
# Create database
docker exec news-system-postgres createdb -U newsapp news_system

# Import data
docker exec -i news-system-postgres psql -U newsapp -d news_system < backup.sql
```

### **3. Verify Migration**
```bash
# Check table counts
docker exec news-system-postgres psql -U newsapp -d news_system -c "SELECT COUNT(*) FROM articles;"
docker exec news-system-postgres psql -U newsapp -d news_system -c "SELECT COUNT(*) FROM content_priority_levels;"
```

## **System Configuration**

### **1. RSS Feed Configuration**
```bash
# Edit RSS sources
vim api/config/rss_sources.json

# Add your RSS feeds
{
  "sources": [
    {
      "name": "Tech News",
      "url": "https://feeds.feedburner.com/TechCrunch/",
      "category": "Technology",
      "priority": "high"
    }
  ]
}
```

### **2. Content Collection Rules**
```bash
# Access prioritization dashboard
# Navigate to: http://localhost:8000/prioritization
# Configure collection rules for automated content filtering
```

### **3. User Interest Profiles**
```bash
# Set up personalized content tracking
# Navigate to: http://localhost:8000/prioritization
# Create user interest rules and priority levels
```

## **Monitoring & Maintenance**

### **1. Health Checks**
```bash
# System health
curl http://localhost:8000/health

# API status
curl http://localhost:8000/api/dashboard

# Database connectivity
docker exec news-system-postgres pg_isready -U newsapp
```

### **2. Log Monitoring**
```bash
# View application logs
docker-compose logs -f app

# View database logs
docker-compose logs -f postgres

# View system metrics
curl http://localhost:8000/metrics
```

### **3. Backup Strategy**
```bash
# Automated daily backup
# Add to crontab:
0 2 * * * docker exec news-system-postgres pg_dump -U newsapp -d news_system > /backups/news_system_$(date +\%Y\%m\%d).sql

# Keep last 7 days
find /backups -name "*.sql" -mtime +7 -delete
```

## **Troubleshooting**

### **Common Issues**

#### **1. React Frontend Not Loading**
```bash
# Check static file serving
curl -I http://localhost:8000/assets/css/main.css

# Verify build directory
docker exec news-system-app ls -la /app/build/

# Rebuild React app if needed
cd web && npm run build
```

#### **2. Database Connection Issues**
```bash
# Check database status
docker-compose ps postgres

# Test connection
docker exec news-system-app python3 -c "from api.app import get_db_connection; print(get_db_connection())"

# Verify environment variables
docker exec news-system-app env | grep DB_
```

#### **3. API Endpoints Not Working**
```bash
# Check Flask app logs
docker-compose logs -f app

# Test individual endpoints
curl http://localhost:8000/api/articles?page=1&per_page=1

# Verify route registration
docker exec news-system-app python3 -c "from api.app import app; print([r.rule for r in app.url_map.iter_rules()])"
```

### **Performance Optimization**

#### **1. Database Tuning**
```bash
# PostgreSQL configuration
docker exec news-system-postgres psql -U newsapp -c "SHOW shared_buffers;"
docker exec news-system-postgres psql -U newsapp -c "SHOW work_mem;"

# Add to postgresql.conf
shared_buffers = 256MB
work_mem = 4MB
maintenance_work_mem = 64MB
```

#### **2. Caching Strategy**
```bash
# Redis integration (optional)
# Add Redis service to docker-compose.yml
# Implement caching in Flask app
```

## **Security Considerations**

### **1. Access Control**
```bash
# Restrict database access
# Update pg_hba.conf to limit connections
# Use strong passwords for all services
```

### **2. Network Security**
```bash
# Firewall configuration
sudo ufw allow 8000/tcp
sudo ufw allow 5432/tcp
sudo ufw enable

# VPN access for remote management
```

### **3. Data Protection**
```bash
# Encrypt sensitive data
# Regular security updates
# Monitor access logs
```

## **Scaling Considerations**

### **1. Horizontal Scaling**
```bash
# Load balancer setup
# Multiple Flask instances
# Database read replicas
```

### **2. Vertical Scaling**
```bash
# Increase container resources
# Optimize database queries
# Add monitoring and alerting
```

## **Support & Maintenance**

### **1. Regular Updates**
```bash
# Update dependencies
cd web && npm update
cd api && pip install -r requirements.txt --upgrade

# Update Docker images
docker-compose pull
docker-compose up -d
```

### **2. Monitoring Setup**
```bash
# Prometheus metrics collection
# Grafana dashboards
# Alert notifications
```

---

## **📋 Deployment Checklist**

- [ ] Environment variables configured
- [ ] Database created and accessible
- [ ] Docker services running
- [ ] Frontend accessible at http://localhost:8000
- [ ] API endpoints responding
- [ ] RSS feeds configured
- [ ] Content prioritization working
- [ ] Backup strategy implemented
- [ ] Monitoring configured
- [ ] Security measures in place

---

**For support and questions, refer to the project documentation or create an issue in the repository.**
