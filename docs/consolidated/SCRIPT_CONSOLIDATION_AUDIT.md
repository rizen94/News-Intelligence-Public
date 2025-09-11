# 🔧 Script Consolidation Audit - News Intelligence System v3.0

## **🚨 Current Script Issues Identified**

### **1. Duplicate/Conflicting Scripts**
- **Multiple Docker cleanup scripts**: `docker-cleanup.sh`, `quick-docker-cleanup.sh`, `setup-docker-cleanup.sh`
- **Multiple deployment scripts**: `deploy-template.sh`, `deployment-dashboard.sh`, `deploy_new_hardware.sh`
- **Multiple setup scripts**: `setup-ollama.sh`, `setup-domain-system.sh`, `setup-local-dns.sh`, `setup-rss-management.sh`
- **Multiple frontend scripts**: `build-react.sh`, `start-frontend.sh` (in web/)

### **2. Script Categories Analysis**

#### **✅ ESSENTIAL PRODUCTION SCRIPTS (Keep)**
- `start.sh` - Main system startup
- `stop.sh` - Main system shutdown
- `web/build-react.sh` - Frontend build
- `web/start-frontend.sh` - Frontend development

#### **🔄 CONSOLIDATION CANDIDATES**
- **Docker Management**: 3 scripts → 1 unified script
- **Deployment**: 8 scripts → 2-3 focused scripts
- **Setup**: 6 scripts → 1 unified setup script
- **Monitoring**: 2 scripts → 1 unified monitoring script

#### **📦 ARCHIVE CANDIDATES**
- `scripts/deployment/` - Move to archive (development-specific)
- `scripts/system-recovery-optimized.sh` - Move to archive
- `scripts/gpu-mode-switch.sh` - Move to archive (hardware-specific)
- `scripts/setup-ollama.sh` - Move to archive (one-time setup)

## **🎯 Proposed Microservice Architecture Scripts**

### **Core Production Scripts (Main Directory)**
```
News Intelligence System/
├── start.sh                    # ✅ System startup
├── stop.sh                     # ✅ System shutdown
├── scripts/
│   ├── setup.sh               # 🔄 Unified system setup
│   ├── docker-manage.sh       # 🔄 Docker operations
│   ├── monitor.sh             # 🔄 System monitoring
│   └── deploy.sh              # 🔄 Production deployment
└── web/
    ├── build.sh               # 🔄 Frontend build
    └── dev.sh                 # 🔄 Frontend development
```

### **Consolidated Script Functions**

#### **1. `scripts/setup.sh` (Unified Setup)**
- Replace: `setup-ollama.sh`, `setup-domain-system.sh`, `setup-local-dns.sh`, `setup-rss-management.sh`
- Functions: Initial system setup, dependencies, configuration

#### **2. `scripts/docker-manage.sh` (Docker Operations)**
- Replace: `docker-cleanup.sh`, `quick-docker-cleanup.sh`, `setup-docker-cleanup.sh`
- Functions: Start, stop, clean, restart, logs

#### **3. `scripts/monitor.sh` (System Monitoring)**
- Replace: `monitor_system.py`, `view_metrics.py`
- Functions: Health checks, metrics, performance monitoring

#### **4. `scripts/deploy.sh` (Production Deployment)**
- Replace: `deploy-template.sh`, `deployment-dashboard.sh`
- Functions: Production deployment, updates, rollbacks

## **📋 Consolidation Plan**

### **Phase 1: Create Unified Scripts**
1. Create `scripts/setup.sh` - Unified system setup
2. Create `scripts/docker-manage.sh` - Docker operations
3. Create `scripts/monitor.sh` - System monitoring
4. Create `scripts/deploy.sh` - Production deployment

### **Phase 2: Archive Redundant Scripts**
1. Move deployment scripts to `archive/v3.0/development/scripts/`
2. Move hardware-specific scripts to archive
3. Move one-time setup scripts to archive
4. Move development scripts to archive

### **Phase 3: Update Documentation**
1. Update README with new script structure
2. Update deployment guides
3. Create script usage documentation

## **🚀 Benefits of Consolidation**

1. **Clarity** - Single script per function
2. **Maintainability** - Easier to update and debug
3. **Consistency** - Standardized script patterns
4. **Professionalism** - Clean, organized structure
5. **Microservice Ready** - Proper service separation

## **⚠️ Risks to Consider**

1. **Functionality Loss** - Ensure all features preserved
2. **Dependencies** - Check script interdependencies
3. **Testing** - Verify all consolidated scripts work
4. **Documentation** - Update all references

---

**Status: READY FOR CONSOLIDATION**
**Priority: HIGH**
**Estimated Time: 45 minutes**
