# 🚀 News Intelligence System v3.0

[![Version](https://img.shields.io/badge/version-3.0-blue.svg)](https://github.com/your-repo/news-intelligence-system)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](docker-compose.unified.yml)
[![Python](https://img.shields.io/badge/python-3.9+-blue.svg)](api/requirements.txt)
[![React](https://img.shields.io/badge/react-18+-blue.svg)](web/package.json)

> **A comprehensive, automated news aggregation and analysis platform powered by AI**

The News Intelligence System is a professional-grade platform that automatically collects, processes, and analyzes news content using cutting-edge AI/ML technologies. Built for organizations that need real-time news intelligence and story tracking capabilities.

---

## ✨ **Key Features**

### 🤖 **AI-Powered Analysis**
- **Automated Summarization**: Llama 3.1 70B powered article summaries
- **Story Classification**: Intelligent content categorization
- **Sentiment Analysis**: Content sentiment detection
- **Entity Extraction**: Key people, places, and organizations

### 📰 **Advanced News Processing**
- **Multi-source Collection**: 100+ RSS feeds and news sources
- **Real-time Processing**: Continuous content ingestion and analysis
- **Story Evolution Tracking**: Monitor how stories develop over time
- **Content Deduplication**: Advanced similarity detection

### 🎯 **Intelligence Delivery**
- **Real-time Dashboards**: Live system monitoring and news overview
- **Story Dossiers**: Comprehensive story profiles with timelines
- **Daily Digests**: Automated summary reports
- **RAG-Enhanced Search**: Advanced content discovery

### 🏗️ **Professional Infrastructure**
- **Unified Deployment**: Single-command setup with all features
- **NAS Storage**: Persistent data storage and backup
- **Background Processing**: Continue working during deployments
- **Enterprise Monitoring**: Prometheus + Grafana observability

---

## 🚀 **Quick Start**

### **Prerequisites**
- Docker and Docker Compose installed
- NAS mounted at `/mnt/terramaster-nas` (or update paths in `.env`)
- At least 10GB free disk space
- 8GB+ RAM recommended

### **Deploy in 3 Steps**

```bash
# 1. Clone the repository
git clone <repository-url>
cd news-intelligence-system

# 2. Deploy the system
./scripts/deployment/deploy-unified.sh

# 3. Access your system
# Main Application: http://localhost:8000
# Grafana Dashboards: http://localhost:3001 (admin/Database@NEWSINT2025)
```

### **Background Deployment**
```bash
# Deploy in background (continues if terminal closes)
./scripts/deployment/deploy-unified.sh --background

# Monitor the deployment
./scripts/deployment/deployment-dashboard.sh
```

---

## 📊 **System Overview**

### **Architecture**
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Data Sources  │───▶│  AI Processing  │───▶│  Intelligence   │
│   (RSS Feeds)   │    │  (Llama 3.1)    │    │  Delivery       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                    ┌─────────────────┐
                    │   Web Interface │
                    │   & Dashboards  │
                    └─────────────────┘
```

### **Technology Stack**
- **Frontend**: React.js with Material-UI
- **Backend**: Python FastAPI with async operations
- **Database**: PostgreSQL with Redis caching
- **ML/AI**: Llama 3.1 70B, RAG systems, custom ML models
- **Infrastructure**: Docker, Docker Compose, NAS storage
- **Monitoring**: Prometheus, Grafana, custom dashboards

---

## 🛠️ **Deployment Options**

### **Basic Deployment**
```bash
# Standard deployment
./scripts/deployment/deploy-unified.sh
```

### **Advanced Options**
```bash
# Force rebuild containers
./scripts/deployment/deploy-unified.sh --build

# Clean deployment (removes old containers)
./scripts/deployment/deploy-unified.sh --clean --build

# Deploy and show logs
./scripts/deployment/deploy-unified.sh --logs

# Background deployment
./scripts/deployment/deploy-unified.sh --background
```

### **Management Commands**
```bash
# Check service status
./scripts/deployment/deploy-unified.sh --status

# Stop all services
./scripts/deployment/deploy-unified.sh --stop

# Restart services
./scripts/deployment/deploy-unified.sh --restart
```

---

## 📈 **Monitoring & Management**

### **Real-time Dashboard**
```bash
# Start monitoring dashboard
./scripts/deployment/deployment-dashboard.sh

# Custom refresh interval
./scripts/deployment/deployment-dashboard.sh --interval 10
```

### **Background Process Management**
```bash
# Check background processes
./scripts/deployment/manage-background.sh status

# View logs
./scripts/deployment/manage-background.sh logs

# Monitor processes in real-time
./scripts/deployment/manage-background.sh monitor

# Stop background processes
./scripts/deployment/manage-background.sh stop
```

### **Access Points**
- **Main Application**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs (Swagger UI)
- **API Reference**: http://localhost:8000/redoc (ReDoc)
- **Grafana Dashboards**: http://localhost:3001 (admin/Database@NEWSINT2025)
- **Prometheus**: http://localhost:9090
- **Node Exporter**: http://localhost:9100

---

## 🎯 **Key Capabilities**

### **Automated News Collection**
- **Multi-source RSS Collection**: 100+ news sources
- **Real-time Processing**: Continuous content ingestion
- **Quality Assurance**: Automated content validation
- **Progress Tracking**: Live collection status monitoring

### **AI-Powered Analysis**
- **Content Summarization**: Automated article summaries
- **Story Classification**: Intelligent categorization
- **Sentiment Analysis**: Content sentiment detection
- **Entity Extraction**: Key people, places, and organizations

### **Story Evolution Tracking**
- **Timeline Analysis**: Story development over time
- **Event Correlation**: Related story connections
- **Living Narratives**: Automated story consolidation
- **Story Dossiers**: Comprehensive story profiles

### **Intelligence Delivery**
- **Real-time Dashboards**: Live system monitoring
- **Advanced Search**: RAG-enhanced content discovery
- **Daily Digests**: Automated summary reports
- **Custom Analytics**: Tailored insights and reports

---

## 🔧 **Configuration**

### **Environment Configuration**
The system uses `.env` for configuration. Key settings:

```bash
# Database Configuration
DB_PASSWORD=Database@NEWSINT2025
DB_HOST=postgres
DB_NAME=news_system
DB_USER=NewsInt_DB

# RSS Collection Settings
RSS_INTERVAL_MINUTES=60
MAX_CONCURRENT_RSS_FEEDS=10
MAX_CONCURRENT_ARTICLES=100

# ML/AI Configuration
LLAMA_MODEL_PATH=/mnt/terramaster-nas/docker-postgres-data/ml-models
RAG_ENABLED=true
SUMMARIZATION_ENABLED=true
```

### **NAS Storage Configuration**
```bash
# NAS mount point
NAS_MOUNT_POINT=/mnt/terramaster-nas

# Storage paths
POSTGRES_DATA_PATH=/mnt/terramaster-nas/docker-postgres-data/pgdata
ML_MODELS_PATH=/mnt/terramaster-nas/docker-postgres-data/ml-models
BACKUP_PATH=/mnt/terramaster-nas/docker-postgres-data/backups
```

---

## 📚 **Documentation**

### **Project Documentation**
- **[Project Overview](PROJECT_OVERVIEW.md)**: High-level system overview and intent
- **[Codebase Summary](CODEBASE_SUMMARY.md)**: Detailed technical architecture
- **[User Guide](USER_GUIDE.md)**: Comprehensive usage instructions

### **Technical Documentation**
- **[UX Framework Guide](UX_FRAMEWORK_APPLICATION_GUIDE.md)**: Development framework
- **[Deployment Guide](UNIFIED_DEPLOYMENT_GUIDE.md)**: Infrastructure setup
- **[Enhanced UX Features](ENHANCED_UX_FEATURES_SUMMARY.md)**: User experience features

---

## 🚨 **Troubleshooting**

### **Common Issues**

#### **Docker Not Running**
```bash
# Start Docker
sudo systemctl start docker

# Check Docker status
docker info
```

#### **NAS Not Mounted**
```bash
# Check mount status
mountpoint -q /mnt/terramaster-nas

# Mount NAS (example)
sudo mount -t nfs your-nas-ip:/path /mnt/terramaster-nas
```

#### **Port Conflicts**
```bash
# Check port usage
netstat -tulpn | grep :8000

# Stop conflicting services
sudo systemctl stop apache2  # or nginx
```

#### **Permission Issues**
```bash
# Fix permissions
sudo chown -R 1000:1000 /mnt/terramaster-nas/docker-postgres-data/
```

### **Getting Help**
- **Check Logs**: `./scripts/deployment/manage-background.sh logs`
- **System Status**: `./scripts/deployment/deploy-unified.sh --status`
- **Monitor Dashboard**: `./scripts/deployment/deployment-dashboard.sh`

---

## 🔄 **Updates & Maintenance**

### **Updating the System**
```bash
# Pull latest changes
git pull origin main

# Rebuild and deploy
./scripts/deployment/deploy-unified.sh --clean --build
```

### **Backup & Recovery**
```bash
# Backup data
./scripts/deployment/backup-data.sh

# Restore data
./scripts/deployment/restore-data.sh
```

### **System Cleanup**
```bash
# Clean up old containers
./scripts/deployment/deploy-unified.sh --clean

# Clean up logs
./scripts/deployment/manage-background.sh cleanup
```

---

## 🤝 **Contributing**

### **Development Setup**
```bash
# Clone repository
git clone <repository-url>
cd news-intelligence-system

# Set up development environment
./scripts/setup-dev.sh

# Run tests
./scripts/run-tests.sh
```

### **Code Standards**
- **Python**: PEP 8 compliance
- **JavaScript**: ESLint configuration
- **Documentation**: Comprehensive inline comments
- **Testing**: Unit and integration tests

---

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 **Acknowledgments**

- **Llama 3.1 70B**: Meta's large language model
- **Material-UI**: React component library
- **Docker**: Containerization platform
- **PostgreSQL**: Database system
- **Prometheus & Grafana**: Monitoring stack

---

## 📞 **Support**

- **Documentation**: Comprehensive guides in `/docs`
- **Issues**: GitHub Issues for bug reports
- **Discussions**: GitHub Discussions for questions
- **Community**: Join our community discussions

---

## 🎯 **Roadmap**

### **Current Version (v3.0)**
- ✅ FastAPI backend with async operations
- ✅ Auto-generated API documentation
- ✅ Enhanced UI/UX with real-time updates
- ✅ AI-powered content analysis
- ✅ Story evolution tracking
- ✅ Professional web interface

### **Upcoming Features**
- 🔄 Multi-language support
- 🔄 Advanced ML models
- 🔄 Custom analytics dashboards
- 🔄 API integrations

---

**The News Intelligence System represents the future of automated news analysis, combining cutting-edge AI with professional infrastructure to deliver actionable intelligence at scale.**

**Built with ❤️ for the news intelligence community**

---

## 📊 **System Requirements**

### **Minimum Requirements**
- **CPU**: 4 cores
- **RAM**: 8GB
- **Storage**: 50GB free space
- **Network**: Internet connection for RSS feeds

### **Recommended Requirements**
- **CPU**: 8+ cores
- **RAM**: 16GB+
- **Storage**: 100GB+ free space
- **GPU**: NVIDIA GPU for ML acceleration (optional)
- **Network**: High-speed internet connection

### **Supported Platforms**
- **Linux**: Ubuntu 20.04+, CentOS 8+, Debian 11+
- **Docker**: Docker 20.10+, Docker Compose 2.0+
- **NAS**: NFS, SMB/CIFS compatible storage