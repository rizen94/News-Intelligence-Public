#!/usr/bin/env python3
"""Force-register Iran cid magnets as hubs and scrub from episode signatures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))

from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import (  # noqa: E402
    get_pipeline_active_domain_keys,
    resolve_domain_schema,
)
from shared.episode_attach_gate import parse_anchor_signature  # noqa: E402


def main() -> int:
    drop = {"cid:2422", "cid:2423", "iran"}
    scrubbed = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, canonical_name FROM politics.entity_canonical
                WHERE id IN (2422, 2423) OR lower(canonical_name) = 'iran'
                """
            )
            rows = cur.fetchall() or []
            print("iran_entities", rows)
            for cid, name in rows:
                cur.execute(
                    """
                    INSERT INTO intelligence.entity_anchor_class
                        (domain_key, entity_name, canonical_entity_id,
                         anchor_class, source, metadata)
                    VALUES (%s, %s, %s, 'hub', 'geopolitics_seed', '{}'::jsonb)
                    ON CONFLICT (domain_key, entity_name) DO UPDATE SET
                        canonical_entity_id = EXCLUDED.canonical_entity_id,
                        anchor_class = 'hub',
                        updated_at = NOW()
                    """,
                    ("politics", str(name or f"cid:{cid}").strip().lower(), int(cid)),
                )
                drop.add(f"cid:{int(cid)}")
                if name:
                    drop.add(str(name).strip().lower())

            for dk in get_pipeline_active_domain_keys():
                schema = resolve_domain_schema(dk)
                cur.execute(
                    f"""
                    SELECT id, anchor_signature FROM {schema}.storylines
                    WHERE anchor_signature IS NOT NULL
                      AND COALESCE(story_kind, '') <> 'container_index'
                      AND COALESCE(is_mega_storyline, FALSE) = FALSE
                    """
                )
                for sid, raw in cur.fetchall() or []:
                    sig = parse_anchor_signature(raw)
                    nid = [t for t in (sig.get("identity") or []) if t not in drop]
                    nsup = [t for t in (sig.get("supporting") or []) if t not in drop]
                    if nid == (sig.get("identity") or []) and nsup == (
                        sig.get("supporting") or []
                    ):
                        continue
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET anchor_signature = %s::jsonb, updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            json.dumps(
                                {"identity": nid[:16], "supporting": nsup[:24]}
                            ),
                            int(sid),
                        ),
                    )
                    scrubbed += 1
                    print(f"scrub {dk} {sid} {len(sig.get('identity') or [])}->{len(nid)}")
            conn.commit()
            cur.execute(
                "SELECT anchor_signature->'identity' FROM politics.storylines WHERE id=3938"
            )
            print("3938_identity", cur.fetchone()[0])
    print(json.dumps({"scrubbed": scrubbed, "drop": sorted(drop)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
