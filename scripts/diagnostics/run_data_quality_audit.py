#!/usr/bin/env python3
"""
Run read-only data quality audit packs against news_intel.

Writes:
  diagnostics/data_quality_report.json
  diagnostics/DATA_QUALITY_AUDIT_REPORT.md

Usage (from repo root):
  PYTHONPATH=api uv run python scripts/diagnostics/run_data_quality_audit.py
  PYTHONPATH=api uv run python scripts/diagnostics/run_data_quality_audit.py --packs 0,1,2
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(os.path.join(ROOT, ".db_password_widow")):
    with open(os.path.join(ROOT, ".db_password_widow")) as f:
        os.environ.setdefault("DB_PASSWORD", f.read().strip())


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def _rollback(cur) -> None:
    try:
        cur.connection.rollback()
    except Exception:
        pass


def _table_exists(cur, schema: str, table: str) -> bool:
    try:
        cur.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_schema = %s AND table_name = %s
            )
            """,
            (schema, table),
        )
        return bool(cur.fetchone()[0])
    except Exception:
        _rollback(cur)
        return False


def _safe_count(cur, sql: str, params: tuple = ()) -> int | None:
    try:
        cur.execute(sql, params)
        row = cur.fetchone()
        return int(row[0]) if row else 0
    except Exception:
        _rollback(cur)
        return None


def _fetch_all(cur, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    try:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:
        _rollback(cur)
        return [{"error": str(e)}]


def _section_in_packs(section_name: str, packs: set[str]) -> bool:
    if packs == {"all"}:
        return True
    m = re.match(r"pack_(\d+)", section_name)
    if m:
        return m.group(1) in packs
    return section_name in packs


def _run_sql_file_sections(path: str, packs: set[str]) -> dict[str, str]:
    text = open(path, encoding="utf-8").read()
    pattern = re.compile(r"-- @section (\S+)\n(.*?)(?=\n-- @section |\Z)", re.S)
    out: dict[str, str] = {}
    for name, body in pattern.findall(text):
        if name.startswith("pack_"):
            if not _section_in_packs(name, packs):
                continue
        elif packs != {"all"}:
            continue
        sql = "\n".join(
            line for line in body.splitlines() if not line.strip().startswith("--")
        ).strip()
        if not sql or sql.startswith("/*"):
            continue
        out[name] = sql
    return out


def _column_exists(cur, schema: str, table: str, column: str) -> bool:
    try:
        cur.execute(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.columns
              WHERE table_schema = %s AND table_name = %s AND column_name = %s
            )
            """,
            (schema, table, column),
        )
        return bool(cur.fetchone()[0])
    except Exception:
        _rollback(cur)
        return False


def _articles_where_clause(cur, schema: str) -> str:
    if _column_exists(cur, schema, "articles", "enrichment_status"):
        return "WHERE enrichment_status IS DISTINCT FROM 'removed'"
    return ""


def _domain_inventory(cur, domain_key: str, schema: str) -> dict[str, Any]:
    inv: dict[str, Any] = {"domain_key": domain_key, "schema_name": schema, "errors": []}
    if not _table_exists(cur, schema, "articles"):
        inv["errors"].append("articles table missing")
        return inv

    where = _articles_where_clause(cur, schema)
    has_enrichment = _column_exists(cur, schema, "articles", "enrichment_status")

    try:
        inv["articles"] = _fetch_all(
            cur,
            f"""
            SELECT
              count(*)::bigint AS total,
              count(*) FILTER (WHERE created_at > now() - interval '24 hours') AS created_24h,
              count(*) FILTER (WHERE created_at > now() - interval '7 days') AS created_7d,
              max(created_at) AS latest_created,
              max(updated_at) AS latest_updated
            FROM {schema}.articles
            {where}
            """,
        )[0]
    except Exception as e:
        _rollback(cur)
        inv["errors"].append(f"articles inventory: {e}")

    try:
        enriched_expr = (
            "count(*) FILTER (WHERE enrichment_status = 'enriched') AS enriched,"
            if has_enrichment
            else "0::bigint AS enriched,"
        )
        summary_expr = (
            "count(*) FILTER (WHERE summary IS NOT NULL AND length(btrim(summary)) > 50) AS has_summary,"
            if _column_exists(cur, schema, "articles", "summary")
            else "0::bigint AS has_summary,"
        )
        quality_expr = (
            "count(*) FILTER (WHERE quality_score IS NOT NULL) AS has_quality_score,"
            if _column_exists(cur, schema, "articles", "quality_score")
            else "0::bigint AS has_quality_score,"
        )
        ml_expr = (
            "count(*) FILTER (WHERE ml_data IS NOT NULL) AS has_ml_data"
            if _column_exists(cur, schema, "articles", "ml_data")
            else "0::bigint AS has_ml_data"
        )
        inv["coverage_funnel"] = _fetch_all(
            cur,
            f"""
            SELECT
              count(*)::bigint AS articles_total,
              count(*) FILTER (WHERE url IS NOT NULL AND btrim(url) <> '') AS has_url,
              count(*) FILTER (WHERE content IS NOT NULL AND length(btrim(content)) > 100) AS has_body_100,
              {enriched_expr}
              {summary_expr}
              {quality_expr}
              {ml_expr}
            FROM {schema}.articles
            {where}
            """,
        )[0]
        total = int(inv["coverage_funnel"].get("articles_total") or 0)
        enriched = int(inv["coverage_funnel"].get("enriched") or 0)
        inv["coverage_funnel"]["enriched_pct"] = round(100.0 * enriched / total, 2) if total else 0.0
    except Exception as e:
        _rollback(cur)
        inv["errors"].append(f"coverage funnel: {e}")

    if _table_exists(cur, "intelligence", "article_to_context"):
        try:
            inv["articles_with_context"] = _safe_count(
                cur,
                f"""
                SELECT count(DISTINCT a.id)
                FROM {schema}.articles a
                JOIN intelligence.article_to_context m
                  ON m.article_id = a.id AND m.domain_key = %s
                {where}
                """,
                (domain_key,),
            )
        except Exception as e:
            _rollback(cur)
            inv["errors"].append(f"context link count: {e}")
    else:
        inv["articles_with_context"] = None

    for tbl in ("storylines", "storyline_articles", "rss_feeds", "article_entities"):
        if _table_exists(cur, schema, tbl):
            inv[tbl] = _safe_count(cur, f"SELECT count(*) FROM {schema}.{tbl}")
        else:
            inv[tbl] = None

    if _table_exists(cur, schema, "rss_feeds"):
        try:
            inv["rss_feeds_unhealthy"] = _safe_count(
                cur,
                f"""
                SELECT count(*) FROM {schema}.rss_feeds
                WHERE is_active = true
                  AND (
                    error_count > 0
                    OR last_fetched IS NULL
                    OR last_fetched < now() - (fetch_interval * interval '2 second')
                  )
                """,
            )
        except Exception as e:
            _rollback(cur)
            inv["errors"].append(f"rss health: {e}")

    return inv


def _domain_duplicates(cur, domain_key: str, schema: str) -> dict[str, Any]:
    out: dict[str, Any] = {"domain_key": domain_key, "schema_name": schema, "errors": []}
    if not _table_exists(cur, schema, "articles"):
        return out

    try:
        out["url_duplicate_groups"] = _safe_count(
            cur,
            f"""
            SELECT count(*) FROM (
              SELECT lower(btrim(url)) AS u
              FROM {schema}.articles
              WHERE url IS NOT NULL AND btrim(url) <> ''
              GROUP BY 1
              HAVING count(*) > 1
            ) d
            """,
        )
        out["url_duplicate_extra_rows"] = _safe_count(
            cur,
            f"""
            WITH g AS (
              SELECT lower(btrim(url)) AS u, count(*) AS c
              FROM {schema}.articles
              WHERE url IS NOT NULL AND btrim(url) <> ''
              GROUP BY 1
              HAVING count(*) > 1
            )
            SELECT coalesce(sum(c - 1), 0)::bigint FROM g
            """,
        )
    except Exception as e:
        _rollback(cur)
        out["errors"].append(f"url dupes: {e}")

    try:
        src_col = "source_domain" if _table_exists(cur, schema, "articles") else None
        if src_col:
            out["title_source_duplicate_groups"] = _safe_count(
                cur,
                f"""
                SELECT count(*) FROM (
                  SELECT lower(btrim(title)), lower(btrim(source_domain))
                  FROM {schema}.articles
                  WHERE title IS NOT NULL AND btrim(title) <> ''
                  GROUP BY 1, 2
                  HAVING count(*) > 1
                ) d
                """,
            )
    except Exception as e:
        _rollback(cur)
        out["errors"].append(f"title/source dupes: {e}")

    if _table_exists(cur, schema, "storyline_articles"):
        try:
            out["articles_on_multiple_storylines"] = _safe_count(
                cur,
                f"""
                SELECT count(*) FROM (
                  SELECT article_id
                  FROM {schema}.storyline_articles
                  GROUP BY article_id
                  HAVING count(DISTINCT storyline_id) > 1
                ) x
                """,
            )
        except Exception as e:
            _rollback(cur)
            out["errors"].append(f"storyline overlap: {e}")

    if _table_exists(cur, schema, "storylines"):
        try:
            out["duplicate_storyline_titles"] = _safe_count(
                cur,
                f"""
                SELECT count(*) FROM (
                  SELECT lower(btrim(title))
                  FROM {schema}.storylines
                  WHERE title IS NOT NULL
                  GROUP BY 1
                  HAVING count(*) > 1
                ) d
                """,
            )
            out["storylines_missing_summary"] = _safe_count(
                cur,
                f"""
                SELECT count(*) FROM {schema}.storylines
                WHERE analysis_summary IS NULL OR length(btrim(analysis_summary)) < 200
                """,
            )
        except Exception as e:
            _rollback(cur)
            out["errors"].append(f"storylines: {e}")

    return out


def _domain_pipeline(cur, schema: str) -> dict[str, Any]:
    out: dict[str, Any] = {"schema_name": schema, "errors": []}
    if not _table_exists(cur, schema, "articles"):
        return out

    has_enrichment = _column_exists(cur, schema, "articles", "enrichment_status")
    has_metadata = _column_exists(cur, schema, "articles", "metadata")

    if has_enrichment:
        try:
            out["enrichment_status"] = _fetch_all(
                cur,
                f"""
                SELECT enrichment_status, enrichment_attempts, count(*)::bigint AS n
                FROM {schema}.articles
                WHERE url IS NOT NULL AND btrim(url) <> ''
                GROUP BY 1, 2
                ORDER BY n DESC
                LIMIT 20
                """,
            )
        except Exception as e:
            _rollback(cur)
            out["errors"].append(f"enrichment: {e}")

    if has_metadata:
        try:
            out["pipeline_skips"] = _fetch_all(
                cur,
                f"""
                SELECT
                  count(*)::bigint AS articles_total,
                  count(*) FILTER (WHERE (metadata #>> '{{pipeline_skip,entity_extraction_skip}}')::boolean) AS entity_skip,
                  count(*) FILTER (WHERE (metadata #>> '{{pipeline_skip,event_extraction_skip}}')::boolean) AS event_skip,
                  count(*) FILTER (WHERE (metadata #>> '{{pipeline_skip,quality_scoring_skip}}')::boolean) AS quality_skip,
                  count(*) FILTER (WHERE (metadata #>> '{{pipeline,entity_extraction,last_pass_at}}') IS NOT NULL) AS entity_pass,
                  count(*) FILTER (WHERE (metadata #>> '{{pipeline,event_extraction,last_pass_at}}') IS NOT NULL) AS event_pass,
                  count(*) FILTER (WHERE (metadata #>> '{{pipeline,topic_clustering,last_pass_at}}') IS NOT NULL) AS topic_pass
                FROM {schema}.articles
                {_articles_where_clause(cur, schema)}
                """,
            )[0]
        except Exception as e:
            _rollback(cur)
            out["errors"].append(f"pipeline skips: {e}")

    return out


def _cross_domain_url_dupes(cur) -> dict[str, Any]:
    """URLs appearing in 2+ active domain schemas (syndication vs accidental dup)."""
    cur.execute(
        "SELECT domain_key, schema_name FROM public.domains WHERE is_active = true ORDER BY display_order"
    )
    domains = cur.fetchall()
    url_to_domains: dict[str, set[str]] = {}
    for domain_key, schema in domains:
        if not _table_exists(cur, schema, "articles"):
            continue
        try:
            cur.execute(
                f"""
                SELECT DISTINCT lower(btrim(url)) AS u
                FROM {schema}.articles
                WHERE url IS NOT NULL AND btrim(url) <> ''
                """
            )
            for (u,) in cur.fetchall():
                if u:
                    url_to_domains.setdefault(u, set()).add(domain_key)
        except Exception:
            _rollback(cur)
    multi = {u: sorted(dks) for u, dks in url_to_domains.items() if len(dks) > 1}
    return {
        "cross_domain_url_count": len(multi),
        "sample": [{"url": u, "domain_keys": dks} for u, dks in list(multi.items())[:25]],
    }


def _build_dashboard(report: dict[str, Any]) -> dict[str, Any]:
    dash: dict[str, Any] = {}
    if report.get("audit_dashboard"):
        rows = report["audit_dashboard"]
        if rows and isinstance(rows[0], dict) and "error" not in rows[0]:
            dash.update(rows[0])
    articles_total = 0
    enriched = 0
    context_linked = 0
    url_dup_extra = 0
    for inv in report.get("pack_1_domains", []):
        funnel = inv.get("coverage_funnel") or {}
        if isinstance(funnel, dict) and funnel.get("error"):
            art = inv.get("articles") or {}
            if isinstance(art, dict) and not art.get("error"):
                articles_total += int(art.get("total") or 0)
            continue
        articles_total += int(funnel.get("articles_total") or 0)
        enriched += int(funnel.get("enriched") or 0)
        context_linked += int(inv.get("articles_with_context") or 0)
    for d in report.get("pack_2_duplicates", {}).get("per_domain", []):
        url_dup_extra += int(d.get("url_duplicate_extra_rows") or 0)
    dash["articles_total_active_domains"] = articles_total
    dash["enriched_articles_active_domains"] = enriched
    dash["context_linked_articles_active_domains"] = context_linked
    dash["url_duplicate_extra_rows"] = url_dup_extra
    if articles_total:
        dash["context_coverage_pct"] = round(100.0 * context_linked / articles_total, 2)
        dash["enriched_pct"] = round(100.0 * enriched / articles_total, 2)
    return dash


def _build_actions(report: dict[str, Any]) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    if report.get("connectivity_note"):
        actions.append(
            {
                "priority": "high",
                "area": "connectivity",
                "finding": report["connectivity_note"],
                "action": "Re-run audit against Widow news_intel when host is reachable (production baseline)",
            }
        )
    gi = report.get("pack_1a_global_intelligence")
    if isinstance(gi, list) and gi and isinstance(gi[0], dict) and gi[0].get("error"):
        actions.append(
            {
                "priority": "high",
                "area": "schema",
                "finding": "intelligence layer missing or incomplete on connected database",
                "action": "Use Widow news_intel; NAS backup is legacy schema snapshot",
            }
        )
    dup = report.get("pack_2_duplicates", {})
    for d in dup.get("per_domain", []):
        extra = d.get("url_duplicate_extra_rows") or 0
        if extra and int(extra) > 100:
            actions.append(
                {
                    "priority": "high",
                    "area": "dedupe",
                    "finding": f"{d.get('domain_key')}: {extra} extra rows in URL duplicate groups",
                    "action": "Review article_duplicate_sources coverage; tighten RSS dedupe at ingest",
                }
            )
    claims = report.get("pack_2_global", {})
    claim_rows = claims.get("pack_2c_claim_duplicates") or []
    claim_dup_count = claims.get("claim_duplicate_groups")
    if (
        claim_dup_count
        and claim_rows
        and isinstance(claim_rows[0], dict)
        and "error" not in claim_rows[0]
    ):
        actions.append(
            {
                "priority": "medium",
                "area": "dedupe",
                "finding": f"{claims.get('claim_duplicate_groups')} claim duplicate groups",
                "action": "Run extracted_claims_dedupe automation or scripts/merge_duplicate_extracted_claims.py",
            }
        )
    auto = report.get("pack_3_automation", [])
    for row in auto:
        if row.get("runs_24h", 0) > 10 and (row.get("success_pct_24h") or 100) < 75:
            actions.append(
                {
                    "priority": "high",
                    "area": "pipeline",
                    "finding": f"Phase {row.get('phase')}: success_pct_24h={row.get('success_pct_24h')}",
                    "action": "Inspect automation_run_history message and api_server.log for phase",
                }
            )
    cross = report.get("pack_2_duplicates", {}).get("cross_domain_urls", {})
    if (cross.get("cross_domain_url_count") or 0) > 50:
        actions.append(
            {
                "priority": "medium",
                "area": "dedupe",
                "finding": f"{cross.get('cross_domain_url_count')} URLs appear in multiple domain silos",
                "action": "Review RSS_INGEST_EXCLUDE_DOMAIN_KEYS and cross-silo syndication policy",
            }
        )

    for inv in report.get("pack_1_domains", []):
        errs = inv.get("errors") or []
        art = inv.get("articles") or {}
        if isinstance(art, dict) and art.get("error"):
            continue
        if errs:
            actions.append(
                {
                    "priority": "high",
                    "area": "integrity",
                    "finding": f"{inv.get('domain_key')}: {errs[0]}",
                    "action": "Repair table/index corruption before further processing",
                }
            )
        funnel = inv.get("coverage_funnel") or {}
        if funnel.get("enriched_pct", 100) < 70 and (funnel.get("articles_total") or 0) > 1000:
            actions.append(
                {
                    "priority": "medium",
                    "area": "coverage",
                    "finding": f"{inv.get('domain_key')}: only {funnel.get('enriched_pct')}% enriched",
                    "action": "Check content_enrichment backlog and AUTOMATION_SKIP_RSS settings",
                }
            )
    if not actions:
        actions.append(
            {
                "priority": "info",
                "area": "baseline",
                "finding": "No critical thresholds tripped on this run",
                "action": "Store report JSON as baseline; re-run weekly",
            }
        )
    return actions


def run_audit(packs: set[str]) -> dict[str, Any]:
    from shared.database.connection import get_db_connection

    sql_path = os.path.join(os.path.dirname(__file__), "data_quality_audit.sql")
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packs_run": sorted(packs),
        "connection": {
            "host": os.environ.get("DB_HOST"),
            "port": os.environ.get("DB_PORT"),
            "database": os.environ.get("DB_NAME") or os.environ.get("DB_DATABASE"),
        },
        "database": None,
        "connectivity_note": None,
    }

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            report["database"] = _fetch_all(
                cur, "SELECT current_database() AS name, pg_database_size(current_database()) AS bytes"
            )[0]

            if _section_in_packs("pack_0_1_database", packs):
                sections = _run_sql_file_sections(sql_path, {"0"})
                report["pack_0"] = {}
                for name, sql in sections.items():
                    try:
                        report["pack_0"][name] = _fetch_all(cur, sql)
                    except Exception as e:
                        report["pack_0"][name] = {"error": str(e)}

            if _section_in_packs("pack_1a_global_intelligence", packs):
                sections = _run_sql_file_sections(sql_path, {"1"})
                for key in (
                    "pack_1a_global_intelligence",
                    "pack_1a_contexts_by_domain",
                    "pack_1a_tracked_events_narratives",
                    "pack_1a_refinement_queue_status",
                ):
                    if key in sections:
                        try:
                            report[key] = _fetch_all(cur, sections[key])
                        except Exception as e:
                            report[key] = {"error": str(e)}

                cur.execute(
                    "SELECT domain_key, schema_name FROM public.domains WHERE is_active = true ORDER BY display_order"
                )
                domains = cur.fetchall()
                report["pack_1_domains"] = [
                    _domain_inventory(cur, dk, sch) for dk, sch in domains
                ]

            if _section_in_packs("pack_2b_multi_context_per_article", packs):
                sections = _run_sql_file_sections(sql_path, {"2"})
                report["pack_2_global"] = {}
                for name, sql in sections.items():
                    try:
                        rows = _fetch_all(cur, sql)
                        report["pack_2_global"][name] = rows
                        if name == "pack_2c_claim_duplicates" and rows and "error" not in rows[0]:
                            report["pack_2_global"]["claim_duplicate_groups"] = len(rows)
                    except Exception as e:
                        report["pack_2_global"][name] = {"error": str(e)}

                cur.execute(
                    "SELECT domain_key, schema_name FROM public.domains WHERE is_active = true ORDER BY display_order"
                )
                domains_dup = cur.fetchall()
                report["pack_2_duplicates"] = {
                    "per_domain": [
                        _domain_duplicates(cur, dk, sch) for dk, sch in domains_dup
                    ],
                    "cross_domain_urls": _cross_domain_url_dupes(cur),
                }

            if _section_in_packs("pack_3a_automation_phase_stats", packs):
                sections = _run_sql_file_sections(sql_path, {"3"})
                if "pack_3a_automation_phase_stats" in sections:
                    report["pack_3_automation"] = _fetch_all(
                        cur, sections["pack_3a_automation_phase_stats"]
                    )
                if "pack_3a_automation_recent_failures" in sections:
                    report["pack_3_automation_failures"] = _fetch_all(
                        cur, sections["pack_3a_automation_recent_failures"]
                    )

                cur.execute(
                    "SELECT domain_key, schema_name FROM public.domains WHERE is_active = true ORDER BY display_order"
                )
                report["pack_3_pipeline"] = {
                    "per_domain": [
                        _domain_pipeline(cur, sch) for _, sch in cur.fetchall()
                    ]
                }

            if packs == {"all"} or "4" in packs:
                if _table_exists(cur, "legal", "storylines"):
                    try:
                        report["pack_4_legal_storylines"] = _safe_count(
                            cur, "SELECT count(*) FROM legal.storylines"
                        )
                    except Exception as e:
                        report["pack_4_legal_storylines"] = {"error": str(e)}

            if _section_in_packs("pack_5_applied_migrations", packs):
                sections = _run_sql_file_sections(sql_path, {"5"})
                if "pack_5_core_tables_per_active_domain" in sections:
                    try:
                        report["pack_5_core_tables_per_active_domain"] = _fetch_all(
                            cur, sections["pack_5_core_tables_per_active_domain"]
                        )
                    except Exception as e:
                        report["pack_5_core_tables_per_active_domain"] = {"error": str(e)}
                report["pack_5"] = {}
                for name, sql in sections.items():
                    try:
                        report["pack_5"][name] = _fetch_all(cur, sql)
                    except Exception as e:
                        report["pack_5"][name] = {"error": str(e)}

            if _section_in_packs("audit_dashboard", packs):
                sections = _run_sql_file_sections(sql_path, {"all"})
                if "audit_dashboard" in sections:
                    report["audit_dashboard"] = _fetch_all(cur, sections["audit_dashboard"])

        if os.environ.get("DB_HOST") == "localhost" and os.environ.get("DB_PORT") == "5433":
            report["connectivity_note"] = (
                "Widow unreachable; audit ran against NAS tunnel (localhost:5433). "
                "Re-run on Widow news_intel when 192.168.93.101 is online for production baseline."
            )
        report["audit_dashboard_summary"] = _build_dashboard(report)
        report["recommended_actions"] = _build_actions(report)
    finally:
        conn.close()

    return report


def _write_markdown(report: dict[str, Any], path: str) -> None:
    lines = [
        "# Data quality audit report",
        "",
        f"Generated: {report.get('generated_at')}",
        "",
    ]
    if report.get("connectivity_note"):
        lines.extend(["## Connectivity", "", report["connectivity_note"], ""])
    dash = report.get("audit_dashboard_summary") or {}
    if dash:
        lines.extend(["## Dashboard KPIs", ""])
        for k, v in dash.items():
            lines.append(f"- {k}: {v}")
        lines.append("")
    lines.extend(["## Recommended actions", ""])
    for a in report.get("recommended_actions", []):
        lines.append(
            f"- **{a.get('priority', '').upper()}** [{a.get('area')}]: {a.get('finding')} — {a.get('action')}"
        )
    lines.extend(["", "## Pack 1 domain summary", ""])
    for inv in report.get("pack_1_domains", []):
        funnel = inv.get("coverage_funnel") or {}
        art = inv.get("articles") or {}
        total = funnel.get("articles_total") or art.get("total")
        lines.append(
            f"- **{inv.get('domain_key')}** (`{inv.get('schema_name')}`): "
            f"articles={total}, enriched={funnel.get('enriched_pct')}%, "
            f"context_linked={inv.get('articles_with_context')}, errors={inv.get('errors')}"
        )
    lines.extend(["", "## Pack 2 duplicate signals", ""])
    g = report.get("pack_2_global", {})
    lines.append(f"- Claim duplicate groups (sample cap 50): {g.get('claim_duplicate_groups', 'n/a')}")
    for d in report.get("pack_2_duplicates", {}).get("per_domain", []):
        lines.append(
            f"- **{d.get('domain_key')}**: url_extra_rows={d.get('url_duplicate_extra_rows')}, "
            f"multi_storyline_articles={d.get('articles_on_multiple_storylines')}"
        )
    lines.extend(["", "## Pack 3 automation (24h)", ""])
    for row in (report.get("pack_3_automation") or [])[:15]:
        lines.append(
            f"- {row.get('phase')}: runs_24h={row.get('runs_24h')}, success_pct={row.get('success_pct_24h')}%"
        )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run News Intelligence data quality audit")
    parser.add_argument(
        "--packs",
        default="all",
        help="Comma-separated pack numbers 0-5 or 'all' (default: all)",
    )
    args = parser.parse_args()
    if args.packs.strip().lower() == "all":
        packs = {"all"}
    else:
        packs = {p.strip() for p in args.packs.split(",")}

    report = run_audit(packs)
    out_dir = os.path.join(ROOT, "diagnostics")
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "data_quality_report.json")
    md_path = os.path.join(out_dir, "DATA_QUALITY_AUDIT_REPORT.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=_json_default)
    _write_markdown(report, md_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
