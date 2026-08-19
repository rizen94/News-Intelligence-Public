# v12 handoff gate results (2026-08-16)

## Widow flags
- `/opt/news-intelligence/.env`: `EPISODE_CONTAINER_ASSEMBLY_ENABLED=true`, `STORYLINE_AUTOMATION_AUTO_ATTACH=0`
- Mig 295 applied: `intelligence.event_episode_links` exists
- Lab baseline synced from **`/opt/news-intelligence`** (Documents tree on Widow was stale)

## DDL notes (triage)
- `editorial_packages.status` CHECK lacks `closed_thin` — migration 297 adds it
- `news_stories.package_id` FK confirmed
- `package_evidence_briefs.package_id` unique confirmed

## Cluster D / Frontend
Cluster D modules still referenced — no blind archive. Frontend heavy on `/storylines/` — API membership flip preferred.
