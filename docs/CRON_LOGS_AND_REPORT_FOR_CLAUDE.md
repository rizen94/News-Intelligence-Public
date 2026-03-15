# News Intelligence — Cron, logs, and activity report (for Claude)

Single reference: **doc list to pass to Claude**, cron jobs (quoted paths), log locations, last-24h report, and placeholders to paste results.

---

## 0. Docs to pass to Claude (in order)

Pass these in order so Claude gets context first. Then paste the last-24h report and log excerpts into sections 4–5 below.

| # | Document | Why |
|---|----------|-----|
| 1 | **AGENTS.md** (project root) | Terminology, entry points, key flows. |
| 2 | **PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md** | What’s built, DB→API→web, gaps. |
| 3 | **ARCHITECTURE_AND_OPERATIONS.md** | Architecture, ops, troubleshooting. |
| 4 | **AUTOMATION_AND_LAST_24H_ACTIVITY.md** | What runs (cron, coordinator, AutomationManager), where it’s recorded. |
| 5 | This doc | Cron, logs, report, and **paste areas** for report + logs. |
| 6 | **CLEANUP_PLAN.md**, **DATABASE_CONNECTION_AUDIT.md**, **TROUBLESHOOTING.md** | Cleanup tasks, DB fixes, common failures. |

Optional: FINANCE_TODO, V6_QUALITY_FIRST_TODO, CONTEXT_CENTRIC_UPGRADE_PLAN. **Light bundle:** 1 → 2 → 4 → this doc (with sections 4–5 filled).

---

## 1. Cron jobs (all paths quoted for "News Intelligence")

Project path contains a space; cron must use quoted paths or the command is split and fails (e.g. "News: not found").

### Install/update each set

From project root: `cd "/path/to/News Intelligence"` then:

| What | Script | When it runs |
|------|--------|---------------|
| RSS collection (health check) | `./scripts/setup_rss_cron_with_health_check.sh` | 6 AM, 6 PM |
| Morning data pipeline (RSS + entity + topic) | `./scripts/setup_morning_data_pipeline.sh` | 4 AM, 5 AM, 6 AM |
| Log archive to NAS | `./scripts/setup_log_archive_cron.sh` | 6 AM, 6 PM |
| Old pipeline_trace.log cleanup | `./scripts/setup_log_cleanup_cron.sh` | 2 AM daily |

### Corrected crontab block (copy-paste reference)

Replace existing News Intelligence entries with the following (paths quoted). Your `@reboot` and other non–News Intelligence lines stay as-is.

```cron
# News Intelligence - delete old pipeline_trace.log (7+ days)
0 2 * * * find "/home/pete/Documents/projects/Projects/News Intelligence/logs" -name 'pipeline_trace.log*' -mtime +7 -delete

# News Intelligence Morning Data Pipeline - RSS + entity + topic extraction
0 4 * * * "/home/pete/Documents/projects/Projects/News Intelligence/scripts/morning_data_pipeline.sh"
0 5 * * * "/home/pete/Documents/projects/Projects/News Intelligence/scripts/morning_data_pipeline.sh"
0 6 * * * "/home/pete/Documents/projects/Projects/News Intelligence/scripts/morning_data_pipeline.sh"

# News Intelligence Log Archive - 2x daily (6 AM, 6 PM)
0 6 * * * cd "/home/pete/Documents/projects/Projects/News Intelligence" && "/home/pete/Documents/projects/Projects/News Intelligence/.venv/bin/python" scripts/log_archive_to_nas.py >> "/home/pete/logs/news_intelligence/log_archive.log" 2>&1
0 18 * * * cd "/home/pete/Documents/projects/Projects/News Intelligence" && "/home/pete/Documents/projects/Projects/News Intelligence/.venv/bin/python" scripts/log_archive_to_nas.py >> "/home/pete/logs/news_intelligence/log_archive.log" 2>&1

# News Intelligence RSS Collection - Twice daily with API health check (6 AM and 6 PM)
0 6 * * * "/home/pete/Documents/projects/Projects/News Intelligence/scripts/rss_collection_with_health_check.sh" >> "/home/pete/logs/news_intelligence/rss_collection.log" 2>&1
0 18 * * * "/home/pete/Documents/projects/Projects/News Intelligence/scripts/rss_collection_with_health_check.sh" >> "/home/pete/logs/news_intelligence/rss_collection.log" 2>&1
```

To apply via scripts (recommended): run the four setup scripts above in order; they merge into existing crontab and remove old unquoted News Intelligence entries.

---

## 2. Log file locations

| Log | Path | Content |
|-----|------|--------|
| RSS collection (cron) | `~/logs/news_intelligence/rss_collection.log` or `$PROJECT/logs/rss_collection.log` | Health check + RSS run output |
| Morning pipeline | `~/logs/news_intelligence/morning_pipeline_YYYYMMDD.log` | RSS + entity + topic extraction per day |
| Log archive | `~/logs/news_intelligence/log_archive.log` | Log archive to NAS runs |
| API server | `$PROJECT/logs/api_server.log` (if file logging enabled) | API stdout/stderr |
| Pipeline traces | `$PROJECT/logs/pipeline_trace.log` | Pipeline trace output (if written) |

`$PROJECT` = `/home/pete/Documents/projects/Projects/News Intelligence`

View: `tail -f "/home/pete/logs/news_intelligence/rss_collection.log"` (adjust path as needed).

---

## 3. Last-24h activity report

Run from project root (no full project venv needed; uses `.venv-report` if present):

```bash
cd "/home/pete/Documents/projects/Projects/News Intelligence"
./scripts/run_last_24h_report.sh
```

First run creates `.venv-report` and installs `psycopg2-binary`. Report shows: articles per domain (24h), RSS fetch counts, pipeline_traces, system alerts, orchestrator state, and tail of cron RSS log. It also lists potential gaps (e.g. no pipeline_traces, no orchestrator runs).

---

## 4. Paste: Last-24h report output

Paste the full terminal output of `./scripts/run_last_24h_report.sh` here for Claude to interpret (what ran, what was collected, what was neglected).

```
[PASTE REPORT OUTPUT BELOW]






```

---

## 5. Paste: Relevant log excerpts

Paste any relevant log excerpts (errors, last runs, or “no activity” lines) for Claude to correlate with the report.

**RSS collection log (last 30–50 lines):**
```
[PASTE tail of rss_collection.log]





```

**Morning pipeline log (today or last run):**
```
[PASTE excerpt of morning_pipeline_YYYYMMDD.log if needed]





```

**Other (API, log archive, etc.):**
```
[PASTE any other relevant log lines]





```

---

## 6. Summary for Claude

- **Cron:** All News Intelligence cron entries use **quoted** paths so the space in “News Intelligence” does not break execution. Use the setup scripts or the corrected crontab block above.
- **Logs:** Key logs are under `~/logs/news_intelligence/` and project `logs/`; paths are in the table in section 2.
- **Activity:** Run `./scripts/run_last_24h_report.sh` and paste the output and any log excerpts into sections 4 and 5 above, then pass this document to Claude for analysis (what ran, what was collected, what failed or was neglected).

**Prompt for Claude:** *“Using the attached docs and pasted last-24h report and logs: (1) Summarize how the system behaves—what runs, what gets collected, where it’s recorded. (2) List missing pieces or gaps. (3) Suggest a short prioritized list of next steps to harden visibility and close gaps.”*
