# News Intelligence System v3.2.0
## Pre-Migration Archive

**Archive Date**: September 9, 2025  
**Status**: Working System (Pre-Migration)  
**Purpose**: Complete backup before v3.3 migration

---

## 📋 **SYSTEM STATUS**

### **Working Components**
- ✅ **API Server**: Responds to HTTP requests
- ✅ **Database**: PostgreSQL connected and functional
- ✅ **RSS Collection**: Articles being collected from feeds
- ✅ **Frontend**: React application running
- ✅ **Basic Routes**: Articles, feeds, health endpoints working

### **Known Issues (To be fixed in v3.3)**
- ⚠️ **Database Schema**: Column name inconsistencies (`status` vs `processing_status`)
- ⚠️ **Data Type Mismatches**: Article IDs as strings vs integers
- ⚠️ **Service Dependencies**: Complex automation manager causing blocking
- ⚠️ **Over-Engineering**: 100+ files, 31+ services, complex interdependencies
- ⚠️ **Performance**: Server hanging on some requests

---

## 🗂️ **ARCHIVE CONTENTS**

### **Core Application**
- `api/` - Complete backend API (37+ routes, 31+ services)
- `web/` - Complete frontend React application
- `configs/` - Docker and system configuration files
- `scripts/` - System management and deployment scripts

### **Documentation**
- `docs/` - Complete project documentation
- `*.md` - All project documentation files
- `migration_scripts/` - Migration plan and implementation scripts

### **Configuration Files**
- `docker-compose.yml` - Docker container configuration
- `Dockerfile*` - Container build files
- `*.sql` - Database schema files
- `*.sh` - Shell scripts for system management

---

## 🔧 **SYSTEM SPECIFICATIONS**

### **Architecture**
- **Backend**: FastAPI with Python 3.8+
- **Frontend**: React 18 with TypeScript
- **Database**: PostgreSQL 13+
- **Cache**: Redis 6+
- **Containerization**: Docker & Docker Compose

### **Key Features**
- RSS feed collection and processing
- Article analysis and ML processing
- Storyline generation and tracking
- Real-time monitoring and health checks
- Automated content processing pipeline

### **File Structure**
```
v3.2.0/
├── api/                    # Backend API (100+ files)
│   ├── routes/            # API endpoints (37+ files)
│   ├── services/          # Business logic (31+ files)
│   ├── modules/           # ML modules (36+ files)
│   └── database/          # Database layer
├── web/                   # Frontend application
│   ├── src/              # React source code
│   └── public/           # Static assets
├── configs/               # Configuration files
├── scripts/               # Management scripts
├── docs/                  # Documentation
└── migration_scripts/     # v3.3 migration tools
```

---

## 🚀 **RESTORATION INSTRUCTIONS**

To restore this v3.2.0 system:

1. **Copy files back to project root**:
   ```bash
   cp -r archive/v3.2.0/* ./
   ```

2. **Start Docker containers**:
   ```bash
   docker-compose up -d
   ```

3. **Start API server**:
   ```bash
   cd api && python3 -c "
   import sys
   sys.path.append('.')
   from main import app
   import uvicorn
   uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')
   "
   ```

4. **Start frontend** (in separate terminal):
   ```bash
   cd web && npm start
   ```

---

## 📊 **MIGRATION TO v3.3**

This archive represents the **last working state** before the comprehensive migration to v3.3. The migration will:

- **Simplify architecture**: 100+ files → ~30 files
- **Consolidate services**: 31+ services → 5 core services
- **Fix database issues**: Standardize schema and data types
- **Improve performance**: Eliminate blocking operations
- **Maintain functionality**: All features preserved

**Migration Script**: `migration_scripts/run_migration.py`

---

*This archive ensures we can always return to a working v3.2.0 system if needed during or after the v3.3 migration.*

