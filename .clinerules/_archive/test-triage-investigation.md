# Test: Pipeline Pending Items Investigation

This is a longform review to exercise the new `.clinerules/workflow.md` rules and unified agent structure. Follow the workflow exactly — triage first, search before write, explain always, persist findings to vault.

## Goal

Collect database data from News Intelligence's `news_intel` DB and diagnose why too many items remain in **pending** state when they no longer need pipeline processing.

## Required Steps

### 1. Triage (explain first, then investigate)

- Check current pending item counts by domain and status
- Identify the table(s) involved: `items`, `pipeline_state`, `rss_feeds`, or wherever pending is tracked
- Pull sample rows of older pending items to understand their source/context

### 2. Search before acting (workflow rule #3)

- Use MemPalace semantic search to find any prior discussions of pending item debt or pipeline status issues
- Check if there are documented pipeline states, processing rules, or known conditions that should mark items as complete/processing/failed

### 3. Database investigation

- Query pending item counts broken down by: domain, age, source type, and last update timestamp
- Find the oldest pending items — what made them pending? Are they still relevant?
- Look at pipeline state tables to understand the lifecycle of items (pending → processing → complete/failed?)
- Check for items that were processed but left in pending due to missing status updates

### 4. Persist findings to Obsidian vault as we go

Follow **`ni-session-vault.md`** (vault MCP). Before each significant finding, **append to** `00_Inbox/handoffs/2026-10-28-pending-items-triage.md` (or job slug for today):
- What you found and why it matters
- SQL queries that produced results (with outputs)
- Patterns or anomalies noticed
- Hypotheses formed

Create the file if it doesn't exist; use `vault_append_note` for subsequent updates. Keep a running log, not just final results.

### 5. Deliver work (delivering work rule)

- Report **all** findings — do not stop at partial results
- State assumptions explicitly when database evidence is ambiguous
- Recommend concrete fixes: SQL patches, process changes, cron cleanup, or architectural changes
- Say exactly what you could not verify and why

### 6. Verification

- After identifying root causes, run targeted queries to confirm hypotheses
- Test proposed fixes on a small subset first before recommending broad application

## Expected Output

A complete investigation report in the vault note with:
1. Current state snapshot (counts, breakdowns)
2. Root cause analysis for each category of stuck pending items
3. Actionable recommendations ranked by impact vs effort
4. Verification queries for each finding
