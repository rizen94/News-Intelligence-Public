# 🔌 Port Mapping Audit - News Intelligence System v3.0

## **🚨 Critical Port Conflicts Identified**

### **1. Multiple Services Using Same Ports**

#### **Port 3000 - CONFLICT!**
- **React Development Server**: `http://localhost:3000/` (web/start-frontend.sh)
- **Grafana**: `http://localhost:3000` (scripts/setup-rss-management.sh)
- **Status**: ⚠️ **CONFLICT** - Both services try to use port 3000

#### **Port 3001 - CONFLICT!**
- **HTML Fallback**: `http://localhost:3001/web/index.html` (web/start-frontend.sh)
- **Grafana**: `http://localhost:3001` (scripts/deployment/setup_nas_storage.sh)
- **Status**: ⚠️ **CONFLICT** - Both services try to use port 3001

#### **Port 3002 - CONFLICT!**
- **Coding Assistant**: `http://localhost:3002` (scripts/gpu-mode-switch.sh)
- **Status**: ⚠️ **POTENTIAL CONFLICT** - May conflict with other services

### **2. Inconsistent Port Usage**

#### **Ollama Service Ports**
- **Default**: `localhost:11434` (most ML modules)
- **Custom IP**: `<OLLAMA_LAN_IP>:11434` (summarization_service.py, background_processor.py)
- **Status**: ⚠️ **INCONSISTENT** - Some modules use localhost, others use custom IP

#### **Database Connection Strings**
- **Main**: `postgresql://newsapp:newsapp_password@postgres:5432/news_intelligence` (docker-compose.yml)
- **Legacy**: `postgresql://newsapp:Database%40NEWSINT2025@localhost:5432/newsintelligence` (api/database/connection.py)
- **Status**: ⚠️ **INCONSISTENT** - Different passwords and database names

## **📊 Current Port Allocation**

### **✅ CONFLICT-FREE PORTS (Docker Compose)**
- **5432** - PostgreSQL (external: 5432)
- **6379** - Redis (external: 6379)
- **8000** - API (external: 8000)
- **80** - Frontend (external: 80)
- **9090** - Prometheus (external: 9090)

### **⚠️ CONFLICTING PORTS (Development)**
- **3000** - React Dev Server + Grafana
- **3001** - HTML Fallback + Grafana
- **3002** - Coding Assistant (potential conflict)

### **🔧 EXTERNAL SERVICE PORTS**
- **11434** - Ollama (external service)
- **9187** - PostgreSQL Exporter (monitoring)
- **9100** - Node Exporter (monitoring)

## **🎯 Port Conflict Resolution Plan**

### **Phase 1: Standardize Development Ports**
1. **React Development**: Keep port 3000
2. **HTML Fallback**: Move to port 3001
3. **Grafana**: Move to port 3002
4. **Coding Assistant**: REMOVED - Project scrapped

### **Phase 2: Standardize Service URLs**
1. **Ollama**: Use consistent `localhost:11434`
2. **Database**: Use consistent connection strings
3. **API**: Use consistent `localhost:8000`

### **Phase 3: Update All References**
1. Update all hardcoded URLs
2. Use environment variables for port configuration
3. Update documentation

## **📋 Recommended Port Allocation**

### **Production Ports (Docker)**
```
5432  - PostgreSQL
6379  - Redis
8000  - API
80    - Frontend
9090  - Prometheus
```

### **Development Ports**
```
3000  - React Development Server
3001  - HTML Fallback
3002  - Grafana
# 3003  - REMOVED - Project scrapped
3004  - Additional Services
```

### **External Service Ports**
```
11434 - Ollama
9187  - PostgreSQL Exporter
9100  - Node Exporter
```

## **🚀 Implementation Steps**

### **1. Create Port Configuration File**
```bash
# Create .env.ports file
REACT_PORT=3000
HTML_FALLBACK_PORT=3001
GRAFANA_PORT=3002
# CODING_ASSISTANT_PORT=3003  # REMOVED - Project scrapped
OLLAMA_PORT=11434
```

### **2. Update All Hardcoded URLs**
- Replace hardcoded localhost:3000 with $REACT_PORT
- Replace hardcoded localhost:3001 with $HTML_FALLBACK_PORT
- Replace hardcoded localhost:3002 with $GRAFANA_PORT

### **3. Update Docker Compose**
- Add port mappings for development services
- Use environment variables for port configuration

### **4. Update Scripts**
- Use environment variables instead of hardcoded ports
- Add port conflict detection

## **⚠️ Risks of Current Configuration**

1. **Service Conflicts** - Multiple services trying to use same ports
2. **Development Issues** - Services may not start due to port conflicts
3. **Inconsistent Behavior** - Different URLs for same services
4. **Maintenance Problems** - Hard to update port configurations

## **✅ Benefits of Resolution**

1. **No Conflicts** - Each service has unique port
2. **Consistent URLs** - Same URLs across all files
3. **Easy Maintenance** - Centralized port configuration
4. **Reliable Development** - Services start without conflicts

---

**Status: READY FOR PORT CONFLICT RESOLUTION**
**Priority: HIGH**
**Estimated Time: 45 minutes**
