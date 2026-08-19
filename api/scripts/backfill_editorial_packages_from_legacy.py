#!/usr/bin/env python3
"""Seed editorial packages from existing storylines (no new intake).

Creates one draft package per non-merged storyline with ≥1 membership, attaches
typed members via joins, and optionally imports legacy prose as unpublished
news_story drafts (citation revalidation required before publish).

  set -a; source .env.dev; set +a
  PYTHONPATH=api python3 api/scripts/backfill_editorial_packages_from_legacy.py --dry-run
  PYTHONPATH=api python3 api/scripts/backfill_editorial_packages_from_legacy.py --domain politics --limit 10
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

_API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API)

from shared.dev_guard import DevGuardError, assert_dev_db_host_safe  # noqa: E402
from shared.database.connection import get_db_connection_context  # noqa: E402
from shared.domain_registry import (  # noqa: E402
    get_active_domain_keys,
    resolve_domain_schema,
)
from services.editorial_package_service import (  # noqa: E402
    add_member,
    create_package,
    find_package_by_legacy_seed,
    primary_modal_for_domain,
    update_package,
)
from services.news_story_service import create_or_update_draft  # noqa: E402

logger = logging.getLogger(__name__)


def _legacy_seed(domain_key: str, storyline_id: int) -> str:
    return f"storyline:{domain_key}:{int(storyline_id)}"


def _prose_from_editorial_document(doc: Any, canonical: Any) -> tuple[str, str]:
    """Return (lede, body_md) from legacy columns."""
    lede = ""
    parts: list[str] = []
    if isinstance(doc, str):
        try:
            doc = json.loads(doc)
        except Exception:
            doc = None
    if isinstance(doc, dict):
        lede = str(doc.get("lede") or "").strip()
        for key in ("developments", "analysis", "background", "outlook"):
            val = doc.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(f"## {key.title()}\n\n{val.strip()}")
            elif isinstance(val, list):
                bullets = []
                for item in val:
                    if isinstance(item, str) and item.strip():
                        bullets.append(f"- {item.strip()}")
                    elif isinstance(item, dict):
                        t = item.get("text") or item.get("summary") or item.get("title")
                        if t:
                            bullets.append(f"- {str(t).strip()}")
                if bullets:
                    parts.append(f"## {key.title()}\n\n" + "\n".join(bullets))
        if doc.get("body") and isinstance(doc["body"], str):
            parts.append(doc["body"].strip())
    if not parts and canonical:
        text = str(canonical).strip()
        if text:
            parts.append(text)
    body = "\n\n".join(parts).strip()
    return lede, body


def _presentation_kind(readiness: dict[str, Any] | None) -> str:
    r = readiness or {}
    if r.get("hybrid_ready"):
        return "hybrid"
    if r.get("event_narrative_ready"):
        return "event_narrative"
    if r.get("research_brief_ready"):
        return "research_brief"
    return "unset"


def _seed_one(
    *,
    domain_key: str,
    schema: str,
    row: dict[str, Any],
    dry_run: bool,
    max_claims: int,
    import_prose: bool,
) -> dict[str, Any]:
    sid = int(row["id"])
    seed = _legacy_seed(domain_key, sid)
    title = (row.get("title") or f"Storyline {sid}").strip()
    existing = find_package_by_legacy_seed(seed)
    stats: dict[str, Any] = {
        "domain_key": domain_key,
        "storyline_id": sid,
        "legacy_seed": seed,
        "created": False,
        "package_id": None,
        "members_added": 0,
        "prose_imported": False,
        "dry_run": dry_run,
    }
    if dry_run:
        stats["package_id"] = existing["id"] if existing else None
        stats["would_create"] = existing is None
        return stats

    if existing:
        package_id = int(existing["id"])
    else:
        pkg = create_package(
            working_title=title[:500],
            summary_stub=f"Legacy seed from {domain_key} storyline {sid}",
            primary_modal=primary_modal_for_domain(domain_key),
            created_by="legacy_backfill",
            domain_keys=[domain_key],
            actor="legacy_backfill",
            metadata={
                "legacy_seed": seed,
                "source_storyline_id": sid,
                "source_domain_key": domain_key,
                "seeded_by": "system",
            },
            status="draft",
        )
        package_id = int(pkg["id"])
        stats["created"] = True
    stats["package_id"] = package_id

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            # Articles via storyline_articles
            cur.execute(
                f"""
                SELECT a.id, a.title, a.url, LEFT(COALESCE(a.content, a.summary, ''), 400) AS snippet
                FROM {schema}.storyline_articles sa
                JOIN {schema}.articles a ON a.id = sa.article_id
                WHERE sa.storyline_id = %s
                ORDER BY sa.article_id
                """,
                (sid,),
            )
            articles = [
                {"id": r[0], "title": r[1], "url": r[2], "snippet": r[3]}
                for r in cur.fetchall()
            ]
            article_ids = [int(a["id"]) for a in articles]

            contexts: list[dict[str, Any]] = []
            if article_ids:
                cur.execute(
                    """
                    SELECT DISTINCT c.id, c.title, LEFT(COALESCE(c.content, ''), 400) AS snippet,
                           atc.article_id, c.domain_key
                    FROM intelligence.article_to_context atc
                    JOIN intelligence.contexts c ON c.id = atc.context_id
                    WHERE atc.domain_key = %s AND atc.article_id = ANY(%s)
                    ORDER BY c.id
                    LIMIT 200
                    """,
                    (domain_key, article_ids),
                )
                contexts = [
                    {
                        "id": r[0],
                        "title": r[1],
                        "snippet": r[2],
                        "article_id": r[3],
                        "domain_key": r[4],
                    }
                    for r in cur.fetchall()
                ]

            context_ids = [int(c["id"]) for c in contexts]
            claims: list[dict[str, Any]] = []
            if context_ids:
                cur.execute(
                    """
                    SELECT ec.id, ec.context_id,
                           COALESCE(ec.subject_text, '') || ' ' ||
                           COALESCE(ec.predicate_text, '') || ' ' ||
                           COALESCE(ec.object_text, '') AS text,
                           ec.confidence
                    FROM intelligence.extracted_claims ec
                    WHERE ec.context_id = ANY(%s)
                    ORDER BY ec.confidence DESC NULLS LAST, ec.id DESC
                    LIMIT %s
                    """,
                    (context_ids, max_claims),
                )
                claims = [
                    {"id": r[0], "context_id": r[1], "text": (r[2] or "").strip(), "confidence": r[3]}
                    for r in cur.fetchall()
                ]

            events: list[dict[str, Any]] = []
            try:
                if article_ids:
                    cur.execute(
                        """
                        SELECT id, title, source_text, source_article_id, location
                        FROM public.chronological_events
                        WHERE storyline_id = %s
                           OR source_article_id = ANY(%s)
                        ORDER BY actual_event_date DESC NULLS LAST, id DESC
                        LIMIT 50
                        """,
                        (sid, article_ids),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id, title, source_text, source_article_id, location
                        FROM public.chronological_events
                        WHERE storyline_id = %s
                        ORDER BY actual_event_date DESC NULLS LAST, id DESC
                        LIMIT 50
                        """,
                        (sid,),
                    )
                events = [
                    {
                        "id": r[0],
                        "title": r[1],
                        "source_text": r[2],
                        "source_article_id": r[3],
                        "location": r[4],
                    }
                    for r in cur.fetchall()
                ]
            except Exception as e:
                logger.debug("chronological_events lookup skipped: %s", e)

    for a in articles:
        url = (a.get("url") or "").strip()
        if not url:
            continue
        add_member(
            package_id,
            member_type="article",
            member_id=int(a["id"]),
            member_family="research",
            domain_key=domain_key,
            role="supporting",
            added_by_modal="system",
            added_by="legacy_backfill",
            provenance={
                "label": (a.get("title") or "")[:240],
                "source_url": url,
                "quote": (a.get("snippet") or "").strip()[:500] or None,
                "article_id": a["id"],
                "legacy_seed": seed,
            },
            actor="legacy_backfill",
        )
        stats["members_added"] += 1

    for c in contexts:
        add_member(
            package_id,
            member_type="context",
            member_id=int(c["id"]),
            member_family="research",
            domain_key=c.get("domain_key") or domain_key,
            role="supporting",
            added_by_modal="system",
            added_by="legacy_backfill",
            provenance={
                "label": (c.get("title") or "")[:240],
                "quote": (c.get("snippet") or "").strip()[:500] or None,
                "article_id": c.get("article_id"),
                "legacy_seed": seed,
            },
            actor="legacy_backfill",
        )
        stats["members_added"] += 1

    for cl in claims:
        add_member(
            package_id,
            member_type="extracted_claim",
            member_id=int(cl["id"]),
            member_family="research",
            domain_key=domain_key,
            role="core_claim",
            added_by_modal="system",
            added_by="legacy_backfill",
            provenance={
                "label": (cl.get("text") or "")[:240],
                "quote": (cl.get("text") or "")[:500] or None,
                "context_id": cl.get("context_id"),
                "legacy_seed": seed,
            },
            actor="legacy_backfill",
        )
        stats["members_added"] += 1

    for ev in events:
        quote = (ev.get("source_text") or "").strip()[:500] or None
        add_member(
            package_id,
            member_type="chronological_event",
            member_id=int(ev["id"]),
            member_family="narrative",
            domain_key=domain_key,
            role="anchor_event",
            added_by_modal="system",
            added_by="legacy_backfill",
            provenance={
                "label": (ev.get("title") or "")[:240],
                "quote": quote,
                "article_id": ev.get("source_article_id"),
                "location": ev.get("location"),
                "legacy_seed": seed,
            },
            actor="legacy_backfill",
        )
        stats["members_added"] += 1

    from services.editorial_package_service import get_package

    pkg = get_package(package_id)
    readiness = (pkg or {}).get("readiness") or {}
    kind = _presentation_kind(readiness if isinstance(readiness, dict) else {})
    rail = primary_modal_for_domain(domain_key)
    if kind != "unset" or rail in ("research", "narrative"):
        # Prefer the domain's modal rail over presentation_kind alone — research_brief_ready
        # can be true on narrative silos when claims were seeded, which incorrectly parked
        # packages in in_research and starved editorial_narrative_pass.
        if rail == "research":
            status = "in_research"
        elif rail == "narrative":
            status = "in_narrative"
        else:
            status = "in_research" if kind == "research_brief" else "in_narrative"
        update_package(
            package_id,
            presentation_kind=kind if kind != "unset" else None,
            status=status,
            primary_modal=rail,
            actor="legacy_backfill",
            modal=rail,
            rationale="legacy seed rail + presentation_kind",
        )

    if import_prose:
        lede, body = _prose_from_editorial_document(
            row.get("editorial_document"),
            row.get("canonical_narrative"),
        )
        if body or lede:
            # Draft save emits a single citation_gap via emit_citation_gap_handoff
            # (do not also create_handoff here — that duplicated system→editor alerts).
            create_or_update_draft(
                package_id,
                title=title[:500],
                lede=lede or None,
                body_md=body or lede,
                presentation_kind=kind if kind != "unset" else None,
                created_by="legacy_backfill",
                actor="legacy_backfill",
            )
            stats["prose_imported"] = True

    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        assert_dev_db_host_safe()
    except DevGuardError as e:
        print(f"Refused: {e}", file=sys.stderr)
        return 2

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--domain", action="append", dest="domains", help="Limit to domain_key")
    p.add_argument("--limit", type=int, default=0, help="Max storylines per domain (0=all)")
    p.add_argument("--max-claims", type=int, default=25)
    p.add_argument("--no-prose", action="store_true", help="Skip news_story draft import")
    args = p.parse_args()

    domains = args.domains or list(get_active_domain_keys())
    results: list[dict[str, Any]] = []
    for dk in domains:
        try:
            schema = resolve_domain_schema(dk)
        except Exception as e:
            logger.warning("skip domain %s: %s", dk, e)
            continue
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                sql = f"""
                    SELECT s.id, s.title, s.editorial_document, s.canonical_narrative
                    FROM {schema}.storylines s
                    WHERE s.merged_into_id IS NULL
                      AND EXISTS (
                        SELECT 1 FROM {schema}.storyline_articles sa
                        WHERE sa.storyline_id = s.id
                      )
                    ORDER BY s.id
                """
                if args.limit and args.limit > 0:
                    sql += f" LIMIT {int(args.limit)}"
                cur.execute(sql)
                cols = [d[0] for d in cur.description]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]

        logger.info("%s: %d candidate storylines", dk, len(rows))
        for row in rows:
            try:
                stats = _seed_one(
                    domain_key=dk,
                    schema=schema,
                    row=row,
                    dry_run=args.dry_run,
                    max_claims=args.max_claims,
                    import_prose=not args.no_prose,
                )
                results.append(stats)
                logger.info(
                    "  storyline %s → package %s created=%s members=%s prose=%s",
                    stats["storyline_id"],
                    stats["package_id"],
                    stats.get("created") or stats.get("would_create"),
                    stats["members_added"],
                    stats["prose_imported"],
                )
            except Exception as e:
                logger.exception("failed storyline %s/%s: %s", dk, row.get("id"), e)
                results.append(
                    {
                        "domain_key": dk,
                        "storyline_id": row.get("id"),
                        "error": str(e),
                    }
                )

    created = sum(1 for r in results if r.get("created") or r.get("would_create"))
    print(
        json.dumps(
            {
                "domains": domains,
                "dry_run": args.dry_run,
                "candidates": len(results),
                "created_or_would_create": created,
                "results": results,
            },
            default=str,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
