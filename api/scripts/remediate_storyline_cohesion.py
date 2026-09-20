#!/usr/bin/env python3
"""
Remediate kitchen-sink storylines with hub-aware durable cohesion (post hub-facets).

Picks the article core that *maximizes* how many members share ≥ min_shared
*non-hub* durable canonicals (or --keeper-article-ids), unlinks the rest,
rebuilds SEI (with hub who/what/where roles), detaches chronological_events.

Default min_shared=1 (hub exclusion is the repair). Use --strict for chemistry
domain min (often 2). Hub institutions never count toward keep/unlink.

  # Single / list
  PYTHONPATH=api python3 api/scripts/remediate_storyline_cohesion.py \\
    --domain legal --storyline-id 3822 --dry-run
  PYTHONPATH=api python3 api/scripts/remediate_storyline_cohesion.py \\
    --domain legal --storyline-id 3822,3856 --apply --retitle

  # Scan mega-bags (article_count ≥ N) and remediate
  PYTHONPATH=api python3 api/scripts/remediate_storyline_cohesion.py \\
    --domain legal --scan-min-articles 30 --dry-run
  PYTHONPATH=api python3 api/scripts/remediate_storyline_cohesion.py \\
    --domain legal --scan-min-articles 30 --apply --max-scan 25
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))


def _parse_ids(raw: str) -> list[int]:
    out: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    return out


def _min_shared_for_domain(domain_key: str, *, strict: bool) -> int:
    if not strict:
        return 1
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        return int(get_domain_synthesis_config(domain_key).membership_min_shared_non_hub())
    except Exception:
        return 1


def _max_keep_core(
    art_cids: dict[int, list[int]],
    shared_durable_canonical_count,
    *,
    need: int,
    prefer_aids: set[int] | None = None,
) -> int:
    """
    Choose the article core that maximizes how many members would be kept
    under hub-excluded durable overlap ≥ need.
    """
    candidates = [a for a in (prefer_aids or art_cids) if art_cids.get(a)]
    if not candidates:
        candidates = list(art_cids) or [0]
    best_aid = candidates[0]
    best_keep = -1
    best_tie = -1
    for aid in candidates:
        core = set(art_cids.get(aid) or [])
        if not core:
            keep_n = 1  # only itself
            tie = 0
        else:
            keep_n = 0
            tie = 0
            for oid, other in art_cids.items():
                if oid == aid:
                    keep_n += 1
                    continue
                n = shared_durable_canonical_count(list(core), other or [])
                if n >= need:
                    keep_n += 1
                    tie += n
        if keep_n > best_keep or (keep_n == best_keep and tie > best_tie):
            best_keep = keep_n
            best_tie = tie
            best_aid = int(aid)
    return int(best_aid)


def _retitle_from_article(conn, schema: str, article_id: int) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT LEFT(COALESCE(title, ''), 200) FROM {schema}.articles WHERE id = %s",
            (article_id,),
        )
        row = cur.fetchone()
    title = (row[0] or "").strip() if row else ""
    return title or None


def _looks_like_digest_title(title: str | None) -> bool:
    t = (title or "").strip().lower()
    if not t:
        return True
    digests = (
        "morning docket",
        "stat pack",
        "evening brief",
        "news roundup",
        "daily digest",
        "weekend roundup",
        "the close",
        "| the close",
    )
    return any(d in t for d in digests)


def report_unlink_ratio_hint(unlink_n: int, member_n: int) -> float:
    return round(unlink_n / max(member_n, 1), 3)


def _scan_storyline_ids(
    conn,
    schema: str,
    *,
    min_articles: int,
    max_scan: int,
) -> list[int]:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT s.id
            FROM {schema}.storylines s
            WHERE s.merged_into_id IS NULL
              AND s.status NOT IN ('archived', 'concluded')
              AND COALESCE(
                    (SELECT COUNT(*) FROM {schema}.storyline_articles sa
                     WHERE sa.storyline_id = s.id),
                    0
                  ) >= %s
            ORDER BY COALESCE(
                (SELECT COUNT(*) FROM {schema}.storyline_articles sa
                 WHERE sa.storyline_id = s.id),
                0
            ) DESC
            LIMIT %s
            """,
            (int(min_articles), int(max_scan)),
        )
        return [int(r[0]) for r in cur.fetchall() or []]


def remediate_one(
    conn,
    *,
    domain_key: str,
    schema: str,
    storyline_id: int,
    keeper_article_ids: set[int] | None,
    apply: bool,
    retitle: bool,
    min_shared: int | None = None,
    strict: bool = False,
) -> dict:
    from shared.assembly_link_funnel import (
        article_durable_canonical_ids,
        shared_durable_canonical_count,
    )
    from shared.story_entity_index import (
        map_entity_type_for_sei,
        resolve_entity_role_for_sei,
    )

    need = max(
        1,
        int(
            min_shared
            if min_shared is not None
            else _min_shared_for_domain(domain_key, strict=strict)
        ),
    )

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT id, title, status, COALESCE(metadata->>'source', '')
            FROM {schema}.storylines
            WHERE id = %s
            """,
            (storyline_id,),
        )
        meta = cur.fetchone()
        if not meta:
            return {"storyline_id": storyline_id, "error": "not_found"}
        cur.execute(
            f"""
            SELECT a.id, LEFT(COALESCE(a.title, ''), 120)
            FROM {schema}.storyline_articles sa
            JOIN {schema}.articles a ON a.id = sa.article_id
            WHERE sa.storyline_id = %s
            ORDER BY sa.added_at NULLS LAST, a.id
            """,
            (storyline_id,),
        )
        members = [(int(r[0]), r[1] or "") for r in cur.fetchall()]

    if not members:
        return {
            "domain": domain_key,
            "storyline_id": storyline_id,
            "title": meta[1],
            "error": "no_members",
        }

    # Hub-excluded durables only — genre magnets never authorize keep
    art_cids = {
        aid: article_durable_canonical_ids(
            conn,
            schema,
            aid,
            domain_key=domain_key,
            exclude_hubs=True,
        )
        for aid, _ in members
    }
    with_non_hub = {aid for aid, cids in art_cids.items() if cids}

    if keeper_article_ids:
        keepers = {aid for aid in keeper_article_ids if aid in art_cids}
        if not keepers:
            return {
                "domain": domain_key,
                "storyline_id": storyline_id,
                "error": "keeper_articles_not_in_membership",
                "requested_keepers": sorted(keeper_article_ids),
            }
        core_aid = sorted(keepers)[0]
    else:
        core_aid = _max_keep_core(
            art_cids,
            shared_durable_canonical_count,
            need=need,
            prefer_aids=with_non_hub or None,
        )
        keepers = {core_aid}

    core_cids: set[int] = set()
    for aid in keepers:
        core_cids.update(art_cids.get(aid) or [])

    keep: list[int] = []
    unlink: list[int] = []
    unlink_reasons: dict[str, int] = {
        "no_core_anchors": 0,
        "hub_only_or_no_overlap": 0,
        "below_min_shared": 0,
    }
    for aid, _title in members:
        if aid in keepers:
            keep.append(aid)
            continue
        if not core_cids:
            unlink.append(aid)
            unlink_reasons["no_core_anchors"] += 1
            continue
        member_cids = art_cids.get(aid) or []
        if not member_cids:
            unlink.append(aid)
            unlink_reasons["hub_only_or_no_overlap"] += 1
            continue
        n = shared_durable_canonical_count(list(core_cids), member_cids)
        if n >= need:
            keep.append(aid)
        else:
            unlink.append(aid)
            unlink_reasons["below_min_shared"] += 1

    new_title = None
    if retitle and keep:
        old_t = (meta[1] or "").strip()
        should_retitle = False
        lower = old_t.lower()
        if lower.startswith("ongoing:") or lower.startswith("global "):
            should_retitle = True
        else:
            try:
                from services.storyline_coherence_guardrails import (
                    is_leaked_storyline_title,
                    is_placeholder_mega_title,
                )

                if is_leaked_storyline_title(old_t) or is_placeholder_mega_title(old_t):
                    should_retitle = True
            except Exception:
                pass
        if should_retitle or report_unlink_ratio_hint(len(unlink), len(members)) >= 0.5:
            candidate = _retitle_from_article(conn, schema, keep[0])
            # Avoid digest / docket wrap titles as the storyline label
            if candidate and not _looks_like_digest_title(candidate):
                new_title = candidate

    report = {
        "domain": domain_key,
        "storyline_id": storyline_id,
        "title_before": (meta[1] or "")[:160],
        "source": meta[3],
        "core_article": core_aid,
        "core_non_hub_durable_cids": sorted(core_cids),
        "min_shared_non_hub": need,
        "members_with_non_hub": len(with_non_hub),
        "member_count_before": len(members),
        "keep": keep,
        "unlink": unlink,
        "keep_n": len(keep),
        "unlink_n": len(unlink),
        "unlink_ratio": round(len(unlink) / max(len(members), 1), 3),
        "unlink_reasons": unlink_reasons,
        "title_after": new_title,
        "gate": "hub_excluded_durable_cohesion",
        "applied": False,
    }

    if not apply:
        return report

    with conn.cursor() as cur:
        if unlink:
            cur.execute(
                f"""
                DELETE FROM {schema}.storyline_articles
                WHERE storyline_id = %s AND article_id = ANY(%s)
                """,
                (storyline_id, unlink),
            )
            cur.execute(
                """
                UPDATE public.chronological_events
                SET storyline_id = ''
                WHERE source_article_id = ANY(%s)
                  AND storyline_id = %s::text
                """,
                (unlink, str(storyline_id)),
            )

        cur.execute(
            f"DELETE FROM {schema}.story_entity_index WHERE storyline_id = %s",
            (storyline_id,),
        )
        cur.execute(
            f"""
            SELECT ae.entity_name, ae.entity_type, ae.canonical_entity_id
            FROM {schema}.article_entities ae
            JOIN {schema}.storyline_articles sa ON sa.article_id = ae.article_id
            WHERE sa.storyline_id = %s AND ae.entity_name IS NOT NULL
            """,
            (storyline_id,),
        )
        buckets: dict[tuple[str, str], dict] = {}
        for name, etype, cid in cur.fetchall() or []:
            n = (name or "").strip()[:255]
            if len(n) < 2:
                continue
            sei_t = map_entity_type_for_sei(etype)
            key = (n.lower(), sei_t)
            if key not in buckets:
                erole, _hk = resolve_entity_role_for_sei(
                    domain_key=domain_key,
                    entity_name=n,
                    entity_type=etype,
                )
                buckets[key] = {
                    "name": n,
                    "type": sei_t,
                    "role": erole,
                    "count": 0,
                    "cid": int(cid) if cid is not None else None,
                }
            buckets[key]["count"] += 1
            if buckets[key]["cid"] is None and cid is not None:
                buckets[key]["cid"] = int(cid)
        for b in buckets.values():
            cur.execute(
                f"""
                INSERT INTO {schema}.story_entity_index
                    (storyline_id, entity_name, entity_type, entity_role,
                     mention_count, last_seen_at, canonical_entity_id)
                VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                ON CONFLICT (storyline_id, entity_name, entity_type) DO UPDATE SET
                    mention_count = EXCLUDED.mention_count,
                    entity_role = COALESCE(
                        NULLIF(EXCLUDED.entity_role, ''),
                        {schema}.story_entity_index.entity_role
                    ),
                    last_seen_at = NOW(),
                    canonical_entity_id = COALESCE(
                        {schema}.story_entity_index.canonical_entity_id,
                        EXCLUDED.canonical_entity_id
                    )
                """,
                (
                    storyline_id,
                    b["name"],
                    b["type"],
                    b["role"],
                    b["count"],
                    b["cid"],
                ),
            )

        remediation_meta = {
            "unlinked": len(unlink),
            "kept": len(keep),
            "core_article": core_aid,
            "min_shared_non_hub": need,
            "gate": "hub_excluded_durable_cohesion",
        }
        if new_title:
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET article_count = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                    ),
                    title = %s,
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{{}}'::jsonb) ||
                        jsonb_build_object('cohesion_remediation', %s::jsonb)
                WHERE id = %s
                """,
                (
                    storyline_id,
                    new_title[:500],
                    json.dumps(remediation_meta),
                    storyline_id,
                ),
            )
        else:
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET article_count = (
                        SELECT COUNT(*) FROM {schema}.storyline_articles
                        WHERE storyline_id = %s
                    ),
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{{}}'::jsonb) ||
                        jsonb_build_object('cohesion_remediation', %s::jsonb)
                WHERE id = %s
                """,
                (
                    storyline_id,
                    json.dumps(remediation_meta),
                    storyline_id,
                ),
            )

    report["applied"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remediate storyline membership with hub-excluded durable cohesion"
    )
    parser.add_argument("--domain", required=True, help="Domain key (e.g. legal)")
    parser.add_argument(
        "--storyline-id",
        default="",
        help="One id or comma-separated list (required unless --scan-min-articles)",
    )
    parser.add_argument(
        "--scan-min-articles",
        type=int,
        default=0,
        help="If >0, scan storylines with ≥N members instead of --storyline-id",
    )
    parser.add_argument(
        "--max-scan",
        type=int,
        default=50,
        help="Cap when using --scan-min-articles",
    )
    parser.add_argument(
        "--keeper-article-ids",
        default="",
        help="Optional comma-separated article ids to anchor (else plurality core)",
    )
    parser.add_argument(
        "--min-shared",
        type=int,
        default=None,
        help="Override non-hub durable overlap required (default: 1; use --strict for chemistry)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Use domain membership_min_shared_non_hub (often 2 for matter_docket)",
    )
    parser.add_argument(
        "--retitle",
        action="store_true",
        default=True,
        help="Retitle from first kept article (default on)",
    )
    parser.add_argument("--no-retitle", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.dry_run and not args.apply:
        print("Pass --dry-run or --apply", file=sys.stderr)
        return 2
    if not args.storyline_id and not args.scan_min_articles:
        print("Pass --storyline-id or --scan-min-articles", file=sys.stderr)
        return 2

    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import resolve_domain_schema

    schema = resolve_domain_schema(args.domain)
    keepers = set(_parse_ids(args.keeper_article_ids)) or None
    retitle = not args.no_retitle
    apply = bool(args.apply)

    reports = []
    with get_db_connection_context() as conn:
        if args.scan_min_articles:
            storyline_ids = _scan_storyline_ids(
                conn,
                schema,
                min_articles=args.scan_min_articles,
                max_scan=args.max_scan,
            )
        else:
            storyline_ids = _parse_ids(args.storyline_id)

        for sid in storyline_ids:
            reports.append(
                remediate_one(
                    conn,
                    domain_key=args.domain,
                    schema=schema,
                    storyline_id=sid,
                    keeper_article_ids=keepers,
                    apply=apply,
                    retitle=retitle,
                    min_shared=args.min_shared,
                    strict=bool(args.strict),
                )
            )
        if apply:
            conn.commit()

    # Compact stdout for scan mode
    compact = [
        {
            "id": r.get("storyline_id"),
            "title_before": r.get("title_before") or r.get("error"),
            "before": r.get("member_count_before"),
            "keep": r.get("keep_n"),
            "unlink": r.get("unlink_n"),
            "ratio": r.get("unlink_ratio"),
            "reasons": r.get("unlink_reasons"),
            "title_after": r.get("title_after"),
            "error": r.get("error"),
        }
        for r in reports
    ]
    print(json.dumps(compact if args.scan_min_articles else reports, indent=2))
    summary = {
        "domain": args.domain,
        "storylines": len(reports),
        "total_unlinked": sum(r.get("unlink_n") or 0 for r in reports),
        "total_kept": sum(r.get("keep_n") or 0 for r in reports),
        "gate": "hub_excluded_durable_cohesion",
        "applied": apply,
    }
    print(json.dumps(summary, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
