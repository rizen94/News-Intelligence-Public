# Entity Service Contracts

Use `services.entity_service_facade` from routes and cross-domain callers. Specialized modules remain the implementation layer.

| Facade function | Delegates to | Input | Output |
|-----------------|--------------|-------|--------|
| `resolve_with_candidates` | `entity_resolution_service` | domain_key, name, type | candidates + canonical id |
| `populate_aliases` | `entity_resolution_service` | domain_key | alias stats |
| `find_merge_candidates` | `entity_resolution_service` | domain_key, thresholds | merge pairs |
| `run_resolution_batch` | `entity_resolution_service` | domain_key, limit | batch stats |
| `sync_profiles` | `entity_profile_sync_service` | domain_key | profiles created |
| `track_positions` | `entity_position_tracker_service` | entity_id | positions list |
| `enrich_entity` | `entity_enrichment_service` | entity_id | enrichment payload |

## HTTP routes

Entity resolution HTTP handlers live in `api/domains/intelligence_hub/routes/entity_resolution.py` (same `/api/...` paths as before the refactor).

## Shared utilities

- String similarity: `shared.text_similarity.sequence_similarity`
- Service envelopes: `shared.services.service_result.service_ok` / `service_err`

See also [BACKGROUND_SERVICES.md](BACKGROUND_SERVICES.md) for worker-level contracts.
