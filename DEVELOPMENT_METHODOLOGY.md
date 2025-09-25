# News Intelligence System - Development Methodology

## 🎯 **Core Principles**

### **1. Environment Separation**
- **DEVELOPMENT**: Local development with hot-reload, debugging, mock data
- **PRODUCTION**: Live system with real data, optimized performance, monitoring
- **NEVER**: Mix development and production environments

### **2. Git Branch Strategy**
- **Master Branch**: Active development, testing, experimentation
- **Production Branch**: Stable, working version ready for production use
- **Rule**: Only promote tested, working code to production

### **3. Root Cause Analysis**
- **Always**: Identify underlying system issues before applying fixes
- **Never**: Apply quick fixes without understanding the problem
- **Focus**: Configuration, security, and architecture before code changes

---

## 🏗️ **Environment Management**

### **Production Environment** ✅ **ACTIVE**
```bash
# Services
Frontend: http://localhost:80 (Docker container)
API: http://localhost:8000 (Docker container)
Database: localhost:5432 (Docker container)
Cache: localhost:6379 (Docker container)
Monitoring: localhost:9090 (Docker container)

# Status: Fully operational with real data
# Purpose: Live system for actual use
```

### **Development Environment** 🔧 **READY**
```bash
# Services (when needed)
Frontend: http://localhost:3001 (React dev server)
API: http://localhost:8001 (Development API)
Database: localhost:5433 (Development database)

# Status: Clean, ready for new features
# Purpose: Code development, debugging, component testing
```

---

## 🔄 **Git Workflow**

### **Development Process**
```bash
# 1. Start development work
git checkout master

# 2. Make changes and test thoroughly
# ... development work ...

# 3. Commit working changes
git add .
git commit -m "Feature: Description of changes"

# 4. Test thoroughly before promoting
```

### **Production Promotion**
```bash
# 1. Only promote when you have a WORKING, TESTED version
git checkout production

# 2. Merge the working changes from master
git merge master

# 3. Tag this as a production release
git tag -a v3.0.2 -m "Production Release: Stable working version"

# 4. Push to remote (if you have one)
git push origin production
git push origin v3.0.2
```

### **Emergency Rollback**
```bash
# If something breaks, rollback to last known good production version
git checkout production
git log --oneline  # Find the last good commit
git reset --hard <last-good-commit-hash>

# Or rollback master to match production
git checkout master
git reset --hard production
```

---

## 🚨 **Critical Rules**

### **DO:**
1. **Always develop on master branch**
2. **Test thoroughly before promoting to production**
3. **Commit working versions to production branch**
4. **Use production branch as your stable reference**
5. **Tag production releases with version numbers**
6. **Check high-level issues (configuration, security) before code changes**
7. **Perform root cause analysis for persistent problems**

### **DON'T:**
1. **Never develop directly on production branch**
2. **Never promote untested code to production**
3. **Never delete the production branch**
4. **Never force-push to production branch**
5. **Never run development and production simultaneously**
6. **Never apply quick fixes without understanding the problem**

---

## 🔧 **Quick Commands**

### **Start Development**
```bash
git checkout master
# Make your changes
```

### **Promote to Production**
```bash
git checkout production
git merge master
git tag -a v3.0.2 -m "Production Release: New feature"
```

### **Emergency Rollback**
```bash
git checkout production
git reset --hard HEAD~1  # Go back one commit
```

### **Check Status**
```bash
git branch -v  # See all branches and their latest commits
git log --oneline -5  # See last 5 commits
```

---

## 📊 **Quality Assurance**

### **Before Production Promotion**
- [ ] All tests pass
- [ ] No compilation errors
- [ ] No ESLint errors
- [ ] Frontend builds successfully
- [ ] API endpoints respond correctly
- [ ] Database schema is up to date
- [ ] All navigation links work
- [ ] Real data displays correctly

### **Production Verification**
- [ ] Frontend accessible at http://localhost:80
- [ ] API accessible at http://localhost:8000
- [ ] Database healthy and responsive
- [ ] All Docker containers running
- [ ] No port conflicts
- [ ] All services communicating correctly

---

## 🎯 **Current Status**

### **Production Branch** ✅ **STABLE**
- **Commit**: `9df10e0` - "PRODUCTION DEPLOYMENT: Frontend built and deployed successfully"
- **Tag**: `v3.0.1` - "Production Release v3.0.1: Complete working system with frontend deployed"
- **Status**: All TypeScript errors fixed, ESLint configured, API working
- **Docker System**: Fully operational (ports 80, 8000, 5432)
- **Database**: Schema applied, all tables created
- **Frontend**: All components working, navigation fixed

### **Master Branch** 🔧 **DEVELOPMENT**
- **Status**: Ready for new development work
- **Conflicts**: Development React server stopped (port 3000 freed)
- **Environment**: Clean, ready for new features

---

## 📋 **Enforcement Tools**

### **Pre-commit Hooks**
```bash
# Check for compilation errors
npm run build

# Check for linting errors
npm run lint

# Check for type errors
npm run type-check
```

### **Production Deployment Checklist**
```bash
# 1. Verify all services are healthy
curl http://localhost:8000/api/health/

# 2. Test frontend accessibility
curl http://localhost:80

# 3. Verify database connectivity
psql -h localhost -p 5432 -U newsapp -d news_intelligence -c "SELECT 1;"

# 4. Check Docker container status
docker ps --format "table {{.Names}}\t{{.Status}}"
```

---

## 🚀 **Next Steps**

1. **✅ Production system operational** with frontend deployed
2. **✅ Git workflow established** with production branch
3. **✅ Environment separation** implemented
4. **✅ Documentation created** for methodology
5. **🔄 Ready for new development** on master branch

---

*Last Updated: $(date)*
*Status: Methodology established and documented*
*Version: 1.0*
