#!/usr/bin/env python3
"""
Event-core quality-type metrics + selective backfill + TE↔storyline facets.

Quality type (cyclosporiasis is an *example*, not the scoreboard):
  - Distinctive identity (rare name / instrument ID / bounded episode)
  - Multi-article co-reference
  - Anti-mega-absorb (not swallowed by geopolitics bags)
  - Cross-domain facet potential

  PYTHONPATH=api python3 api/scripts/event_core_pilot_metrics.py
  PYTHONPATH=api python3 api/scripts/event_core_pilot_metrics.py --backfill --apply
  PYTHONPATH=api python3 api/scripts/event_core_pilot_metrics.py --link-facets --apply
  PYTHONPATH=api python3 api/scripts/event_core_pilot_metrics.py --probe-kinds
  PYTHONPATH=api python3 api/scripts/event_core_pilot_metrics.py --example cyclosporiasis

No full-corpus reprocess — quality-type founding paths only.

Facet semantics (conservative): one dominant active storyline per TE+domain —
the storyline holding the most event_article_membership member articles in that
domain. Uses link_te_storyline_facet (UNIQUE-safe). See STORYLINE_CANONICAL_MODEL
+ docs/reviews/assembly_connection_pack/OPERATOR_ANSWERS.md.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("event_core_pilot")

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT / "api") not in sys.path:
    sys.path.insert(0, str(_ROOT / "api"))

# Illustrative examples of the quality type — NOT the exclusive scoreboard.
QUALITY_TYPE_EXAMPLES_DEFAULT = (
    "cyclosporiasis",
    "cyclospora",
    "hantavirus",
    "lettuce recall",
)


def _domains():
    try:
        from shared.domain_registry import get_pipeline_active_domain_keys

        return list(get_pipeline_active_domain_keys() or [])
    except Exception:
        return ["politics", "medicine", "finance", "legal", "artificial-intelligence"]


def _schema(domain_key: str) -> str:
    from shared.domain_registry import resolve_domain_schema

    return resolve_domain_schema(domain_key)


def measure_quality_type(conn) -> dict:
    """
    Score event-core TEs on quality-type dimensions (not cyclosporiasis-only).
    """
    out: dict = {
        "scoreboard": "quality_type",
        "note": (
            "cyclosporiasis is one example of the quality type; "
            "metrics score all anchored TEs + founding path coverage"
        ),
        "te_with_anchors": 0,
        "typed_membership_rows": 0,
        "facet_rows": 0,
        "multi_article_tes": 0,
        "cross_domain_tes": 0,
        "mega_absorb_suspects": [],
        "by_anchor_kind": {},
        "quality_episodes": [],
    }
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM intelligence.tracked_events
            WHERE anchors IS NOT NULL AND anchors <> '[]'::jsonb
            """
        )
        out["te_with_anchors"] = int(cur.fetchone()[0] or 0)
        cur.execute("SELECT COUNT(*) FROM intelligence.event_article_membership")
        out["typed_membership_rows"] = int(cur.fetchone()[0] or 0)
        cur.execute(
            "SELECT COUNT(*) FROM intelligence.tracked_event_storyline_facets"
        )
        out["facet_rows"] = int(cur.fetchone()[0] or 0)

        cur.execute(
            """
            SELECT e->>'kind' AS kind, COUNT(*) AS n
            FROM intelligence.tracked_events t
            CROSS JOIN LATERAL jsonb_array_elements(COALESCE(t.anchors, '[]'::jsonb)) e
            GROUP BY 1
            ORDER BY n DESC
            """
        )
        out["by_anchor_kind"] = {
            (r[0] or "unknown"): int(r[1] or 0) for r in (cur.fetchall() or [])
        }

        cur.execute(
            """
            SELECT te.id, te.event_name,
                   COALESCE(te.anchors->0->>'value', '') AS primary_anchor,
                   COALESCE(te.anchors->0->>'kind', '') AS primary_kind,
                   COUNT(DISTINCT m.article_id) AS n_articles,
                   COUNT(DISTINCT m.domain_key) AS n_domains,
                   ARRAY_AGG(DISTINCT m.domain_key) FILTER (WHERE m.domain_key IS NOT NULL)
                     AS domains
            FROM intelligence.tracked_events te
            LEFT JOIN intelligence.event_article_membership m
              ON m.tracked_event_id = te.id
            WHERE te.anchors IS NOT NULL AND te.anchors <> '[]'::jsonb
            GROUP BY te.id, te.event_name
            ORDER BY n_articles DESC NULLS LAST, te.id
            LIMIT 50
            """
        )
        rows = cur.fetchall() or []
        for (
            te_id,
            name,
            anchor,
            kind,
            n_arts,
            n_doms,
            domains,
        ) in rows:
            n_arts = int(n_arts or 0)
            n_doms = int(n_doms or 0)
            if n_arts >= 2:
                out["multi_article_tes"] += 1
            if n_doms >= 2:
                out["cross_domain_tes"] += 1
            out["quality_episodes"].append(
                {
                    "tracked_event_id": int(te_id),
                    "event_name": (name or "")[:120],
                    "anchor": anchor,
                    "kind": kind,
                    "n_articles": n_arts,
                    "n_domains": n_doms,
                    "domains": list(domains or []),
                    "passes_multi_article": n_arts >= 2,
                    "passes_cross_domain": n_doms >= 2,
                }
            )

        # Mega-absorb contamination: quality-anchor articles sitting in fat bags
        # without typed membership for that TE.
        from services.event_core_membership_service import find_quality_anchors_in_text

        for dk in _domains():
            schema = _schema(dk)
            try:
                cur.execute(
                    f"""
                    SELECT a.id, a.title, s.id, LEFT(s.title, 80),
                           (SELECT COUNT(*) FROM {schema}.storyline_articles sa2
                            WHERE sa2.storyline_id = s.id) AS n_links,
                           LEFT(COALESCE(a.title,'') || ' ' || COALESCE(a.summary,''), 500)
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    JOIN {schema}.storylines s ON s.id = sa.storyline_id AND s.status = 'active'
                    WHERE (SELECT COUNT(*) FROM {schema}.storyline_articles sa2
                           WHERE sa2.storyline_id = s.id) >= 40
                    LIMIT 120
                    """
                )
                bag_rows = cur.fetchall() or []
            except Exception as e:
                logger.debug("mega scan %s: %s", dk, e)
                try:
                    conn.rollback()
                except Exception:
                    pass
                continue
            for aid, title, sid, stitle, n_links, blob in bag_rows:
                hits = find_quality_anchors_in_text(blob or "")
                if not hits:
                    continue
                for hit in hits:
                    cur.execute(
                        """
                        SELECT 1 FROM intelligence.event_article_membership
                        WHERE domain_key = %s AND article_id = %s
                          AND lower(anchor_ref) = %s
                        LIMIT 1
                        """,
                        (dk, aid, hit["value"]),
                    )
                    if cur.fetchone():
                        continue
                    out["mega_absorb_suspects"].append(
                        {
                            "domain": dk,
                            "article_id": aid,
                            "article_title": (title or "")[:100],
                            "storyline_id": sid,
                            "storyline_title": stitle,
                            "n_links": int(n_links or 0),
                            "anchor": hit["value"],
                            "kind": hit["kind"],
                        }
                    )

    multi = out["multi_article_tes"]
    te_n = out["te_with_anchors"] or 1
    out["multi_article_rate"] = round(multi / te_n, 3)
    out["cross_domain_rate"] = round(out["cross_domain_tes"] / te_n, 3)
    suspects = len(out["mega_absorb_suspects"])
    te_m = out["typed_membership_rows"]
    denom = suspects + te_m
    out["untyped_mega_ratio_proxy"] = (
        round(suspects / denom, 3) if denom else None
    )
    return out


def measure_examples(conn, examples: list[str]) -> dict:
    """Spot-check illustrative examples (including cyclosporiasis) — not the scoreboard."""
    out: dict = {"role": "illustrative_examples_only", "examples": examples, "per": {}}
    with conn.cursor() as cur:
        for a in examples:
            per = {"articles": 0, "in_mega_storylines": 0, "te_membership": 0}
            for dk in _domains():
                schema = _schema(dk)
                try:
                    cur.execute(
                        f"""
                        SELECT a.id, s.id,
                               (SELECT COUNT(*) FROM {schema}.storyline_articles sa2
                                WHERE sa2.storyline_id = s.id) AS n_links
                        FROM {schema}.articles a
                        LEFT JOIN {schema}.storyline_articles sa ON sa.article_id = a.id
                        LEFT JOIN {schema}.storylines s
                          ON s.id = sa.storyline_id AND s.status = 'active'
                        WHERE lower(COALESCE(a.title, '') || ' ' || COALESCE(a.summary, ''))
                              LIKE %s
                        LIMIT 200
                        """,
                        (f"%{a}%",),
                    )
                    rows = cur.fetchall() or []
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    continue
                for _aid, sid, n_links in rows:
                    per["articles"] += 1
                    if sid and int(n_links or 0) >= 40:
                        per["in_mega_storylines"] += 1
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.event_article_membership
                WHERE lower(anchor_ref) = %s
                """,
                (a,),
            )
            per["te_membership"] = int(cur.fetchone()[0] or 0)
            out["per"][a] = per
    return out


def probe_founding_kinds(conn, *, limit_per_domain: int = 80) -> dict:
    """Runtime probe: what quality-anchor kinds exist in recent articles (H1/H3/H4)."""
    from services.event_core_membership_service import find_quality_anchors_in_text

    stats = {
        "scanned": 0,
        "with_any_anchor": 0,
        "by_kind": {},
        "sample_non_seed": [],
    }
    with conn.cursor() as cur:
        for dk in _domains():
            schema = _schema(dk)
            try:
                cur.execute(
                    f"""
                    SELECT id, title,
                           LEFT(COALESCE(title,'') || ' ' || COALESCE(summary,'')
                                || ' ' || COALESCE(content,''), 4500)
                    FROM {schema}.articles
                    ORDER BY COALESCE(published_at, created_at) DESC
                    LIMIT %s
                    """,
                    (limit_per_domain,),
                )
                rows = cur.fetchall() or []
            except Exception as e:
                logger.warning("probe %s: %s", dk, e)
                conn.rollback()
                continue
            for aid, title, blob in rows:
                stats["scanned"] += 1
                hits = find_quality_anchors_in_text(blob or "")
                if not hits:
                    continue
                stats["with_any_anchor"] += 1
                for h in hits:
                    k = h["kind"]
                    stats["by_kind"][k] = stats["by_kind"].get(k, 0) + 1
                    if k != "seed_example" and len(stats["sample_non_seed"]) < 25:
                        stats["sample_non_seed"].append(
                            {
                                "domain": dk,
                                "article_id": aid,
                                "title": (title or "")[:100],
                                "anchor": h["value"],
                                "kind": k,
                            }
                        )
    return stats


def backfill(conn, examples: list[str], *, apply: bool, limit_per_domain: int = 50) -> dict:
    """Selective backfill for illustrative examples + any quality hits in those articles."""
    from services.event_core_membership_service import found_and_attach_rare_anchors

    stats = {"scanned": 0, "attached": 0, "created_te": 0, "dry_run": not apply}
    with conn.cursor() as cur:
        for dk in _domains():
            schema = _schema(dk)
            for a in examples:
                try:
                    cur.execute(
                        f"""
                        SELECT id, title, summary, left(COALESCE(content, ''), 4000) AS content
                        FROM {schema}.articles
                        WHERE lower(COALESCE(title, '') || ' ' || COALESCE(summary, '')) LIKE %s
                        ORDER BY COALESCE(published_at, created_at) DESC
                        LIMIT %s
                        """,
                        (f"%{a}%", limit_per_domain),
                    )
                    cols = [d[0] for d in cur.description]
                    rows = [dict(zip(cols, r)) for r in (cur.fetchall() or [])]
                except Exception as e:
                    logger.warning("backfill query %s %s: %s", dk, a, e)
                    conn.rollback()
                    continue
                for art in rows:
                    stats["scanned"] += 1
                    if not apply:
                        continue
                    res = found_and_attach_rare_anchors(
                        cur, domain_key=dk, article=art, storyline_id=None
                    )
                    if res.get("created_te_ids"):
                        stats["created_te"] += len(res["created_te_ids"])
                    if res.get("attached_te_ids"):
                        stats["attached"] += len(res["attached_te_ids"])
        if apply:
            conn.commit()
        else:
            conn.rollback()
    return stats


def backfill_quality_scan(
    conn, *, apply: bool, limit_per_domain: int = 100
) -> dict:
    """
    Scan recent articles for any quality-type anchor (instrument / morph / seed)
    and found+attach — not limited to cyclosporiasis examples.
    """
    from services.event_core_membership_service import (
        find_quality_anchors_in_text,
        found_and_attach_rare_anchors,
    )

    stats = {
        "scanned": 0,
        "hit": 0,
        "attached": 0,
        "created_te": 0,
        "dry_run": not apply,
        "by_kind": {},
    }
    with conn.cursor() as cur:
        for dk in _domains():
            schema = _schema(dk)
            try:
                cur.execute(
                    f"""
                    SELECT id, title, summary, left(COALESCE(content, ''), 4000) AS content
                    FROM {schema}.articles
                    ORDER BY COALESCE(published_at, created_at) DESC
                    LIMIT %s
                    """,
                    (limit_per_domain,),
                )
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in (cur.fetchall() or [])]
            except Exception as e:
                logger.warning("quality scan %s: %s", dk, e)
                conn.rollback()
                continue
            for art in rows:
                stats["scanned"] += 1
                blob = " ".join(
                    [
                        str(art.get("title") or ""),
                        str(art.get("summary") or ""),
                        str(art.get("content") or ""),
                    ]
                )
                hits = find_quality_anchors_in_text(blob)
                if not hits:
                    continue
                stats["hit"] += 1
                for h in hits:
                    k = h["kind"]
                    stats["by_kind"][k] = stats["by_kind"].get(k, 0) + 1
                if not apply:
                    continue
                res = found_and_attach_rare_anchors(
                    cur, domain_key=dk, article=art, storyline_id=None
                )
                if res.get("created_te_ids"):
                    stats["created_te"] += len(res["created_te_ids"])
                if res.get("attached_te_ids"):
                    stats["attached"] += len(res["attached_te_ids"])
        if apply:
            conn.commit()
        else:
            conn.rollback()
    return stats


def link_facets(
    conn,
    *,
    apply: bool,
    te_ids: list[int] | None = None,
    ensure_projections: bool = True,
) -> dict:
    from services.event_core_membership_service import link_facets_from_article_membership

    return link_facets_from_article_membership(
        conn,
        tracked_event_ids=te_ids,
        apply=apply,
        ensure_projections=ensure_projections,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--example",
        action="append",
        dest="examples",
        help="Illustrative quality-type example (repeatable); not the scoreboard",
    )
    ap.add_argument(
        "--anchor",
        action="append",
        dest="examples",
        help="Alias for --example (legacy)",
    )
    ap.add_argument("--backfill", action="store_true", help="Backfill illustrative examples")
    ap.add_argument(
        "--quality-scan",
        action="store_true",
        help="Scan recent articles for any quality-type anchor and found+attach",
    )
    ap.add_argument(
        "--probe-kinds",
        action="store_true",
        help="Probe founding-path kinds in recent articles (no writes)",
    )
    ap.add_argument("--link-facets", action="store_true")
    ap.add_argument("--te-id", action="append", type=int, dest="te_ids")
    ap.add_argument("--no-ensure-projections", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    examples = [a.lower() for a in (args.examples or list(QUALITY_TYPE_EXAMPLES_DEFAULT))]

    from shared.database.connection import get_db_connection

    conn = get_db_connection()
    if not conn:
        logger.error("no db")
        return 1
    try:
        report: dict = {
            "quality_type": measure_quality_type(conn),
            "illustrative_examples": measure_examples(conn, examples),
        }
        if args.probe_kinds:
            report["probe_kinds"] = probe_founding_kinds(conn)
        if args.backfill:
            report["backfill"] = backfill(conn, examples, apply=bool(args.apply))
        if args.quality_scan:
            report["quality_scan"] = backfill_quality_scan(
                conn, apply=bool(args.apply)
            )
        if args.link_facets:
            report["link_facets"] = link_facets(
                conn,
                apply=bool(args.apply),
                te_ids=args.te_ids or None,
                ensure_projections=not bool(args.no_ensure_projections),
            )
        if args.json:
            print(json.dumps(report, default=str, indent=2))
        else:
            qt = report["quality_type"]
            logger.info(
                "QUALITY-TYPE scoreboard: te_anchored=%s membership=%s facets=%s "
                "multi_article=%s (rate=%s) cross_domain=%s (rate=%s) "
                "mega_suspects=%s untyped_mega_proxy=%s kinds=%s",
                qt["te_with_anchors"],
                qt["typed_membership_rows"],
                qt["facet_rows"],
                qt["multi_article_tes"],
                qt["multi_article_rate"],
                qt["cross_domain_tes"],
                qt["cross_domain_rate"],
                len(qt["mega_absorb_suspects"]),
                qt["untyped_mega_ratio_proxy"],
                qt["by_anchor_kind"],
            )
            for ep in (qt.get("quality_episodes") or [])[:15]:
                logger.info(
                    "  TE %s [%s/%s] arts=%s domains=%s %s",
                    ep["tracked_event_id"],
                    ep.get("kind"),
                    ep.get("anchor"),
                    ep["n_articles"],
                    ep["n_domains"],
                    (ep.get("event_name") or "")[:70],
                )
            ex = report["illustrative_examples"]
            logger.info("Illustrative examples (not scoreboard):")
            for a, per in (ex.get("per") or {}).items():
                logger.info(
                    "  %s: articles≈%s mega≈%s te_mem=%s",
                    a,
                    per["articles"],
                    per["in_mega_storylines"],
                    per["te_membership"],
                )
            if args.probe_kinds:
                logger.info("probe_kinds=%s", report.get("probe_kinds"))
            if args.backfill:
                logger.info("backfill=%s", report.get("backfill"))
            if args.quality_scan:
                logger.info("quality_scan=%s", report.get("quality_scan"))
            if args.link_facets:
                logger.info("link_facets=%s", report.get("link_facets"))
        return 0
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
