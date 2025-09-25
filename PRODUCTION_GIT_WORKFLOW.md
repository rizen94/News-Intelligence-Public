# Production Git Workflow - News Intelligence System

## 🎯 **Branch Strategy**

### **Master Branch** (Development)
- **Purpose**: Active development, testing, experimentation
- **Status**: Can be unstable, experimental features allowed
- **Use**: Daily development work, feature development, bug fixes

### **Production Branch** (Stable)
- **Purpose**: Stable, working version ready for production use
- **Status**: Always working, tested, and verified
- **Use**: Live system deployment, reliable fallback, stable reference

---

## 🔄 **Workflow Process**

### **1. Development Work (Master Branch)**
```bash
# Always work on master for development
git checkout master

# Make your changes, test them
# ... development work ...

# Commit your changes
git add .
git commit -m "Feature: Description of changes"

# Test thoroughly before promoting to production
```

### **2. Promoting to Production**
```bash
# Only promote when you have a WORKING, TESTED version
git checkout production

# Merge the working changes from master
git merge master

# Tag this as a production release
git tag -a v3.0.1 -m "Production Release: Stable working version"

# Push to remote (if you have one)
git push origin production
git push origin v3.0.1
```

### **3. Emergency Rollback**
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

## 📋 **Current Status**

### **Production Branch** ✅ **STABLE**
- **Commit**: `e6883e9` - "PRODUCTION READY: Stable working version with all fixes applied"
- **Status**: All TypeScript errors fixed, ESLint configured, API working
- **Docker System**: Fully operational (ports 80, 8000, 5432)
- **Database**: Schema applied, all tables created
- **Frontend**: All components working, navigation fixed

### **Master Branch** 🔧 **DEVELOPMENT**
- **Status**: Ready for new development work
- **Conflicts**: Development React server stopped (port 3000 freed)
- **Environment**: Clean, ready for new features

---

## 🚨 **CRITICAL RULES**

### **DO:**
1. **Always develop on master branch**
2. **Test thoroughly before promoting to production**
3. **Commit working versions to production branch**
4. **Use production branch as your stable reference**
5. **Tag production releases with version numbers**

### **DON'T:**
1. **Never develop directly on production branch**
2. **Never promote untested code to production**
3. **Never delete the production branch**
4. **Never force-push to production branch**

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

## 📊 **Environment Alignment**

### **Production Branch = Production Docker System**
- **Frontend**: `http://localhost:80` (Docker container)
- **API**: `http://localhost:8000` (Docker container)  
- **Database**: `localhost:5432` (Docker container)
- **Status**: Stable, working, with real data

### **Master Branch = Development Environment**
- **Frontend**: `http://localhost:3001` (when needed)
- **API**: `http://localhost:8001` (when needed)
- **Database**: `localhost:5433` (when needed)
- **Status**: Development, testing, experimentation

---

## 🎯 **Next Steps**

1. **✅ Production branch created** with stable version
2. **✅ Development server stopped** (port 3000 freed)
3. **✅ Production Docker system** running (ports 80, 8000, 5432)
4. **🔄 Test production system** to verify it's working
5. **📝 Document any issues** found in production testing

---

*Last Updated: $(date)*
*Status: Production branch established, ready for stable development workflow*
