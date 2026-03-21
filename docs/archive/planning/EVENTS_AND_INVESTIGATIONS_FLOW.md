# Events and Investigations: How They Relate to Contexts and Entities

## Summary

- **Contexts** (~6k) and **entities** (~7k) are populated by earlier phases (context_sync, entity extraction, entity_profile_build).
- **Events** are *derived* from contexts by the **event_tracking** phase: it groups contexts into real-world “tracked events” via LLM.
- **Investigations** are journalism-style dossiers generated from a tracked event (and its chronicles/contexts). They are stored in `intelligence.event_reports` and are created on demand or by the **investigation_report_refresh** phase (which only *refreshes* existing reports; until recently it did not create reports for *new* events).

So “new investigations” are determined by: (1) having **tracked_events** (from event_tracking), then (2) either requesting a report via the API or running the refresh job, which now also **creates initial reports** for events that don’t have one yet.

---

## Data flow

| Stage | Source | Output | Phase / service |
|--------|--------|--------|------------------|
| Contexts | Articles (per domain) | `intelligence.contexts` | **context_sync** (context_processor_service) |
| Entities | Articles + contexts | `intelligence.entity_*` tables | entity extraction, **entity_profile_build** |
| **Events** | **Contexts** (unlinked) | `intelligence.tracked_events`, `intelligence.event_chronicles` | **event_tracking** (event_tracking_service) |
| Investigations | Tracked event + chronicles + contexts | `intelligence.event_reports` | **investigation_report_refresh** + API `generate_tracked_event_report` |

---

## Why you might see many contexts/entities but few events

1. **Event tracking runs in batches**  
   Each run processes up to ~300 unlinked contexts (30 per LLM batch × 3 domains), every 15 minutes. With thousands of contexts, the backlog drains over multiple runs; use “Run phase now” for event_tracking to process more immediately.

2. **Only clusters of 2+ contexts become events**  
   The LLM groups contexts into events; a proposed event is only written if **at least two contexts** belong to it. Single-article “events” are never created.

3. **Event tracking may be off or slow**  
   Check `api/config/context_centric.yaml`: `tasks.event_tracking` should be `true`. Also check the Monitor phase timeline: when did **event_tracking** last run, and is it running regularly?

4. **Confirm events in the DB**  
   Run:
   - `SELECT COUNT(*) FROM intelligence.tracked_events;`
   - `SELECT COUNT(*) FROM intelligence.event_chronicles;`
   If these are 0 or low, event_tracking either hasn’t run much or the LLM is returning few/empty groupings.

---

## How “new investigations” are determined

- **Process managers / orchestrators** do not “decide” which story is a new investigation in the abstract. They:
  1. Run **event_tracking**, which creates/updates **tracked_events** and **event_chronicles** from contexts.
  2. Run **investigation_report_refresh**, which:
     - **Refreshes** existing reports when an event’s context set has changed (re-generates the dossier).
     - **Creates** initial reports for tracked_events that don’t yet have a row in `event_reports` (up to a small limit per run).

- So “new investigations” in practice = new or updated rows in `intelligence.event_reports`, driven by:
  - New or updated **tracked_events** (from event_tracking), and  
  - The refresh job creating/updating reports for those events.

---

## Consolidating investigations into a superset story

Related investigations (e.g. several events about “the war in Iran” from different angles) can be grouped into **superset events**:

- **Service:** `api/services/investigation_consolidation_service.py` — clusters tracked_events by theme (event_name + geographic_scope tokens), creates one **superset** event per cluster with `event_type='superset'` and `sub_event_ids` listing the component events.
- **Trigger:** `POST /api/context_centric/investigations/consolidate?limit_events=200` — runs consolidation once. Optional query: `limit_events` (50–500).
- **Data:** Superset events appear in the same `tracked_events` list; filter with `event_type=superset`. Each component event keeps its own report; you can generate a separate combined report for the superset event (same `POST .../tracked_events/{id}/report`).

No automation phase is wired by default; run the API when you want to merge related investigations. An automation phase can be added later to run consolidation periodically.

---

## Quick checks

| What you want to check | Where |
|------------------------|--------|
| Event tracking enabled | `api/config/context_centric.yaml` → `tasks.event_tracking` |
| Last run of event_tracking | Monitor page → Phase timeline, or automation status |
| Count of events | `SELECT COUNT(*) FROM intelligence.tracked_events;` |
| Count of reports | `SELECT COUNT(*) FROM intelligence.event_reports;` |
| Create report for one event | API: `POST .../context_centric/tracked_events/{event_id}/report` (generate_tracked_event_report) |
| Merge related investigations into supersets | API: `POST .../context_centric/investigations/consolidate` |

---

## Backlog mode and orchestrator priority

The automation manager uses **backlog metrics** so the orchestrator prioritizes work and avoids empty cycles:

- **Per-phase backlog** — `api/services/backlog_metrics.py` counts pending work: unlinked contexts (event_tracking), articles without context (context_sync), contexts without claims (claim_extraction), entity profiles to build, events without reports.
- **Skip when empty** — Phases that have 0 pending work are not run (no empty cycles).
- **Backlog mode** — When a phase’s backlog exceeds 200, it runs at least every 5 minutes regardless of its base interval, so backlogs drain faster.
- **Priority by work** — Among tasks due to run, the scheduler queues the phase with the **largest backlog first**, so workers process the busiest pipeline first.

Backlog counts are exposed in the automation status API (`backlog_counts`) for the Monitor UI.

---

## Related code

- **Event discovery**: `api/services/event_tracking_service.py` — `discover_events_from_contexts`, `run_event_tracking_batch`
- **Investigation reports**: `api/services/investigation_report_service.py` — `generate_investigation_report`, `refresh_stale_investigation_reports`, `create_initial_reports_for_new_events`
- **Backlog & priority**: `api/services/backlog_metrics.py` — `get_all_backlog_counts`, `SKIP_WHEN_EMPTY`, `BACKLOG_HIGH_THRESHOLD`
- **Automation**: `api/services/automation_manager.py` — `_execute_event_tracking`, `_execute_investigation_report_refresh`, `_should_run_task` (backlog-aware)
