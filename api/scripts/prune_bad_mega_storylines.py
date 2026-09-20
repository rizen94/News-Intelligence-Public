#!/usr/bin/env python3
"""
Prune bad mega-storylines: placeholder titles (Ongoing: WHAT), JSON/prompt leaks,
and retired Mega-storyline covering… template descriptions.

Default is dry-run. With --apply:
  - If re-derived title is good and mega coherence passes → rename + refresh counts
  - Otherwise → unparent children, archive mega, clear is_mega_storyline / template desc
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone

from services.storyline_coherence_guardrails import (
    assess_mega_group_coherence,
    is_leaked_storyline_title,
    is_mega_template_description,
    is_overly_generic_storyline_title,
    is_placeholder_mega_title,
    mega_quality_score_for_title,
)
from services.storyline_consolidation_service import (
    StorylineInfo,
    _schema_for_domain,
    derive_mega_storyline_title,
    get_consolidation_service,
)
from shared.domain_registry import get_pipeline_active_domain_keys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_NOW = datetime.now(timezone.utc)


def _is_bad_mega_title(title: str | None) -> bool:
    if not title:
        return True
    if (
        is_placeholder_mega_title(title)
        or is_leaked_storyline_title(title)
        or is_overly_generic_storyline_title(title)
    ):
        return True
    # Derived junk from key_entities / earnings templates
    lower = (title or "").strip().lower()
    if lower.startswith("ongoing:"):
        rest = lower[len("ongoing:") :].strip()
        if "keywords" in rest or "entities" in rest or rest.startswith("ongoing"):
            return True
    return False


def _child_info(row: dict) -> StorylineInfo:
    ents = set()
    raw = row.get("key_entities")
    if isinstance(raw, dict):
        for k in raw.keys():
            if isinstance(k, str) and len(k) >= 3:
                ents.add(k.lower())
    title = row.get("title") or ""
    # Prefer title tokens via discovery-style extraction at prune time
    from services.ai_storyline_discovery import get_discovery_service

    try:
        ents |= get_discovery_service().extract_entities(title)
    except Exception:
        pass
    return StorylineInfo(
        id=int(row["id"]),
        title=title,
        description=row.get("description") or "",
        article_count=int(row.get("article_count") or 0),
        created_at=row.get("created_at") or _NOW,
        updated_at=row.get("updated_at") or _NOW,
        parent_id=row.get("parent_storyline_id"),
        is_mega=False,
        entities=ents,
    )


def prune_domain(domain_key: str, *, apply: bool) -> dict[str, int]:
    schema = _schema_for_domain(domain_key)
    svc = get_consolidation_service()
    stats = {"scanned": 0, "renamed": 0, "archived": 0, "templates_cleared": 0}
    conn = svc.get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title, description, article_count, status
                FROM {schema}.storylines
                WHERE COALESCE(is_mega_storyline, FALSE) = TRUE
                  AND merged_into_id IS NULL
                ORDER BY id
                """
            )
            megas = cur.fetchall()
            for row in megas:
                mega_id = int(row[0])
                title = row[1]
                description = row[2]
                stats["scanned"] += 1

                title_bad = _is_bad_mega_title(title)
                template_desc = is_mega_template_description(description)
                if not title_bad and not template_desc:
                    continue

                cur.execute(
                    f"""
                    SELECT id, title, description, article_count, created_at, updated_at,
                           parent_storyline_id, key_entities
                    FROM {schema}.storylines
                    WHERE parent_storyline_id = %s AND merged_into_id IS NULL
                    ORDER BY article_count DESC NULLS LAST, id
                    """,
                    (mega_id,),
                )
                child_rows = cur.fetchall()
                colnames = [d[0] for d in cur.description]
                children = [
                    _child_info(dict(zip(colnames, r))) for r in child_rows
                ]

                new_title = derive_mega_storyline_title(children) if children else ""
                coherent_ok, coherent_reason = (
                    assess_mega_group_coherence(domain_key, children)
                    if len(children) >= 2
                    else (False, "too_few_children")
                )
                can_rename = (
                    bool(children)
                    and coherent_ok
                    and not _is_bad_mega_title(new_title)
                    and not is_placeholder_mega_title(new_title)
                    and not is_leaked_storyline_title(new_title)
                )

                if can_rename:
                    logger.info(
                        "[%s] rename mega %s: %r -> %r",
                        domain_key,
                        mega_id,
                        title,
                        new_title,
                    )
                    stats["renamed"] += 1
                    if apply:
                        cur.execute(
                            f"""
                            UPDATE {schema}.storylines
                            SET title = %s,
                                quality_score = %s,
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                new_title,
                                mega_quality_score_for_title(new_title, coherent=True),
                                mega_id,
                            ),
                        )
                        svc._refresh_mega_counts_from_db(cur, schema, mega_id)
                    continue

                logger.info(
                    "[%s] archive mega %s title=%r reason=title_bad=%s template=%s "
                    "coherence=%s derived=%r children=%s",
                    domain_key,
                    mega_id,
                    title,
                    title_bad,
                    template_desc,
                    coherent_reason if children else "no_children",
                    new_title,
                    len(children),
                )
                stats["archived"] += 1
                if template_desc:
                    stats["templates_cleared"] += 1
                if apply:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET parent_storyline_id = NULL, updated_at = NOW()
                        WHERE parent_storyline_id = %s
                        """,
                        (mega_id,),
                    )
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET status = 'archived',
                            is_mega_storyline = FALSE,
                            description = NULL,
                            quality_score = %s,
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (
                            mega_quality_score_for_title(title, coherent=False),
                            mega_id,
                        ),
                    )

            # Clear leftover template descriptions on still-active megas with good titles
            cur.execute(
                f"""
                SELECT id, title, description FROM {schema}.storylines
                WHERE COALESCE(is_mega_storyline, FALSE) = TRUE
                  AND merged_into_id IS NULL
                  AND status IS DISTINCT FROM 'archived'
                  AND description ILIKE 'Mega-storyline covering%%'
                """
            )
            for mega_id, title, description in cur.fetchall():
                if _is_bad_mega_title(title):
                    continue  # handled above
                logger.info(
                    "[%s] clear template description on mega %s (%r)",
                    domain_key,
                    mega_id,
                    title,
                )
                if apply:
                    svc._refresh_mega_counts_from_db(cur, schema, int(mega_id))
                    stats["templates_cleared"] += 1
                else:
                    stats["templates_cleared"] += 1

            if apply:
                conn.commit()
            else:
                conn.rollback()
    except Exception as e:
        logger.error("[%s] prune failed: %s", domain_key, e)
        conn.rollback()
        raise
    finally:
        conn.close()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune bad mega-storylines")
    parser.add_argument(
        "--domain",
        action="append",
        help="Domain key (repeatable). Default: all pipeline-active domains.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes (default is dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report only (default). Kept for explicit runbooks.",
    )
    args = parser.parse_args()
    apply = bool(args.apply) and not args.dry_run
    domains = args.domain or list(get_pipeline_active_domain_keys())

    totals = {"scanned": 0, "renamed": 0, "archived": 0, "templates_cleared": 0}
    for domain_key in domains:
        stats = prune_domain(domain_key, apply=apply)
        logger.info("[%s] %s", domain_key, stats)
        for k, v in stats.items():
            totals[k] = totals.get(k, 0) + v

    logger.info(
        "Done. totals=%s apply=%s",
        totals,
        apply,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
