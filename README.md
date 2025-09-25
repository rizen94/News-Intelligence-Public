# News Intelligence System v3.0

## 🎯 **System Overview**

The News Intelligence System is an AI-powered news aggregation and analysis platform that processes RSS feeds, analyzes articles, and creates intelligent storylines for investigative journalism.

### **Current Status: PRODUCTION READY** ✅
- **Frontend**: `http://localhost:80` - React web interface
- **API**: `http://localhost:8000` - FastAPI backend
- **Database**: `localhost:5432` - PostgreSQL with real data
- **Cache**: `localhost:6379` - Redis caching
- **Monitoring**: `localhost:9090` - Prometheus metrics

---

## 📚 **Documentation Index**

### **Core Documentation**
- **[DEVELOPMENT_METHODOLOGY.md](./DEVELOPMENT_METHODOLOGY.md)** - Development workflow and best practices
- **[PRODUCTION_GIT_WORKFLOW.md](./PRODUCTION_GIT_WORKFLOW.md)** - Git branch strategy and workflow
- **[ENVIRONMENT_MANAGEMENT.md](./ENVIRONMENT_MANAGEMENT.md)** - Environment separation strategy

### **System Documentation**
- **[DEPLOYMENT_STATUS.md](./DEPLOYMENT_STATUS.md)** - Current deployment status
- **[docs/PROJECT_OVERVIEW.md](./docs/PROJECT_OVERVIEW.md)** - High-level system overview
- **[docker-compose.yml](./docker-compose.yml)** - Docker container configuration

### **Enforcement Tools**
- **[scripts/enforce_methodology.sh](./scripts/enforce_methodology.sh)** - Methodology enforcement script
- **[scripts/pre_deployment_check.sh](./scripts/pre_deployment_check.sh)** - Pre-deployment validation
- **[scripts/test_pipeline.sh](./scripts/test_pipeline.sh)** - Pipeline testing script

---

## 🚀 **Quick Start**

### **Access Production System**
```bash
# Web Interface
open http://localhost:80

# API Documentation
open http://localhost:8000/docs

# Monitoring Dashboard
open http://localhost:9090
```

### **Development Workflow**
```bash
# Start development
git checkout master

# Make changes and test
# ... development work ...

# Promote to production (only when working!)
./scripts/enforce_methodology.sh promote
```

### **System Management**
```bash
# Check system status
./scripts/enforce_methodology.sh status

# Run methodology checks
./scripts/enforce_methodology.sh check

# Emergency rollback
./scripts/enforce_methodology.sh rollback
```

---

## 🏗️ **Architecture**

### **Frontend (React + TypeScript)**
- **Location**: `web/`
- **Port**: 80 (production), 3001 (development)
- **Features**: Dashboard, Articles, Storylines, RSS Feeds, Intelligence Hub

### **Backend (FastAPI + Python)**
- **Location**: `api/`
- **Port**: 8000
- **Features**: REST API, ML pipelines, RSS processing, Database management

### **Database (PostgreSQL)**
- **Location**: Docker container
- **Port**: 5432
- **Features**: Articles, Storylines, RSS Feeds, User data

### **Cache (Redis)**
- **Location**: Docker container
- **Port**: 6379
- **Features**: Session storage, Data caching, Pipeline state

### **Monitoring (Prometheus)**
- **Location**: Docker container
- **Port**: 9090
- **Features**: System metrics, Performance monitoring, Health checks

---

## 🔧 **Development Environment**

### **Prerequisites**
- Docker and Docker Compose
- Node.js 16+ (for frontend development)
- Python 3.9+ (for backend development)
- Git

### **Environment Setup**
```bash
# Clone repository
git clone <repository-url>
cd news-intelligence-system

# Start production system
docker-compose up -d

# Verify system health
./scripts/enforce_methodology.sh status
```

---

## 📋 **Key Features**

### **News Processing**
- RSS feed aggregation and monitoring
- Article content extraction and analysis
- Duplicate detection and deduplication
- Quality scoring and filtering

### **Intelligence Analysis**
- AI-powered storyline creation
- Sentiment analysis and trend detection
- Entity extraction and relationship mapping
- Multi-perspective analysis

### **User Interface**
- Responsive web dashboard
- Real-time data visualization
- Interactive storyline exploration
- Advanced search and filtering

### **Monitoring & Analytics**
- Pipeline performance tracking
- System health monitoring
- Error logging and alerting
- Usage analytics and reporting

---

## 🚨 **Critical Rules**

### **Development Methodology**
1. **Always develop on master branch**
2. **Test thoroughly before promoting to production**
3. **Never run development and production simultaneously**
4. **Use root cause analysis for persistent problems**
5. **Check configuration and security before code changes**

### **Environment Separation**
- **Production**: Live system with real data (ports 80, 8000, 5432)
- **Development**: Local development with mock data (ports 3001, 8001, 5433)
- **Never mix**: Development and production environments

### **Git Workflow**
- **Master**: Active development and testing
- **Production**: Stable, working version only
- **Promotion**: Only when code is tested and working
- **Rollback**: Always available for emergency recovery

---

## 📊 **System Status**

### **Production Environment** ✅ **OPERATIONAL**
- **Frontend**: React web interface deployed and accessible
- **API**: FastAPI backend running with all endpoints working
- **Database**: PostgreSQL with complete schema and real data
- **Cache**: Redis operational for session and data caching
- **Monitoring**: Prometheus collecting system metrics

### **Development Environment** 🔧 **READY**
- **Git**: Master branch ready for new development
- **Ports**: All development ports available (3001, 8001, 5433)
- **Tools**: Development tools and scripts ready
- **Documentation**: Complete methodology documentation

---

## 🎯 **Next Steps**

1. **✅ Production system operational** with frontend deployed
2. **✅ Development methodology established** and documented
3. **✅ Enforcement tools created** for methodology compliance
4. **✅ Git workflow implemented** with production branch
5. **🔄 Ready for new development** on master branch

---

## 📞 **Support**

### **Documentation**
- All documentation is in the root directory
- Methodology enforcement script: `./scripts/enforce_methodology.sh`
- System status check: `./scripts/enforce_methodology.sh status`

### **Troubleshooting**
- Check system status: `./scripts/enforce_methodology.sh status`
- Run methodology checks: `./scripts/enforce_methodology.sh check`
- View container logs: `docker logs <container-name>`
- Emergency rollback: `./scripts/enforce_methodology.sh rollback`

---

*Last Updated: $(date)*
*Status: Production Ready*
*Version: 3.0.1*
*Methodology: Established and Enforced*