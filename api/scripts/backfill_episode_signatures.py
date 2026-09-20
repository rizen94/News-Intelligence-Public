#!/usr/bin/env python3
"""
Backfill episode anchor_signature from SEI / article entities (hubs stripped).

Skips story_kind=container_index. Dry-run by default.

  PYTHONPATH=api python3 api/scripts/backfill_episode_signatures.py --domain legal --dry-run
  PYTHONPATH=api python3 api/scripts/backfill_episode_signatures.py --all --apply --min-members 2
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
from shared.episode_attach_gate import (  # noqa: E402
    classify_event_anchors,
    parse_anchor_signature,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("backfill_episode_signatures")


def _signature_from_sei(cur, schema: str, episode_id: int, domain_key: str) -> dict:
    """Build identity/supporting from SEI durable non-hub entities."""
    cur.execute(
        f"""
        SELECT entity_name, entity_type, canonical_entity_id, entity_role,
               COALESCE(mention_count, 1)
        FROM {schema}.story_entity_index
        WHERE storyline_id = %s
        ORDER BY COALESCE(mention_count, 1) DESC
        LIMIT 80
        """,
        (int(episode_id),),
    )
    rows = cur.fetchall() or []
    # Reuse classifier by faking entity list via names
    names = [r[0] for r in rows if r[0]]
    # Prefer roles if present
    identity: list[str] = []
    supporting: list[str] = []
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        hubs = get_domain_synthesis_config(domain_key).hub_name_set()
    except Exception:
        hubs = frozenset()

    for name, etype, cid, role, mentions in rows:
        name_l = (name or "").strip().lower()
        if not name_l:
            continue
        if name_l in hubs or any(len(h) >= 5 and (h in name_l or name_l in h) for h in hubs):
            continue
        role_l = (role or "").strip().lower()
        if role_l in ("who", "what", "where", "hub"):
            continue
        token = f"cid:{int(cid)}" if cid is not None else name_l
        et = (etype or "").strip().lower()
        if et in ("organization", "person", "company", "court", "instrument") or (
            name_l and (len(name_l) >= 12 or any(ch.isdigit() for ch in name_l))
        ):
            if mentions and int(mentions) >= 2:
                identity.append(token)
            else:
                supporting.append(token)
        else:
            supporting.append(token)

    # Dedupe
    def _dedupe(xs: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for x in xs:
            if x not in seen:
                seen.add(x)
                out.append(x)
        return out

    return {
        "identity": _dedupe(identity)[:16],
        "supporting": _dedupe(supporting)[:24],
    }


def backfill_domain(
    domain_key: str,
    *,
    apply: bool,
    min_members: int,
    limit: int,
    only_empty: bool,
) -> dict:
    schema = resolve_domain_schema(domain_key)
    stats = {"domain": domain_key, "scanned": 0, "updated": 0, "skipped": 0}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.id, s.title,
                       COALESCE(s.story_kind, ''),
                       COALESCE(s.is_mega_storyline, FALSE),
                       s.anchor_signature,
                       s.signature_locked_at,
                       (SELECT COUNT(*) FROM {schema}.storyline_articles sa
                        WHERE sa.storyline_id = s.id)
                FROM {schema}.storylines s
                WHERE COALESCE(s.story_kind, '') <> 'container_index'
                  AND COALESCE(s.is_mega_storyline, FALSE) = FALSE
                  AND s.status IN ('active', 'dormant', 'emerging')
                ORDER BY s.id DESC
                LIMIT %s
                """,
                (int(limit),),
            )
            rows = cur.fetchall() or []
            for sid, title, skind, is_mega, raw_sig, locked_at, n_members in rows:
                stats["scanned"] += 1
                if int(n_members or 0) < min_members and min_members > 0:
                    # Still allow SEI-only backfill for thin episodes
                    pass
                sig = parse_anchor_signature(raw_sig)
                if only_empty and (sig["identity"] or sig["supporting"]):
                    stats["skipped"] += 1
                    continue
                if locked_at is not None and only_empty:
                    stats["skipped"] += 1
                    continue
                new_sig = _signature_from_sei(cur, schema, int(sid), domain_key)
                if not new_sig["identity"] and not new_sig["supporting"]:
                    # Try member article entities (SEI often empty after remediation)
                    cur.execute(
                        f"""
                        SELECT article_id FROM {schema}.storyline_articles
                        WHERE storyline_id = %s ORDER BY article_id LIMIT 5
                        """,
                        (int(sid),),
                    )
                    arts = [int(r[0]) for r in (cur.fetchall() or [])]
                    id_acc: list[str] = []
                    sup_acc: list[str] = []
                    for aid in arts:
                        classified = classify_event_anchors(
                            conn,
                            domain_key=domain_key,
                            schema=schema,
                            article_id=int(aid),
                        )
                        id_acc.extend(classified.get("identity") or [])
                        sup_acc.extend(classified.get("supporting") or [])
                    # dedupe
                    def _d(xs: list[str]) -> list[str]:
                        seen: set[str] = set()
                        out: list[str] = []
                        for x in xs:
                            if x not in seen:
                                seen.add(x)
                                out.append(x)
                        return out

                    new_sig = {
                        "identity": _d(id_acc)[:16],
                        "supporting": _d(sup_acc)[:24],
                    }
                if not new_sig["identity"] and not new_sig["supporting"]:
                    stats["skipped"] += 1
                    continue
                logger.info(
                    "[%s] episode %s id=%s/%s → %s",
                    domain_key,
                    sid,
                    len(new_sig["identity"]),
                    len(new_sig["supporting"]),
                    (title or "")[:60],
                )
                if apply:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET anchor_signature = %s::jsonb,
                            signature_locked_at = COALESCE(signature_locked_at, NOW()),
                            episode_state = CASE
                                WHEN episode_state = 'forming' THEN 'active'
                                ELSE COALESCE(episode_state, 'active')
                            END,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (json.dumps(new_sig), int(sid)),
                    )
                    stats["updated"] += 1
            if apply:
                conn.commit()
            else:
                conn.rollback()
    return stats


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain")
    p.add_argument("--all", action="store_true")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--min-members", type=int, default=0)
    p.add_argument("--limit", type=int, default=500)
    p.add_argument(
        "--include-nonempty",
        action="store_true",
        help="Overwrite signatures that already have anchors (default: only empty)",
    )
    args = p.parse_args()
    apply = bool(args.apply) and not args.dry_run
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        p.error("Pass --domain or --all")
    out = []
    for dk in domains:
        st = backfill_domain(
            dk,
            apply=apply,
            min_members=args.min_members,
            limit=args.limit,
            only_empty=not args.include_nonempty,
        )
        out.append(st)
        logger.info("stats %s", st)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
