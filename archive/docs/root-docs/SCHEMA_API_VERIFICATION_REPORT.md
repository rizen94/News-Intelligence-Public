# Schema vs API Verification Report
**Date:** 2025-10-29  
**Purpose:** Verify v4 schema matches all API calls before legacy table cleanup

---

## 🔍 Executive Summary

**CRITICAL ISSUES FOUND:** Multiple API endpoints reference tables/columns that don't exist in v4 schema. **DO NOT proceed with table cleanup until these are fixed.**

---

## ✅ V4 Schema Tables (11 tables)

1. `analysis_results_v4`
2. `article_topics_v4`
3. `articles_v4`
4. `pipeline_traces_v4`
5. `rss_feeds_v4`
6. `storyline_articles_v4`
7. `storylines_v4`
8. `system_metrics_v4`
9. `topic_clusters_v4`
10. `user_preferences_v4`
11. `users_v4`

---

## ❌ CRITICAL ISSUES

### 1. Missing Columns in v4 Tables

#### `articles_v4` - Missing:
- ❌ **`summary`** - Referenced in storyline_management.py lines 321, 381, 506, 618
- ❌ **`quality_score`** - Referenced in news_aggregation.py line 336, intelligence_hub.py line 310
- ❌ **`sentiment_label`** - Referenced in content_analysis.py

#### `storylines_v4` - Missing:
- ❌ **`analysis_summary`** - Referenced in storyline_management.py lines 370, 496, 607, 691
- ❌ **`quality_score`** - Referenced in storyline_management.py line 692, intelligence_hub.py line 313
- ❌ **`article_count`** - Referenced in storyline_management.py line 408

#### `storyline_articles_v4` - Missing:
- ❌ **`relevance_score`** - Referenced in storyline_management.py line 284 (INSERT statement tries to use this)

---

### 2. Missing Tables (Referenced but Not in v4 Schema)

1. **`timeline_events`** 
   - Referenced in: `storyline_management.py` line 552
   - **Impact:** Timeline endpoint will fail
   - **Action Required:** Create table or remove endpoint

2. **`intelligence_insights`**
   - Referenced in: `intelligence_hub.py` lines 79, 303, 359
   - **Impact:** Intelligence insights endpoints will fail
   - **Action Required:** Create table or remove functionality

3. **`trend_predictions`**
   - Referenced in: `intelligence_hub.py` lines 190, 306, 409
   - **Impact:** Trend prediction endpoints will fail
   - **Action Required:** Create table or remove functionality

4. **`system_alerts`**
   - Referenced in: `system_monitoring.py` lines 178, 236, 279, 368, 373
   - **Impact:** System alerts endpoints will fail
   - **Action Required:** Create table or remove functionality

5. **`user_profiles`**
   - Referenced in: `user_management.py` (multiple references)
   - **Action Required:** Should use `users_v4` instead

6. **`article_topic_clusters`**
   - Referenced in: `intelligence_hub.py` lines 465, 541
   - **Action Required:** Should use `article_topics_v4` instead

---

### 3. Incorrect Table References

#### Using non-v4 table names:

1. **`storyline_articles`** (should be `storyline_articles_v4`)
   - Found in: `storyline_management.py` lines 383, 508
   - Found in: `intelligence_hub.py` line 299
   - **Fix:** Change to `storyline_articles_v4`

2. **`articles`** (should be `articles_v4`)
   - Found in: `system_monitoring.py` lines 344, 347, 362, 368, 395, 622
   - Found in: `content_analysis.py` line 397
   - Found in: `intelligence_hub.py` lines 466, 542
   - **Fix:** Change to `articles_v4`

3. **`article_topic_clusters`** (should be `article_topics_v4`)
   - Found in: `intelligence_hub.py` lines 465, 541
   - **Fix:** Change to `article_topics_v4`

---

## 📊 Data Loss Risk Assessment

### 🔴 HIGH RISK (Will Cause Errors Immediately)

1. **Missing `summary` column in `articles_v4`**
   - Multiple endpoints query this column
   - Will cause "column does not exist" errors

2. **Missing `timeline_events` table**
   - `/api/v4/storyline-management/storylines/{id}/timeline` endpoint will fail

3. **Missing `system_alerts` table**
   - Multiple monitoring endpoints will fail

4. **Incorrect `storyline_articles` references**
   - JOINs will fail if legacy table is dropped

### 🟡 MEDIUM RISK (Will Cause Errors in Specific Operations)

1. **Missing `analysis_summary` in `storylines_v4`**
   - Will fail when trying to read/write storyline analysis

2. **Missing `relevance_score` in `storyline_articles_v4`**
   - INSERT will fail when adding articles to storylines with relevance score

3. **Missing `quality_score` columns**
   - Analytics endpoints will fail when trying to calculate averages

### 🟢 LOW RISK (May cause minor issues)

1. **Missing `article_count` in `storylines_v4`**
   - Can be calculated dynamically, but inefficient

---

## 🔧 Required Fixes Before Cleanup

### Priority 1: Add Missing Columns

```sql
-- Add to articles_v4
ALTER TABLE articles_v4 
ADD COLUMN IF NOT EXISTS summary TEXT,
ADD COLUMN IF NOT EXISTS quality_score DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS sentiment_label VARCHAR(50);

-- Add to storylines_v4
ALTER TABLE storylines_v4 
ADD COLUMN IF NOT EXISTS analysis_summary TEXT,
ADD COLUMN IF NOT EXISTS quality_score DECIMAL(3,2),
ADD COLUMN IF NOT EXISTS article_count INTEGER DEFAULT 0;

-- Add to storyline_articles_v4
ALTER TABLE storyline_articles_v4 
ADD COLUMN IF NOT EXISTS relevance_score DECIMAL(3,2);
```

### Priority 2: Fix Table Name References

1. Replace `storyline_articles` → `storyline_articles_v4` in:
   - `storyline_management.py` lines 383, 508
   - `intelligence_hub.py` line 299

2. Replace `articles` → `articles_v4` in:
   - `system_monitoring.py` (multiple locations)
   - `content_analysis.py` line 397
   - `intelligence_hub.py` lines 466, 542

3. Replace `article_topic_clusters` → `article_topics_v4` in:
   - `intelligence_hub.py` lines 465, 541

4. Replace `user_profiles` → `users_v4` in:
   - `user_management.py` (all references)

### Priority 3: Handle Missing Tables

**Option A: Create Missing Tables (if functionality needed)**
- Create `timeline_events_v4`
- Create `intelligence_insights_v4`
- Create `trend_predictions_v4`
- Create `system_alerts_v4`

**Option B: Remove/Disable Functionality (if not needed)**
- Comment out endpoints that use missing tables
- Add TODO comments for future implementation

---

## ✅ Verification Checklist

Before proceeding with legacy table cleanup:

- [ ] Add missing columns to v4 tables
- [ ] Fix all table name references (storyline_articles → storyline_articles_v4, etc.)
- [ ] Decide on missing tables (create or remove functionality)
- [ ] Test all API endpoints after fixes
- [ ] Verify no "column does not exist" errors
- [ ] Verify no "table does not exist" errors
- [ ] Run full integration tests
- [ ] Backup database
- [ ] Document any removed functionality

---

## 📝 Notes

- Current database has **97 total tables** (86 legacy + 11 v4)
- All v4 tables are properly named with `_v4` suffix
- Main issues are:
  1. API code still references legacy table names
  2. API code expects columns that weren't migrated
  3. Some functionality references tables that don't exist in v4

**Recommendation:** Fix all Priority 1 and Priority 2 issues, then re-run this verification before proceeding with cleanup.


