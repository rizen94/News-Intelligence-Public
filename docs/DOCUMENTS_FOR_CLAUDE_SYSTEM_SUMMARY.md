# Documents to pass to Claude for system summary and missing pieces

Pass these **in order** so Claude gets context before detail. After the list, paste **live outputs** (last-24h report, crontab, log excerpts) into the bundle doc or into `CRON_LOGS_AND_REPORT_FOR_CLAUDE.md`.

---

## 1. Core context (what the system is)

| # | Document | Why |
|---|----------|-----|
| 1 | **AGENTS.md** (project root) | Terminology, entry points, key flows, single source of truth. |
| 2 | **docs/PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md** | What’s built, DB→API→web, domains, E2E chains, known gaps. |
| 3 | **docs/ARCHITECTURE_AND_OPERATIONS.md** | Architecture, ops, troubleshooting. |

These three give Claude the “what and how” of News Intelligence.

---

## 2. Automation and behavior (what runs, what’s recorded)

| # | Document | Why |
|---|----------|-----|
| 4 | **docs/AUTOMATION_AND_LAST_24H_ACTIVITY.md** | What runs automatically (cron, OrchestratorCoordinator, AutomationManager), where it’s recorded, and what isn’t. |
| 5 | **docs/CRON_LOGS_AND_REPORT_FOR_CLAUDE.md** | Cron jobs (quoted paths), log locations, how to run the last-24h report, and **placeholders to paste** report + logs. |

Fill section 4 and 5 of `CRON_LOGS_AND_REPORT_FOR_CLAUDE.md` with the report output and log excerpts before passing it.

---

## 3. Gaps and development (missing pieces, cleanup, TODOs)

| # | Document | Why |
|---|----------|-----|
| 6 | **docs/CLEANUP_PLAN.md** | Post-development cleanup, remaining doc tasks, merge/rename. |
| 7 | **docs/DATABASE_CONNECTION_AUDIT.md** | DB single source of truth; what was fixed so “missing pieces” aren’t duplicate DB config. |
| 8 | **docs/TROUBLESHOOTING.md** | Common failures (DB, health degraded, 503, log errors) so Claude can tie behavior to known issues. |

Optional if you care about a specific area:

- **docs/FINANCE_TODO.md** — Finance domain remaining work.
- **docs/V6_QUALITY_FIRST_TODO.md** — v6 quality-first priorities.
- **docs/CONTEXT_CENTRIC_UPGRADE_PLAN.md** — Context-centric / entity work.

---

## 4. Live data to paste (so Claude sees actual behavior)

Run these and paste the results into `CRON_LOGS_AND_REPORT_FOR_CLAUDE.md` (sections 4 and 5) or into a single “Live snapshot” section at the end of this doc:

1. **Last-24h report**  
   `./scripts/run_last_24h_report.sh`  
   → Paste full output (articles per domain, RSS fetch counts, pipeline_traces, orchestrator state, gaps).

2. **Crontab**  
   `crontab -l`  
   → Paste so Claude sees what’s actually scheduled and that paths are quoted.

3. **Log excerpts (if something failed or looks wrong)**  
   - Last 30–50 lines of `~/logs/news_intelligence/rss_collection.log`  
   - Last 30–50 lines of `~/logs/news_intelligence/morning_pipeline_YYYYMMDD.log` (today)  
   - Any API or pipeline errors from `logs/api_server.log` or stdout.

---

## 5. Minimal “light” bundle (if context limit is tight)

If you can’t pass everything, use this order:

1. **AGENTS.md**
2. **docs/PROJECT_SCOPE_AND_DEVELOPMENT_STATUS.md**
3. **docs/AUTOMATION_AND_LAST_24H_ACTIVITY.md**
4. **docs/CRON_LOGS_AND_REPORT_FOR_CLAUDE.md** (with report + crontab + log excerpts pasted in)

That’s enough for a solid system summary and to flag missing or broken automation; add ARCHITECTURE_AND_OPERATIONS and TROUBLESHOOTING if Claude needs to tie behavior to ops or known errors.

---

## 6. Prompt you can give Claude

After attaching the docs and pasted outputs, you can say:

*“Using the attached docs and the pasted last-24h report, crontab, and log excerpts: (1) Summarize how the News Intelligence system behaves in production—what runs automatically, what gets collected, and where it’s recorded. (2) List any missing pieces or gaps for development—e.g. automation that isn’t recorded, cron that might be broken, or features that are only partially connected. (3) Suggest a short prioritized list of next steps to harden behavior visibility and close the main gaps.”*
