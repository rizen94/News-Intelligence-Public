# Legacy Table Cleanup

## Situation
- **97 legacy tables** from old schema
- **11 v4 tables** (current, working)
- Drops are slow due to network latency (NAS storage)

## Solution Created

### Script 1: `scripts/rename_legacy_fast.py`
**Purpose:** Quickly rename all legacy tables to `archived_` prefix
**Time:** ~5-10 seconds
**Method:** Uses ALTER TABLE RENAME (fast SQL operation)

**Usage:**
```bash
cd "/home/pete/Documents/projects/Projects/News Intelligence"
python3 scripts/rename_legacy_fast.py
```

This will:
- Rename all 97 legacy tables to `archived_tablename`
- Takes seconds instead of minutes
- Immediately removes them from queries
- Keeps data intact

### Script 2: `scripts/slow_drop_archived.sh`
**Purpose:** Slowly drop archived tables in background over time
**Time:** Drop 5 tables every 5 minutes
**Method:** Batch processing to avoid network issues

**Usage:**
```bash
cd "/home/pete/Documents/projects/Projects/News Intelligence"

# Run in background
nohup bash scripts/slow_drop_archived.sh > /dev/null 2>&1 &

# Check progress
tail -f logs/slow_drop.log

# Stop it
pkill -f slow_drop_archived.sh
```

This will:
- Drop 5 archived tables
- Wait 5 minutes
- Repeat until all tables are dropped
- Logs progress to `logs/slow_drop.log`

## Why This Approach?

1. **Immediate relief:** Renaming gets them out of the way instantly
2. **No downtime:** Background drops don't block operations
3. **NAS friendly:** Small batches avoid network saturation
4. **Safe:** Can be stopped/restarted at any time

## Current Status

Your data is SAFE:
- ✅ 1,312 articles in `articles_v4`
- ✅ 52 RSS feeds in `rss_feeds_v4`
- ✅ 1 storyline in `storylines_v4`
- ✅ System fully operational

The 97 legacy tables are just taking up space but not interfering.

