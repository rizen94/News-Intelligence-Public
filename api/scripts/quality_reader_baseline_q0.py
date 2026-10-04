#!/usr/bin/env python3
"""
Q0 instrument-first baseline for News reader failures F1–F11.

Writes a ranked markdown table (SQL metrics + automated hand-proxy scores).
True human hand scores can overwrite the proxy column later.

  PYTHONPATH=api python3 api/scripts/quality_reader_baseline_q0.py
  PYTHONPATH=api python3 api/scripts/quality_reader_baseline_q0.py --out docs/QUALITY_READER_BASELINE_Q0.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_API = Path(__file__).resolve().parents[1]
_ROOT = _API.parent
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from shared.database.connection import get_db_connection_context
from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema


def _schemas() -> list[tuple[str, str]]:
    out = []
    for dk in get_pipeline_active_domain_keys():
        try:
            out.append((dk, resolve_domain_schema(dk)))
        except Exception:
            continue
    return out or [("politics", "politics"), ("finance", "finance")]


def _magnet_threshold() -> int:
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        cfg = get_domain_synthesis_config("politics") or {}
        link = cfg.get("link_score_profile") or {}
        return int(link.get("max_member_articles") or 32)
    except Exception:
        return 32


def _fetch_home_slate(cur) -> list[dict[str, Any]]:
    """Reader-served morning expansions (same gates as home catalog)."""
    from datetime import date

    from services.vault_notes_registry_service import list_morning_expansions

    # Prefer today's slate; fall back to recent 2-day window (home_feed path).
    expansions = list_morning_expansions(briefing_day=date.today().isoformat(), limit=40)
    if not expansions:
        expansions = list_morning_expansions(briefing_day=None, limit=40)
    out: list[dict[str, Any]] = []
    for ex in expansions:
        out.append(
            {
                "id": ex.get("id"),
                "domain_key": ex.get("domain_key"),
                "storyline_id": ex.get("object_id"),
                "title": ex.get("title"),
                "body": ex.get("body_md") or ex.get("summary_md") or "",
                "lifecycle": "living",
                "note_status": "note_ready",
                "updated_at": ex.get("note_updated_at"),
                "metadata": ex.get("metadata") or {},
                "article_count": ex.get("article_count"),
            }
        )
    # Empty list is a real reader signal (no served slate) — do not fall back to
    # ungated inventory, which would inflate F1/F3 vs what Home actually shows.
    return out


def _storyline_row(cur, schema: str, sid: int) -> dict[str, Any] | None:
    cur.execute(
        f"""
        SELECT id, title, article_count, quality_score, status,
               editorial_document, updated_at, created_at
        FROM {schema}.storylines
        WHERE id = %s
        """,
        (sid,),
    )
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))


def _member_titles(cur, schema: str, sid: int, limit: int = 40) -> list[str]:
    # Prefer junction table if present
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = 'storyline_articles'
        """,
        (schema,),
    )
    if cur.fetchone():
        cur.execute(
            f"""
            SELECT a.title FROM {schema}.storyline_articles sa
            JOIN {schema}.articles a ON a.id = sa.article_id
            WHERE sa.storyline_id = %s
            ORDER BY COALESCE(a.published_at, a.created_at) DESC NULLS LAST
            LIMIT %s
            """,
            (sid, limit),
        )
        return [r[0] or "" for r in cur.fetchall()]
    cur.execute(
        f"""
        SELECT title FROM {schema}.articles
        WHERE storyline_id = %s
        ORDER BY COALESCE(published_at, created_at) DESC NULLS LAST
        LIMIT %s
        """,
        (sid, limit),
    )
    return [r[0] or "" for r in cur.fetchall()]


def _yieldable_stats(cur, schema: str, sid: int) -> dict[str, int]:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = 'storyline_articles'
        """,
        (schema,),
    )
    has_junc = bool(cur.fetchone())
    if has_junc:
        join = f"""
            FROM {schema}.storyline_articles sa
            JOIN {schema}.articles a ON a.id = sa.article_id
            WHERE sa.storyline_id = %s
        """
        params: tuple[Any, ...] = (sid,)
    else:
        join = f"FROM {schema}.articles a WHERE a.storyline_id = %s"
        params = (sid,)
    cur.execute(
        f"""
        SELECT COUNT(*)::int AS n,
               COUNT(*) FILTER (WHERE a.enrichment_status = 'enriched')::int AS enriched,
               COUNT(*) FILTER (
                 WHERE a.enrichment_status = 'enriched'
                   AND LENGTH(COALESCE(a.content,'')) < 200
               )::int AS enriched_thin,
               COUNT(*) FILTER (
                 WHERE a.enrichment_status = 'enriched'
                   AND LENGTH(COALESCE(a.content,'')) >= 200
                   AND NOT EXISTS (
                     SELECT 1 FROM {schema}.article_entities ae WHERE ae.article_id = a.id
                   )
               )::int AS enriched_no_entities
        {join}
        """,
        params,
    )
    n, enr, thin, no_ent = cur.fetchone()
    return {
        "members": int(n or 0),
        "enriched": int(enr or 0),
        "enriched_thin": int(thin or 0),
        "enriched_no_entities": int(no_ent or 0),
    }


def _parse_meta(raw: Any) -> dict:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw) or {}
        except Exception:
            return {}
    return {}


def run_baseline() -> dict[str, Any]:
    from services.vault_quality_gates import (
        briefing_citations_ok,
        briefing_require_citations_enabled,
        expansion_coherence_gate_enabled,
        expansion_coherence_ok,
        entity_note_min_hits,
    )

    magnet_max = _magnet_threshold()
    schemas = _schemas()
    schema_by_domain = {dk: sch for dk, sch in schemas}

    with get_db_connection_context() as conn:
        cur = conn.cursor()
        expansions = _fetch_home_slate(cur)

        # F7 stubs
        cur.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE note_type='entity' AND COALESCE(lifecycle,'stub')='stub')::int,
              COUNT(*) FILTER (WHERE note_type='entity' AND lifecycle='index')::int,
              COUNT(*) FILTER (WHERE note_type='entity' AND lifecycle='living')::int,
              COUNT(*) FILTER (
                WHERE note_type='entity'
                  AND COALESCE(lifecycle,'stub')='stub'
                  AND (object_id IS NULL)
              )::int
            FROM intelligence.vault_notes
            """
        )
        stub_n, index_n, living_ent, stub_no_oid = cur.fetchone()

        # F10 daily briefings
        cur.execute(
            """
            SELECT id, title, COALESCE(body_md, summary_md, '') AS body, updated_at, metadata
            FROM intelligence.vault_notes
            WHERE note_type = 'daily_briefing'
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 5
            """
        )
        brief_cols = [d[0] for d in cur.description]
        daily_briefs = [dict(zip(brief_cols, r)) for r in cur.fetchall()]

        # Global false-enriched sample (F9) — yieldable check, not noisy cookie ILIKE.
        from services.article_content_enrichment_service import is_false_enriched_body

        f9_enriched = f9_bad = 0
        for dk, sch in schemas:
            try:
                cur.execute(
                    f"""
                    SELECT id, content
                    FROM {sch}.articles
                    WHERE enrichment_status = 'enriched'
                      AND created_at > NOW() - INTERVAL '14 days'
                    ORDER BY id DESC
                    LIMIT 400
                    """
                )
                rows = cur.fetchall() or []
                f9_enriched += len(rows)
                f9_bad += sum(1 for _aid, content in rows if is_false_enriched_body(content))
            except Exception:
                conn.rollback()
                continue

        # Multi-home (F8): articles in multiple storylines + also_in exposure gap
        f8_multi = 0
        f8_total = 0
        f8_multi_homes = 0  # storylines that contain ≥1 multi-home article
        f8_also_in_ok = 0
        for dk, sch in schemas:
            cur.execute(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = %s AND table_name = 'storyline_articles'
                """,
                (sch,),
            )
            if not cur.fetchone():
                continue
            try:
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int,
                           COUNT(*) FILTER (WHERE c > 1)::int
                    FROM (
                      SELECT article_id, COUNT(DISTINCT storyline_id) AS c
                      FROM {sch}.storyline_articles
                      GROUP BY article_id
                    ) t
                    """
                )
                tot, multi = cur.fetchone()
                f8_total += int(tot or 0)
                f8_multi += int(multi or 0)
                # Sample up to 40 multi-home storylines: also_in is exposable if another
                # active storyline shares any member article (same SQL as pack).
                cur.execute(
                    f"""
                    WITH multi_arts AS (
                      SELECT article_id
                      FROM {sch}.storyline_articles
                      GROUP BY article_id
                      HAVING COUNT(DISTINCT storyline_id) > 1
                    ),
                    homes AS (
                      SELECT DISTINCT sa.storyline_id
                      FROM {sch}.storyline_articles sa
                      JOIN multi_arts m ON m.article_id = sa.article_id
                      JOIN {sch}.storylines s ON s.id = sa.storyline_id
                      WHERE COALESCE(s.status, '') NOT IN ('merged','deleted','archived')
                      LIMIT 40
                    )
                    SELECT h.storyline_id,
                           EXISTS (
                             SELECT 1
                             FROM {sch}.storyline_articles sa
                             JOIN {sch}.storyline_articles sa2
                               ON sa2.article_id = sa.article_id
                              AND sa2.storyline_id <> sa.storyline_id
                             JOIN {sch}.storylines s2 ON s2.id = sa2.storyline_id
                             WHERE sa.storyline_id = h.storyline_id
                               AND COALESCE(s2.status, '') NOT IN ('merged','deleted','archived')
                           ) AS also_in_ok
                    FROM homes h
                    """
                )
                for _sid, also_ok in cur.fetchall() or []:
                    f8_multi_homes += 1
                    if also_ok:
                        f8_also_in_ok += 1
            except Exception:
                conn.rollback()

        # Pull cache sources (acceptance: ready/cached vs deferred)
        pull_ready = pull_deferred = pull_total = 0
        try:
            cur.execute(
                """
                SELECT
                  COUNT(*)::int,
                  COUNT(*) FILTER (
                    WHERE COALESCE(context_meta->>'cache_source', '') IN ('vault_expansion', 'prior_pull')
                       OR status = 'ready'
                  )::int,
                  COUNT(*) FILTER (
                    WHERE COALESCE(context_meta->>'cache_source', '') = 'deferred'
                  )::int
                FROM intelligence.article_context_pulls
                WHERE created_at > NOW() - INTERVAL '14 days'
                """
            )
            pull_total, pull_ready, pull_deferred = cur.fetchone()
        except Exception:
            conn.rollback()
            pull_ready = pull_deferred = pull_total = 0

        # Per-expansion metrics for F1–F6, F11 sample
        magnet_hits = 0
        coherence_fail = 0
        stale_durable = 0
        no_usable = 0
        thin_member_arcs = 0
        scored = []
        titles_for_dupe: list[tuple[str, str, int]] = []  # domain, title, sid

        for ex in expansions:
            dk = ex.get("domain_key") or ""
            sid = int(ex.get("storyline_id") or 0)
            sch = schema_by_domain.get(dk)
            title = ex.get("title") or ""
            body = ex.get("body") or ""
            ac = None
            qscore = None
            editorial = {}
            ed_updated = None
            members: list[str] = []
            ystat = {"members": 0, "enriched": 0, "enriched_thin": 0, "enriched_no_entities": 0}
            if sch and sid:
                sl = _storyline_row(cur, sch, sid)
                if sl:
                    ac = int(sl.get("article_count") or 0)
                    qscore = sl.get("quality_score")
                    editorial = sl.get("editorial_document") or {}
                    if isinstance(editorial, str):
                        try:
                            editorial = json.loads(editorial)
                        except Exception:
                            editorial = {}
                    ed_updated = sl.get("updated_at")
                    members = _member_titles(cur, sch, sid)
                    ystat = _yieldable_stats(cur, sch, sid)
            ok, reason = expansion_coherence_ok(
                title=title, body=body, member_titles=members, article_count=ac
            )
            if not ok and "magnet" in reason:
                magnet_hits += 1
            if not ok and reason not in ("gate_disabled",):
                coherence_fail += 1
            # F2: durable present, expansion older? or pack would prefer durable when expansion thinner
            durable_text = ""
            if isinstance(editorial, dict):
                durable_text = " ".join(
                    str(editorial.get(k) or "")
                    for k in ("lede", "summary", "body", "narrative")
                )
            exp_updated = ex.get("updated_at")
            if durable_text.strip() and len(body.strip()) < 80:
                stale_durable += 1  # durable would win over empty living
            elif durable_text.strip() and exp_updated and ed_updated:
                try:
                    if ed_updated > exp_updated and len(body) < 200:
                        stale_durable += 1
                except Exception:
                    pass
            if len((body or "").strip()) < 80 and len(durable_text.strip()) < 80:
                no_usable += 1
            if ystat["enriched"] > 0:
                bad_share = (ystat["enriched_thin"] + ystat["enriched_no_entities"]) / max(
                    1, ystat["enriched"]
                )
                if bad_share >= 0.5:
                    thin_member_arcs += 1
            if ac is not None and ac >= magnet_max:
                magnet_hits += 1
            titles_for_dupe.append((dk, title, sid))
            scored.append(
                {
                    "domain": dk,
                    "storyline_id": sid,
                    "title": title[:120],
                    "article_count": ac,
                    "quality_score": float(qscore) if qscore is not None else None,
                    "coherence_ok": ok,
                    "coherence_reason": reason,
                    "body_len": len(body or ""),
                    "durable_len": len(durable_text.strip()),
                    "yield": ystat,
                }
            )

        # F11 near-dupe: token overlap on titles in slate
        def toks(t: str) -> set[str]:
            return {w for w in re.findall(r"[a-z0-9]{3,}", (t or "").lower())}

        dupe_pairs = 0
        for i in range(len(titles_for_dupe)):
            for j in range(i + 1, len(titles_for_dupe)):
                a, b = toks(titles_for_dupe[i][1]), toks(titles_for_dupe[j][1])
                if not a or not b:
                    continue
                inter = len(a & b)
                if inter >= 3 and inter / max(1, min(len(a), len(b))) >= 0.5:
                    dupe_pairs += 1

        # F10 citations on living daily briefings vs same-day expansions
        from services.vault_quality_gates import daily_briefing_serve_allowed

        cite_ok = True
        cite_reason = "no_living_brief"
        f10_fail_share = 0.0
        cur.execute(
            """
            SELECT COALESCE(body_md, summary_md, '') AS body, metadata
            FROM intelligence.vault_notes
            WHERE note_type = 'daily_briefing'
              AND COALESCE(lifecycle, 'living') = 'living'
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 5
            """
        )
        living_rows = cur.fetchall() or []
        if living_rows:
            fail_n = 0
            last_reason = "ok"
            for body, meta in living_rows:
                meta = meta if isinstance(meta, dict) else _parse_meta(meta)
                day = str(meta.get("briefing_day") or "")
                ok, reason = daily_briefing_serve_allowed(body or "", briefing_day=day)
                if not ok:
                    fail_n += 1
                    last_reason = reason
            cite_ok = fail_n == 0
            cite_reason = "all_cited" if cite_ok else last_reason
            f10_fail_share = fail_n / max(1, len(living_rows))
        # silence unused fetch when present
        _ = daily_briefs

        # F6: correlation proxy — mean quality_score of magnet vs non-magnet in slate
        qs_all = [s["quality_score"] for s in scored if s["quality_score"] is not None]
        qs_magnet = [
            s["quality_score"]
            for s in scored
            if s["quality_score"] is not None
            and (
                (s["article_count"] or 0) >= magnet_max
                or "magnet" in (s["coherence_reason"] or "")
            )
        ]

        n_exp = max(1, len(expansions))
        living_or_durable = sum(
            1
            for s in scored
            if (s.get("body_len") or 0) >= 120 or (s.get("durable_len") or 0) >= 80
        )
        f8_also_in_exposed = f8_also_in_ok / max(1, f8_multi_homes)
        f8_without_also_in = 1.0 - f8_also_in_exposed if f8_multi_homes else 0.0
        metrics = {
            "F1_magnet_rate": magnet_hits / n_exp,
            "F2_stale_durable_rate": stale_durable / n_exp,
            "F3_coherence_fail_rate": coherence_fail / n_exp,
            "F4_no_usable_brief_rate": no_usable / n_exp,
            "F5_thin_member_arc_rate": thin_member_arcs / n_exp,
            "F6_mean_quality_on_slate": (sum(qs_all) / len(qs_all)) if qs_all else None,
            "F6_mean_quality_on_magnets": (sum(qs_magnet) / len(qs_magnet)) if qs_magnet else None,
            "F7_entity_stub": int(stub_n or 0),
            "F7_entity_index": int(index_n or 0),
            "F7_entity_living": int(living_ent or 0),
            "F7_stub_share": int(stub_n or 0) / max(1, int(stub_n or 0) + int(index_n or 0) + int(living_ent or 0)),
            "F8_multi_home_share": f8_multi / max(1, f8_total),
            "F8_multi_home_n": f8_multi,
            "F8_also_in_exposed_rate": f8_also_in_exposed,
            "F8_without_also_in_rate": f8_without_also_in,
            "F8_multi_home_storylines_sampled": f8_multi_homes,
            "F9_false_enriched_proxy_rate": f9_bad / max(1, f9_enriched),
            "F9_enriched_14d": f9_enriched,
            "F10_citations_ok": cite_ok,
            "F10_citations_reason": cite_reason,
            "F10_fail_share": f10_fail_share,
            "F10_require_citations_enabled": briefing_require_citations_enabled(),
            "F11_near_dupe_pairs": dupe_pairs,
            "slate_n": len(expansions),
            "magnet_max_member_articles": magnet_max,
            "expansion_coherence_gate_enabled": expansion_coherence_gate_enabled(),
            "entity_md_min_hits": entity_note_min_hits(),
            "living_or_durable_rate": living_or_durable / n_exp,
            "pull_total_14d": int(pull_total or 0),
            "pull_ready_cached_14d": int(pull_ready or 0),
            "pull_deferred_14d": int(pull_deferred or 0),
            "pull_deferred_share": int(pull_deferred or 0) / max(1, int(pull_total or 0)),
        }

        # Automated hand-proxy for 20 storylines (top 10 slate + 10 by article_count)
        sample = scored[:10]
        # add 10 high article_count actives
        for dk, sch in schemas:
            try:
                cur.execute(
                    f"""
                    SELECT id, title, article_count, quality_score
                    FROM {sch}.storylines
                    WHERE COALESCE(status,'') NOT IN ('merged','deleted','archived')
                    ORDER BY article_count DESC NULLS LAST
                    LIMIT 10
                    """
                )
                for sid, title, ac, qs in cur.fetchall():
                    if any(s["storyline_id"] == sid and s["domain"] == dk for s in sample):
                        continue
                    members = _member_titles(cur, sch, sid)
                    ok, reason = expansion_coherence_ok(
                        title=title or "",
                        body="",
                        member_titles=members,
                        article_count=int(ac or 0),
                    )
                    sample.append(
                        {
                            "domain": dk,
                            "storyline_id": int(sid),
                            "title": (title or "")[:120],
                            "article_count": int(ac or 0),
                            "quality_score": float(qs) if qs is not None else None,
                            "coherence_ok": ok,
                            "coherence_reason": reason,
                            "body_len": 0,
                            "durable_len": 0,
                            "yield": _yieldable_stats(cur, sch, int(sid)),
                            "from_active_pool": True,
                        }
                    )
                    if len(sample) >= 20:
                        break
            except Exception:
                conn.rollback()
            if len(sample) >= 20:
                break
        sample = sample[:20]

        hand_rows = []
        for s in sample:
            # Proxy 1–5 scores matching rubric dimensions (not human)
            one_story = 5
            if (s.get("article_count") or 0) >= magnet_max:
                one_story = 2
            if "magnet" in (s.get("coherence_reason") or ""):
                one_story = min(one_story, 1)
            current = 4 if (s.get("body_len") or 0) >= 120 else (2 if (s.get("durable_len") or 0) > 80 else 1)
            citeable = 4 if s.get("coherence_ok") else 2
            understand = 4 if (s.get("body_len") or 0) >= 120 or (s.get("durable_len") or 0) >= 80 else 1
            journalism = 4
            y = s.get("yield") or {}
            if y.get("enriched"):
                bad = (y.get("enriched_thin", 0) + y.get("enriched_no_entities", 0)) / max(
                    1, y["enriched"]
                )
                if bad >= 0.5:
                    journalism = 2
            hand_rows.append(
                {
                    **s,
                    "proxy_F1_one_story": one_story,
                    "proxy_F2_current": current,
                    "proxy_F3_citeable": citeable,
                    "proxy_F4_understand": understand,
                    "proxy_F5_journalism": journalism,
                    "proxy_mean": round(
                        (one_story + current + citeable + understand + journalism) / 5.0, 2
                    ),
                }
            )

    # Rank by pain: high rate + low hand proxy
    pain = []
    rate_map = {
        "F1": metrics["F1_magnet_rate"],
        "F2": metrics["F2_stale_durable_rate"],
        "F3": metrics["F3_coherence_fail_rate"],
        "F4": metrics["F4_no_usable_brief_rate"],
        "F5": metrics["F5_thin_member_arc_rate"],
        "F7": metrics["F7_stub_share"],
        # F8 pain = multi-home packs that cannot expose also_in (UX gap), not raw multi-link share.
        "F8": float(metrics.get("F8_without_also_in_rate") or 0.0),
        "F9": metrics["F9_false_enriched_proxy_rate"],
        "F11": min(1.0, metrics["F11_near_dupe_pairs"] / max(1, metrics["slate_n"] or 1)),
    }
    # F6: pain from magnet share on served slate + score-vs-novelty proxy.
    # Novelty gate shipped: magnet exclusion on next prime; served-slate magnet rate
    # is the reader-facing signal until expansions rotate.
    f6_pain = float(metrics.get("F1_magnet_rate") or 0.0)
    if metrics.get("F6_mean_quality_on_magnets") and metrics.get("F6_mean_quality_on_slate"):
        if metrics["F6_mean_quality_on_magnets"] >= metrics["F6_mean_quality_on_slate"]:
            f6_pain = max(f6_pain, 0.25)
    rate_map["F6"] = min(1.0, f6_pain)
    rate_map["F10"] = float(metrics.get("F10_fail_share") or (0.0 if metrics["F10_citations_ok"] else 0.8))

    labels = {
        "F1": "magnet bag on slate",
        "F2": "stale durable as live",
        "F3": "expansion title↔body junk",
        "F4": "no usable brief",
        "F5": "thin/non-yieldable members",
        "F6": "slate by score not novelty",
        "F7": "vault stub flood",
        "F8": "multi-home exclusive confusion",
        "F9": "false enriched",
        "F10": "uncited briefing prose",
        "F11": "near-dupe arcs on slate",
    }
    for fid, rate in rate_map.items():
        pain.append((fid, labels[fid], float(rate or 0)))
    pain.sort(key=lambda x: -x[2])

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": metrics,
        "rank": pain,
        "hand_proxy_sample": hand_rows,
        "hand_proxy_means": {
            "F1": sum(h["proxy_F1_one_story"] for h in hand_rows) / max(1, len(hand_rows)),
            "F2": sum(h["proxy_F2_current"] for h in hand_rows) / max(1, len(hand_rows)),
            "F3": sum(h["proxy_F3_citeable"] for h in hand_rows) / max(1, len(hand_rows)),
            "F4": sum(h["proxy_F4_understand"] for h in hand_rows) / max(1, len(hand_rows)),
            "F5": sum(h["proxy_F5_journalism"] for h in hand_rows) / max(1, len(hand_rows)),
        },
    }


def render_md(data: dict[str, Any]) -> str:
    m = data["metrics"]
    lines = [
        "# Quality reader baseline Q0",
        "",
        f"Generated: `{data['generated_at']}` (UTC)",
        "",
        "Automated SQL metrics + **hand-proxy** scores on a 20-storyline sample "
        "(not a human rater — replace proxy columns when a human scores).",
        "",
        "## Prod gate flags observed",
        "",
        f"- `expansion_coherence_gate_enabled`: `{m.get('expansion_coherence_gate_enabled')}`",
        f"- `briefing_require_citations_enabled`: `{m.get('F10_require_citations_enabled')}`",
        f"- `entity_md_min_hits`: `{m.get('entity_md_min_hits')}`",
        f"- `max_member_articles` (politics config): `{m.get('magnet_max_member_articles')}`",
        f"- slate expansions examined: `{m.get('slate_n')}`",
        "",
        "## Ranked failures (by automated pain rate)",
        "",
        "| Rank | ID | Failure | Pain rate | Notes |",
        "|------|----|---------|-----------|-------|",
    ]
    for i, (fid, label, rate) in enumerate(data["rank"], 1):
        note = ""
        if fid == "F10":
            note = m.get("F10_citations_reason") or ""
        if fid == "F7":
            note = f"stub={m['F7_entity_stub']} index={m['F7_entity_index']} living={m['F7_entity_living']}"
        if fid == "F8":
            note = (
                f"also_in_exposed={m.get('F8_also_in_exposed_rate')} "
                f"multi_share={m.get('F8_multi_home_share')}"
            )
        if fid == "F9":
            note = f"enriched_14d={m['F9_enriched_14d']}"
        if fid == "F11":
            note = f"pairs={m['F11_near_dupe_pairs']}"
        if fid == "F6":
            note = (
                f"mean_qs_slate={m.get('F6_mean_quality_on_slate')} "
                f"mean_qs_magnet={m.get('F6_mean_quality_on_magnets')}"
            )
        lines.append(f"| {i} | {fid} | {label} | {rate:.3f} | {note} |")

    # Acceptance bar vs best-product criteria
    f1 = float(m.get("F1_magnet_rate") or 0)
    f3 = float(m.get("F3_coherence_fail_rate") or 0)
    f6 = next((r for fid, _l, r in data["rank"] if fid == "F6"), 0.0)
    f2 = float(m.get("F2_stale_durable_rate") or 0)
    f7 = float(m.get("F7_stub_share") or 0)
    living = float(m.get("living_or_durable_rate") or 0)
    deferred = float(m.get("pull_deferred_share") or 0)
    f8_gap = float(m.get("F8_without_also_in_rate") or 0)
    hand4 = float(data["hand_proxy_means"].get("F4") or 0)
    checks = [
        ("Home novel/coherent/non-magnet", f1 + f3 <= 0.12 and float(f6 or 0) <= 0.0, f"F1={f1:.3f} F3={f3:.3f} F6={f6}"),
        ("Storyline living or durable", living >= 0.80 and hand4 >= 3.5, f"living_or_durable={living:.3f} hand_F4={hand4:.2f}"),
        ("Pull ready/cached", deferred <= 0.50 or int(m.get("pull_total_14d") or 0) == 0, f"deferred_share={deferred:.3f}"),
        ("Reading=living Index=stubs", f7 <= 0.05, f"stub_share={f7:.3f}"),
        ("Durable not competing live", f2 <= 0.0, f"F2={f2:.3f} F8_also_in_gap={f8_gap:.3f}"),
    ]
    lines.extend(["", "## Acceptance bar", "", "| Criterion | Pass | Evidence |", "|-----------|------|----------|"])
    for name, ok, evid in checks:
        lines.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {evid} |")
    lines.extend(
        [
            "",
            "## Metric detail",
            "",
            "```json",
            json.dumps(m, indent=2, default=str),
            "```",
            "",
            "## Hand-proxy means (n=%d)" % len(data["hand_proxy_sample"]),
            "",
        ]
    )
    for k, v in data["hand_proxy_means"].items():
        lines.append(f"- {k}: {v:.2f}")
    lines.extend(["", "## Sample (20)", "", "| domain | id | articles | proxy_mean | title |", "|--------|----|----------|------------|-------|"])
    for h in data["hand_proxy_sample"]:
        lines.append(
            f"| {h.get('domain')} | {h.get('storyline_id')} | {h.get('article_count')} | "
            f"{h.get('proxy_mean')} | {(h.get('title') or '')[:60].replace('|', '/')} |"
        )
    lines.extend(
        [
            "",
            "## Q1 recommendation",
            "",
            f"**Top failure:** `{data['rank'][0][0]}` — {data['rank'][0][1]} "
            f"(pain={data['rank'][0][2]:.3f}).",
            "",
            "Ship only the candidate gate for this ID next (see quality plan F-table).",
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        default=str(_ROOT / "docs" / "QUALITY_READER_BASELINE_Q0.md"),
        help="Markdown output path",
    )
    ap.add_argument(
        "--json-out",
        default=str(_ROOT / "data" / "quality_reader_baseline_q0.json"),
        help="JSON output path",
    )
    args = ap.parse_args()
    data = run_baseline()
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    md = render_md(data)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(md, encoding="utf-8")
    print(md)
    print(f"Wrote {args.out}", file=sys.stderr)
    print(f"Wrote {args.json_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
