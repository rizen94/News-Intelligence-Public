# Archive Criteria and Balance Guidelines

## Date: 2025-01-XX
## Purpose: Define clear criteria for what gets archived vs kept active

---

## 🎯 **ARCHIVING PHILOSOPHY**

### **Core Principle**
**Archive historical/completed work, keep active/current documentation**

The goal is to:
- ✅ Preserve all history (nothing deleted)
- ✅ Reduce clutter in active directories
- ✅ Make current documentation easy to find
- ✅ Maintain clear separation between active and historical

---

## 📋 **ARCHIVING CRITERIA**

### **1. Log Files**

#### **Archive If:**
- ✅ **Historical migration logs** - One-time migration operations
  - Example: `v4_migration*.log`
  - Criteria: Migration completed, log is historical record
  
- ✅ **One-time operation logs** - Logs from completed operations
  - Example: `ollama_download.log`
  - Criteria: Operation completed, log is historical record
  
- ✅ **Build logs** - Generated during build process
  - Example: `web/build.log`, `web/react_output.log`
  - Criteria: Can be regenerated, not needed for runtime
  
- ✅ **Old/inactive logs** - Not modified in last 7+ days
  - Example: `ml_processor.log` (if not actively used)
  - Criteria: No recent activity, historical record only

#### **Keep Active If:**
- ✅ **Runtime application logs** - Active service logs
  - Example: `api/logs/app.log`, `api/logs/pipeline_trace.log`
  - Criteria: Actively being written to, needed for debugging
  
- ✅ **Recent logs** - Modified in last 7 days
  - Criteria: Recent activity indicates active use
  
- ✅ **Error/debug logs** - Needed for troubleshooting
  - Criteria: May contain recent errors or debug info

**Balance**: Archive completed operations, keep active monitoring

---

### **2. Documentation Files**

#### **Archive If:**
- ✅ **Completion reports** - "Done" status documents
  - Pattern: `*_COMPLETE.md`, `*_COMPLETION.md`
  - Criteria: Work is finished, document is historical record
  - Examples:
    - `TOPIC_CLUSTERING_IMPLEMENTATION_COMPLETE.md`
    - `V4_PRODUCTION_DEPLOYMENT_COMPLETE.md`
    - `FRONTEND_FIX_APPLIED_REPORT.md`
  
- ✅ **Historical summaries** - Past phase/work summaries
  - Pattern: `*_SUMMARY.md` (historical)
  - Criteria: Summarizes completed work, not current status
  - Examples:
    - `PHASE1_IMPLEMENTATION_SUMMARY.md`
    - `PROJECT_CLEANUP_SUMMARY.md`
    - `COMPREHENSIVE_PROGRESS_SUMMARY.md`
  
- ✅ **Historical reports** - Past analysis/fix reports
  - Pattern: `*_REPORT.md`, `*_FIX_REPORT.md`
  - Criteria: Documents completed work, not ongoing issues
  - Examples:
    - `ISSUES_FIXED_REPORT.md` (historical fixes)
    - `HEALTH_CHECK_ANALYSIS_REPORT.md` (past analysis)
    - `SYSTEM_FIXES_VERIFICATION_REPORT.md` (completed fixes)
  
- ✅ **Production deployment reports** - Historical deployments
  - Location: `docs/production-reports/`
  - Criteria: Documents past deployments, not current state
  - Examples:
    - `PRODUCTION_DEPLOYMENT_REPORT.md`
    - `PRODUCTION_DEPLOYMENT_COMPLETE.md`
    - `PRODUCTION_CLEANUP_AND_REDEPLOYMENT_REPORT.md`
  
- ✅ **Analysis reports** - Historical analysis
  - Location: `docs/analysis-reports/`
  - Criteria: Past analysis, not current system state
  - Examples:
    - `COMPREHENSIVE_SYSTEM_ANALYSIS_REPORT.md`
    - `ARTICLES_PAGE_DEBUG.md` (if issue resolved)
    - `BROWSER_CACHING_ISSUE_ANALYSIS.md` (if issue resolved)
  
- ✅ **Historical architecture docs** - Past architecture analysis
  - Pattern: `V4_*_ANALYSIS.md` (historical)
  - Criteria: Analysis of past state, not current architecture
  - Examples:
    - `V4_CROSS_REFERENCE_ANALYSIS.md`
    - `V4_CRITICAL_GAP_ANALYSIS.md`
    - `V4_DOCUMENTATION_FIXES_SUMMARY.md`

#### **Keep Active If:**
- ✅ **Current system documentation** - Active reference docs
  - Examples:
    - `API_DOCUMENTATION.md` - Current API reference
    - `SYSTEM_STATUS.md` - Current system status
    - `TROUBLESHOOTING.md` - Current troubleshooting guide
    - `CODING_STYLE_GUIDE.md` - Current coding standards
  
- ✅ **Feature documentation** - Active feature docs
  - Examples:
    - `CONFIDENCE_BASED_TOPIC_CLUSTERING.md` - Current feature
    - `TOPIC_CLUSTERING_ITERATION_ANALYSIS.md` - Current analysis
    - `RSS_FEED_MANAGEMENT_SYSTEM.md` - Current system docs
  
- ✅ **Planning documents** - Future work
  - Examples:
    - `V4_IMPLEMENTATION_ROADMAP.md` - Future planning
    - `STABILITY_ASSESSMENT_AND_ACTION_PLAN.md` - Current plan
  
- ✅ **Current issue tracking** - Active issues
  - Examples:
    - `PENDING_ISSUES_REPORT.md` - Current issues (if recent)
    - `NON_CRITICAL_ISSUES_FIXED.md` - Recent fixes
  
- ✅ **Architecture standards** - Current standards
  - Examples:
    - `ARCHITECTURAL_STANDARDS.md` - Current standards
    - `V4_COMPLETE_ARCHITECTURE.md` - Current architecture

**Balance**: Archive completed work, keep active reference and planning

---

## ⚖️ **BALANCING FACTORS**

### **1. Time-Based Criteria**

| Age | Action | Reasoning |
|-----|--------|-----------|
| **< 7 days** | Keep Active | Recent = likely still relevant |
| **7-30 days** | Review | May be active or historical |
| **30-90 days** | Archive (if completed) | Likely historical if work is done |
| **> 90 days** | Archive | Almost certainly historical |

### **2. Status-Based Criteria**

| Status | Action | Reasoning |
|--------|--------|-----------|
| **"COMPLETE"** | Archive | Work is done, document is historical |
| **"PENDING"** | Keep Active | Work is ongoing |
| **"FIXED"** | Archive | Issue resolved, historical record |
| **"ACTIVE"** | Keep Active | Currently in use |
| **"PLANNING"** | Keep Active | Future work reference |

### **3. Content-Based Criteria**

| Content Type | Action | Reasoning |
|--------------|--------|-----------|
| **Historical Summary** | Archive | Past work summary |
| **Current Reference** | Keep Active | Active documentation |
| **Planning Document** | Keep Active | Future work reference |
| **Completed Fix** | Archive | Historical fix record |
| **Active Issue** | Keep Active | Current problem tracking |

### **4. Location-Based Criteria**

| Location | Action | Reasoning |
|----------|--------|-----------|
| **Root directory** | Review for archive | Often temporary/completion docs |
| **`docs/`** | Keep active | Main documentation location |
| **`docs/production-reports/`** | Archive | Historical deployment records |
| **`docs/analysis-reports/`** | Archive | Historical analysis |
| **`docs/consolidated/`** | Keep active | Organized reference docs |

---

## 🔍 **DECISION TREE**

```
Is the file/document:
│
├─ A log file?
│  ├─ Historical migration/one-time operation? → ARCHIVE
│  ├─ Build log (can regenerate)? → ARCHIVE
│  ├─ Not modified in 7+ days? → ARCHIVE
│  └─ Active runtime log? → KEEP ACTIVE
│
├─ A completion/summary report?
│  ├─ Work is finished? → ARCHIVE
│  └─ Work is ongoing? → KEEP ACTIVE
│
├─ A fix/issue report?
│  ├─ Issue resolved (historical)? → ARCHIVE
│  └─ Issue pending (current)? → KEEP ACTIVE
│
├─ A reference document?
│  ├─ Current system reference? → KEEP ACTIVE
│  ├─ Historical reference? → ARCHIVE
│  └─ Planning document? → KEEP ACTIVE
│
└─ An analysis document?
   ├─ Current system analysis? → KEEP ACTIVE
   └─ Historical analysis? → ARCHIVE
```

---

## 📊 **CURRENT SCRIPT BALANCE**

### **What the Script Archives**

#### **Logs** (Safe to Archive)
- ✅ Migration logs - Historical, one-time operations
- ✅ Build logs - Can regenerate
- ✅ Old logs - Not recently modified
- ⚠️ **Excludes**: Active logs in `api/logs/` (runtime logs)

#### **Documentation** (Historical Only)
- ✅ Production reports - Past deployments
- ✅ Analysis reports - Historical analysis
- ✅ Phase summaries - Completed phases
- ✅ Completion docs - Finished work
- ✅ Historical fixes - Resolved issues
- ⚠️ **Excludes**: Current docs, planning docs, reference docs

### **What the Script Preserves**

#### **Active Logs**
- ✅ `api/logs/*.log` - Runtime application logs
- ✅ Recent logs - Modified in last 7 days

#### **Active Documentation**
- ✅ Core documentation (`API_DOCUMENTATION.md`, etc.)
- ✅ Current feature docs
- ✅ Planning documents
- ✅ Current issue tracking
- ✅ Architecture standards

---

## ⚠️ **EDGE CASES & CONSIDERATIONS**

### **1. Recent Completion Reports**
**Question**: What if a completion report is very recent?

**Answer**: 
- If work just completed (< 7 days), consider keeping temporarily
- If work completed and verified, safe to archive
- **Script behavior**: Archives all completion reports (can be adjusted)

### **2. Active Issue Reports**
**Question**: What if `PENDING_ISSUES_REPORT.md` has current issues?

**Answer**:
- **Script behavior**: Keeps `PENDING_ISSUES_REPORT.md` active
- Archives `ISSUES_FIXED_REPORT.md` (historical fixes)
- Consolidates both into historical archive

### **3. Planning Documents**
**Question**: What about future planning docs?

**Answer**:
- **Script behavior**: Keeps planning docs active
- Examples: `V4_IMPLEMENTATION_ROADMAP.md`, `STABILITY_ASSESSMENT_AND_ACTION_PLAN.md`
- These are future work, not historical

### **4. Build Logs**
**Question**: Should build logs be archived?

**Answer**:
- **Yes**: Build logs can be regenerated
- They're not needed for runtime
- Historical build logs are rarely referenced
- **Script behavior**: Archives build logs

### **5. Active Service Logs**
**Question**: What about logs in `api/logs/`?

**Answer**:
- **Never archive**: These are actively being written to
- Needed for debugging and monitoring
- **Script behavior**: Explicitly excludes `api/logs/`

---

## 🎯 **RECOMMENDED ADJUSTMENTS**

### **Option 1: Conservative (Current Script)**
- Archives clearly historical files
- Preserves all active documentation
- Safe default, minimal risk

### **Option 2: More Aggressive**
- Archive completion reports older than 30 days
- Archive analysis reports older than 60 days
- More cleanup, slightly more risk

### **Option 3: Custom Criteria**
- Add date-based checks
- Add content analysis
- More sophisticated, requires more maintenance

---

## 📝 **SCRIPT MODIFICATIONS NEEDED?**

### **Current Script Strengths**
- ✅ Safe defaults (preserves active docs)
- ✅ Clear exclusions (active logs)
- ✅ Organized structure
- ✅ No deletion (only moves)

### **Potential Improvements**
1. **Date-based checks**: Only archive files older than X days
2. **Content analysis**: Check file content for "COMPLETE" vs "ACTIVE"
3. **User confirmation**: Ask before archiving each category
4. **Dry-run mode**: Show what would be archived without doing it

---

## ✅ **RECOMMENDATION**

**Current script balance is GOOD**:
- ✅ Archives clearly historical files
- ✅ Preserves active documentation
- ✅ Safe and conservative approach
- ✅ Can be run with confidence

**Optional enhancement**: Add a `--dry-run` flag to preview changes before executing.

---

*Criteria defined: 2025-01-XX*
*Ready for review and adjustment*

