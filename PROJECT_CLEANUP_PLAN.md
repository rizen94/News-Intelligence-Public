# Project Structure Cleanup Plan

**Date**: September 26, 2025  
**Status**: 📋 **PLANNING**  
**Goal**: Clean, organized project structure while preserving all functionality

## 🎯 Cleanup Objectives

1. **Preserve All Functionality** - Keep everything that works, even if unused
2. **Identify Production Components** - Mark stable, production-ready code
3. **Archive Development Artifacts** - Move test scripts, copies, outdated files
4. **Create Clean Structure** - Organized, maintainable directory layout
5. **Remove Waste** - Eliminate duplicates, temporary files, unused scripts

## 📊 Current Structure Analysis

### **Root Directory Issues**
- **17 shell scripts** - Many redundant or outdated
- **12 Python files** - Mix of production and test files
- **Multiple Docker files** - Different versions and configurations
- **Scattered documentation** - Already cleaned up
- **Test files in root** - Should be in tests/ directory

### **Key Components Identified**

#### **Production-Ready Components** ✅
- `api/` - Core API backend (stable)
- `web/` - Frontend application (stable)
- `docker-compose.yml` - Main Docker configuration
- `start.sh` - Main startup script
- `docs/` - Documentation (recently cleaned)
- Core service files (`.service`)

#### **Development/Test Components** 🔧
- `scripts/` - Mix of production and development scripts
- `test_*.py` files in root
- Multiple Docker configurations
- Development scripts and utilities
- Backup and archive directories

#### **Redundant/Outdated Components** 🗑️
- Duplicate test files
- Old Docker configurations
- Redundant startup scripts
- Temporary files
- Old backup files

## 🏗️ Proposed Clean Structure

### **Production Directory Structure**
```
News Intelligence/
├── README.md                          # Main documentation
├── docker-compose.yml                 # Production Docker config
├── start.sh                          # Main startup script
├── stop.sh                           # Main stop script
├── docs/                             # Documentation
├── api/                              # Backend API
├── web/                              # Frontend application
├── nginx/                            # Nginx configuration
├── monitoring/                       # Monitoring config
├── configs/                          # Configuration files
├── scripts/                          # Production scripts only
│   ├── production/                   # Production scripts
│   └── maintenance/                  # Maintenance scripts
├── tests/                            # All test files
├── archive/                          # Archived components
└── development/                      # Development tools
    ├── scripts/                      # Development scripts
    ├── docker/                       # Development Docker configs
    └── tools/                        # Development utilities
```

## 📋 Cleanup Actions

### **Phase 1: Identify and Categorize**

#### **Production Scripts** (Keep in root or scripts/production/)
- `start.sh` - Main startup
- `stop.sh` - Main stop
- `manage-service.sh` - Service management
- `setup-autostart.sh` - Production setup

#### **Development Scripts** (Move to development/scripts/)
- `start-dev.sh` - Development startup
- `setup_dev_env.sh` - Development setup
- `quick_fix_startup.sh` - Quick fixes
- `hybrid_dev_prod_system.sh` - Hybrid system
- `version_manager.py` - Version management

#### **Test Files** (Move to tests/)
- `test_article_service.py`
- `test_db_endpoint.py`
- All files in `api/tests/`
- All files in `scripts/test_*`

#### **Docker Configurations** (Consolidate)
- Keep: `docker-compose.yml` (production)
- Archive: `docker-compose-robust-nas.yml`
- Archive: `Dockerfile.optimized`
- Archive: `Dockerfile.simple`
- Keep: `Dockerfile.frontend`

#### **Service Files** (Keep in root)
- `news-intelligence-system.service` (main)
- Archive: `news-intelligence-api.service`
- Archive: `news-intelligence-auto-build.service`

### **Phase 2: Create Clean Structure**

#### **Create New Directories**
```bash
mkdir -p scripts/production
mkdir -p scripts/maintenance
mkdir -p tests
mkdir -p development/scripts
mkdir -p development/docker
mkdir -p development/tools
```

#### **Move Files to Appropriate Locations**
- Production scripts → `scripts/production/`
- Development scripts → `development/scripts/`
- Test files → `tests/`
- Old Docker configs → `development/docker/`
- Utility scripts → `development/tools/`

### **Phase 3: Archive Redundant Components**

#### **Archive Directory Structure**
```
archive/project_cleanup_20250926/
├── old_scripts/                      # Old/redundant scripts
├── old_docker/                       # Old Docker configs
├── old_services/                     # Old service files
├── test_artifacts/                   # Test files and artifacts
└── development_tools/                # Development utilities
```

## 🔧 Implementation Plan

### **Step 1: Backup Current State**
```bash
# Create backup of current structure
cp -r . ../News_Intelligence_Backup_$(date +%Y%m%d)
```

### **Step 2: Create New Structure**
```bash
# Create new directory structure
mkdir -p scripts/{production,maintenance}
mkdir -p tests
mkdir -p development/{scripts,docker,tools}
mkdir -p archive/project_cleanup_20250926/{old_scripts,old_docker,old_services,test_artifacts,development_tools}
```

### **Step 3: Move Files Systematically**
- Move production scripts to `scripts/production/`
- Move development scripts to `development/scripts/`
- Move test files to `tests/`
- Move old Docker configs to `development/docker/`
- Archive redundant files

### **Step 4: Update References**
- Update any hardcoded paths in scripts
- Update documentation to reflect new structure
- Update Docker configurations if needed

### **Step 5: Verify Functionality**
- Test all production scripts
- Verify Docker containers start correctly
- Check that all functionality is preserved

## 🎯 Success Criteria

### **Clean Structure Achieved**
- ✅ Root directory contains only essential files
- ✅ Clear separation between production and development
- ✅ All functionality preserved
- ✅ Easy navigation and maintenance

### **Production Components**
- ✅ Stable, tested code in production locations
- ✅ Clear startup and management scripts
- ✅ Proper Docker configuration
- ✅ Comprehensive documentation

### **Development Components**
- ✅ Development tools organized separately
- ✅ Test files in dedicated directory
- ✅ Development scripts easily accessible
- ✅ Old configurations archived safely

## 📋 File Categorization

### **Keep in Root** (Essential Production Files)
- `README.md`
- `docker-compose.yml`
- `start.sh`
- `stop.sh`
- `news-intelligence-system.service`
- Core documentation files

### **Move to scripts/production/**
- `manage-service.sh`
- `setup-autostart.sh`
- `setup-autostart-simple.sh`

### **Move to development/scripts/**
- `start-dev.sh`
- `setup_dev_env.sh`
- `quick_fix_startup.sh`
- `hybrid_dev_prod_system.sh`
- `version_manager.py`

### **Move to tests/**
- `test_article_service.py`
- `test_db_endpoint.py`
- All files from `api/tests/`
- All files from `scripts/test_*`

### **Archive**
- `docker-compose-robust-nas.yml`
- `Dockerfile.optimized`
- `Dockerfile.simple`
- `news-intelligence-api.service`
- `news-intelligence-auto-build.service`
- `auto-build-prod.sh`
- `build-prod.sh`
- `deploy-prod.sh`
- `cleanup_unused_components.sh`
- `status.sh`
- `start_manual.sh`
- `start_production_api.sh`

## 🚀 Next Steps

1. **Review this plan** and make any adjustments
2. **Create backup** of current state
3. **Execute cleanup** systematically
4. **Test functionality** after each phase
5. **Update documentation** to reflect new structure

---

**Cleanup Status**: 📋 **PLANNING COMPLETE**  
**Ready for Implementation**: ✅ **YES**  
**Estimated Time**: 2-3 hours  
**Risk Level**: 🟡 **LOW** (with proper backup)
