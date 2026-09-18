# Agent connection queries (News Intelligence)

Canned read paths for exploring how events, episodes, entities, and threads connect.
Use these **HTTP routes** from agents with API access, or mirror the SQL via **postgres-mcp**
(read-only on Widow `news_intel`).

## HTTP API (`/api/connections/*`)

| Route | Purpose |
|-------|---------|
| `GET /api/connections/coverage` | Full linkage coverage (same as Monitor) |
| `GET /api/connections/orphan_summary` | Compact global + per-domain gaps |
| `GET /api/connections/events/{event_id}` | CE → EEL → episode → narrative thread + cluster |
| `GET /api/connections/entities/{entity_profile_id}` | Profile → facts, SEI storylines, graph edges |
| `GET /api/connections/chains/tracked_events/{id}` | TE → CE → episode → thread (full chain) |
| `POST /api/connections/graph/refresh?dry_run=true` | Project EEL/SEI/threads → `graph_connection_links` |

Monitor panel: `GET /api/system_monitoring/linkage_coverage`

Legacy reconciliation list: `GET /api/event_reconciliation`

## postgres-mcp equivalents

**Orphan summary**

```sql
SELECT COUNT(DISTINCT event_id) AS linked,
       (SELECT COUNT(*) FROM public.chronological_events) AS total
FROM intelligence.event_episode_links
WHERE inference_stage <> 'quarantined';
```

**Event connections**

```sql
SELECT eel.*, ce.title, ce.event_cluster_id
FROM intelligence.event_episode_links eel
JOIN public.chronological_events ce ON ce.id = eel.event_id
WHERE eel.event_id = :event_id AND eel.inference_stage <> 'quarantined';
```

**Entity → storylines (SEI)**

```sql
SELECT sei.storyline_id, s.title
FROM politics.story_entity_index sei
JOIN politics.storylines s ON s.id = sei.storyline_id
JOIN intelligence.entity_profiles ep ON LOWER(ep.canonical_name) = LOWER(sei.entity_name)
WHERE ep.id = :entity_profile_id AND s.merged_into_id IS NULL
LIMIT 40;
```

## Implementation

- Services: `api/services/linkage_coverage_service.py`, `api/services/connection_query_service.py`
- Reconciliation chain: `api/services/event_reconciliation_service.py` → `get_connection_chain_for_tracked_event`
- Graph projection: `refresh_assembly_graph_edges()` (optional nightly via `EPISODE_ASSEMBLY_GRAPH_PROJECTION=true`)

## Agent rules

1. **SELECT only** via postgres-mcp — writes go through NI API maintenance phases.
2. Prefer `/api/connections/chains/tracked_events/{id}` over hand-rolled joins for TE traces.
3. `graph_connection_links` may be empty until projection runs or chemistry phases materialize edges.
