#!/usr/bin/env python3
"""
Seed geopolitics / institution hubs into entity_anchor_class and scrub them
out of episode identity signatures (move to ignored — hubs never admit alone).

  PYTHONPATH=api python3 api/scripts/seed_and_scrub_hub_anchors.py --dry-run
  PYTHONPATH=api python3 api/scripts/seed_and_scrub_hub_anchors.py --apply
"""

from __future__ import annotations

import argparse
import json
import logging
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_scrub_hubs")

# Country / org magnets that must never be solo identity admit tokens.
_GEOPOLITICS_HUBS = [
    "iran",
    "russia",
    "china",
    "united states",
    "united states of america",
    "usa",
    "u.s.",
    "uk",
    "united kingdom",
    "israel",
    "ukraine",
    "saudi arabia",
    "nato",
    "european union",
    "eu",
    "united nations",
    "un",
    "g7",
    "g20",
    "white house",
    "pentagon",
    "kremlin",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = bool(args.apply)
    seeded = 0
    scrubbed = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for dk in get_pipeline_active_domain_keys():
                for name in _GEOPOLITICS_HUBS:
                    # Resolve cid when possible
                    schema = resolve_domain_schema(dk)
                    cid = None
                    try:
                        cur.execute(
                            f"""
                            SELECT id FROM {schema}.entity_canonical
                            WHERE lower(canonical_name) = %s
                            LIMIT 1
                            """,
                            (name,),
                        )
                        row = cur.fetchone()
                        if row:
                            cid = int(row[0])
                    except Exception:
                        pass
                    if apply:
                        cur.execute(
                            """
                            INSERT INTO intelligence.entity_anchor_class
                                (domain_key, entity_name, canonical_entity_id,
                                 anchor_class, source, metadata)
                            VALUES (%s, %s, %s, 'hub', 'geopolitics_seed', '{}'::jsonb)
                            ON CONFLICT (domain_key, entity_name) DO UPDATE SET
                                anchor_class = 'hub',
                                canonical_entity_id = COALESCE(
                                    EXCLUDED.canonical_entity_id,
                                    intelligence.entity_anchor_class.canonical_entity_id
                                ),
                                updated_at = NOW()
                            """,
                            (dk, name, cid),
                        )
                    seeded += 1

                # Scrub episode signatures
                schema = resolve_domain_schema(dk)
                hub_cids: set[str] = set()
                hub_names = set(_GEOPOLITICS_HUBS)
                try:
                    cur.execute(
                        """
                        SELECT canonical_entity_id, lower(entity_name)
                        FROM intelligence.entity_anchor_class
                        WHERE anchor_class = 'hub'
                          AND (domain_key = %s OR domain_key IS NULL)
                        """,
                        (dk,),
                    )
                    for cid, n in cur.fetchall() or []:
                        if cid is not None:
                            hub_cids.add(f"cid:{int(cid)}")
                        if n:
                            hub_names.add(str(n).strip().lower())
                except Exception:
                    pass

                cur.execute(
                    f"""
                    SELECT id, anchor_signature FROM {schema}.storylines
                    WHERE COALESCE(story_kind, '') <> 'container_index'
                      AND COALESCE(is_mega_storyline, FALSE) = FALSE
                      AND anchor_signature IS NOT NULL
                    """
                )
                for sid, raw in cur.fetchall() or []:
                    sig = parse_anchor_signature(raw)
                    new_id = [
                        t
                        for t in (sig.get("identity") or [])
                        if t not in hub_cids and t not in hub_names
                    ]
                    new_sup = [
                        t
                        for t in (sig.get("supporting") or [])
                        if t not in hub_cids and t not in hub_names
                    ]
                    if new_id == (sig.get("identity") or []) and new_sup == (
                        sig.get("supporting") or []
                    ):
                        continue
                    logger.info(
                        "[%s] scrub episode %s identity %s→%s",
                        dk,
                        sid,
                        len(sig.get("identity") or []),
                        len(new_id),
                    )
                    scrubbed += 1
                    if apply:
                        cur.execute(
                            f"""
                            UPDATE {schema}.storylines
                            SET anchor_signature = %s::jsonb, updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                json.dumps(
                                    {"identity": new_id[:16], "supporting": new_sup[:24]}
                                ),
                                int(sid),
                            ),
                        )
            if apply:
                conn.commit()
    print(json.dumps({"apply": apply, "hub_seeds": seeded, "signatures_scrubbed": scrubbed}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
