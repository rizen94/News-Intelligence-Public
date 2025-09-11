# 🔍 News Intelligence System - Versioning Audit and Fix Plan

## **Current Versioning Issues Identified**

### **🚨 Critical Versioning Inconsistencies**

1. **Multiple Version Numbers in Use:**
   - v3.0 (in some files)
   - v3.1.0 (in most files)
   - v3.3.0 (in changelog and release files)

2. **Inconsistent Version References:**
   - API files: Mix of v3.0 and v3.1.0
   - Documentation: v3.1.0 and v3.3.0
   - Changelog: v3.3.0
   - Release files: v3.3.0

3. **File Structure Issues:**
   - `docs/v3.1.0/` directory exists but system is v3.0
   - `CHANGELOG_v3.3.0.md` but system is v3.0
   - `V3.3.0_RELEASE_SUMMARY.md` but system is v3.0

## **🎯 Standardization Plan**

### **Target Version: v3.0 (Current Working Version)**

All files should reference **v3.0** as the current working version.

## **📋 Files Requiring Version Updates**

### **1. Core System Files**
- [ ] `api/database/connection.py` - Change v3.1.0 → v3.0
- [ ] `api/routes/articles.py` - Change v3.1.0 → v3.0
- [ ] `api/routes/storylines.py` - Change v3.1.0 → v3.0
- [ ] `api/routes/rag_enhancement.py` - Change v3.1.0 → v3.0
- [ ] `api/routes/timeline.py` - Already v3.0 ✅
- [ ] `api/routes/intelligence.py` - Already v3.0 ✅

### **2. Documentation Files**
- [ ] `API_ANALYSIS_REPORT.md` - Change v3.1.0 → v3.0
- [ ] `api_audit.py` - Change v3.1.0 → v3.0
- [ ] `CHANGELOG_v3.3.0.md` - Rename to `CHANGELOG_v3.0.md`
- [ ] `V3.3.0_RELEASE_SUMMARY.md` - Rename to `V3.0_RELEASE_SUMMARY.md`

### **3. Directory Structure**
- [ ] `docs/v3.1.0/` - Rename to `docs/v3.0/`
- [ ] Update all files in `docs/v3.1.0/` to reference v3.0

### **4. Startup Scripts**
- [ ] `start.sh` - Already updated to v3.0 ✅

## **🔄 Renaming Plan**

### **Phase 1: Rename Files**
1. `CHANGELOG_v3.3.0.md` → `CHANGELOG_v3.0.md`
2. `V3.3.0_RELEASE_SUMMARY.md` → `V3.0_RELEASE_SUMMARY.md`
3. `docs/v3.1.0/` → `docs/v3.0/`

### **Phase 2: Update Content**
1. Update all version references to v3.0
2. Update file headers and comments
3. Update API documentation
4. Update changelog entries

### **Phase 3: Cleanup**
1. Remove any orphaned v3.1.0 or v3.3.0 references
2. Update README files
3. Update deployment scripts

## **📊 Impact Assessment**

### **Files Affected: 15+ files**
### **Directories Affected: 2 directories**
### **Risk Level: LOW** (mostly cosmetic changes)

## **✅ Success Criteria**

1. All files reference v3.0 consistently
2. No orphaned version references
3. Directory structure matches version
4. Documentation is consistent
5. System maintains functionality

## **🚀 Implementation Order**

1. **Rename files and directories**
2. **Update file content**
3. **Update documentation**
4. **Verify system functionality**
5. **Update deployment scripts**

---

**Status: READY FOR IMPLEMENTATION**
**Priority: HIGH**
**Estimated Time: 30 minutes**
