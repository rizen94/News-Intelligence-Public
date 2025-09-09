# News Intelligence System v3.3.0 - System Reboot Checklist

**Date**: September 9, 2025  
**Version**: v3.3.0  
**Purpose**: Complete system verification after reboot

---

## **🚀 PRE-REBOOT PREPARATION**

### **✅ Critical Issues Fixed Before Reboot**
- [x] **ArticleProcessingService**: Added missing `process_single_article` method
- [x] **AI Processing Service**: Enhanced JSON parsing to handle malformed AI responses
- [x] **Automation Manager**: Running in background thread to prevent blocking
- [x] **Database Connections**: Fixed connection string issues across all services
- [x] **Startup Scripts**: Created comprehensive startup and recovery scripts

### **📁 Files Created/Modified**
- [x] `startup_with_recovery.sh` - Main startup script
- [x] `monitor_system.sh` - System monitoring
- [x] `disaster_recovery.sh` - Disaster recovery options
- [x] `enhanced_rss_stack_trace.py` - RSS processing testing
- [x] `api/main.py` - Background automation manager
- [x] `api/services/article_processing_service.py` - Added missing method
- [x] `api/services/ai_processing_service.py` - Enhanced JSON parsing

---

## **🔄 POST-REBOOT VERIFICATION CHECKLIST**

### **Phase 1: System Startup (0-5 minutes)**

#### **1.1 Basic System Check**
- [ ] **System Boot**: Verify system started successfully
- [ ] **Docker Service**: `sudo systemctl status docker` - should be active
- [ ] **Network**: Internet connectivity confirmed
- [ ] **Disk Space**: `df -h` - ensure adequate space (>10GB free)
- [ ] **Memory**: `free -h` - ensure adequate RAM (>4GB available)

#### **1.2 Project Directory**
- [ ] **Navigate**: `cd "/home/pete/Documents/Projects/News Intelligence"`
- [ ] **Permissions**: Verify user has read/write access
- [ ] **Files Present**: Check key files exist:
  - [ ] `startup_with_recovery.sh`
  - [ ] `monitor_system.sh`
  - [ ] `disaster_recovery.sh`
  - [ ] `docker-compose.yml`
  - [ ] `api/main.py`

### **Phase 2: Docker Services (5-10 minutes)**

#### **2.1 Docker Startup**
- [ ] **Start Docker**: `sudo systemctl start docker` (if not running)
- [ ] **Docker Status**: `docker --version` - confirm Docker is available
- [ ] **Docker Compose**: `docker-compose --version` - confirm available

#### **2.2 Container Management**
- [ ] **Start Containers**: `docker-compose up -d`
- [ ] **Container Status**: `docker-compose ps` - all containers should be "Up"
- [ ] **PostgreSQL**: `docker exec news-system-postgres pg_isready -U newsapp`
- [ ] **Redis**: `docker exec news-system-redis redis-cli ping` - should return "PONG"

#### **2.3 Database Verification**
- [ ] **Database Connection**: `docker exec news-system-postgres psql -U newsapp -d newsintelligence -c "SELECT 1;"`
- [ ] **Schema Check**: `docker exec news-system-postgres psql -U newsapp -d newsintelligence -c "\dt"`
- [ ] **Data Check**: `docker exec news-system-postgres psql -U newsapp -d newsintelligence -c "SELECT COUNT(*) FROM articles;"`

### **Phase 3: API Server (10-15 minutes)**

#### **3.1 Python Environment**
- [ ] **Python Version**: `python3 --version` - should be 3.8+
- [ ] **Virtual Environment**: `ls -la venv/` - check if exists
- [ ] **Dependencies**: `pip list | grep -E "(fastapi|uvicorn|psycopg2)"`

#### **3.2 API Server Startup**
- [ ] **Start Server**: `./startup_with_recovery.sh` OR manual start:
  ```bash
  cd api
  python3 -c "
  import sys
  sys.path.append('.')
  from main import app
  import uvicorn
  uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')
  " &
  ```
- [ ] **Server Process**: `ps aux | grep -E "(python.*api|uvicorn)"` - should show running process
- [ ] **Port Check**: `netstat -tlnp | grep :8000` - port 8000 should be listening

#### **3.3 API Health Check**
- [ ] **Health Endpoint**: `curl -s http://localhost:8000/api/health/ | jq '.'`
  - Expected: `{"success": true, "data": {"status": "healthy"}}`
- [ ] **Response Time**: Should respond within 5 seconds
- [ ] **Database Status**: Health check should show database as "healthy"

### **Phase 4: Automation & ML Processing (15-20 minutes)**

#### **4.1 Automation Manager**
- [ ] **Logs Check**: `tail -f logs/startup.log` - look for "Automation manager started in background thread"
- [ ] **Process Check**: `ps aux | grep automation` - should show automation processes
- [ ] **No Blocking**: API endpoints should respond quickly (< 2 seconds)

#### **4.2 ML Processing Verification**
- [ ] **Article Processing**: Check logs for "Task article_processing" - should not show errors
- [ ] **JSON Parsing**: Check logs for "Error parsing JSON response" - should be reduced
- [ ] **Processing Status**: `docker exec news-system-postgres psql -U newsapp -d newsintelligence -c "SELECT processing_status, COUNT(*) FROM articles GROUP BY processing_status;"`

#### **4.3 RSS Processing**
- [ ] **RSS Feeds**: `curl -s http://localhost:8000/api/rss/feeds/ | jq '.data.feeds | length'`
- [ ] **Articles Count**: `curl -s http://localhost:8000/api/articles/ | jq '.data.total_count'`
- [ ] **Recent Articles**: Check for articles created in last 10 minutes

### **Phase 5: Frontend (Optional - 20-25 minutes)**

#### **5.1 Node.js Check**
- [ ] **Node Version**: `node --version` - should be 14+ (if available)
- [ ] **NPM**: `npm --version` - should be available

#### **5.2 Frontend Startup**
- [ ] **Dependencies**: `cd web && npm install` (if Node.js available)
- [ ] **Start Frontend**: `npm start` (if Node.js 14+)
- [ ] **Frontend Access**: `curl -s http://localhost:3000` - should return HTML

### **Phase 6: System Monitoring (25-30 minutes)**

#### **6.1 Monitoring Scripts**
- [ ] **System Monitor**: `./monitor_system.sh` - should show all green checkmarks
- [ ] **Log Monitoring**: `tail -f logs/startup.log` - no critical errors
- [ ] **Resource Usage**: `htop` or `top` - reasonable CPU/memory usage

#### **6.2 Performance Verification**
- [ ] **API Response Time**: Multiple `curl` requests should be fast
- [ ] **Database Performance**: Queries should complete quickly
- [ ] **Memory Usage**: Should not be growing indefinitely
- [ ] **CPU Usage**: Should be reasonable (< 80% sustained)

### **Phase 7: Disaster Recovery Testing (30-35 minutes)**

#### **7.1 Recovery Scripts**
- [ ] **Recovery Script**: `./disaster_recovery.sh` - should show menu options
- [ ] **Backup Check**: `ls -la backups/` - should show recent backups
- [ ] **Service Management**: `sudo systemctl status news-intelligence` (if enabled)

#### **7.2 Failure Simulation**
- [ ] **API Restart**: Stop and restart API server
- [ ] **Database Restart**: `docker-compose restart news-system-postgres`
- [ ] **Full Recovery**: Test disaster recovery script

---

## **🔍 TROUBLESHOOTING GUIDE**

### **Common Issues & Solutions**

#### **Docker Issues**
```bash
# If containers won't start
docker-compose down
docker system prune -f
docker-compose up -d --build

# If database connection fails
docker exec news-system-postgres psql -U newsapp -d newsintelligence -c "SELECT 1;"
```

#### **API Server Issues**
```bash
# If API won't start
pkill -f "python.*api"
cd api
python3 -c "from main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8000)"

# If port is in use
sudo lsof -i :8000
sudo kill -9 <PID>
```

#### **Database Issues**
```bash
# If database is corrupted
docker-compose down
docker volume rm news-intelligence_postgres_data
docker-compose up -d
# Re-run migrations
```

#### **Automation Issues**
```bash
# Check automation logs
tail -f logs/startup.log | grep automation

# Restart automation
pkill -f "python.*api"
./startup_with_recovery.sh
```

---

## **📊 SUCCESS CRITERIA**

### **System is Fully Operational When:**
- [ ] All Docker containers are running
- [ ] API server responds to health checks
- [ ] Database is accessible and contains data
- [ ] Automation manager is running without errors
- [ ] Articles are being processed (status changes from 'raw')
- [ ] RSS feeds are being fetched
- [ ] No critical errors in logs
- [ ] System resources are stable

### **Performance Benchmarks:**
- [ ] API response time: < 2 seconds
- [ ] Database queries: < 1 second
- [ ] Memory usage: < 2GB
- [ ] CPU usage: < 50% average
- [ ] Article processing: > 10 articles/hour

---

## **📝 POST-REBOOT REPORT**

**Reboot Date**: _______________  
**Completed By**: _______________  
**Total Time**: _______________  

### **Issues Encountered:**
1. ________________________________
2. ________________________________
3. ________________________________

### **Resolution Actions:**
1. ________________________________
2. ________________________________
3. ________________________________

### **System Status:**
- [ ] **Fully Operational**
- [ ] **Partially Operational** (issues noted above)
- [ ] **Not Operational** (requires intervention)

### **Next Steps:**
1. ________________________________
2. ________________________________
3. ________________________________

---

**✅ SYSTEM REBOOT CHECKLIST COMPLETE**

