# 🚀 News Intelligence System v3.0 - Unified Deployment

## 🎯 **All-in-One Package with NAS Storage**

A comprehensive, automated news aggregation and analysis system designed for professional use. This unified deployment combines all the best features into one tidy package with NAS storage and full monitoring.

---

## ✨ **What's New in v3.0**

### **🔄 Unified Deployment**
- **Single Command Deployment** - No more choosing between profiles
- **All Features Included** - Everything enabled by default
- **NAS Storage** - Persistent data across restarts
- **Full Monitoring** - Professional monitoring stack included

### **🧠 Enhanced Features**
- **AI Summarization** - Llama 3.1 70B powered article summaries
- **RAG Enhanced** - Advanced retrieval-augmented generation
- **Living Story Narrator** - Automated story consolidation
- **Storyline Tracking** - Real-time story evolution monitoring
- **Daily Digests** - Automated briefing generation

---

## 🚀 **Quick Start**

### **1. Prerequisites**
- Linux (Ubuntu 20.04+, Pop!_OS 20.04+)
- Docker Engine 20.10+ and Docker Compose 2.0+
- 4GB RAM minimum, 8GB recommended
- NAS mounted at `/mnt/terramaster-nas`

### **2. Deploy the System**
```bash
# Clone the repository
git clone https://github.com/your-username/news-intelligence-system.git
cd news-intelligence-system

# Deploy with unified script
chmod +x scripts/deployment/deploy-unified.sh
./scripts/deployment/deploy-unified.sh
```

### **3. Access Your System**
- **Main Application**: http://localhost:8000
- **Grafana Dashboards**: http://localhost:3001 (admin/Database@NEWSINT2025)
- **Prometheus**: http://localhost:9090

---

## 📦 **What's Included**

### **Core Services**
- ✅ **News System Application** - Full-featured web interface
- ✅ **PostgreSQL Database** - Persistent data storage on NAS
- ✅ **Redis Cache** - High-performance caching layer
- ✅ **All ML/AI Features** - RAG, Living Narrator, Storyline Tracking
- ✅ **All Web Features** - Dashboard, Articles, Story Dossiers, etc.

### **Monitoring & Analytics**
- ✅ **Prometheus** - Metrics collection and storage
- ✅ **Grafana** - Professional monitoring dashboards
- ✅ **Node Exporter** - System resource monitoring
- ✅ **PostgreSQL Exporter** - Database performance monitoring
- ✅ **NVIDIA GPU Exporter** - GPU monitoring (if available)

### **Optional Services**
- 🔧 **Nginx Reverse Proxy** - Production-ready web server
- 🔧 **SSL/TLS Termination** - Secure connections

---

## 🔧 **Management Commands**

### **Deploy**
```bash
./scripts/deployment/deploy-unified.sh                    # Deploy with default settings
./scripts/deployment/deploy-unified.sh --build           # Deploy with rebuild
./scripts/deployment/deploy-unified.sh --clean --build   # Clean deployment with rebuild
./scripts/deployment/deploy-unified.sh --logs            # Deploy and show logs
```

### **Manage**
```bash
./scripts/deployment/deploy-unified.sh --status          # Check service status
./scripts/deployment/deploy-unified.sh --stop            # Stop all services
./scripts/deployment/deploy-unified.sh --restart         # Restart all services
./scripts/deployment/deploy-unified.sh --info            # Show system information
```

---

## 📊 **System Capabilities**

### **Content Collection**
- **RSS Feed Management** - Add, configure, and monitor RSS sources
- **Automatic Collection** - Scheduled content collection and processing
- **Content Validation** - Quality assessment and filtering
- **Error Handling** - Robust error handling and recovery

### **Content Analysis**
- **Text Processing** - HTML cleaning and text normalization
- **Language Detection** - Automatic language identification
- **Quality Scoring** - Content reliability assessment
- **Metadata Extraction** - Publication dates, categories, authors

### **Intelligence Features**
- **Deduplication Engine** - Vector-based similarity detection
- **Entity Recognition** - Named entity extraction and classification
- **Story Clustering** - Automatic content grouping and threading
- **Priority Management** - Content importance scoring and ranking

### **AI/ML Features**
- **AI Summarization** - Llama 3.1 70B powered article summaries
- **Content Analysis** - Multi-dimensional quality scoring system
- **Sentiment Analysis** - AI-powered sentiment classification
- **Key Point Extraction** - Automated bullet point generation
- **RAG Enhanced** - Advanced retrieval-augmented generation
- **Living Story Narrator** - Automated story consolidation
- **Storyline Tracking** - Real-time story evolution monitoring

### **User Experience**
- **Dashboard Overview** - System metrics and content statistics
- **Content Browsing** - Article, cluster, and entity management
- **Advanced Search** - Full-text search with filtering
- **Real-time Updates** - Live data refresh and notifications

---

## 🏗️ **Technical Specifications**

### **Backend Stack**
- **Framework**: Flask 2.3.3 (Python 3.11+)
- **Database**: PostgreSQL 15 with pgvector extension
- **Cache**: Redis 7
- **API**: RESTful API with comprehensive endpoints
- **Processing**: Modular content processing pipeline
- **Monitoring**: Prometheus metrics and health checks

### **Frontend Stack**
- **Framework**: React 18.2.0 with Material-UI
- **Charts**: Recharts for data visualization
- **Routing**: React Router for navigation
- **State**: Context API for global state management
- **Styling**: Material-UI theme system

### **Infrastructure**
- **Containerization**: Docker with Docker Compose
- **Networking**: Custom bridge network (172.20.0.0/16)
- **Storage**: NAS integration for persistent data
- **Monitoring**: Prometheus, Grafana, Node Exporter
- **Security**: Container isolation and access controls

---

## 📈 **Performance & Scalability**

### **Performance Features**
- **Connection Pooling** - Efficient database connection management
- **Caching Strategy** - Application and database caching
- **Async Processing** - Background task processing
- **Resource Optimization** - CPU and memory optimization

### **Scaling Capabilities**
- **Horizontal Scaling** - Multiple backend instances
- **Database Clustering** - Primary-replica setup
- **Load Balancing** - Request distribution across instances
- **Storage Scaling** - NAS or cloud storage integration

---

## 🔒 **Security & Reliability**

### **Security Features**
- **Input Validation** - SQL injection and XSS protection
- **Rate Limiting** - API request throttling
- **CORS Control** - Cross-origin resource sharing management
- **Container Isolation** - Docker-based security boundaries
- **Data Encryption** - Encryption at rest and in transit

### **Reliability Features**
- **Health Checks** - Comprehensive system health monitoring
- **Automatic Recovery** - Service restart and recovery
- **Backup Systems** - Automated data backup procedures
- **Error Handling** - Robust error handling and logging
- **Monitoring** - Real-time system oversight and alerting

---

## 📁 **File Structure**

```
News Intelligence/
├── docker-compose.unified.yml    # Unified Docker Compose file
├── env.unified                   # Unified environment configuration
├── scripts/deployment/
│   └── deploy-unified.sh         # Unified deployment script
├── UNIFIED_DEPLOYMENT_GUIDE.md   # Detailed deployment guide
├── README_UNIFIED.md             # This file
├── api/                          # Backend application
├── web/                          # Frontend application
└── docs/                         # Documentation
```

---

## 🚨 **Troubleshooting**

### **Common Issues**

#### **NAS Not Mounted**
```bash
# Check if NAS is mounted
mountpoint -q /mnt/terramaster-nas && echo "NAS mounted" || echo "NAS not mounted"

# Mount your NAS
sudo mkdir -p /mnt/terramaster-nas
# Add your NAS mount command here
```

#### **Permission Issues**
```bash
# Fix NAS permissions
sudo chown -R 1000:1000 /mnt/terramaster-nas/docker-postgres-data/
```

#### **Port Conflicts**
```bash
# Check what's using port 8000
sudo lsof -i :8000

# Stop conflicting services
sudo systemctl stop apache2  # if Apache is running
sudo systemctl stop nginx     # if Nginx is running
```

### **Health Checks**
```bash
# Check if services are healthy
curl http://localhost:8000/health
curl http://localhost:9090/-/healthy
curl http://localhost:3001/api/health
```

---

## 📚 **Documentation**

### **Getting Started**
- **[UNIFIED_DEPLOYMENT_GUIDE.md](UNIFIED_DEPLOYMENT_GUIDE.md)** - Detailed deployment guide
- **[docs/QUICK_START.md](docs/QUICK_START.md)** - Quick start guide
- **[docs/USER_MANUAL.md](docs/USER_MANUAL.md)** - Complete user guide

### **Technical Documentation**
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Technical design and components
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** - Production deployment instructions
- **[docs/ML_INTEGRATION.md](docs/ML_INTEGRATION.md)** - AI/ML features and capabilities

---

## 🚀 **Future Roadmap**

### **Version 4.0 - Enhanced ML Integration**
- **Advanced Content Summarization** - Multi-model AI summaries
- **Predictive Analytics** - Trend prediction and insights
- **Custom Models** - Domain-specific machine learning models
- **Real-time Processing** - Stream processing capabilities

### **Enterprise Features**
- **Multi-tenancy** - Multiple organization support
- **Advanced Analytics** - Business intelligence dashboards
- **API Management** - Advanced API management and authentication
- **Integration Hub** - Third-party system connections

---

## 🤝 **Contributing**

### **Getting Started**
1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes** and commit (`git commit -m 'Add amazing feature'`)
4. **Push to the branch** (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

### **Development Setup**
```bash
# Clone and setup development environment
git clone https://github.com/your-username/news-intelligence-system.git
cd news-intelligence-system

# Install dependencies
pip install -r api/requirements.txt
cd web && npm install

# Run development servers
# Backend: python api/app.py
# Frontend: npm start
```

---

## 📞 **Support & Community**

### **Getting Help**
- **📚 Documentation**: Check the comprehensive documentation
- **🐛 Issues**: Report bugs and request features via GitHub Issues
- **💬 Discussions**: Join community discussions in GitHub Discussions
- **📧 Contact**: Reach out for professional support

### **Community Guidelines**
- **Be respectful** and inclusive in all interactions
- **Help others** by answering questions and sharing knowledge
- **Follow best practices** for code quality and documentation
- **Contribute constructively** to improve the system

---

## 📄 **License**

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🎉 **Acknowledgments**

The News Intelligence System v3.0 represents a significant evolution in automated news intelligence, combining:

- **Modern web technologies** (React, Material-UI)
- **Robust backend architecture** (Flask, PostgreSQL, Redis)
- **Professional monitoring** (Prometheus, Grafana)
- **Production-grade infrastructure** (Docker, NAS storage)
- **Advanced AI/ML capabilities** (RAG, Living Narrator, Storyline Tracking)

**Ready for immediate production deployment!** 🚀

---

## 🔗 **Quick Links**

- **[🚀 Unified Deployment Guide](UNIFIED_DEPLOYMENT_GUIDE.md)** - Detailed deployment instructions
- **[📖 User Manual](docs/USER_MANUAL.md)** - Complete feature guide
- **[🏗️ Architecture](docs/ARCHITECTURE.md)** - Technical system design
- **[📁 Project Structure](PROJECT_STRUCTURE.md)** - Clean project organization

---

**Built with ❤️ for the news intelligence community**
