"""
Qualified investigation table names — single source for SQL.

Pre-cutover: nri.resolved_mentions etc.
Post-cutover: set USE_INVESTIGATION_PREFIXED_TABLES=true → intelligence.investigation_* tables.
"""

from __future__ import annotations

from config.runtime import investigation_schema, investigation_table_prefix


def _qualified(base: str) -> str:
    schema = investigation_schema()
    prefix = investigation_table_prefix()
    return f"{schema}.{prefix}{base}"


# Core investigation tables
T_WATERMARKS = _qualified("watermarks")
T_RESOLVED_MENTIONS = _qualified("resolved_mentions")
T_PARKED_RESOLUTION = _qualified("parked_resolution")
T_ENTITY_BRIDGE = _qualified("entity_bridge")
T_PROVISIONAL_MINTS = _qualified("provisional_mints")
T_FTM_ENTITY_CACHE = _qualified("ftm_entity_cache")
T_LOOP_RUN = _qualified("loop_run")

# Intelligence tables (not migrated)
T_ENTITY_PROFILES = "intelligence.entity_profiles"
T_CONTEXTS = "intelligence.contexts"
T_CONTEXT_ENTITY_MENTIONS = "intelligence.context_entity_mentions"
T_EXTRACTED_CLAIMS = "intelligence.extracted_claims"
