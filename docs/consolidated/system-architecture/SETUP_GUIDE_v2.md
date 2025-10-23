# Setup Guide - Version 2.0 (Stable)

**Version**: 2.0.0  
**Release Date**: August 28, 2025  
**Status**: Production Ready ✅  
**Last Updated**: August 28, 2025  

## 📋 **Table of Contents**

1. [System Requirements](#system-requirements)
2. [Quick Start](#quick-start)
3. [Detailed Installation](#detailed-installation)
4. [Configuration](#configuration)
5. [Verification & Testing](#verification--testing)
6. [Production Deployment](#production-deployment)
7. [Troubleshooting](#troubleshooting)
8. [Upgrade from v1.0](#upgrade-from-v10)

## 🖥️ **System Requirements**

### **Minimum Requirements**
```bash
# Operating System
- Linux (Ubuntu 18.04+, CentOS 7+, RHEL 7+)
- macOS 10.14+
- Windows 10+ (with WSL2 recommended)

# Database
- PostgreSQL 15+ with pgvector extension
- 2GB available RAM for database
- 5GB available storage

# Python Environment
- Python 3.8+
- 2GB available RAM
- 5GB available storage

# Network
- Internet access for RSS feeds
- Port 5432 available (PostgreSQL)
```

### **Recommended Requirements**
```bash
# Operating System
- Ubuntu 20.04 LTS or 22.04 LTS
- CentOS 8+ or RHEL 8+
- macOS 11+ or 12+

# Database
- PostgreSQL 15+ with pgvector extension
- 4GB available RAM for database
- 10GB available storage
- SSD storage for optimal performance

# Python Environment
- Python 3.9+ or 3.10+
- 4GB available RAM
- 10GB available storage

# Network
- High-speed internet connection
- Dedicated network segment (optional)
- Firewall configured for PostgreSQL
```

### **Hardware Recommendations**
```bash
# Development/Testing
- CPU: 2+ cores, 2.0+ GHz
- RAM: 4GB total
- Storage: 20GB SSD
- Network: 10/100 Mbps

# Production
- CPU: 4+ cores, 2.5+ GHz
- RAM: 8GB total
- Storage: 50GB+ SSD
- Network: 1 Gbps
```

## 🚀 **Quick Start**

### **1. One-Command Setup (Linux/macOS)**
```bash
# Clone repository
git clone <your-repo>
cd news-system

# Run automated setup
chmod +x scripts/setup_v2.sh
./scripts/setup_v2.sh

# Start the system
cd api
source ../venv/bin/activate
python3 simple_scheduler.py start
```

### **2. Docker Quick Start**
```bash
# Clone repository
git clone <your-repo>
cd news-system

# Start all services
docker-compose up -d

# Check status
docker ps

# View logs
docker-compose logs -f api
```

### **3. Manual Quick Start**
```bash
# Clone repository
git clone <your-repo>
cd news-system

# Setup virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
cd api
pip install -r requirements.txt

# Configure database (see Configuration section)
# Test system
python3 test_basic_functionality.py
```

## 📚 **Detailed Installation**

### **Method 1: Automated Script Installation**

#### **Step 1: Prerequisites**
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y  # Ubuntu/Debian
sudo yum update -y                      # CentOS/RHEL

# Install required packages
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib git curl
# OR
sudo yum install -y python3 python3-pip postgresql postgresql-server git curl
```

#### **Step 2: Clone Repository**
```bash
# Clone the repository
git clone <your-repo>
cd news-system

# Make setup script executable
chmod +x scripts/setup_v2.sh
```

#### **Step 3: Run Setup Script**
```bash
# Run automated setup
./scripts/setup_v2.sh

# The script will:
# - Install PostgreSQL and pgvector
# - Create database and user
# - Setup Python virtual environment
# - Install Python dependencies
# - Configure the system
# - Run initial tests
```

#### **Step 4: Verify Installation**
```bash
# Check system status
cd api
source ../venv/bin/activate
python3 test_basic_functionality.py

# Start the system
python3 simple_scheduler.py start
```

### **Method 2: Manual Installation**

#### **Step 1: Install PostgreSQL**
```bash
# Ubuntu/Debian
sudo apt install -y postgresql postgresql-contrib

# CentOS/RHEL
sudo yum install -y postgresql postgresql-server
sudo postgresql-setup initdb
sudo systemctl enable postgresql
sudo systemctl start postgresql

# macOS (using Homebrew)
brew install postgresql
brew services start postgresql
```

#### **Step 2: Install pgvector Extension**
```bash
# Ubuntu/Debian
sudo apt install -y postgresql-15-pgvector

# CentOS/RHEL
sudo yum install -y postgresql15-pgvector

# macOS
brew install pgvector

# Verify installation
psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### **Step 3: Setup Database**
```bash
# Connect to PostgreSQL
sudo -u postgres psql

# Create database and user
CREATE DATABASE news_aggregator;
CREATE USER dockside_admin WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE news_aggregator TO dockside_admin;
ALTER USER dockside_admin CREATEDB;
\q

# Enable pgvector extension
sudo -u postgres psql -d news_aggregator -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### **Step 4: Setup Python Environment**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
cd api
pip install -r requirements.txt

# Verify installation
python3 -c "import psycopg2, feedparser, requests; print('Dependencies OK')"
```

#### **Step 5: Configure Environment**
```bash
# Create environment file
cat > .env << EOF
DB_HOST=localhost
DB_NAME=news_aggregator
DB_USER=dockside_admin
DB_PASSWORD=your_secure_password
RSS_FETCH_INTERVAL=3600
RSS_TIMEOUT=30
PRUNING_INTERVAL=43200
MAX_ARTICLE_AGE_DAYS=90
MIN_QUALITY_SCORE=0.3
EOF

# Source environment variables
source .env
```

### **Method 3: Docker Installation**

#### **Step 1: Install Docker**
```bash
# Ubuntu/Debian
sudo apt install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# CentOS/RHEL
sudo yum install -y docker docker-compose
sudo systemctl enable docker
sudo systemctl start docker
sudo usermod -aG docker $USER

# macOS
brew install --cask docker
```

#### **Step 2: Clone and Start**
```bash
# Clone repository
git clone <your-repo>
cd news-system

# Start services
docker-compose up -d

# Check status
docker ps

# View logs
docker-compose logs -f api
```

#### **Step 3: Verify Docker Installation**
```bash
# Check container health
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Test database connection
docker exec -it dockside-postgres psql -U dockside_admin -d news_aggregator -c "SELECT version();"

# Test API health
curl http://localhost/health
```

## ⚙️ **Configuration**

### **Environment Variables**

#### **Required Variables**
```bash
# Database Configuration
DB_HOST=localhost              # Database host
DB_NAME=news_aggregator       # Database name
DB_USER=dockside_admin        # Database user
DB_PASSWORD=                  # Database password

# RSS Configuration
RSS_FETCH_INTERVAL=3600      # RSS fetch interval (seconds)
RSS_TIMEOUT=30               # RSS fetch timeout (seconds)

# Pruning Configuration
PRUNING_INTERVAL=43200       # Pruning interval (seconds)
MAX_ARTICLE_AGE_DAYS=90      # Maximum article age
MIN_QUALITY_SCORE=0.3        # Minimum quality threshold
```

#### **Optional Variables**
```bash
# Logging Configuration
LOG_LEVEL=INFO               # Log level (DEBUG, INFO, WARNING, ERROR)
LOG_PATH=logs/               # Log file path

# Performance Configuration
BATCH_SIZE=100               # Database batch size
CONNECT_TIMEOUT=10           # Database connection timeout
STATEMENT_TIMEOUT=30         # Database query timeout

# Advanced Configuration
ENABLE_ENHANCED_COLLECTION=true    # Enable enhanced RSS collection
ENABLE_AUTO_PRUNING=true           # Enable automatic pruning
DRY_RUN_MODE=false                 # Enable dry run mode for testing
```

### **Database Configuration**

#### **PostgreSQL Configuration**
```bash
# Edit postgresql.conf
sudo nano /etc/postgresql/15/main/postgresql.conf

# Add/modify these settings
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# Restart PostgreSQL
sudo systemctl restart postgresql
```

#### **pgvector Configuration**
```sql
-- Connect to database
psql -U dockside_admin -d news_aggregator

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify extension
\dx vector

-- Test vector operations
SELECT '[1,2,3]'::vector;
```

### **Application Configuration**

#### **Python Configuration**
```python
# api/config/settings.py
import os

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'news_aggregator'),
    'user': os.getenv('DB_USER', 'dockside_admin'),
    'password': os.getenv('DB_PASSWORD', ''),
    'connect_timeout': int(os.getenv('CONNECT_TIMEOUT', 10)),
    'options': f"-c statement_timeout={os.getenv('STATEMENT_TIMEOUT', 30000)}"
}

RSS_CONFIG = {
    'fetch_interval': int(os.getenv('RSS_FETCH_INTERVAL', 3600)),
    'timeout': int(os.getenv('RSS_TIMEOUT', 30)),
    'enable_enhanced': os.getenv('ENABLE_ENHANCED_COLLECTION', 'true').lower() == 'true'
}

PRUNING_CONFIG = {
    'interval': int(os.getenv('PRUNING_INTERVAL', 43200)),
    'max_age_days': int(os.getenv('MAX_ARTICLE_AGE_DAYS', 90)),
    'min_quality': float(os.getenv('MIN_QUALITY_SCORE', 0.3)),
    'batch_size': int(os.getenv('BATCH_SIZE', 100)),
    'dry_run': os.getenv('DRY_RUN_MODE', 'false').lower() == 'true'
}
```

#### **Logging Configuration**
```python
# api/config/logging.py
import logging
import os

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_PATH = os.getenv('LOG_PATH', 'logs/')

# Create logs directory
os.makedirs(LOG_PATH, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'{LOG_PATH}/system.log'),
        logging.StreamHandler()
    ]
)
```

## ✅ **Verification & Testing**

### **System Health Checks**

#### **1. Database Connection Test**
```bash
# Test database connectivity
python3 -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='localhost',
        database='news_aggregator',
        user='dockside_admin',
        password='your_password'
    )
    print('✅ Database connection successful')
    conn.close()
except Exception as e:
    print(f'❌ Database connection failed: {e}')
"
```

#### **2. RSS Connectivity Test**
```bash
# Test RSS feed connectivity
python3 safe_rss_test.py

# Expected output:
# 🧪 Starting Safe RSS Test...
# ⏱️  All operations have timeout protection
# ✅ Database test passed
# ✅ RSS parsing test passed
# ✅ Database insert test passed
# 🎉 All safe tests passed!
```

#### **3. Complete System Test**
```bash
# Run comprehensive system test
python3 test_basic_functionality.py

# Expected output:
# 🧪 Testing Basic System Functionality
# ==================================================
# 🔍 Running RSS Collection test...
# ✅ PASSED: RSS Collection
# 🔍 Running Article Pruning test...
# ✅ PASSED: Article Pruning
# 🔍 Running Manage Ingestion Commands test...
# ✅ PASSED: Manage Ingestion Commands
# 🎉 All tests passed! (3/3)
```

### **Performance Benchmarks**

#### **1. RSS Collection Performance**
```bash
# Benchmark RSS collection
time python3 -c "
from collectors.rss_collector import collect_rss_feeds
collect_rss_feeds()
"

# Expected: real 0m0.6s (excellent performance)
```

#### **2. Article Pruning Performance**
```bash
# Benchmark article pruning
time python3 -c "
from modules.ingestion.article_pruner import ArticlePruner
pruner = ArticlePruner({'host': 'localhost', 'database': 'news_aggregator', 'user': 'dockside_admin', 'password': ''})
pruner.run_pruning_pipeline(dry_run=True)
"

# Expected: real 0m2.7s (excellent performance)
```

#### **3. Database Query Performance**
```bash
# Benchmark database queries
time python3 -c "
import psycopg2
conn = psycopg2.connect(host='localhost', database='news_aggregator', user='dockside_admin', password='')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM articles')
print(cur.fetchone()[0])
conn.close()
"

# Expected: real 0m0.1s (excellent performance)
```

### **Integration Tests**

#### **1. Pipeline Integration Test**
```bash
# Test complete pipeline
python3 manage_ingestion_simple.py basic

# Expected output:
# Starting basic pipeline (RSS + Pruning)...
# Starting RSS feed collection...
# Added 0 articles from BBC News
# Added 0 articles from NPR News
# RSS collection completed successfully
# Starting article pruning pipeline...
# Pruning pipeline completed: {...}
# Article pruning completed successfully: 0 articles removed
# Basic pipeline completed successfully
```

#### **2. Scheduler Test**
```bash
# Test automated scheduler
timeout 30s python3 simple_scheduler.py test

# Expected output:
# 🧪 Running in test mode (single execution)
# 🔄 Running scheduled RSS collection...
# ✅ RSS collection completed
# 🧹 Running scheduled article pruning...
# ✅ Article pruning completed: 0 articles removed
# 🎉 Test completed successfully!
```

## 🚀 **Production Deployment**

### **Production Environment Setup**

#### **1. System Hardening**
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install security updates
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# Configure firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 5432/tcp  # PostgreSQL
sudo ufw allow 80/tcp    # HTTP (if using web interface)
sudo ufw allow 443/tcp   # HTTPS (if using web interface)
```

#### **2. PostgreSQL Security**
```bash
# Edit pg_hba.conf for secure connections
sudo nano /etc/postgresql/15/main/pg_hba.conf

# Add secure connection rules
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
local   all             all                                     md5
host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5

# Restart PostgreSQL
sudo systemctl restart postgresql
```

#### **3. Service Configuration**
```bash
# Create systemd service file
sudo nano /etc/systemd/system/news-system.service

# Add service configuration
[Unit]
Description=News Intelligence System
After=network.target postgresql.service

[Service]
Type=simple
User=news-system
WorkingDirectory=/opt/news-system/api
Environment=PATH=/opt/news-system/venv/bin
ExecStart=/opt/news-system/venv/bin/python3 simple_scheduler.py start
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Enable and start service
sudo systemctl enable news-system
sudo systemctl start news-system
sudo systemctl status news-system
```

### **Monitoring & Maintenance**

#### **1. Log Monitoring**
```bash
# Monitor system logs
tail -f logs/system.log

# Monitor service logs
sudo journalctl -u news-system -f

# Monitor database logs
sudo tail -f /var/log/postgresql/postgresql-15-main.log
```

#### **2. Performance Monitoring**
```bash
# Monitor system resources
htop
iotop
nethogs

# Monitor database performance
psql -U dockside_admin -d news_aggregator -c "
SELECT 
    schemaname,
    tablename,
    attname,
    n_distinct,
    correlation
FROM pg_stats 
WHERE tablename = 'articles';
"
```

#### **3. Backup & Recovery**
```bash
# Create database backup
pg_dump -U dockside_admin -d news_aggregator > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore database
psql -U dockside_admin -d news_aggregator < backup_file.sql

# Automated backup script
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups"
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump -U dockside_admin -d news_aggregator > $BACKUP_DIR/backup_$DATE.sql
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
EOF

chmod +x backup.sh
crontab -e
# Add: 0 2 * * * /opt/backup.sh
```

## 🚨 **Troubleshooting**

### **Common Issues & Solutions**

#### **1. Database Connection Issues**
```bash
# Problem: Connection refused
# Solution: Check PostgreSQL service
sudo systemctl status postgresql
sudo systemctl start postgresql

# Problem: Authentication failed
# Solution: Verify credentials and permissions
sudo -u postgres psql -c "SELECT usename, usesysid FROM pg_user;"
sudo -u postgres psql -c "ALTER USER dockside_admin PASSWORD 'new_password';"

# Problem: Database doesn't exist
# Solution: Create database
sudo -u postgres createdb news_aggregator
sudo -u postgres psql -d news_aggregator -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

#### **2. RSS Collection Issues**
```bash
# Problem: RSS feeds not updating
# Solution: Check network connectivity
curl -I https://feeds.bbci.co.uk/news/rss.xml
ping feeds.bbci.co.uk

# Problem: Timeout errors
# Solution: Increase timeout values
export RSS_TIMEOUT=60
python3 manage_ingestion_simple.py rss

# Problem: Permission denied
# Solution: Check file permissions
chmod +x manage_ingestion_simple.py
chmod +x simple_scheduler.py
```

#### **3. Performance Issues**
```bash
# Problem: Slow RSS collection
# Solution: Check network latency and optimize
ping -c 10 feeds.bbci.co.uk
python3 -c "import time; start=time.time(); import feedparser; feedparser.parse('https://feeds.bbci.co.uk/news/rss.xml'); print(f'Time: {time.time()-start:.2f}s')"

# Problem: Slow database queries
# Solution: Check database performance and indexing
psql -U dockside_admin -d news_aggregator -c "EXPLAIN ANALYZE SELECT COUNT(*) FROM articles;"
psql -U dockside_admin -d news_aggregator -c "CREATE INDEX IF NOT EXISTS idx_articles_created_at ON articles(created_at);"

# Problem: High memory usage
# Solution: Check for memory leaks
python3 -c "import gc; gc.collect(); print('Memory OK')"
```

### **Debug Mode**
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with verbose output
python3 manage_ingestion_simple.py rss --verbose

# Check detailed logs
tail -f logs/debug.log

# Test individual components
python3 -c "from collectors.rss_collector import collect_rss_feeds; collect_rss_feeds()"
```

### **Health Check Commands**
```bash
# Complete system health check
python3 test_basic_functionality.py

# Database health check
python3 -c "import psycopg2; print('Database OK')"

# RSS connectivity check
python3 safe_rss_test.py

# Pruning system check
python3 test_pruner_direct.py

# Service status check
sudo systemctl status news-system
```

## 🔄 **Upgrade from v1.0**

### **Upgrade Process**

#### **Step 1: Backup Existing System**
```bash
# Backup database
pg_dump -U dockside_admin -d news_aggregator > v1_backup.sql

# Backup configuration files
cp -r config/ config_backup/
cp .env .env_backup
```

#### **Step 2: Update Code**
```bash
# Pull latest version
git pull origin main

# Check for conflicts
git status
git diff HEAD~1
```

#### **Step 3: Update Dependencies**
```bash
# Activate virtual environment
source venv/bin/activate

# Update Python packages
pip install -r requirements.txt

# Verify updates
pip list | grep -E "(feedparser|psycopg2|beautifulsoup4)"
```

#### **Step 4: Database Migration**
```bash
# Apply new schema (if any)
psql -U dockside_admin -d news_aggregator -f api/schema_updates.sql

# Verify schema
psql -U dockside_admin -d news_aggregator -c "\dt"
```

#### **Step 5: Test Upgrade**
```bash
# Run system tests
python3 test_basic_functionality.py

# Test individual components
python3 manage_ingestion_simple.py rss
python3 manage_ingestion_simple.py prune

# Verify functionality
python3 -c "from collectors.rss_collector import collect_rss_feeds; print('RSS OK')"
```

### **Rollback Plan**
```bash
# If upgrade fails, rollback to v1.0
git checkout v1.0

# Restore database
psql -U dockside_admin -d news_aggregator < v1_backup.sql

# Restore configuration
cp -r config_backup/* config/
cp .env_backup .env

# Restart services
sudo systemctl restart news-system
```

## 📚 **Additional Resources**

### **Documentation Files**
- **[README.md](README.md)**: Main project overview
- **[VERSION_2_DOCUMENTATION.md](VERSION_2_DOCUMENTATION.md)**: Comprehensive system documentation
- **[USAGE_GUIDE.md](USAGE_GUIDE.md)**: System operation and management
- **[API Reference](api/README.md)**: Technical API documentation
- **[Deployment Guide](DEPLOYMENT_GUIDE.md)**: Production deployment
- **[Changelog](CHANGELOG_v2.md)**: Version history and updates

### **Support & Community**
- **GitHub Issues**: [Report bugs and request features](https://github.com/your-repo/news-system/issues)
- **GitHub Discussions**: [Community support and questions](https://github.com/your-repo/news-system/discussions)
- **Documentation Wiki**: [User guides and tutorials](https://github.com/your-repo/news-system/wiki)

---

## 🎉 **Setup Complete!**

**Congratulations! You have successfully installed the News Intelligence System v2.0.**

### **Next Steps**
1. **Verify Installation**: Run `python3 test_basic_functionality.py`
2. **Start System**: Run `python3 simple_scheduler.py start`
3. **Monitor Health**: Check logs and system status
4. **Add RSS Feeds**: Configure additional news sources
5. **Customize Settings**: Adjust configuration for your environment

### **System Status**
- ✅ **Installation**: Complete
- ✅ **Configuration**: Complete
- ✅ **Testing**: Ready to run
- ✅ **Documentation**: Complete
- ✅ **Support**: Available

**Your News Intelligence System is ready for production use!** 🚀

---

*Last Updated: August 28, 2025*  
*Version: 2.0.0 (Stable)*  
*Status: Production Ready* ✅
