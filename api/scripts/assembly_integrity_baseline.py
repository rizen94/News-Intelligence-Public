#!/usr/bin/env python3
"""Assembly integrity baseline A1–A4 (Widow).

  PYTHONPATH=api .venv/bin/python api/scripts/assembly_integrity_baseline.py \\
    --out docs/ASSEMBLY_INTEGRITY_A1.md
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "api"))
sys.path.insert(0, str(_ROOT))

env_file = _ROOT / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv

        load_dotenv(env_file, override=False)
    except Exception:
        pass


def _schemas() -> list[tuple[str, str]]:
    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

    out = []
    for dk in get_pipeline_active_domain_keys():
        try:
            out.append((dk, resolve_domain_schema(dk)))
        except Exception:
            continue
    return out


def run_baseline() -> dict[str, Any]:
    from shared.database.connection import get_db_connection_context
    from shared.episode_attach_gate import episode_container_assembly_enabled

    assembly_on = bool(episode_container_assembly_enabled())
    schemas = _schemas()
    bag_only = eel_only = count_drift_eps = eps_checked = 0

    with get_db_connection_context() as conn:
        cur = conn.cursor()
        for dk, sch in schemas:
            if not assembly_on:
                continue
            try:
                cur.execute(
                    f"""
                    WITH eel_arts AS (
                      SELECT eel.episode_id, ce.source_article_id AS article_id
                      FROM intelligence.event_episode_links eel
                      JOIN public.chronological_events ce ON ce.id = eel.event_id
                      WHERE eel.domain_key = %s
                        AND COALESCE(eel.inference_stage, '') <> 'quarantined'
                        AND ce.source_article_id IS NOT NULL
                    ),
                    bag_arts AS (
                      SELECT storyline_id AS episode_id, article_id
                      FROM {sch}.storyline_articles
                    )
                    SELECT
                      (SELECT COUNT(*)::int FROM bag_arts b
                       WHERE NOT EXISTS (
                         SELECT 1 FROM eel_arts e
                         WHERE e.episode_id = b.episode_id AND e.article_id = b.article_id
                       )),
                      (SELECT COUNT(*)::int FROM eel_arts e
                       WHERE NOT EXISTS (
                         SELECT 1 FROM bag_arts b
                         WHERE b.episode_id = e.episode_id AND b.article_id = e.article_id
                       ))
                    """,
                    (dk,),
                )
                bo, eo = cur.fetchone()
                bag_only += int(bo or 0)
                eel_only += int(eo or 0)
                cur.execute(
                    f"""
                    WITH eel AS (
                      SELECT eel.episode_id, COUNT(DISTINCT ce.source_article_id)::int AS eel_n
                      FROM intelligence.event_episode_links eel
                      JOIN public.chronological_events ce ON ce.id = eel.event_id
                      WHERE eel.domain_key = %s
                        AND COALESCE(eel.inference_stage, '') <> 'quarantined'
                        AND ce.source_article_id IS NOT NULL
                      GROUP BY eel.episode_id
                    )
                    SELECT COUNT(*)::int,
                           COUNT(*) FILTER (
                             WHERE COALESCE(s.article_count, 0) IS DISTINCT FROM COALESCE(eel.eel_n, 0)
                           )::int
                    FROM {sch}.storylines s
                    LEFT JOIN eel ON eel.episode_id = s.id
                    WHERE s.merged_into_id IS NULL
                      AND COALESCE(s.status, '') NOT IN ('merged','deleted','archived')
                      AND (COALESCE(eel.eel_n, 0) > 0 OR COALESCE(s.article_count, 0) > 0)
                    """,
                    (dk,),
                )
                checked, drift = cur.fetchone()
                eps_checked += int(checked or 0)
                count_drift_eps += int(drift or 0)
            except Exception:
                conn.rollback()

        # A2 prime freshness
        cur.execute(
            """
            SELECT
              COUNT(*)::int,
              EXTRACT(EPOCH FROM (NOW() - MAX(note_updated_at)))/3600.0,
              EXTRACT(EPOCH FROM (NOW() - MIN(note_updated_at)))/3600.0,
              PERCENTILE_CONT(0.5) WITHIN GROUP (
                ORDER BY EXTRACT(EPOCH FROM (NOW() - note_updated_at))/3600.0
              )
            FROM intelligence.vault_notes
            WHERE note_type = 'expansion'
              AND COALESCE(lifecycle, 'living') = 'living'
              AND note_updated_at >= NOW() - INTERVAL '7 days'
            """
        )
        exp_n, max_age_h, min_age_h, med_age_h = cur.fetchone()
        try:
            cur.execute(
                """
                SELECT
                  COUNT(*)::int,
                  COUNT(*) FILTER (
                    WHERE COALESCE(context_meta->>'cache_source', '') = 'deferred'
                  )::int
                FROM intelligence.article_context_pulls
                WHERE created_at > NOW() - INTERVAL '14 days'
                """
            )
            pull_tot, pull_def = cur.fetchone()
        except Exception:
            conn.rollback()
            pull_tot = pull_def = 0

        stale_novel = 0
        for dk, sch in schemas:
            try:
                cur.execute(
                    f"""
                    SELECT COUNT(*)::int
                    FROM {sch}.storylines s
                    WHERE s.merged_into_id IS NULL
                      AND COALESCE(s.status, '') = 'active'
                      AND EXISTS (
                        SELECT 1 FROM {sch}.storyline_articles sa
                        JOIN {sch}.articles a ON a.id = sa.article_id
                        WHERE sa.storyline_id = s.id
                          AND COALESCE(a.published_at, a.created_at) >= NOW() - INTERVAL '2 days'
                      )
                      AND NOT EXISTS (
                        SELECT 1 FROM intelligence.vault_notes vn
                        WHERE vn.domain_key = %s
                          AND vn.note_type = 'expansion'
                          AND vn.object_id = s.id
                          AND COALESCE(vn.lifecycle, 'living') = 'living'
                          AND vn.note_updated_at >= NOW() - INTERVAL '36 hours'
                      )
                    """,
                    (dk,),
                )
                stale_novel += int(cur.fetchone()[0] or 0)
            except Exception:
                conn.rollback()

        # A3 false-enrich among recent EEL source articles
        false_eel = eel_arts_14d = 0
        for dk, sch in schemas:
            try:
                cur.execute(
                    f"""
                    SELECT COUNT(DISTINCT ce.source_article_id)::int,
                           COUNT(DISTINCT ce.source_article_id) FILTER (
                             WHERE LENGTH(COALESCE(a.content,'')) < 200
                                OR a.content ILIKE '%%access denied%%'
                                OR a.content ILIKE '%%enable javascript%%'
                                OR a.content ILIKE '%%subscribe%%'
                                OR a.enrichment_status IN ('failed','inaccessible','removed')
                           )::int
                    FROM intelligence.event_episode_links eel
                    JOIN public.chronological_events ce ON ce.id = eel.event_id
                    JOIN {sch}.articles a ON a.id = ce.source_article_id
                    WHERE eel.domain_key = %s
                      AND eel.created_at > NOW() - INTERVAL '14 days'
                      AND COALESCE(eel.inference_stage, '') <> 'quarantined'
                    """,
                    (dk,),
                )
                n, bad = cur.fetchone()
                eel_arts_14d += int(n or 0)
                false_eel += int(bad or 0)
            except Exception:
                conn.rollback()

        # A4 package↔vault (brief activity OR package activity in window)
        try:
            cur.execute(
                """
                SELECT
                  COUNT(DISTINCT p.id)::int,
                  COUNT(DISTINCT p.id) FILTER (
                    WHERE COALESCE(b.vault_rel_path, '') <> ''
                       OR COALESCE(b.metadata->>'vault_rel_path', '') <> ''
                       OR EXISTS (
                         SELECT 1 FROM intelligence.vault_notes vn
                         WHERE vn.object_id = p.id
                           AND (
                             vn.metadata->>'package_id' = p.id::text
                             OR vn.vault_path ILIKE '%%pkg-' || p.id::text || '%%'
                             OR vn.tags @> ARRAY['package/' || p.id::text]
                           )
                       )
                  )::int
                FROM intelligence.editorial_packages p
                LEFT JOIN intelligence.package_evidence_briefs b ON b.package_id = p.id
                WHERE COALESCE(p.updated_at, p.created_at) > NOW() - INTERVAL '90 days'
                   OR COALESCE(b.updated_at, b.created_at) > NOW() - INTERVAL '90 days'
                """
            )
            pkg_n, pkg_vault = cur.fetchone()
        except Exception as e:
            print(f"A4 package vault metric failed: {e}", file=sys.stderr)
            conn.rollback()
            pkg_n = pkg_vault = 0
        try:
            cur.execute(
                """
                SELECT
                  COUNT(*)::int,
                  COUNT(*) FILTER (
                    WHERE EXISTS (
                      SELECT 1 FROM intelligence.vault_notes vn
                      WHERE vn.note_type IN ('clipping', 'article')
                        AND vn.object_id = m.member_id
                        AND (
                          COALESCE(m.domain_key, '') = ''
                          OR vn.domain_key = m.domain_key
                        )
                        AND (
                          vn.vault_path ILIKE '%%20_Clippings%%'
                          OR vn.vault_path ILIKE '%%/20_Clippings/%%'
                        )
                    )
                  )::int
                FROM intelligence.editorial_package_members m
                WHERE m.member_type = 'article'
                  AND COALESCE(m.status, 'active') = 'active'
                  AND m.added_at > NOW() - INTERVAL '90 days'
                """
            )
            art_mem, art_clip = cur.fetchone()
        except Exception as e:
            print(f"A4 article clipping metric failed: {e}", file=sys.stderr)
            conn.rollback()
            art_mem = art_clip = 0

    drift_total = bag_only + eel_only
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "assembly_enabled": assembly_on,
        "A1": {
            "bag_only": bag_only,
            "eel_only": eel_only,
            "drift_total": drift_total,
            "count_drift_episodes": count_drift_eps,
            "episodes_checked": eps_checked,
            "count_drift_rate": count_drift_eps / max(1, eps_checked),
        },
        "A2": {
            "expansions_7d": int(exp_n or 0),
            "max_age_hours": float(max_age_h) if max_age_h is not None else None,
            "min_age_hours": float(min_age_h) if min_age_h is not None else None,
            "median_age_hours": float(med_age_h) if med_age_h is not None else None,
            "pull_total_14d": int(pull_tot or 0),
            "pull_deferred_14d": int(pull_def or 0),
            "pull_deferred_share": int(pull_def or 0) / max(1, int(pull_tot or 0)),
            "stale_novel_episodes_36h": stale_novel,
        },
        "A3": {
            "eel_source_articles_14d": eel_arts_14d,
            "false_enrich_proxy": false_eel,
            "false_enrich_rate": false_eel / max(1, eel_arts_14d),
        },
        "A4": {
            "packages_30d": int(pkg_n or 0),
            "packages_with_vault_brief": int(pkg_vault or 0),
            "vault_brief_share": int(pkg_vault or 0) / max(1, int(pkg_n or 0)),
            "article_members_30d": int(art_mem or 0),
            "article_members_with_clipping": int(art_clip or 0),
            "clipping_share": int(art_clip or 0) / max(1, int(art_mem or 0)),
        },
    }


def render_md(data: dict[str, Any], title: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"Generated: `{data['generated_at']}` (UTC)",
        "",
        f"episode_container_assembly: `{data.get('assembly_enabled')}`",
        "",
        "## A1 EEL vs bag",
        "",
        "```json",
        json.dumps(data["A1"], indent=2),
        "```",
        "",
        "## A2 Prime freshness / Pull",
        "",
        "```json",
        json.dumps(data["A2"], indent=2),
        "```",
        "",
        "## A3 Yieldable before attach",
        "",
        "```json",
        json.dumps(data["A3"], indent=2),
        "```",
        "",
        "## A4 Package↔vault",
        "",
        "```json",
        json.dumps(data["A4"], indent=2),
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(_ROOT / "docs" / "ASSEMBLY_INTEGRITY_BASELINE.md"))
    ap.add_argument("--json-out", default=str(_ROOT / "data" / "assembly_integrity_baseline.json"))
    ap.add_argument("--title", default="Assembly integrity baseline")
    args = ap.parse_args()
    data = run_baseline()
    Path(args.json_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.json_out).write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    md = render_md(data, args.title)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(md, encoding="utf-8")
    print(md)
    print(f"Wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
