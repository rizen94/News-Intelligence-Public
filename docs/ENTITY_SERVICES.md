# Entity Service Contracts

Use `services.entity_service_facade` from routes and cross-domain callers. Specialized modules remain the implementation layer.

| Facade function | Delegates to | Input | Output |
|-----------------|--------------|-------|--------|
| `resolve_with_candidates` | `entity_resolution_service` | domain_key, name, type | candidates + canonical id |
| `populate_aliases` | `entity_resolution_service` | domain_key | alias stats |
| `find_merge_candidates` | `entity_resolution_service` | domain_key, thresholds | merge pairs |
| `run_resolution_batch` | `entity_resolution_service` | domain_key, limit | batch stats |
| `sync_profiles` | `entity_profile_sync_service` | domain_key | profiles created |
| `auto_merge_high_confidence` | `entity_resolution_service` | domain_key, threshold | merge stats |
| `link_cross_domain_entities` | `entity_resolution_service` | confidence, limit | cross-domain links |
| `schema_for_domain` | `entity_resolution_service` | domain_key | schema name |
| `extract_positions_for_entity` | `entity_position_tracker_service` | domain_key, entity_id | positions |
| `run_position_tracker_batch` | `entity_position_tracker_service` | domain, limits | batch stats |
| `run_enrichment_batch` | `entity_enrichment_service` | limit | profiles updated |
| `enrich_entity` | `entity_enrichment_service` | entity_id | enrichment payload |

## HTTP routes

Entity resolution HTTP handlers live in `api/domains/intelligence_hub/routes/entity_resolution.py` (same `/api/...` paths as before the refactor).

## Shared utilities

- String similarity: `shared.text_similarity.sequence_similarity`
- Service envelopes: `shared.services.service_result.service_ok` / `service_err`

See also [BACKGROUND_SERVICES.md](BACKGROUND_SERVICES.md) for worker-level contracts.
