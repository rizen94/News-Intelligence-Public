"""
Curated bulk seeding for ``{domain}.entity_canonical`` + ``entity_profiles`` (via sync).

Use when you want **matching** against known world actors instead of waiting for gap discovery.
YAML: ``api/config/seed_world_entities.yaml`` — run ``api/scripts/seed_world_entities_from_yaml.py``.
"""

from __future__ import annotations

import logging
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import is_valid_domain_key, resolve_domain_schema

from services.entity_profile_sync_service import sync_domain_entity_profiles
from services.entity_resolution_service import ENTITY_TYPES

logger = logging.getLogger(__name__)


def normalize_seed_entity_type(raw: str | None) -> str:
    """
    Map API / spreadsheet labels to ``entity_canonical.entity_type`` CHECK values.

    Accepts: person, organization, subject, recurring_event, family (snake_case)
    or legacy: PERSON, ORG, GPE, ORGANIZATION, LOCATION, EVENT, etc.
    """
    if not raw:
        return "organization"
    s = str(raw).strip()
    low = s.lower()
    if low in ENTITY_TYPES:
        return low
    up = s.upper()
    if up in ("PERSON", "PER", "POLITICIAN", "POL"):
        return "person"
    if up in ("ORG", "ORGANIZATION", "ORGANISATION", "COMPANY", "CORP", "GOV", "GOVERNMENT"):
        return "organization"
    if up in ("GPE", "LOCATION", "LOC", "COUNTRY", "NATION", "PLACE", "REGION"):
        return "subject"
    if up in ("EVENT", "RECURRING_EVENT", "RECURRING"):
        return "recurring_event"
    if up in ("FAMILY",):
        return "family"
    if up in ("SUBJECT", "TOPIC", "THEME"):
        return "subject"
    return "organization"


def bulk_seed_canonical_entries(
    domain_key: str,
    entries: list[dict[str, Any]],
    *,
    sync_profiles: bool = True,
) -> dict[str, Any]:
    """
    Insert ``entity_canonical`` rows (idempotent) and optional alias lists.

    Each entry: ``canonical_name`` or ``name`` (required), ``entity_type`` (optional), ``aliases`` (optional list[str]).
    """
    if not is_valid_domain_key(domain_key):
        return {"success": False, "error": "invalid_domain", "inserted": 0, "skipped": 0, "aliases_updated": 0}
    if not entries:
        return {"success": True, "inserted": 0, "skipped": 0, "aliases_updated": 0}

    schema = resolve_domain_schema(domain_key)
    inserted = 0
    skipped = 0
    aliases_updated = 0

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db", "inserted": 0, "skipped": 0, "aliases_updated": 0}

    try:
        with conn.cursor() as cur:
            for ent in entries:
                if not isinstance(ent, dict):
                    continue
                name = (ent.get("canonical_name") or ent.get("name") or "").strip()
                if len(name) < 2:
                    skipped += 1
                    continue
                et = normalize_seed_entity_type(ent.get("entity_type"))
                aliases_raw = ent.get("aliases") or []
                if isinstance(aliases_raw, str):
                    aliases_raw = [a.strip() for a in aliases_raw.split(",") if a.strip()]
                aliases = [a.strip() for a in aliases_raw if isinstance(a, str) and len(a.strip()) >= 2]
                aliases = [a for a in aliases if a.lower() != name.lower()]

                cur.execute(
                    f"""
                    INSERT INTO {schema}.entity_canonical (canonical_name, entity_type, aliases)
                    SELECT %s, %s, %s::text[]
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {schema}.entity_canonical ec
                        WHERE lower(trim(ec.canonical_name)) = lower(trim(%s))
                          AND ec.entity_type = %s
                    )
                    """,
                    (name, et, aliases, name, et),
                )
                if cur.rowcount and cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
                    if not aliases:
                        continue
                    cur.execute(
                        f"""
                        SELECT id, COALESCE(aliases, '{{}}'::text[])
                        FROM {schema}.entity_canonical
                        WHERE lower(trim(canonical_name)) = lower(trim(%s))
                          AND entity_type = %s
                        LIMIT 1
                        """,
                        (name, et),
                    )
                    row = cur.fetchone()
                    if not row:
                        continue
                    cid, existing = int(row[0]), list(row[1] or [])
                    seen = {x.lower() for x in existing if x}
                    merged = list(existing)
                    for a in aliases:
                        if a.lower() not in seen and a.lower() != name.lower():
                            merged.append(a)
                            seen.add(a.lower())
                    if merged != existing:
                        cur.execute(
                            f"""
                            UPDATE {schema}.entity_canonical
                            SET aliases = %s, updated_at = NOW()
                            WHERE id = %s
                            """,
                            (merged, cid),
                        )
                        aliases_updated += 1
        conn.commit()
    except Exception as e:
        logger.warning("bulk_seed_canonical_entries: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {
            "success": False,
            "error": str(e)[:500],
            "inserted": inserted,
            "skipped": skipped,
            "aliases_updated": aliases_updated,
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass

    mapped = 0
    if sync_profiles:
        try:
            mapped = sync_domain_entity_profiles(domain_key)
        except Exception as e:
            logger.warning("bulk_seed sync_domain_entity_profiles: %s", e)

    return {
        "success": True,
        "domain_key": domain_key,
        "inserted": inserted,
        "skipped": skipped,
        "aliases_updated": aliases_updated,
        "entity_profile_sync_new_mappings": mapped,
    }
