# Project Health and Cleanup Plan

## Date: 2025-01-XX
## Purpose: Comprehensive project health assessment and cleanup recommendations

---

## 📊 **CURRENT PROJECT HEALTH STATUS**

### ✅ **What's Healthy**

| Area | Status | Notes |
|------|--------|-------|
| **Code Quality** | ✅ Good | Coding standards followed, linting clean |
| **Documentation** | ✅ Good | Comprehensive, recently organized |
| **Architecture** | ✅ Good | Well-structured, domain-based |
| **Dependencies** | ✅ Stable | Requirements pinned, compatible versions |
| **Active Logs** | ✅ Good | Runtime logs in proper location |
| **Git Structure** | ✅ Good | Proper version control |

### ⚠️ **Areas Needing Cleanup**

| Area | Issue | Impact | Priority |
|------|-------|--------|----------|
| **Python Cache** | `__pycache__` directories | Minor clutter | Low |
| **Backup Files** | `*.backup` files in codebase | Confusion, clutter | Medium |
| **Duplicate Requirements** | `requirements-fixed.txt` vs `api/requirements.txt` | Maintenance burden | Medium |
| **Old Logs** | Logs in `logs/` directory >30 days | Disk space | Low |
| **Test Files** | Test files in root directory | Organization | Low |
| **Unused Scripts** | Old/unused scripts | Confusion | Low |

---

## 🧹 **CLEANUP RECOMMENDATIONS**

### **1. Python Cache Files** (Low Priority)

**Issue**: `__pycache__` directories scattered throughout codebase

**Impact**: 
- Minor clutter
- Can be regenerated
- Should be in `.gitignore` (likely already is)

**Action**:
```bash
# Remove Python cache files
find . -type d -name "__pycache__" ! -path "./archive/*" ! -path "./.git/*" ! -path "./node_modules/*" -exec rm -r {} + 2>/dev/null
find . -name "*.pyc" ! -path "./archive/*" ! -path "./.git/*" ! -path "./node_modules/*" -delete 2>/dev/null
```

**Recommendation**: Add to `.gitignore` if not already there, run cleanup script

---

### **2. Backup Files** (Medium Priority)

**Issue**: Multiple `*.backup` files in codebase

**Found**:
- `docker-compose.yml.backup`
- `api/main.py.backup`
- `api/routes.backup/`
- `api/domains/*/routes/*.backup_20251025_153237`
- `web/src/services/apiService.ts.backup`
- `web/src/pages/Articles/Articles.js.backup`
- `backups/` directory (legitimate backups)

**Impact**:
- Confusion about which files are active
- Clutter in codebase
- Potential for using wrong file

**Action**:
```bash
# Archive backup files (not in backups/ directory)
find . -name "*.backup" ! -path "./archive/*" ! -path "./backups/*" ! -path "./.git/*" -type f
find . -name "*.backup_*" ! -path "./archive/*" ! -path "./backups/*" ! -path "./.git/*" -type f
```

**Recommendation**: Move to `archive/backups/` or delete if no longer needed

---

### **3. Duplicate Requirements Files** (Medium Priority)

**Issue**: Two requirements files:
- `api/requirements.txt` (active)
- `requirements-fixed.txt` (duplicate?)

**Impact**:
- Confusion about which to use
- Maintenance burden (update both)
- Potential version drift

**Action**:
1. Compare files to see if identical
2. If identical: Remove `requirements-fixed.txt`
3. If different: Consolidate and remove duplicate
4. Update any scripts that reference `requirements-fixed.txt`

**Recommendation**: Consolidate to single `api/requirements.txt`

---

### **4. Old Log Files** (Low Priority)

**Issue**: Log files in `logs/` directory older than 30 days

**Impact**:
- Disk space usage
- Clutter
- Historical logs should be archived

**Action**:
```bash
# Archive old logs (>30 days)
find logs -name "*.log" -mtime +30 -exec mv {} archive/logs/historical/ \;
```

**Recommendation**: Set up log rotation or periodic archiving

---

### **5. Test Files in Root** (Low Priority)

**Issue**: Test files in project root:
- `test_enhanced_timeline.py`
- `test_improved_summary.py`
- `debug_api_endpoints.py`

**Impact**:
- Organization
- Clutter

**Action**: Move to `tests/` directory

**Recommendation**: Organize test files into `tests/` directory

---

### **6. Unused/Old Scripts** (Low Priority)

**Issue**: Potentially unused scripts in `scripts/` and root

**Impact**:
- Confusion
- Maintenance burden

**Action**: Review and archive unused scripts

**Recommendation**: Document which scripts are active vs historical

---

### **7. Duplicate Configuration Files** (Low Priority)

**Issue**: Multiple configuration files:
- `docker-compose.yml`
- `docker-compose.yml.backup`
- `configs/` directory

**Impact**:
- Confusion about which config is active

**Action**: Archive backup configs, consolidate active configs

---

### **8. Documentation in Root** (Already Addressed)

**Status**: ✅ Already archived by archive script

---

## 🔧 **HEALTH CHECK RECOMMENDATIONS**

### **1. Dependency Health**

**Current Status**: ✅ Dependencies are pinned and compatible

**Recommendations**:
- [ ] Check for security vulnerabilities: `pip-audit` or `safety check`
- [ ] Review outdated packages (if any)
- [ ] Document why specific versions are pinned

### **2. Code Quality**

**Current Status**: ✅ Coding standards followed

**Recommendations**:
- [ ] Run full linting check: `flake8 api/`
- [ ] Check for unused imports
- [ ] Verify no dead code
- [ ] Run type checking (if using mypy)

### **3. Test Coverage**

**Current Status**: ⚠️ Test files exist, coverage unknown

**Recommendations**:
- [ ] Run test suite: `pytest tests/`
- [ ] Check test coverage: `pytest --cov=api tests/`
- [ ] Document test coverage percentage
- [ ] Identify gaps in test coverage

### **4. Security Audit**

**Current Status**: ⚠️ Not yet completed

**Recommendations**:
- [ ] Run `pip-audit` for Python dependencies
- [ ] Run `npm audit` for Node.js dependencies
- [ ] Review environment variables and secrets
- [ ] Check for hardcoded credentials
- [ ] Review SQL injection prevention
- [ ] Check CORS configuration

### **5. Performance Health**

**Current Status**: ✅ Performance optimizations in place

**Recommendations**:
- [ ] Review database query performance
- [ ] Check for N+1 query problems
- [ ] Review caching effectiveness
- [ ] Monitor API response times

### **6. Database Health**

**Current Status**: ✅ Schema complete, migrations working

**Recommendations**:
- [ ] Check for unused tables/columns
- [ ] Review index usage
- [ ] Check for missing indexes
- [ ] Review migration history

---

## 📋 **CLEANUP PRIORITY MATRIX**

| Task | Priority | Effort | Impact | Status |
|------|----------|--------|--------|--------|
| Remove Python cache | Low | 5 min | Low | ⚠️ Pending |
| Archive backup files | Medium | 15 min | Medium | ⚠️ Pending |
| Consolidate requirements | Medium | 10 min | Medium | ⚠️ Pending |
| Archive old logs | Low | 10 min | Low | ⚠️ Pending |
| Organize test files | Low | 10 min | Low | ⚠️ Pending |
| Security audit | High | 2-4 hours | High | ⚠️ Pending |
| Test coverage check | Medium | 1-2 hours | Medium | ⚠️ Pending |
| Dependency audit | Medium | 30 min | Medium | ⚠️ Pending |

---

## 🚀 **RECOMMENDED CLEANUP SCRIPT**

### **Quick Cleanup (5-10 minutes)**

```bash
#!/bin/bash
# Quick Project Cleanup Script

cd "$(dirname "$0")/.."

echo "🧹 Starting quick cleanup..."

# 1. Remove Python cache
echo "Removing Python cache files..."
find . -type d -name "__pycache__" ! -path "./archive/*" ! -path "./.git/*" ! -path "./node_modules/*" -exec rm -r {} + 2>/dev/null
find . -name "*.pyc" ! -path "./archive/*" ! -path "./.git/*" ! -path "./node_modules/*" -delete 2>/dev/null
echo "✅ Python cache cleaned"

# 2. Archive backup files
echo "Archiving backup files..."
mkdir -p archive/backups/codebase
find . -name "*.backup" ! -path "./archive/*" ! -path "./backups/*" ! -path "./.git/*" -type f -exec mv {} archive/backups/codebase/ \; 2>/dev/null
find . -name "*.backup_*" ! -path "./archive/*" ! -path "./backups/*" ! -path "./.git/*" -type f -exec mv {} archive/backups/codebase/ \; 2>/dev/null
echo "✅ Backup files archived"

# 3. Consolidate requirements
if [ -f "requirements-fixed.txt" ] && [ -f "api/requirements.txt" ]; then
    if diff -q requirements-fixed.txt api/requirements.txt > /dev/null 2>&1; then
        echo "Removing duplicate requirements-fixed.txt..."
        mv requirements-fixed.txt archive/backups/codebase/ 2>/dev/null
        echo "✅ Duplicate requirements removed"
    else
        echo "⚠️  Requirements files differ - manual review needed"
    fi
fi

# 4. Archive old logs (>30 days)
echo "Archiving old logs..."
mkdir -p archive/logs/historical
find logs -name "*.log" -mtime +30 -exec mv {} archive/logs/historical/ \; 2>/dev/null
echo "✅ Old logs archived"

# 5. Organize test files
echo "Organizing test files..."
mkdir -p tests/root-tests
for file in test_*.py debug_*.py; do
    if [ -f "$file" ]; then
        mv "$file" tests/root-tests/ 2>/dev/null
    fi
done
echo "✅ Test files organized"

echo ""
echo "✅ Quick cleanup complete!"
```

---

## 🔍 **DETAILED HEALTH CHECKS**

### **1. Dependency Security**

**Check Python Dependencies**:
```bash
# Install pip-audit if needed
pip install pip-audit

# Check for vulnerabilities
pip-audit -r api/requirements.txt
```

**Check Node.js Dependencies**:
```bash
cd web
npm audit
npm outdated
```

### **2. Code Quality**

**Run Linting**:
```bash
# Python
flake8 api/ --exclude=archive,node_modules,__pycache__

# JavaScript/TypeScript
cd web
npm run lint
```

**Check for Unused Imports**:
```bash
# Python (using autoflake)
pip install autoflake
autoflake --check --recursive api/

# JavaScript/TypeScript (using ESLint)
cd web
npm run lint
```

### **3. Test Coverage**

**Run Tests**:
```bash
# Python tests
pytest tests/ -v --cov=api --cov-report=html

# Frontend tests (if configured)
cd web
npm test
```

### **4. Database Health**

**Check Database**:
```bash
# Connect to database and check:
# - Unused tables
# - Missing indexes
# - Orphaned records
# - Migration status
```

---

## 📊 **CLEANUP IMPACT ASSESSMENT**

### **Low Risk Cleanup** (Safe to Do)
- ✅ Remove Python cache files
- ✅ Archive backup files
- ✅ Archive old logs
- ✅ Organize test files
- ✅ Remove duplicate requirements (if identical)

### **Medium Risk Cleanup** (Review First)
- ⚠️ Remove unused scripts (verify not needed)
- ⚠️ Consolidate config files (verify no dependencies)
- ⚠️ Archive old test files (verify not needed)

### **High Risk** (Requires Careful Review)
- ❌ Remove any code files (verify not used)
- ❌ Change dependency versions (test thoroughly)
- ❌ Modify database schema (backup first)

---

## ✅ **RECOMMENDED ACTION PLAN**

### **Phase 1: Quick Wins** (15-30 minutes)

1. **Remove Python Cache** (5 min)
   - Safe, can regenerate
   - Reduces clutter

2. **Archive Backup Files** (10 min)
   - Move to archive
   - Reduces confusion

3. **Consolidate Requirements** (10 min)
   - Remove duplicate
   - Simplify maintenance

### **Phase 2: Organization** (30-60 minutes)

4. **Archive Old Logs** (10 min)
   - Move logs >30 days old
   - Free up disk space

5. **Organize Test Files** (10 min)
   - Move to tests/ directory
   - Better organization

6. **Review Unused Scripts** (30 min)
   - Document active vs historical
   - Archive unused ones

### **Phase 3: Health Checks** (2-4 hours)

7. **Security Audit** (2 hours)
   - Dependency vulnerabilities
   - Code security review

8. **Test Coverage** (1-2 hours)
   - Run test suite
   - Document coverage

9. **Code Quality** (1 hour)
   - Full linting
   - Unused imports
   - Dead code review

---

## 🎯 **SUMMARY**

### **Immediate Actions** (Do Now)
1. ✅ Remove Python cache files
2. ✅ Archive backup files
3. ✅ Consolidate requirements files

### **Short Term** (This Week)
4. Archive old logs
5. Organize test files
6. Security audit

### **Ongoing** (Regular Maintenance)
7. Test coverage monitoring
8. Dependency updates
9. Code quality checks

---

*Plan created: 2025-01-XX*
*Ready for implementation*

