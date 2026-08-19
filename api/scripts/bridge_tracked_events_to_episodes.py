#!/usr/bin/env python3
"""Bridge intelligence.tracked_events to canonical episodes via anchor overlap.

  PYTHONPATH=api python3 api/scripts/bridge_tracked_events_to_episodes.py --all --apply
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
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema  # noqa: E402
from shared.episode_attach_gate import parse_anchor_signature, signature_match  # noqa: E402
from shared.episode_title_match import episode_title_similarity  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("bridge_tracked_events")


def _te_domain_keys(raw) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    return []


def _anchors_from_te(anchors_raw, participant_ids) -> dict:
    identity: list[str] = []
    supporting: list[str] = []
    if isinstance(anchors_raw, dict):
        identity.extend(str(x) for x in (anchors_raw.get("identity") or [])[:12])
        supporting.extend(str(x) for x in (anchors_raw.get("supporting") or [])[:12])
    if participant_ids:
        for pid in participant_ids[:12]:
            token = f"cid:{int(pid)}"
            if token not in identity:
                identity.append(token)
    return {"identity": identity, "supporting": supporting, "hub": []}


def bridge_domain(domain_key: str, *, apply: bool, limit: int) -> dict:
    schema = resolve_domain_schema(domain_key)
    stats = {"domain": domain_key, "scanned": 0, "bridged": 0, "skipped": 0}

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, anchors, key_participant_entity_ids, domain_keys
                FROM intelligence.tracked_events
                WHERE storyline_id IS NULL
                  AND %s = ANY(domain_keys)
                ORDER BY updated_at DESC NULLS LAST
                LIMIT %s
                """,
                (domain_key, int(limit)),
            )
            rows = cur.fetchall() or []

        for te_id, anchors_raw, participant_ids, domain_keys in rows:
            stats["scanned"] += 1
            event_anchors = _anchors_from_te(anchors_raw, participant_ids)
            if not (event_anchors.get("identity") or event_anchors.get("supporting")):
                stats["skipped"] += 1
                continue

            best_ep: int | None = None
            best_score = 0.0
            te_name = ""
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT event_name FROM intelligence.tracked_events WHERE id = %s",
                    (int(te_id),),
                )
                row_name = cur.fetchone()
                te_name = (row_name[0] if row_name else "") or ""

            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, title, anchor_signature
                    FROM {schema}.storylines
                    WHERE merged_into_id IS NULL
                      AND COALESCE(story_kind, '') <> 'container_index'
                      AND status NOT IN ('archived', 'concluded')
                    ORDER BY updated_at DESC NULLS LAST
                    LIMIT 200
                    """
                )
                for sid, title, raw_sig in cur.fetchall() or []:
                    title_sim = episode_title_similarity(te_name, title or "") if te_name else 0.0
                    if title_sim >= 0.72 and title_sim > best_score:
                        best_score = title_sim
                        best_ep = int(sid)
                        continue
                    if not raw_sig:
                        continue
                    sig = parse_anchor_signature(raw_sig)
                    ok, matched, _reason = signature_match(
                        sig, event_anchors, min_supporting=2, min_identity=2
                    )
                    if ok and len(matched) > best_score:
                        best_score = float(len(matched))
                        best_ep = int(sid)

            if not best_ep:
                stats["skipped"] += 1
                continue

            if apply:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE intelligence.tracked_events
                        SET storyline_id = %s, updated_at = NOW()
                        WHERE id = %s AND storyline_id IS NULL
                        """,
                        (best_ep, int(te_id)),
                    )
                conn.commit()
            stats["bridged"] += 1

    stats["apply"] = apply
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--domain")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=500)
    args = ap.parse_args()
    apply = bool(args.apply) and not args.dry_run
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        ap.error("Pass --domain or --all")

    results = [bridge_domain(dk, apply=apply, limit=args.limit) for dk in domains]
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
