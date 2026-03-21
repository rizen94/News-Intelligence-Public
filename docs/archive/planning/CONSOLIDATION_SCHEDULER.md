# Consolidation Scheduler

The app runs a **unified consolidation loop** that rotates through four types. By default one consolidation runs **every hour** (each type ~6× per day). You can set a longer interval for fewer runs (e.g. 3 h for ~2× per type per day).

## What runs

| Step | What it does |
|------|----------------|
| **storylines** | Merges similar storylines and creates mega-storylines (all domains). `StorylineConsolidationService.run_all_domains()`. |
| **entities** | Merges duplicate entities, prunes low-value, extracts relationships. `entity_organizer_service.run_cycle()`. |
| **investigations** | Groups related tracked_events into superset events (e.g. “War in Iran” from different angles). `investigation_consolidation_service.run_consolidation()`. |
| **events** | Same as investigations (second run in the rotation for more frequent event supersets). |

## Schedule

- **Interval:** 1 hour between runs by default (`CONSOLIDATION_INTERVAL_SECONDS = 3600` in `api/services/consolidation_scheduler.py`). Set to 10800 (3 h) for ~2× per type per day.
- **Rotation:** storylines → entities → investigations → events → storylines → …
- **Startup:** First run is after 1 minute (`CONSOLIDATION_STARTUP_DELAY_SECONDS`) so the system isn’t overloaded right after deploy.
- **Effect:** With 1 h interval, one consolidation runs every hour; each type runs ~6× per 24 hours. With 3 h interval, each type runs ~2× per 24 hours.

## Config

Edit `api/services/consolidation_scheduler.py`:

- `CONSOLIDATION_INTERVAL_SECONDS` — seconds between runs (default 3600 = 1 h). Use 10800 (3 h) for ~2× per type per day.
- `CONSOLIDATION_STARTUP_DELAY_SECONDS` — delay before first run (default 60).
- `CONSOLIDATION_TYPES` — list of step names; order is the rotation order.

## Manual runs

All four consolidation types have real implementations and can be triggered via API or the scheduler:

- **Storylines:** `GET /api/storylines/consolidation/status`, `POST /api/storylines/consolidation/run` (all domains), `POST /api/{domain}/storylines/consolidation/run`, `POST /api/{domain}/storylines/merge/{primary_id}/{secondary_id}`, `GET /api/{domain}/storylines/hierarchy`. Implemented in `storyline_consolidation_service` (merge similar storylines, create mega-storylines, DB updates).
- **Entities:** `POST /api/context_centric/entities/consolidate?domain_key=...` (omit `domain_key` for all domains). Implemented in `entity_organizer_service.run_cycle()` and `intelligence_cleanup_controller` (merge duplicates, prune, relationship extraction).
- **Investigations / events:** `POST /api/context_centric/investigations/consolidate?limit_events=200`. Implemented in `investigation_consolidation_service.run_consolidation()` (cluster tracked_events by theme, create superset events with `sub_event_ids`).

## Where it’s started

The loop runs in a background thread started in `api/main_v4.py` at startup (“Consolidation Scheduler”). It is stopped on app shutdown via `consolidation_stop_event`.
