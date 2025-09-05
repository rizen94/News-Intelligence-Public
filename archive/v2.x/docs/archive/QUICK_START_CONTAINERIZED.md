# 🚀 **News Intelligence System v2.0.0 - Containerized Quick Start**

## 🎯 **What You Get**

A **production-ready, scalable, and portable** news intelligence system that:
- ✅ **Runs automatically on reboot**
- ✅ **Scales with your hardware**
- ✅ **Easy to migrate to new servers**
- ✅ **Ready for future ML features**
- ✅ **Professional monitoring and logging**

## ⚡ **Quick Start (5 Minutes)**

### **1. Prerequisites**
```bash
# Install Docker and Docker Compose
sudo apt update
sudo apt install -y docker.io docker-compose git curl

# Enable Docker service
sudo systemctl enable docker
sudo systemctl start docker

# Add user to docker group (optional, for non-sudo usage)
sudo usermod -aG docker $USER
newgrp docker
```

### **2. Deploy the System**
```bash
# Clone the repository
git clone https://github.com/your-repo/news-system.git
cd news-system

# Make deployment script executable
chmod +x deploy.sh

# Deploy everything automatically
./deploy.sh deploy
```

### **3. Verify Deployment**
```bash
# Check service status
./deploy.sh status

# View logs
./deploy.sh logs
```

## 🌐 **Access Your System**

| Service | URL | Credentials | Purpose |
|---------|-----|-------------|---------|
| **News System** | http://localhost | N/A | Main application |
| **Grafana** | http://localhost:3000 | admin/admin123 | Monitoring dashboard |
| **Prometheus** | http://localhost:9090 | N/A | Metrics collection |
| **PostgreSQL** | localhost:5432 | dockside_admin/secure_password_123 | Database |
| **Redis** | localhost:6379 | redis_password_123 | Caching & queues |

## 🔧 **Daily Operations**

### **Start/Stop Services**
```bash
# Start all services
./deploy.sh start

# Stop all services
./deploy.sh stop

# Restart all services
./deploy.sh restart
```

### **Backup & Restore**
```bash
# Create backup
./deploy.sh backup

# Restore from backup
./deploy.sh restore backups/backup_YYYYMMDD_HHMMSS.sql
```

### **Monitoring & Logs**
```bash
# View real-time logs
./deploy.sh logs

# Check service status
./deploy.sh status

# Monitor resources
docker stats
```

## 🚀 **Auto-Start on Reboot**

### **Option 1: Systemd Service (Recommended)**
```bash
# Install the systemd service
sudo cp news-system.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable news-system
sudo systemctl start news-system

# Verify it's enabled
sudo systemctl is-enabled news-system
```

### **Option 2: Docker Compose Auto-Start**
```bash
# Docker Compose already has restart: unless-stopped
# Services will automatically restart on reboot
```

## 📊 **System Monitoring**

### **Grafana Dashboards**
1. Open http://localhost:3000
2. Login with admin/admin123
3. Navigate to Dashboards
4. View system performance metrics

### **Custom Metrics Available**
- RSS collection frequency and success rate
- Article processing performance
- Database query performance
- System resource usage
- Error rates and response times

## 🔒 **Security Features**

### **Built-in Security**
- ✅ Non-root container execution
- ✅ Network isolation
- ✅ Rate limiting (API: 10 req/s, Web: 30 req/s)
- ✅ Health checks and auto-restart
- ✅ Secure password defaults

### **Production Hardening**
```bash
# Generate strong passwords
openssl rand -base64 32 > .env.production

# Enable HTTPS (uncomment in nginx config)
# Configure SSL certificates in docker/nginx/ssl/
```

## 📈 **Scaling & Performance**

### **Current Configuration**
- **RSS Collection**: Every 60 minutes
- **Article Pruning**: Every 12 hours
- **Database Pool**: 10 connections
- **Memory Limits**: Optimized for 4GB+ RAM

### **Scale Up (Future)**
```bash
# Edit .env file
RSS_INTERVAL_MINUTES=30      # More frequent collection
MAX_CONCURRENT_RSS_FEEDS=20  # Handle more feeds
DATABASE_POOL_SIZE=20        # More database connections
```

### **Horizontal Scaling**
```yaml
# Edit docker-compose.yml
services:
  news-system:
    deploy:
      replicas: 3  # Run 3 instances
```

## 🔄 **Migration to New Hardware**

### **1. Backup Current System**
```bash
./deploy.sh backup
cp .env .env.backup
```

### **2. Transfer to New Server**
```bash
# Copy backup files
scp backups/* user@new-server:/path/to/news-system/backups/
scp .env.backup user@new-server:/path/to/news-system/.env
```

### **3. Deploy on New Hardware**
```bash
# On new server
git clone https://github.com/your-repo/news-system.git
cd news-system
./deploy.sh deploy
./deploy.sh restore backups/backup_YYYYMMDD_HHMMSS.sql
```

## 🆘 **Troubleshooting**

### **Common Issues**

1. **Services Won't Start**
   ```bash
   # Check Docker status
   sudo systemctl status docker
   
   # Check logs
   ./deploy.sh logs
   ```

2. **Database Connection Issues**
   ```bash
   # Check PostgreSQL health
   docker-compose exec postgres pg_isready -U dockside_admin
   
   # Verify network
   docker-compose exec news-system ping postgres
   ```

3. **Performance Issues**
   ```bash
   # Monitor resources
   docker stats
   
   # Check service health
   docker-compose ps
   ```

### **Reset Everything**
```bash
# Complete cleanup (WARNING: Deletes all data)
./deploy.sh cleanup

# Fresh deployment
./deploy.sh deploy
```

## 🎯 **Next Steps**

### **Immediate (v2.0.0)**
- ✅ System is running and stable
- ✅ RSS collection working
- ✅ Article pruning automated
- ✅ Monitoring active

### **Short Term (v2.1.0)**
- 🔄 Add more RSS feeds
- 🔄 Customize pruning rules
- 🔄 Set up alerts and notifications
- 🔄 Performance tuning

### **Long Term (v3.0.0)**
- 🚀 ML-powered content analysis
- 🚀 Advanced clustering and summarization
- 🚀 Story tracking and evolution
- 🚀 RAG-powered research

## 📞 **Support**

- **Documentation**: [VERSION_2_DOCUMENTATION.md](VERSION_2_DOCUMENTATION.md)
- **Migration Guide**: [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
- **Setup Guide**: [SETUP_GUIDE_v2.md](SETUP_GUIDE_v2.md)
- **Issues**: GitHub Issues page

---

**🎉 Congratulations!** Your News Intelligence System is now:
- **Containerized** for easy deployment
- **Scalable** for future growth
- **Portable** for hardware migration
- **Production-ready** for 24/7 operation
- **Future-proofed** for ML features

**Next**: Add RSS feeds, customize settings, and enjoy automated news intelligence!
