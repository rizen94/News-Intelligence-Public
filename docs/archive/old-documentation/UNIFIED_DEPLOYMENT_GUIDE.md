# 🚀 News Intelligence System v3.0 - Unified Deployment Guide

## 🎯 **All-in-One Package with NAS Storage**

This unified deployment combines all the best features from the local, NAS, and production deployments into one comprehensive package. No more choosing between different profiles - everything is included by default!

---

## ✨ **What's Included**

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

## 🚀 **Quick Start**

### **1. Prerequisites**
```bash
# Ensure Docker is running
docker --version
docker compose version

# Mount your NAS (if not already mounted)
sudo mkdir -p /mnt/terramaster-nas
# Mount your NAS to /mnt/terramaster-nas
```

### **2. Deploy the System**
```bash
# Make the deployment script executable
chmod +x scripts/deployment/deploy-unified.sh

# Deploy with default settings
./scripts/deployment/deploy-unified.sh

# Or deploy with rebuild
./scripts/deployment/deploy-unified.sh --build

# Or in background mode (continues if terminal closes)
./scripts/deployment/deploy-unified.sh --background
```

### **3. Monitor Your Deployment**
```bash
# Real-time dashboard
./scripts/deployment/deployment-dashboard.sh

# Check background processes
./scripts/deployment/manage-background.sh status

# View logs
./scripts/deployment/manage-background.sh logs

# Monitor processes in real-time
./scripts/deployment/manage-background.sh monitor
```

### **4. Access Your System**
- **Main Application**: http://localhost:8000
- **Grafana Dashboards**: http://localhost:3001 (admin/Database@NEWSINT2025)
- **Prometheus**: http://localhost:9090
- **Node Exporter**: http://localhost:9100

---

## 🎯 **Enhanced User Experience Features**

### **Better Error Messaging**
- **Detailed Error Information**: Clear error messages with specific solutions
- **Exit Code Explanations**: Understand what went wrong and how to fix it
- **Context-Aware Messages**: Errors include relevant context and next steps

### **Activity Updates & Confirmations**
- **Real-time Progress**: See exactly what's happening during deployment
- **Time Estimates**: Know how long each operation will take
- **User Confirmations**: Confirm before destructive operations
- **Status Updates**: Clear success/failure indicators

### **Background Process Management**
- **Background Mode**: Deployments continue even if terminal closes
- **Process Tracking**: Monitor background processes and their status
- **Log Management**: Automatic log file creation and management
- **Safe Exit**: Background processes continue running until explicitly stopped

### **Interactive Notifications**
- **Progress Spinners**: Visual feedback during long operations
- **Color-coded Output**: Easy to distinguish between info, warnings, and errors
- **Confirmation Prompts**: Prevent accidental destructive operations
- **Helpful Suggestions**: Get guidance on what to do next

---

## 📋 **Deployment Options**

### **Basic Deployment**
```bash
./scripts/deployment/deploy-unified.sh
```

### **Clean Deployment (Remove old containers)**
```bash
./scripts/deployment/deploy-unified.sh --clean
```

### **Rebuild Deployment**
```bash
./scripts/deployment/deploy-unified.sh --build
```

### **Clean + Rebuild**
```bash
./scripts/deployment/deploy-unified.sh --clean --build
```

### **Deploy with Logs**
```bash
./scripts/deployment/deploy-unified.sh --logs
```

---

## 🔧 **Management Commands**

### **Check Status**
```bash
./scripts/deployment/deploy-unified.sh --status
```

### **Stop Services**
```bash
./scripts/deployment/deploy-unified.sh --stop
```

### **Restart Services**
```bash
./scripts/deployment/deploy-unified.sh --restart
```

### **View Logs**
```bash
./scripts/deployment/deploy-unified.sh --logs
```

### **System Information**
```bash
./scripts/deployment/deploy-unified.sh --info
```

---

## 📁 **File Structure**

```
News Intelligence/
├── docker-compose.unified.yml    # Unified Docker Compose file
├── env.unified                   # Unified environment configuration
├── scripts/deployment/
│   └── deploy-unified.sh         # Unified deployment script
└── UNIFIED_DEPLOYMENT_GUIDE.md   # This guide
```

---

## ⚙️ **Configuration**

### **Environment Variables**
All configuration is in `env.unified`:

```bash
# Core settings
DB_PASSWORD=Database@NEWSINT2025
RSS_INTERVAL_MINUTES=60
LOG_LEVEL=INFO

# Performance tuning
POSTGRES_SHARED_BUFFERS=256MB
MAX_CONCURRENT_RSS_FEEDS=10

# Feature flags
ENABLE_ML_PROCESSING=true
ENABLE_RAG_ENHANCED=true
ENABLE_LIVING_NARRATOR=true
```

### **NAS Storage Paths**
All data is stored on NAS for persistence:
```
/mnt/terramaster-nas/docker-postgres-data/
├── pgdata/           # PostgreSQL data
├── data/             # Application data
├── logs/             # Application logs
├── backups/          # Database backups
├── temp/             # Temporary files
├── ml-models/        # ML models
├── cache/            # Application cache
├── uploads/          # File uploads
├── prometheus-data/  # Prometheus metrics
├── grafana-data/     # Grafana dashboards
└── redis-data/       # Redis data
```

---

## 🔍 **Service Details**

### **Ports Used**
| Service | Port | Description |
|---------|------|-------------|
| News System | 8000 | Main web application |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |
| Grafana | 3001 | Monitoring dashboards |
| Prometheus | 9090 | Metrics collection |
| Node Exporter | 9100 | System metrics |
| PostgreSQL Exporter | 9187 | Database metrics |
| NVIDIA GPU Exporter | 9445 | GPU metrics (if available) |
| Nginx | 80/443 | Reverse proxy (optional) |

### **Container Names**
- `news-system-app` - Main application
- `news-system-postgres` - Database
- `news-system-redis` - Cache
- `news-system-prometheus` - Metrics
- `news-system-grafana` - Dashboards
- `news-system-node-exporter` - System monitoring
- `news-system-postgres-exporter` - Database monitoring
- `news-system-nvidia-exporter` - GPU monitoring

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

#### **Container Issues**
```bash
# Check container status
docker compose -f docker-compose.unified.yml ps

# View container logs
docker compose -f docker-compose.unified.yml logs news-system

# Restart specific service
docker compose -f docker-compose.unified.yml restart news-system
```

### **Health Checks**
```bash
# Check if services are healthy
curl http://localhost:8000/health
curl http://localhost:9090/-/healthy
curl http://localhost:3001/api/health
```

---

## 📊 **Monitoring**

### **Grafana Dashboards**
Access Grafana at http://localhost:3001 with:
- **Username**: admin
- **Password**: Database@NEWSINT2025

### **Prometheus Metrics**
Access Prometheus at http://localhost:9090

### **System Metrics**
- **Node Exporter**: http://localhost:9100
- **PostgreSQL Exporter**: http://localhost:9187
- **GPU Exporter**: http://localhost:9445 (if GPU available)

---

## 🔄 **Updates and Maintenance**

### **Update the System**
```bash
# Pull latest changes
git pull

# Rebuild and deploy
./scripts/deployment/deploy-unified.sh --clean --build
```

### **Backup Data**
```bash
# Backup is automatic, but you can also:
docker compose -f docker-compose.unified.yml exec postgres pg_dump -U NewsInt_DB news_system > backup.sql
```

### **Clean Up**
```bash
# Remove old containers and volumes
./scripts/deployment/deploy-unified.sh --clean

# Clean up Docker system
docker system prune -f
```

---

## 🎉 **Benefits of Unified Deployment**

### **✅ Advantages**
- **Single Command Deployment** - No more choosing profiles
- **All Features Included** - Everything enabled by default
- **NAS Storage** - Persistent data across restarts
- **Full Monitoring** - Professional monitoring stack
- **Production Ready** - All security and performance features
- **Easy Management** - Simple commands for all operations

### **🔧 What's Different**
- **No Profiles** - Everything is included by default
- **NAS Storage Only** - No local storage options
- **All Features Enabled** - ML, RAG, Living Narrator, etc.
- **Full Monitoring** - Prometheus + Grafana included
- **Simplified Commands** - One script for everything

---

## 📞 **Support**

### **Getting Help**
- Check the logs: `./scripts/deployment/deploy-unified.sh --logs`
- Check status: `./scripts/deployment/deploy-unified.sh --status`
- View system info: `./scripts/deployment/deploy-unified.sh --info`

### **Documentation**
- **README.md** - Project overview
- **docs/QUICK_START.md** - Quick start guide
- **docs/USER_MANUAL.md** - Complete user guide
- **docs/ARCHITECTURE.md** - Technical architecture

---

## 🚀 **Ready to Deploy!**

Your unified News Intelligence System is ready to deploy with a single command:

```bash
./scripts/deployment/deploy-unified.sh
```

**Enjoy your all-in-one news intelligence platform!** 🎉
