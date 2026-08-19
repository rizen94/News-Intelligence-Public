#!/usr/bin/env python3
"""
Reclassify mega storylines → container indexes; strip article membership;
seed hub/entity_anchor_class projections; quarantine untyped related links.

Size alone is not proof of a bad bag — a focused signed episode can grow large.
Demote when already mega-flagged, Ongoing: absorb bags, unsigned sprawl, or
extreme size. Locked-signature episodes under --extreme-articles are protected
by default.

Dry-run by default. Apply with --apply.

  PYTHONPATH=api python3 api/scripts/migrate_megas_to_containers.py --domain legal
  PYTHONPATH=api python3 api/scripts/migrate_megas_to_containers.py --all --min-articles 80 --apply
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

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("migrate_megas_to_containers")


def _seed_hub_anchor_classes(cur, domain_key: str) -> int:
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        cfg = get_domain_synthesis_config(domain_key)
        hubs = cfg.hub_name_set()
    except Exception:
        hubs = frozenset()
    n = 0
    for name in sorted(hubs):
        cur.execute(
            """
            INSERT INTO intelligence.entity_anchor_class
                (domain_key, entity_name, anchor_class, source, metadata)
            VALUES (%s, %s, 'hub', 'hub_facets', '{}'::jsonb)
            ON CONFLICT (domain_key, entity_name) DO UPDATE SET
                anchor_class = 'hub',
                updated_at = NOW()
            """,
            (domain_key, name),
        )
        n += 1
    return n


def _signature_has_identity(raw_sig) -> bool:
    try:
        from shared.episode_attach_gate import parse_anchor_signature

        sig = parse_anchor_signature(raw_sig)
        return bool(sig.get("identity"))
    except Exception:
        return False


def migrate_domain(
    domain_key: str,
    *,
    min_articles: int,
    apply: bool,
    quarantine_related: bool,
    protect_signed: bool = True,
    extreme_articles: int = 120,
) -> dict:
    schema = resolve_domain_schema(domain_key)
    stats = {
        "domain": domain_key,
        "schema": schema,
        "candidates": 0,
        "megas_found": 0,
        "skipped_signed": 0,
        "membership_stripped": 0,
        "hub_classes_seeded": 0,
        "quarantined_links": 0,
        "te_containers": 0,
    }
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            stats["hub_classes_seeded"] = _seed_hub_anchor_classes(cur, domain_key)

            try:
                cur.execute(
                    f"""
                    SELECT s.id, s.title, COALESCE(s.article_count, 0)::int,
                           COALESCE(s.is_mega_storyline, FALSE),
                           COALESCE(s.story_kind, ''),
                           s.signature_locked_at,
                           s.anchor_signature
                    FROM {schema}.storylines s
                    WHERE COALESCE(s.story_kind, '') <> 'container_index'
                      AND (
                        COALESCE(s.is_mega_storyline, FALSE) = TRUE
                        OR COALESCE(s.article_count, 0) >= %s
                        OR EXISTS (
                            SELECT 1 FROM {schema}.storyline_articles sa
                            WHERE sa.storyline_id = s.id
                            GROUP BY sa.storyline_id
                            HAVING COUNT(*) >= %s
                        )
                      )
                    ORDER BY COALESCE(s.article_count, 0) DESC
                    """,
                    (min_articles, min_articles),
                )
            except Exception:
                conn.rollback()
                cur.execute(
                    f"""
                    SELECT s.id, s.title, COALESCE(s.article_count, 0)::int,
                           COALESCE(s.is_mega_storyline, FALSE),
                           '',
                           NULL,
                           NULL
                    FROM {schema}.storylines s
                    WHERE COALESCE(s.is_mega_storyline, FALSE) = TRUE
                       OR COALESCE(s.article_count, 0) >= %s
                       OR EXISTS (
                            SELECT 1 FROM {schema}.storyline_articles sa
                            WHERE sa.storyline_id = s.id
                            GROUP BY sa.storyline_id
                            HAVING COUNT(*) >= %s
                       )
                    ORDER BY COALESCE(s.article_count, 0) DESC
                    """,
                    (min_articles, min_articles),
                )
            rows = cur.fetchall() or []
            stats["candidates"] = len(rows)

            for row in rows:
                sid, title, acount, is_mega, skind = row[0], row[1], row[2], row[3], row[4]
                locked_at = row[5] if len(row) > 5 else None
                raw_sig = row[6] if len(row) > 6 else None
                title_l = (title or "").strip().lower()
                ongoing_bag = title_l.startswith("ongoing:")
                has_identity = _signature_has_identity(raw_sig)
                # Size alone is not wrong. Protect locked signed episodes unless
                # mega-flagged, Ongoing: bag, or extreme sprawl.
                if (
                    protect_signed
                    and locked_at is not None
                    and has_identity
                    and not is_mega
                    and not ongoing_bag
                    and int(acount or 0) < int(extreme_articles)
                ):
                    stats["skipped_signed"] += 1
                    logger.info(
                        "[%s] skip signed episode id=%s articles=%s title=%s",
                        domain_key,
                        sid,
                        acount,
                        (title or "")[:80],
                    )
                    continue

                stats["megas_found"] += 1
                logger.info(
                    "[%s] mega/container candidate id=%s articles=%s mega=%s kind=%s title=%s",
                    domain_key,
                    sid,
                    acount,
                    is_mega,
                    skind,
                    (title or "")[:80],
                )
                if not apply:
                    continue
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET story_kind = 'container_index',
                        is_mega_storyline = TRUE,
                        episode_state = COALESCE(episode_state, 'concluded'),
                        automation_enabled = FALSE,
                        metadata = COALESCE(metadata, '{{}}'::jsonb)
                            || '{{"assembly_role":"container_index"}}'::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (int(sid),),
                )
                cur.execute(
                    f"""
                    DELETE FROM {schema}.storyline_articles
                    WHERE storyline_id = %s
                    RETURNING article_id
                    """,
                    (int(sid),),
                )
                deleted = cur.fetchall() or []
                stats["membership_stripped"] += len(deleted)
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET article_count = 0, total_articles = 0, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (int(sid),),
                )
                # Seed / update a TE container index row when possible
                try:
                    cur.execute(
                        """
                        INSERT INTO intelligence.tracked_events
                        (event_type, event_name, start_date, geographic_scope,
                         key_participant_entity_ids, milestones, domain_keys,
                         editorial_briefing, editorial_briefing_json,
                         briefing_version, briefing_status,
                         anchors, particulars, arc_state, container_kind)
                        VALUES (
                            'container_index', %s, CURRENT_DATE, NULL,
                            '[]', '[]', %s,
                            NULL, NULL,
                            1, 'draft',
                            '[]'::jsonb, %s::jsonb, 'dormant', 'demoted_mega'
                        )
                        RETURNING id
                        """,
                        (
                            f"[container] {(title or sid)}"[:200],
                            [domain_key],
                            json.dumps(
                                {
                                    "source_episode_id": int(sid),
                                    "domain_key": domain_key,
                                    "former_article_count": int(acount or 0),
                                }
                            ),
                        ),
                    )
                    te_id = (cur.fetchone() or (None,))[0]
                    if te_id:
                        stats["te_containers"] += 1
                        cur.execute(
                            """
                            INSERT INTO intelligence.tracked_event_storyline_facets
                                (tracked_event_id, domain_key, storyline_id, facet)
                            VALUES (%s, %s, %s, 'container_index')
                            ON CONFLICT DO NOTHING
                            """,
                            (int(te_id), domain_key, int(sid)),
                        )
                except Exception as exc:
                    logger.debug("TE container seed skip: %s", exc)

            if quarantine_related and apply:
                try:
                    cur.execute(
                        """
                        UPDATE intelligence.event_episode_links
                        SET inference_stage = 'quarantined',
                            updated_at = NOW(),
                            metadata = metadata || '{"quarantine_reason":"migrate_untyped"}'::jsonb
                        WHERE domain_key = %s
                          AND inference_stage <> 'quarantined'
                          AND (
                            matched_anchors IS NULL
                            OR matched_anchors = '[]'::jsonb
                          )
                        """,
                        (domain_key,),
                    )
                    stats["quarantined_links"] = cur.rowcount or 0
                except Exception as exc:
                    logger.debug("quarantine skip (table may be empty): %s", exc)

            if apply:
                conn.commit()
            else:
                conn.rollback()
    return stats


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domain", help="Single domain key")
    p.add_argument("--all", action="store_true", help="All pipeline-active domains")
    p.add_argument(
        "--min-articles",
        type=int,
        default=40,
        help="Size floor for demotion candidates (default 40). Not proof of a bad bag alone.",
    )
    p.add_argument(
        "--extreme-articles",
        type=int,
        default=120,
        help="Signed episodes at/above this size may still demote (default 120).",
    )
    p.add_argument(
        "--protect-signed",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Skip locked-signature episodes under extreme size unless mega/Ongoing (default on).",
    )
    p.add_argument("--apply", action="store_true")
    p.add_argument(
        "--no-quarantine",
        action="store_true",
        help="Skip quarantining empty-anchor event_episode_links",
    )
    args = p.parse_args()
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        p.error("Pass --domain KEY or --all")
    apply = bool(args.apply)
    logger.info(
        "mode=%s min_articles=%s extreme=%s protect_signed=%s domains=%s",
        "APPLY" if apply else "DRY-RUN",
        args.min_articles,
        args.extreme_articles,
        args.protect_signed,
        domains,
    )
    all_stats = []
    for dk in domains:
        st = migrate_domain(
            dk,
            min_articles=args.min_articles,
            apply=apply,
            quarantine_related=not args.no_quarantine,
            protect_signed=bool(args.protect_signed),
            extreme_articles=int(args.extreme_articles),
        )
        all_stats.append(st)
        logger.info("stats %s", st)
    print(json.dumps(all_stats, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
