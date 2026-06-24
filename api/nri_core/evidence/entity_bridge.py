"""Bridge NI entity_profile_id to identity spine ftm_id."""

from __future__ import annotations

import json

from config.investigation_tables import T_ENTITY_BRIDGE, T_FTM_ENTITY_CACHE
from nri_core.evidence import ni_reader
from nri_core.spine.api.lookup import get_entity


def upsert_entity_bridge(
    entity_profile_id: int,
    ftm_id: str,
    bridge_score: float,
) -> None:
    with ni_reader.news_intel_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {T_ENTITY_BRIDGE}
                    (entity_profile_id, ftm_id, bridge_score)
                VALUES (%s, %s, %s)
                ON CONFLICT (entity_profile_id) DO UPDATE SET
                    ftm_id = EXCLUDED.ftm_id,
                    bridge_score = GREATEST(
                        COALESCE({T_ENTITY_BRIDGE}.bridge_score, 0),
                        EXCLUDED.bridge_score
                    ),
                    bridged_at = NOW()
                """,
                (entity_profile_id, ftm_id, bridge_score),
            )
        conn.commit()


def sync_ftm_entity_cache(ftm_id: str) -> None:
    entity = get_entity(ftm_id)
    if not entity:
        return
    with ni_reader.news_intel_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {T_FTM_ENTITY_CACHE}
                    (ftm_id, schema_name, caption, dataset, anchors, synced_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
                ON CONFLICT (ftm_id) DO UPDATE SET
                    schema_name = EXCLUDED.schema_name,
                    caption = EXCLUDED.caption,
                    dataset = EXCLUDED.dataset,
                    anchors = EXCLUDED.anchors,
                    synced_at = NOW()
                """,
                (
                    entity.ftm_id,
                    entity.schema_name,
                    entity.caption,
                    entity.dataset,
                    json.dumps(entity.anchors),
                ),
            )
        conn.commit()


def bridge_auto_link(
    entity_profile_id: int,
    ftm_id: str,
    bridge_score: float,
) -> None:
    upsert_entity_bridge(entity_profile_id, ftm_id, bridge_score)
    sync_ftm_entity_cache(ftm_id)
