
## Full Inventory of Decision Points for `storyline_article_suggestions` Data Loss

### 1. Kill-Switch: `.env` Line 64

```
STORYLINE_AUTOMATION_AUTO_ATTACH=0
```

**Decision flow:**
- `assembly_link_funnel.py:35` → `automation_auto_attach_enabled()` returns `env_bool("STORYLINE_AUTOMATION_AUTO_ATTACH", False)`
- With `.env` value of `0`, this returns **False** (kill-switch ON)
- When kill-switch is ON, the only path is `_store_suggestions()` (not `_auto_add_articles()`)

### 2. Decision Tree in `process_discoveries()` (storyline_automation_service.py)

```
Line 382: if automation_mode == "auto_approve":
    Line 384: from shared.assembly_link_funnel import automation_auto_attach_enabled
    Line 385: if not automation_auto_attach_enabled():  # True when AUTO_ATTACH=0
        _store_suggestions(...)   → INSERT with status='pending'
    else:
        _auto_add_articles(...)   → direct commit (requires AUTO_ATTACH=1)
else:
    _store_suggestions(...)       → INSERT with status='pending'
```

**Critical path:** Since AUTO_ATTACH=0 in `.env`, ALL storylines go through `_store_suggestions()`.

### 3. `_store_suggestions()` Behavior (line ~1256)

- Inserts each suggested article into `public.storyline_article_suggestions`
- `status = 'pending'` always (no automatic transition)
- `expires_at = NOW() + INTERVAL '7 days'` (TTL expiry)
- No function updates status from 'pending' → anything else
- **No worker/cron/endpoint processes pending items**

### 4. `_auto_add_articles()` Behavior (line ~1433)

- Only executed when `automation_auto_attach_enabled() == True`
- Scores articles via cosine similarity (`min_semantic_score = 0.80` from line 49)
- Applies `admit()` decision logic (with MembershipIntent.AUTOMATION)
- **Completely bypassed by kill-switch**

### 5. Current Database State (confirmed)

| Metric | Value |
|--------|-------|
| `emerging_storylines.emerging` | 3,223 active targets |
| `emerging_storylines.confirmed` | 712 completed items |
| `storyline_article_suggestions.pending` | ~996K+ items |
| Oldest pending | >30 days (past TTL) |
| Items >7 days old | ~615K+ (expired TTL) |

### 6. Missing Components (confirmed absent)

- **No purge/cleanup cron**: `DELETE FROM storyline_article_suggestions WHERE expires_at < NOW()` doesn't exist anywhere
- **No pending worker**: No script or endpoint processes `status='pending'` items
- **No manual `/approve` endpoint**: The `admit()` logic only exists in `_auto_add_articles()`, gated by AUTO_ATTACH flag
- **Dead references verified**: `items` and `pipeline_state` tables do NOT exist in public schema. They are orphaned names from earlier pipeline designs.
- **rss_feeds exists**: It's a valid table (used extensively for RSS feeds), not dead.

### 7. Cron Scripts Checked (none handle pending suggestions)

1. `cron_wikipedia_preseed.sh` — Wikipedia seeding only
2. `setup_log_archive_cron.sh` — Log archiving only
3. `setup_log_cleanup_cron.sh` — Cleanup only
4. `setup_rss_cron_with_health_check.sh` — RSS health checks only
5. `setup_diagnostics_cron.py` — Diagnostics only
6. `install_weekly_backup_cron.sh` — Backups only

### 8. Root Cause Summary

**The pipeline works correctly up to suggestion generation, but the auto-commit path is blocked by design and no manual worker was built.**

1. Kill-switch `STORYLINE_AUTOMATION_AUTO_ATTACH=0` → blocks `_auto_add_articles()` (line 385)
2. All items go to `_store_suggestions()` → inserted with `status='pending'`
3. No cron, worker, or endpoint processes pending items
4. Items accumulate: ~996K suggestions sitting in 'pending' indefinitely
5. TTL expires after 7 days → items become stale/irrelevant data (615K+ already expired)

### 9. Recommendations

#### Immediate (low effort, high impact):
1. **Enable AUTO_ATTACH**: Set `STORYLINE_AUTOMATION_AUTO_ATTACH=1` in `.env` and restart service
   - This re-enables the `_auto_add_articles()` path
   - New items will be auto-committed; existing pending items won't be processed (separate concern)
2. **Add TTL cleanup cron**: `DELETE FROM storyline_article_suggestions WHERE expires_at < NOW()`

#### Medium term:
1. **Build pending-items worker**: Either a cron script that calls `_store_suggestions()` + processes results, or an endpoint that triggers approval for pending items in batches
2. **Remove dead references**: Code referencing `items` and `pipeline_state` tables should be cleaned up or updated to use existing tables
3. **Add status distribution monitoring**: Track % of pending/processing/completed over time

#### Long term:
1. **Consider removing the kill-switch entirely** if auto-approval is the desired default behavior
2. **Implement a two-stage approval system** (auto-approve with grace period → manual review fallback)
3. **Document pipeline states explicitly**: `pending` → `processing` → `approved`/`rejected`/`expired`
