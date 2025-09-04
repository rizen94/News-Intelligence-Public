# 🚀 Quick Start Guide - News Intelligence System v3.0

## ⚡ **GET UP AND RUNNING IN 5 MINUTES**

This guide will get your News Intelligence System running quickly with local storage. For production deployment with NAS storage, see the [Deployment Guide](DEPLOYMENT.md).

---

## 🎯 **PREREQUISITES**

### **System Requirements**
- **OS**: Linux (Ubuntu 20.04+, Pop!_OS 20.04+)
- **RAM**: 4GB minimum, 8GB recommended
- **Storage**: 10GB minimum for local deployment
- **Docker**: Docker Engine 20.10+ and Docker Compose 2.0+

### **Hardware Recommendations**
- **CPU**: 4+ cores for optimal performance
- **RAM**: 8GB+ for production workloads
- **Storage**: SSD recommended for database performance
- **Network**: Stable internet connection for RSS feeds

---

## 🐳 **STEP 1: INSTALL DOCKER**

### **Ubuntu/Pop!_OS**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin

# Log out and back in, or run:
newgrp docker
```

### **Verify Installation**
```bash
docker --version
docker compose version
```

---

## 📥 **STEP 2: CLONE THE PROJECT**

```bash
# Clone the repository
git clone https://github.com/your-username/news-intelligence-system.git
cd news-intelligence-system

# Check out the stable v3.0 branch
git checkout v3.0
```

---

## ⚙️ **STEP 3: CONFIGURE ENVIRONMENT**

### **Local Development (Default)**
The `.env` file is pre-configured for local development:

```bash
# Verify configuration
cat .env | grep -E "ENVIRONMENT|STORAGE_TYPE|ENABLE_MONITORING"
```

**Expected output:**
```
ENVIRONMENT=local
STORAGE_TYPE=local
ENABLE_MONITORING=false
```

### **Customize Settings (Optional)**
```bash
# Edit environment variables
nano .env

# Key settings you might want to change:
# - DB_PASSWORD: Database password
# - LOG_LEVEL: Logging level (DEBUG, INFO, WARNING)
# - RSS_INTERVAL_MINUTES: RSS collection frequency
```

---

## 🚀 **STEP 4: DEPLOY THE SYSTEM**

### **Quick Deploy (Local Storage)**
```bash
# Make deployment script executable
chmod +x scripts/deployment/deploy-v2.9.sh

# Deploy with local storage
./scripts/deployment/deploy-v2.9.sh
```

### **What This Does**
- ✅ **Starts PostgreSQL** database with local storage
- ✅ **Launches Flask backend** with all API endpoints
- ✅ **Serves React frontend** on port 8000
- ✅ **Creates database schema** automatically
- ✅ **Populates sample data** for testing

---

## 🌐 **STEP 5: ACCESS YOUR SYSTEM**

### **Main Application**
- **URL**: http://localhost:8000
- **Status**: System dashboard and monitoring

### **API Endpoints**
- **Health Check**: http://localhost:8000/health
- **System Status**: http://localhost:8000/api/system/status
- **Dashboard Data**: http://localhost:8000/api/dashboard/real

---

## 📊 **STEP 6: VERIFY SYSTEM STATUS**

### **Check Running Services**
```bash
# View all running containers
docker compose ps

# Check service logs
docker compose logs -f
```

### **Expected Services**
- ✅ **postgres-local** - Database (port 5432)
- ✅ **news-system-local** - Backend API (port 8000)

---

## 🧪 **STEP 7: TEST BASIC FUNCTIONALITY**

### **1. Dashboard Access**
- Navigate to http://localhost:8000
- Verify dashboard loads with sample data
- Check that charts and statistics display

### **2. RSS Feed Addition**
- Go to Sources page
- Add a test RSS feed (e.g., BBC News)
- Verify feed is added and shows as active

### **3. Article Collection**
- Wait for RSS collection cycle (default: 60 minutes)
- Check Articles page for collected content
- Verify deduplication is working

---

## 🔧 **STEP 8: BASIC CONFIGURATION**

### **Add RSS Feeds**
```bash
# Example RSS feeds to test with:
# - BBC News: https://feeds.bbci.co.uk/news/rss.xml
# - Reuters: https://feeds.reuters.com/reuters/topNews
# - TechCrunch: https://techcrunch.com/feed/
```

### **Customize Collection Rules**
- Set content priorities
- Configure deduplication thresholds
- Adjust collection schedules

---

## 📈 **STEP 9: MONITOR SYSTEM HEALTH**

### **System Metrics**
- **Database connections** - Check for connection errors
- **RSS collection success** - Monitor feed health
- **Processing performance** - Watch article processing times

### **Log Monitoring**
```bash
# View backend logs
docker compose logs -f news-system-local

# View database logs
docker compose logs -f postgres-local
```

---

## 🚨 **TROUBLESHOOTING COMMON ISSUES**

### **Port Already in Use**
```bash
# Check what's using port 8000
sudo lsof -i :8000

# Stop conflicting services
sudo systemctl stop apache2  # if Apache is running
sudo systemctl stop nginx     # if Nginx is running
```

### **Database Connection Issues**
```bash
# Check database status
docker compose ps postgres-local

# Restart database
docker compose restart postgres-local

# Check database logs
docker compose logs postgres-local
```

### **Frontend Not Loading**
```bash
# Check if React build exists
ls -la web/build/

# Rebuild frontend if needed
cd web && npm run build
```

---

## 🔄 **STEP 10: NEXT STEPS**

### **Immediate Actions**
1. **Test RSS collection** with real feeds
2. **Verify content processing** pipeline
3. **Check system monitoring** and alerts
4. **Validate backup procedures**

### **Production Preparation**
1. **Review [Deployment Guide](DEPLOYMENT.md)** for production setup
2. **Configure NAS storage** for data persistence
3. **Set up monitoring** with Prometheus/Grafana
4. **Implement backup** and recovery procedures

### **Future Enhancements**
1. **ML Integration** - Content summarization and analysis
2. **Advanced Analytics** - Trend detection and insights
3. **User Management** - Multi-user support and authentication
4. **API Extensions** - Third-party integrations

---

## 📞 **GETTING HELP**

### **Documentation**
- **[User Manual](USER_MANUAL.md)** - Complete feature guide
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions
- **[API Reference](API_REFERENCE.md)** - Backend API documentation

### **Support**
- **GitHub Issues**: Report bugs and request features
- **Documentation**: Check relevant guides for your use case
- **Community**: Join discussions in the project repository

---

## 🎉 **SUCCESS!**

**Congratulations!** You now have a fully functional News Intelligence System running locally. The system includes:

- ✅ **Automated RSS collection** and processing
- ✅ **Content deduplication** and clustering
- ✅ **Professional web interface** with real-time monitoring
- ✅ **Production-ready backend** with comprehensive APIs
- ✅ **Scalable architecture** ready for growth

**Your system is ready to start collecting and analyzing news content!** 🚀

---

## 🔗 **RELATED DOCUMENTATION**

- **[Project Overview](PROJECT_OVERVIEW.md)** - System capabilities and features
- **[User Manual](USER_MANUAL.md)** - Complete usage guide
- **[Deployment Guide](DEPLOYMENT.md)** - Production deployment instructions
- **[Architecture Guide](ARCHITECTURE.md)** - Technical system design

