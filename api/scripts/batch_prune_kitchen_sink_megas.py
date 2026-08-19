#!/usr/bin/env python3
"""
Batch-prune kitchen-sink mega storylines across all pipeline domains.

Strategy:
  1. Inventory storylines with member count > domain attach_hard_cap
  2. For each: try core dissimilar prune (fresh connection; capped passes)
  3. If still over cap: bulk title-anchor force-cap to attach_hard_cap

  PYTHONPATH=api python3 api/scripts/batch_prune_kitchen_sink_megas.py
  PYTHONPATH=api python3 api/scripts/batch_prune_kitchen_sink_megas.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Ensure api/ on path when run as script
_API = Path(__file__).resolve().parent.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

os.environ.setdefault("STORYLINE_CORE_PRUNE_MAX_UNLINKS", "2500")
os.environ.setdefault("STORYLINE_CORE_PRUNE_AUTO_APPLY", "true")
os.environ.setdefault("STORYLINE_CORE_PRUNE_ENABLED", "true")


def _fresh_conn():
    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        raise RuntimeError("no db connection")
    try:
        conn.rollback()
    except Exception:
        pass
    return conn


def sa_count(conn, schema: str, sid: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT COUNT(*) FROM {schema}.storyline_articles WHERE storyline_id = %s",
            (sid,),
        )
        return int(cur.fetchone()[0] or 0)


def sync_count(conn, schema: str, sid: int) -> int:
    with conn.cursor() as cur:
        cur.execute(
            f"""
            UPDATE {schema}.storylines s
            SET article_count = sub.n,
                total_articles = sub.n,
                updated_at = NOW()
            FROM (
              SELECT COUNT(*)::int AS n
              FROM {schema}.storyline_articles WHERE storyline_id = %s
            ) sub
            WHERE s.id = %s
            RETURNING s.article_count
            """,
            (sid, sid),
        )
        row = cur.fetchone()
    conn.commit()
    return int(row[0] or 0) if row else 0


def inventory(*, include_archived: bool = False, include_merged: bool = False) -> list[dict[str, Any]]:
    from shared.domain_registry import pipeline_url_schema_pairs
    from shared.storyline_attach_caps import attach_hard_cap

    conn = _fresh_conn()
    out: list[dict[str, Any]] = []
    try:
        with conn.cursor() as cur:
            for dk, schema in pipeline_url_schema_pairs():
                cap = attach_hard_cap(dk)
                status_sql = "TRUE" if include_archived else (
                    "COALESCE(s.status, 'active') NOT IN ('archived', 'merged')"
                )
                merged_sql = "TRUE" if include_merged else "s.merged_into_id IS NULL"
                cur.execute(
                    f"""
                    SELECT s.id, s.title, s.status, s.merged_into_id,
                           (SELECT COUNT(*) FROM {schema}.storyline_articles sa
                            WHERE sa.storyline_id = s.id) AS sa_n
                    FROM {schema}.storylines s
                    WHERE {merged_sql}
                      AND ({status_sql})
                    """
                )
                for sid, title, status, merged_into, sa_n in cur.fetchall() or []:
                    n = int(sa_n or 0)
                    if n <= cap:
                        continue
                    title_s = title or ""
                    out.append(
                        {
                            "domain": dk,
                            "schema": schema,
                            "id": int(sid),
                            "title": title_s,
                            "sa": n,
                            "cap": cap,
                            "status": status,
                            "merged_into_id": merged_into,
                            "shell": title_s.lower().startswith("ongoing:")
                            or "live update" in title_s.lower(),
                        }
                    )
            # Repair stale article_count on active unmerged rows
            for dk, schema in pipeline_url_schema_pairs():
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines s
                    SET article_count = sub.n, total_articles = sub.n
                    FROM (
                      SELECT storyline_id, COUNT(*)::int AS n
                      FROM {schema}.storyline_articles
                      GROUP BY storyline_id
                    ) sub
                    WHERE s.id = sub.storyline_id
                      AND COALESCE(s.article_count, 0) <> sub.n
                    """
                )
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines s
                    SET article_count = 0, total_articles = 0
                    WHERE merged_into_id IS NULL
                      AND COALESCE(article_count, 0) > 0
                      AND NOT EXISTS (
                        SELECT 1 FROM {schema}.storyline_articles sa
                        WHERE sa.storyline_id = s.id
                      )
                    """
                )
        conn.commit()
    finally:
        conn.close()
    out.sort(key=lambda m: m["sa"], reverse=True)
    return out


def force_title_cap(
    schema: str, sid: int, title: str, cap: int, *, dry_run: bool
) -> dict[str, Any]:
    from services.storyline_core_prune_service import (
        distinctive_title_anchors,
        member_matches_title_anchor,
        tokenize,
    )

    conn = _fresh_conn()
    try:
        anchors = distinctive_title_anchors(title)
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.id, a.title, COALESCE(sa.relevance_score, 0)
                FROM {schema}.storyline_articles sa
                JOIN {schema}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                """,
                (sid,),
            )
            rows = cur.fetchall() or []

        scored: list[tuple[int, float, int]] = []
        for aid, atitle, rel in rows:
            title_l = (atitle or "").lower()
            toks = tokenize(atitle or "")
            hit = 0
            if anchors:
                if member_matches_title_anchor(anchors, atitle or "", toks):
                    hit += 2
                hit += len(anchors & toks)
                for a in anchors:
                    if len(a) >= 5 and a in title_l:
                        hit += 1
            scored.append((hit, float(rel or 0), int(aid)))
        scored.sort(reverse=True)
        with_hit = [r for r in scored if r[0] > 0]
        keepers = with_hit[:cap] if with_hit else scored[: max(3, min(cap, 12))]
        keep_ids = {r[2] for r in keepers}
        drop_ids = [aid for _, _, aid in scored if aid not in keep_ids]

        if dry_run:
            return {
                "force_unlinked": 0,
                "would_unlink": len(drop_ids),
                "kept": len(keep_ids),
                "final": len(keep_ids),
                "anchors_n": len(anchors),
            }

        # Bulk delete for speed on multi-thousand megas
        with conn.cursor() as cur:
            if drop_ids:
                # Chunk to avoid huge ANY arrays
                for i in range(0, len(drop_ids), 500):
                    chunk = drop_ids[i : i + 500]
                    cur.execute(
                        f"""
                        DELETE FROM {schema}.storyline_articles
                        WHERE storyline_id = %s AND article_id = ANY(%s)
                        """,
                        (sid, chunk),
                    )
            # Clear narrative surfaces the UI prefers (editorial lede > analysis >
            # description). Membership prune alone leaves SCOTUS/climate ledes on
            # Hungary-chess style bags.
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET quality_metrics = COALESCE(quality_metrics, '{{}}'::jsonb) || %s::jsonb,
                    description = NULL,
                    ai_generated_description = NULL,
                    summary = NULL,
                    master_summary = NULL,
                    analysis_summary = NULL,
                    canonical_narrative = NULL,
                    timeline_summary = NULL,
                    synthesized_content = NULL,
                    synthesized_markdown = NULL,
                    editorial_document = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    json.dumps(
                        {
                            "kitchen_sink": True,
                            "narrative_cleared": True,
                            "narrative_cleared_reason": "batch_kitchen_sink_prune",
                            "membership_freeze": {
                                "reason": "batch_kitchen_sink_prune",
                                "frozen": True,
                            },
                        }
                    ),
                    sid,
                ),
            )
        conn.commit()
        final = sync_count(conn, schema, sid)
        return {
            "force_unlinked": len(drop_ids),
            "kept": len(keep_ids),
            "final": final,
            "anchors_n": len(anchors),
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass


def try_core_prune(domain: str, sid: int, cap: int) -> dict[str, Any]:
    """One core-prune pass with its own connection lifecycle; never share txn."""
    from services.storyline_core_prune_service import prune_dissimilar_parts

    try:
        stats = prune_dissimilar_parts(domain, sid, dry_run=False, count_only=False)
        return {
            "ok": True,
            "unlinked": int(stats.get("unlinked") or 0),
            "kept": stats.get("kept_members"),
            "kitchen_sink": stats.get("kitchen_sink"),
            "error": stats.get("error"),
        }
    except Exception as e:
        return {"ok": False, "unlinked": 0, "error": str(e)[:300]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force-only",
        action="store_true",
        help="Skip core prune; only title-anchor force-cap (safer for huge bags)",
    )
    parser.add_argument(
        "--max-core-size",
        type=int,
        default=800,
        help="Only attempt core prune when sa_count <= this (default 800)",
    )
    parser.add_argument(
        "--include-archived",
        action="store_true",
        help="Also prune archived storylines over the domain attach cap",
    )
    parser.add_argument(
        "--clear-merged-children",
        action="store_true",
        default=True,
        help="Delete leftover storyline_articles on merged_into_id children (default on)",
    )
    parser.add_argument(
        "--keep-merged-children",
        action="store_true",
        help="Do not clear memberships on merged-away child storylines",
    )
    args = parser.parse_args()

    if args.clear_merged_children and not args.keep_merged_children and not args.dry_run:
        from shared.domain_registry import pipeline_url_schema_pairs

        conn = _fresh_conn()
        try:
            with conn.cursor() as cur:
                for dk, schema in pipeline_url_schema_pairs():
                    cur.execute(
                        f"""
                        DELETE FROM {schema}.storyline_articles sa
                        USING {schema}.storylines s
                        WHERE sa.storyline_id = s.id
                          AND s.merged_into_id IS NOT NULL
                        """
                    )
                    deleted = cur.rowcount
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET article_count = 0, total_articles = 0, updated_at = NOW()
                        WHERE merged_into_id IS NOT NULL
                          AND COALESCE(article_count, 0) <> 0
                        """
                    )
                    print(f"cleared merged-child memberships {dk}: {deleted}")
            conn.commit()
        finally:
            conn.close()

    megas = inventory(include_archived=bool(args.include_archived))
    by_domain: dict[str, int] = {}
    for m in megas:
        by_domain[m["domain"]] = by_domain.get(m["domain"], 0) + 1

    print(f"TARGETS {len(megas)} dry_run={args.dry_run} force_only={args.force_only}")
    for dk, n in sorted(by_domain.items()):
        print(f"  {dk}: {n}")

    summary: list[dict[str, Any]] = []
    for i, m in enumerate(megas):
        dk, schema, sid, title, cap, before = (
            m["domain"],
            m["schema"],
            m["id"],
            m["title"],
            m["cap"],
            m["sa"],
        )
        print(
            f"[{i+1}/{len(megas)}] {dk}/{sid} before={before} cap={cap} "
            f"{'(shell) ' if m['shell'] else ''}{title[:55]!r}"
        )

        core_unlinked = 0
        if (
            not args.dry_run
            and not args.force_only
            and before <= args.max_core_size
            and before > cap
        ):
            for pass_i in range(1, 4):
                conn = _fresh_conn()
                n_now = sa_count(conn, schema, sid)
                conn.close()
                if n_now <= cap:
                    break
                stats = try_core_prune(dk, sid, cap)
                if not stats.get("ok"):
                    print(f"  core fail: {stats.get('error')}")
                    break
                u = int(stats.get("unlinked") or 0)
                core_unlinked += u
                conn = _fresh_conn()
                after_p = sa_count(conn, schema, sid)
                sync_count(conn, schema, sid)
                conn.close()
                print(f"  core pass {pass_i}: → {after_p} unlinked={u}")
                if u == 0:
                    break

        conn = _fresh_conn()
        after_core = sa_count(conn, schema, sid)
        conn.close()

        forced = False
        force_info: dict[str, Any] | None = None
        if after_core > cap or args.dry_run:
            # Force-cap if still over — also for huge bags skipped by core
            if after_core > cap or args.force_only or before > args.max_core_size:
                force_info = force_title_cap(
                    schema, sid, title, cap, dry_run=args.dry_run
                )
                forced = True
                print(
                    f"  FORCE: would={force_info.get('would_unlink')} "
                    f"unlinked={force_info.get('force_unlinked')} "
                    f"kept={force_info.get('kept')} final={force_info.get('final')}"
                )

        conn = _fresh_conn()
        final = sa_count(conn, schema, sid) if not args.dry_run else (
            force_info.get("final") if force_info else after_core
        )
        if not args.dry_run:
            sync_count(conn, schema, sid)
        conn.close()

        row = {
            "domain": dk,
            "id": sid,
            "before": before,
            "after": final,
            "core_unlinked": core_unlinked,
            "forced": forced,
            "ok": int(final or 0) <= cap,
            "title": title[:70],
        }
        summary.append(row)

    remaining = [] if args.dry_run else inventory()
    print("\n=== SUMMARY ===")
    print(
        f"processed={len(summary)} ok={sum(1 for s in summary if s['ok'])} "
        f"still_over={len(remaining)}"
    )
    for dk in sorted({s["domain"] for s in summary}):
        rows = [s for s in summary if s["domain"] == dk]
        print(
            f"  {dk}: {sum(1 for r in rows if r['ok'])}/{len(rows)} under cap; "
            f"core_unlinked={sum(r['core_unlinked'] for r in rows)}"
        )
    return 0 if not remaining else 1


if __name__ == "__main__":
    raise SystemExit(main())
