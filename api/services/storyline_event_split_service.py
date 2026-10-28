"""
Event-core split hygiene — propose splitting kitchen-sink bags into TE megathreads.

Phase 4: hygiene vocabulary gains "split". Default dry-run; apply only with
EVENT_CORE_SPLIT_APPLY=true and event-core flag on.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from config.runtime import env_bool
from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

logger = logging.getLogger(__name__)


def event_core_split_apply() -> bool:
    return env_bool("EVENT_CORE_SPLIT_APPLY", False)


def propose_storyline_splits(
    domain_key: str,
    *,
    min_members: int = 40,
    limit_storylines: int = 20,
) -> list[dict[str, Any]]:
    """
    For oversized storylines, group members by rare anchors found in titles.
    Each distinct rare anchor → proposed TE split (does not mutate unless apply).
    """
    from services.event_core_membership_service import (
        event_core_membership_enabled,
        find_rare_anchors_in_text,
        rare_anchor_lexicon,
    )

    if not event_core_membership_enabled():
        return []
    schema = resolve_domain_schema(domain_key)
    lexicon = rare_anchor_lexicon()
    proposals: list[dict[str, Any]] = []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT s.id, s.title, COUNT(sa.article_id)::int AS n
                FROM {schema}.storylines s
                JOIN {schema}.storyline_articles sa ON sa.storyline_id = s.id
                WHERE s.status = 'active'
                GROUP BY s.id, s.title
                HAVING COUNT(sa.article_id) >= %s
                ORDER BY COUNT(sa.article_id) DESC
                LIMIT %s
                """,
                (min_members, limit_storylines),
            )
            storylines = cur.fetchall() or []
            for sid, title, n in storylines:
                cur.execute(
                    f"""
                    SELECT a.id, a.title
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    """,
                    (sid,),
                )
                by_anchor: dict[str, list[int]] = defaultdict(list)
                for aid, atitle in cur.fetchall() or []:
                    hits = find_rare_anchors_in_text(atitle or "", lexicon=lexicon)
                    for h in hits:
                        by_anchor[h].append(int(aid))
                if len(by_anchor) < 2 and not by_anchor:
                    # No rare anchors — compound title heuristic only
                    proposals.append(
                        {
                            "domain": domain_key,
                            "storyline_id": int(sid),
                            "title": title,
                            "n_members": int(n),
                            "action": "review_no_rare_anchor",
                            "splits": [],
                        }
                    )
                    continue
                splits = [
                    {"anchor": a, "article_ids": ids, "n": len(ids)}
                    for a, ids in sorted(by_anchor.items(), key=lambda x: -len(x[1]))
                ]
                if len(splits) >= 1:
                    proposals.append(
                        {
                            "domain": domain_key,
                            "storyline_id": int(sid),
                            "title": title,
                            "n_members": int(n),
                            "action": "split_to_tracked_events",
                            "splits": splits,
                        }
                    )
    return proposals


def apply_split_proposals(
    proposals: list[dict[str, Any]],
    *,
    dry_run: bool | None = None,
) -> dict[str, Any]:
    """
    For each split anchor, mint TE + typed membership for listed articles.
    Does not unlink from the source bag unless EVENT_CORE_SPLIT_UNLINK=true.
    """
    from services.event_core_membership_service import (
        event_core_membership_enabled,
        found_and_attach_rare_anchors,
    )

    if not event_core_membership_enabled():
        return {"skipped": True, "reason": "flag_off"}
    apply = event_core_split_apply() if dry_run is None else (not dry_run)
    unlink = env_bool("EVENT_CORE_SPLIT_UNLINK", False)
    created = 0
    attached = 0
    unlinked = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for prop in proposals:
                if prop.get("action") != "split_to_tracked_events":
                    continue
                dk = prop["domain"]
                schema = resolve_domain_schema(dk)
                sid = int(prop["storyline_id"])
                for sp in prop.get("splits") or []:
                    anchor = sp["anchor"]
                    for aid in sp.get("article_ids") or []:
                        art = {"id": aid, "title": "", "summary": "", "content": anchor}
                        # Ensure title carries anchor for detector
                        cur.execute(
                            f"SELECT id, title, summary, left(COALESCE(content,''), 500) "
                            f"FROM {schema}.articles WHERE id = %s",
                            (aid,),
                        )
                        row = cur.fetchone()
                        if not row:
                            continue
                        art = {
                            "id": row[0],
                            "title": row[1],
                            "summary": row[2],
                            "content": row[3],
                        }
                        if not apply:
                            continue
                        res = found_and_attach_rare_anchors(
                            cur, domain_key=dk, article=art, storyline_id=None
                        )
                        if res.get("created_te_ids"):
                            created += len(res["created_te_ids"])
                        if res.get("attached_te_ids"):
                            attached += 1
                        if unlink:
                            cur.execute(
                                f"""
                                DELETE FROM {schema}.storyline_articles
                                WHERE storyline_id = %s AND article_id = %s
                                """,
                                (sid, aid),
                            )
                            unlinked += cur.rowcount
            if apply:
                conn.commit()
            else:
                conn.rollback()
    return {
        "dry_run": not apply,
        "te_created": created,
        "membership_attached": attached,
        "unlinked_from_bags": unlinked,
        "proposals": len(proposals),
    }


def run_event_core_split_hygiene(*, dry_run: bool = True) -> dict[str, Any]:
    """Scan all pipeline domains for split proposals; optionally apply."""
    all_props: list[dict[str, Any]] = []
    for dk in get_pipeline_active_domain_keys() or []:
        all_props.extend(propose_storyline_splits(dk))
    result = apply_split_proposals(all_props, dry_run=dry_run)
    result["proposal_count"] = len(all_props)
    result["proposals_sample"] = all_props[:10]
    return result
