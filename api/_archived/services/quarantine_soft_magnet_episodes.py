#!/usr/bin/env python3
"""
Quarantine soft-magnet thin episodes: high EEL count, weak title↔signature fit.

Demotes mismatched magnets to container_index, quarantines EELs, clears CE stamps.
Dry-run by default; pass --apply to write.

  PYTHONPATH=api python3 api/scripts/quarantine_soft_magnet_episodes.py --all
  PYTHONPATH=api python3 api/scripts/quarantine_soft_magnet_episodes.py --all --apply
  PYTHONPATH=api python3 api/scripts/quarantine_soft_magnet_episodes.py --domain politics --ids 5049 --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import re
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
logger = logging.getLogger("quarantine_soft_magnet_episodes")

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{2,}", re.I)


def _title_tokens(title: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(title or "")}


def _sig_name_tokens(sig: object) -> set[str]:
    if not isinstance(sig, dict):
        return set()
    out: set[str] = set()
    for x in list(sig.get("identity") or []) + list(sig.get("supporting") or []):
        s = str(x).strip().lower()
        if not s or s.startswith("cid:"):
            continue
        out |= _title_tokens(s)
        out.add(s)
    return out


def _title_sig_mismatch(title: str, sig: object) -> bool:
    """True when signature names share no token with the title."""
    names = _sig_name_tokens(sig)
    if not names:
        return True
    title_toks = _title_tokens(title)
    if not title_toks:
        return False
    # Any overlapping multi-char token counts as a fit
    return names.isdisjoint(title_toks)


def quarantine_domain(
    domain_key: str,
    *,
    apply: bool,
    min_eels: int,
    max_articles: int,
    only_ids: list[int] | None,
    lookback_hours: int | None,
) -> dict:
    schema = resolve_domain_schema(domain_key)
    stats = {
        "domain": domain_key,
        "candidates": 0,
        "demoted": 0,
        "eels_quarantined": 0,
        "ce_cleared": 0,
        "ids": [],
    }
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            params: list = [domain_key]
            age_sql = ""
            if lookback_hours is not None:
                age_sql = " AND s.created_at > NOW() - (%s || ' hours')::interval "
                params.append(str(int(lookback_hours)))
            id_sql = ""
            if only_ids:
                id_sql = " AND s.id = ANY(%s) "
                params.append(list(only_ids))
            params.extend([int(max_articles), int(min_eels)])
            cur.execute(
                f"""
                SELECT s.id, s.title, COALESCE(s.article_count, 0)::int,
                       s.anchor_signature,
                       (
                         SELECT COUNT(*)::int
                         FROM intelligence.event_episode_links e
                         WHERE e.domain_key = %s
                           AND e.episode_id = s.id
                           AND e.inference_stage <> 'quarantined'
                       ) AS eel_n
                FROM {schema}.storylines s
                WHERE COALESCE(s.story_kind, '') = 'event_narrative'
                  AND s.signature_locked_at IS NOT NULL
                  AND COALESCE(s.is_mega_storyline, FALSE) = FALSE
                  {age_sql}
                  {id_sql}
                  AND COALESCE(s.article_count, 0) <= %s
                ORDER BY s.id
                """,
                tuple(params),
            )
            rows = cur.fetchall() or []
            for sid, title, acount, sig, eel_n in rows:
                eel_n = int(eel_n or 0)
                if eel_n < int(min_eels) and not only_ids:
                    continue
                mismatch = _title_sig_mismatch(title or "", sig)
                # Explicit --ids always act; auto mode requires mismatch OR extreme EEL pile
                extreme = eel_n >= max(int(min_eels) * 2, 30)
                if only_ids:
                    act = True
                    reason = "explicit_id"
                elif mismatch:
                    act = True
                    reason = "title_signature_mismatch"
                elif extreme:
                    act = True
                    reason = "extreme_eel_pile"
                else:
                    continue
                stats["candidates"] += 1
                stats["ids"].append(int(sid))
                logger.info(
                    "[%s] magnet id=%s arts=%s eels=%s reason=%s title=%s",
                    domain_key,
                    sid,
                    acount,
                    eel_n,
                    reason,
                    (title or "")[:70],
                )
                if not apply:
                    continue
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET story_kind = 'container_index',
                        is_mega_storyline = TRUE,
                        automation_enabled = FALSE,
                        episode_state = 'concluded',
                        metadata = COALESCE(metadata, '{{}}'::jsonb)
                            || %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (
                        json.dumps(
                            {
                                "assembly_role": "container_index",
                                "demote_reason": "soft_magnet",
                                "magnet_reason": reason,
                                "magnet_eels_at_demote": eel_n,
                            }
                        ),
                        int(sid),
                    ),
                )
                cur.execute(
                    f"""
                    DELETE FROM {schema}.storyline_articles WHERE storyline_id = %s
                    """,
                    (int(sid),),
                )
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET article_count = 0, total_articles = 0, updated_at = NOW()
                    WHERE id = %s
                    """,
                    (int(sid),),
                )
                cur.execute(
                    """
                    UPDATE intelligence.event_episode_links
                    SET inference_stage = 'quarantined',
                        updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb)
                            || '{"quarantine_reason":"soft_magnet"}'::jsonb
                    WHERE domain_key = %s
                      AND episode_id = %s
                      AND inference_stage <> 'quarantined'
                    """,
                    (domain_key, int(sid)),
                )
                stats["eels_quarantined"] += cur.rowcount or 0
                cur.execute(
                    """
                    UPDATE public.chronological_events
                    SET storyline_id = ''
                    WHERE storyline_id = %s
                       OR storyline_id = %s
                    """,
                    (str(int(sid)), f"{schema}:{int(sid)}"),
                )
                stats["ce_cleared"] += cur.rowcount or 0
                stats["demoted"] += 1

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
    p.add_argument("--ids", type=int, nargs="*", help="Force-quarantine these episode ids")
    p.add_argument("--min-eels", type=int, default=15)
    p.add_argument("--max-articles", type=int, default=8)
    p.add_argument(
        "--lookback-hours",
        type=int,
        default=None,
        help="Only consider episodes created in this window (default: all)",
    )
    args = p.parse_args()
    domains = (
        list(get_pipeline_active_domain_keys())
        if args.all
        else ([args.domain] if args.domain else [])
    )
    if not domains:
        p.error("Pass --domain KEY or --all")
    out = []
    for dk in domains:
        st = quarantine_domain(
            dk,
            apply=bool(args.apply),
            min_eels=int(args.min_eels),
            max_articles=int(args.max_articles),
            only_ids=list(args.ids) if args.ids else None,
            lookback_hours=args.lookback_hours,
        )
        out.append(st)
        logger.info("stats %s", st)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
