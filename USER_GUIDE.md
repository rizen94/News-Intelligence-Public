# 📖 News Intelligence System v3.0 - User Guide

## 🎯 **Welcome to the News Intelligence System**

This comprehensive user guide will help you set up, configure, and effectively use the News Intelligence System. Whether you're a system administrator, analyst, or end user, this guide provides step-by-step instructions for all aspects of the system.

---

## 📋 **Table of Contents**

1. [Getting Started](#getting-started)
2. [System Setup](#system-setup)
3. [Configuration](#configuration)
4. [Using the Web Interface](#using-the-web-interface)
5. [Monitoring & Management](#monitoring--management)
6. [Advanced Features](#advanced-features)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)

---

## 🚀 **Getting Started**

### **What You'll Need**
- **Hardware**: 8GB+ RAM, 50GB+ storage, internet connection
- **Software**: Docker, Docker Compose, NAS storage (optional)
- **Time**: 15-30 minutes for initial setup
- **Knowledge**: Basic command line familiarity

### **What You'll Get**
- **Automated News Collection**: 100+ RSS feeds
- **AI-Powered Analysis**: Content summarization and classification
- **Story Tracking**: Monitor story evolution over time
- **Professional Interface**: Real-time dashboards and analytics
- **Enterprise Monitoring**: System health and performance tracking

---

## 🛠️ **System Setup**

### **Step 1: Prerequisites Check**

#### **Docker Installation**
```bash
# Check if Docker is installed
docker --version
docker compose version

# If not installed, install Docker
# Ubuntu/Debian:
sudo apt update
sudo apt install docker.io docker-compose-plugin

# Start Docker service
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -aG docker $USER
# Log out and back in for group changes to take effect
```

#### **NAS Storage Setup (Optional but Recommended)**
```bash
# Create mount point
sudo mkdir -p /mnt/terramaster-nas

# Mount your NAS (example for NFS)
sudo mount -t nfs your-nas-ip:/path /mnt/terramaster-nas

# Make mount permanent (add to /etc/fstab)
echo "your-nas-ip:/path /mnt/terramaster-nas nfs defaults 0 0" | sudo tee -a /etc/fstab
```

#### **System Requirements Check**
```bash
# Check available disk space
df -h

# Check available memory
free -h

# Check CPU cores
nproc
```

### **Step 2: Download and Deploy**

#### **Clone the Repository**
```bash
# Clone the repository
git clone <repository-url>
cd news-intelligence-system

# Verify files are present
ls -la
```

#### **Initial Deployment**
```bash
# Make deployment script executable
chmod +x scripts/deployment/deploy-unified.sh

# Deploy the system
./scripts/deployment/deploy-unified.sh

# The system will:
# 1. Check prerequisites
# 2. Create necessary directories
# 3. Start all services
# 4. Perform health checks
# 5. Show access information
```

#### **Background Deployment (Recommended)**
```bash
# Deploy in background mode
./scripts/deployment/deploy-unified.sh --background

# This allows you to:
# - Close the terminal while deployment continues
# - Continue working while the system sets up
# - Monitor progress through the dashboard
```

### **Step 3: Verify Installation**

#### **Check Service Status**
```bash
# Check if all services are running
./scripts/deployment/deploy-unified.sh --status

# You should see:
# ✅ postgres: Up
# ✅ news-system: Up
# ✅ redis: Up
# ✅ prometheus: Up
# ✅ grafana: Up
```

#### **Access the System**
- **Main Application**: http://localhost:8000
- **Grafana Dashboards**: http://localhost:3001 (admin/Database@NEWSINT2025)
- **Prometheus**: http://localhost:9090
- **Node Exporter**: http://localhost:9100

---

## ⚙️ **Configuration**

### **Environment Configuration**

#### **Basic Configuration**
Edit `env.unified` to customize your system:

```bash
# Database Configuration
DB_PASSWORD=Database@NEWSINT2025
DB_HOST=postgres
DB_NAME=news_system
DB_USER=NewsInt_DB

# RSS Collection Settings
RSS_INTERVAL_MINUTES=60          # How often to check RSS feeds
MAX_CONCURRENT_RSS_FEEDS=10      # Number of feeds to process simultaneously
MAX_CONCURRENT_ARTICLES=100      # Number of articles to process simultaneously

# ML/AI Configuration
LLAMA_MODEL_PATH=/mnt/terramaster-nas/docker-postgres-data/ml-models
RAG_ENABLED=true
SUMMARIZATION_ENABLED=true
STORY_CLASSIFICATION_ENABLED=true
```

#### **Advanced Configuration**
```bash
# Performance Tuning
POSTGRES_SHARED_BUFFERS=256MB
POSTGRES_EFFECTIVE_CACHE_SIZE=1GB
POSTGRES_WORK_MEM=4MB
POSTGRES_MAINTENANCE_WORK_MEM=64MB

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
MAX_LOG_SIZE_MB=100
LOG_RETENTION_DAYS=30

# Monitoring Configuration
PROMETHEUS_RETENTION=15d
GRAFANA_ADMIN_PASSWORD=Database@NEWSINT2025
```

### **RSS Feed Configuration**

#### **Adding Custom RSS Feeds**
```bash
# Edit the RSS configuration in the system
# The system comes with 100+ pre-configured feeds
# You can add custom feeds through the web interface
```

#### **Feed Categories**
- **News**: General news sources
- **Technology**: Tech industry news
- **Business**: Business and finance news
- **Politics**: Political news and analysis
- **Science**: Scientific news and research

### **ML Model Configuration**

#### **Model Settings**
```bash
# Llama 3.1 70B Configuration
LLAMA_MODEL_PATH=/mnt/terramaster-nas/docker-postgres-data/ml-models
LLAMA_MODEL_NAME=llama-3.1-70b
LLAMA_MAX_TOKENS=2048
LLAMA_TEMPERATURE=0.7

# RAG Configuration
RAG_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
RAG_CHUNK_SIZE=512
RAG_CHUNK_OVERLAP=50
RAG_TOP_K=5
```

---

## 🌐 **Using the Web Interface**

### **Main Dashboard**

#### **Accessing the Dashboard**
1. Open your web browser
2. Navigate to http://localhost:8000
3. You'll see the main dashboard with:
   - System status overview
   - Recent articles
   - Story tracking
   - ML processing status

#### **Dashboard Features**
- **Real-time Updates**: Live data refresh
- **System Health**: Service status indicators
- **Recent Activity**: Latest news and processing
- **Quick Actions**: Common tasks and operations

### **Article Analysis**

#### **Viewing Articles**
1. Click on "Articles" in the navigation
2. Browse through collected articles
3. Use filters to find specific content
4. Click on articles for detailed analysis

#### **Article Features**
- **Content Analysis**: AI-powered insights
- **Sentiment Analysis**: Content sentiment detection
- **Entity Extraction**: Key people, places, organizations
- **Related Stories**: Connected content
- **Timeline**: Article processing history

### **Story Dossiers**

#### **Story Tracking**
1. Navigate to "Story Dossiers"
2. View comprehensive story profiles
3. Track story evolution over time
4. Analyze story connections

#### **Story Features**
- **Timeline View**: Story development over time
- **Related Articles**: All articles about the story
- **Key Events**: Important story milestones
- **Sentiment Trends**: How sentiment changes
- **Entity Tracking**: Key people and organizations

### **ML Processing Status**

#### **Monitoring ML Pipeline**
1. Go to "ML Processing" section
2. View real-time processing status
3. Monitor model performance
4. Check processing queues

#### **ML Features**
- **Processing Queue**: Articles waiting for analysis
- **Model Status**: AI model health and performance
- **Processing History**: Completed analysis tasks
- **Performance Metrics**: Processing speed and accuracy

---

## 📊 **Monitoring & Management**

### **Real-time Dashboard**

#### **Starting the Dashboard**
```bash
# Start the monitoring dashboard
./scripts/deployment/deployment-dashboard.sh

# The dashboard shows:
# - System resource usage
# - Service health status
# - Real-time metrics
# - Background processes
```

#### **Dashboard Controls**
- **q**: Quit dashboard
- **r**: Refresh now
- **s**: Show service status
- **l**: Show recent logs
- **h**: Show help

### **Background Process Management**

#### **Checking Background Processes**
```bash
# View all background processes
./scripts/deployment/manage-background.sh status

# View process logs
./scripts/deployment/manage-background.sh logs

# Monitor processes in real-time
./scripts/deployment/manage-background.sh monitor
```

#### **Managing Background Processes**
```bash
# Stop all background processes
./scripts/deployment/manage-background.sh stop

# Clean up log files
./scripts/deployment/manage-background.sh cleanup
```

### **Grafana Monitoring**

#### **Accessing API Documentation**
1. Navigate to http://localhost:8000/docs for Swagger UI
2. Navigate to http://localhost:8000/redoc for ReDoc
3. Explore interactive API documentation and testing

#### **Accessing Grafana**
1. Navigate to http://localhost:3001
2. Login with admin/Database@NEWSINT2025
3. Explore pre-configured dashboards

#### **Available Dashboards**
- **System Overview**: CPU, memory, disk usage
- **Application Metrics**: Request rates, response times
- **Database Performance**: Query performance, connections
- **ML Pipeline**: Processing metrics and performance

### **Prometheus Metrics**

#### **Accessing Prometheus**
1. Navigate to http://localhost:9090
2. Explore collected metrics
3. Create custom queries
4. Set up alerts

#### **Key Metrics**
- **System Metrics**: CPU, memory, disk, network
- **Application Metrics**: HTTP requests, response times
- **Database Metrics**: Connections, queries, performance
- **Custom Metrics**: Business-specific metrics

---

## 🔧 **Advanced Features**

### **Custom RSS Feeds**

#### **Adding Custom Feeds**
1. Access the web interface
2. Go to "Configuration" section
3. Add new RSS feed URLs
4. Configure feed categories and settings

#### **Feed Management**
- **Feed Validation**: Automatic feed health checks
- **Category Assignment**: Organize feeds by topic
- **Update Frequency**: Customize collection intervals
- **Quality Monitoring**: Track feed reliability

### **ML Model Customization**

#### **Model Configuration**
```bash
# Edit model settings in env.unified
LLAMA_MODEL_PATH=/path/to/your/models
LLAMA_MODEL_NAME=your-custom-model
LLAMA_MAX_TOKENS=4096
LLAMA_TEMPERATURE=0.5
```

#### **Custom Models**
- **Fine-tuned Models**: Use your own trained models
- **Model Switching**: Switch between different models
- **Performance Tuning**: Optimize model parameters
- **A/B Testing**: Compare model performance

### **API Integration**

#### **REST API Access**
```bash
# API endpoints available at:
# http://localhost:8000/api/

# Example API calls:
curl http://localhost:8000/api/articles
curl http://localhost:8000/api/stories
curl http://localhost:8000/api/intelligence

# Interactive API documentation:
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

#### **API Features**
- **RESTful Design**: Standard HTTP methods
- **Data Validation**: Input/output validation
- **Error Handling**: Comprehensive error responses
- **Documentation**: Auto-generated API docs

### **Data Export**

#### **Exporting Data**
```bash
# Export articles
curl http://localhost:8000/api/articles/export?format=json

# Export stories
curl http://localhost:8000/api/stories/export?format=csv

# Export intelligence data
curl http://localhost:8000/api/intelligence/export?format=xlsx
```

#### **Export Formats**
- **JSON**: Structured data format
- **CSV**: Spreadsheet-compatible format
- **XLSX**: Excel-compatible format
- **XML**: XML data format

---

## 🚨 **Troubleshooting**

### **Common Issues**

#### **Services Not Starting**
```bash
# Check Docker status
docker info

# Check service logs
docker compose -f docker-compose.unified.yml logs

# Restart services
./scripts/deployment/deploy-unified.sh --restart
```

#### **Database Connection Issues**
```bash
# Check database status
docker compose -f docker-compose.unified.yml ps postgres

# Check database logs
docker compose -f docker-compose.unified.yml logs postgres

# Reset database
./scripts/deployment/deploy-unified.sh --clean --build
```

#### **ML Processing Issues**
```bash
# Check ML service status
docker compose -f docker-compose.unified.yml ps news-system

# Check ML logs
docker compose -f docker-compose.unified.yml logs news-system

# Restart ML services
docker compose -f docker-compose.unified.yml restart news-system
```

#### **NAS Storage Issues**
```bash
# Check NAS mount
mountpoint -q /mnt/terramaster-nas

# Check NAS permissions
ls -la /mnt/terramaster-nas/

# Fix permissions
sudo chown -R 1000:1000 /mnt/terramaster-nas/docker-postgres-data/
```

### **Performance Issues**

#### **Slow Processing**
```bash
# Check system resources
./scripts/deployment/deployment-dashboard.sh

# Check processing queue
# Access web interface -> ML Processing

# Optimize configuration
# Edit env.unified -> increase MAX_CONCURRENT_ARTICLES
```

#### **High Memory Usage**
```bash
# Check memory usage
free -h

# Check container memory
docker stats

# Restart services
./scripts/deployment/deploy-unified.sh --restart
```

### **Getting Help**

#### **Log Analysis**
```bash
# View system logs
./scripts/deployment/manage-background.sh logs

# View specific service logs
docker compose -f docker-compose.unified.yml logs [service-name]

# Follow logs in real-time
docker compose -f docker-compose.unified.yml logs -f
```

#### **System Diagnostics**
```bash
# Run system diagnostics
./scripts/deployment/deploy-unified.sh --info

# Check system health
./scripts/deployment/deployment-dashboard.sh

# Monitor background processes
./scripts/deployment/manage-background.sh monitor
```

---

## 💡 **Best Practices**

### **System Administration**

#### **Regular Maintenance**
```bash
# Daily: Check system status
./scripts/deployment/deploy-unified.sh --status

# Weekly: Clean up logs
./scripts/deployment/manage-background.sh cleanup

# Monthly: Update system
git pull origin main
./scripts/deployment/deploy-unified.sh --clean --build
```

#### **Backup Strategy**
```bash
# Regular backups
./scripts/deployment/backup-data.sh

# Test restore procedures
./scripts/deployment/restore-data.sh

# Monitor backup success
# Check Grafana dashboard for backup metrics
```

#### **Security Practices**
- **Change Default Passwords**: Update default credentials
- **Regular Updates**: Keep system updated
- **Access Control**: Limit system access
- **Network Security**: Use firewalls and VPNs

### **Performance Optimization**

#### **Resource Management**
- **Monitor Resources**: Use Grafana dashboards
- **Optimize Configuration**: Tune environment variables
- **Scale Resources**: Add more CPU/memory as needed
- **Clean Up**: Regular cleanup of old data

#### **ML Pipeline Optimization**
- **Model Selection**: Choose appropriate models
- **Batch Processing**: Process articles in batches
- **Caching**: Use Redis for performance
- **Monitoring**: Track ML performance metrics

### **Data Management**

#### **Content Organization**
- **Feed Categories**: Organize RSS feeds by topic
- **Quality Control**: Monitor feed reliability
- **Deduplication**: Use built-in deduplication features
- **Archival**: Archive old content regularly

#### **Story Tracking**
- **Regular Review**: Review story dossiers regularly
- **Connection Analysis**: Analyze story connections
- **Trend Monitoring**: Monitor story trends
- **Alert Setup**: Set up alerts for important stories

---

## 🎯 **Next Steps**

### **Learning More**
1. **Explore the Web Interface**: Familiarize yourself with all features
2. **Read the Documentation**: Review all available guides
3. **Experiment with Configuration**: Customize settings for your needs
4. **Monitor Performance**: Use monitoring tools to optimize

### **Advanced Usage**
1. **Custom RSS Feeds**: Add your own news sources
2. **ML Model Customization**: Fine-tune AI models
3. **API Integration**: Integrate with other systems
4. **Custom Dashboards**: Create custom Grafana dashboards

### **Community & Support**
1. **Join Discussions**: Participate in community discussions
2. **Report Issues**: Help improve the system
3. **Share Knowledge**: Help other users
4. **Contribute**: Contribute to the project

---

## 📞 **Support & Resources**

### **Documentation**
- **Project Overview**: [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)
- **Codebase Summary**: [CODEBASE_SUMMARY.md](CODEBASE_SUMMARY.md)
- **Deployment Guide**: [UNIFIED_DEPLOYMENT_GUIDE.md](UNIFIED_DEPLOYMENT_GUIDE.md)

### **Getting Help**
- **GitHub Issues**: Report bugs and request features
- **GitHub Discussions**: Ask questions and share ideas
- **Community Forums**: Join community discussions
- **Documentation**: Comprehensive guides and references

---

**Congratulations! You now have a comprehensive understanding of the News Intelligence System. Use this guide as your reference for setup, configuration, and operation.**

**Built with ❤️ for the news intelligence community**
