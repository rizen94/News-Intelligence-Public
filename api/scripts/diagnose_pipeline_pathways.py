#!/usr/bin/env python3
"""
Pipeline pathway diagnostic — collection → enrichment → context → claims → storylines.

Writes JSON summary to stdout.

  PYTHONPATH=api python3 api/scripts/diagnose_pipeline_pathways.py
  DEBUG_RUN_ID=baseline-before PYTHONPATH=api python3 api/scripts/diagnose_pipeline_pathways.py > docs/pipeline_repair/snapshot.json
"""

from __future__ import annotations

from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

LOG_PATH = Path(__file__).resolve().parents[2] / ".cursor" / "pipeline-pathways-audit.jsonl"
RUN_ID = env_str("DEBUG_RUN_ID", "pathway-audit")
WIDOW_ADJACENT_LOG = Path("/opt/news-intelligence/logs/widow_db_adjacent.log")


def _pipeline_domain_schema_pairs() -> list[tuple[str, str]]:
    try:
        from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

        keys = get_pipeline_active_domain_keys()
        if keys:
            return [(k, resolve_domain_schema(k)) for k in keys]
    except Exception:
        pass
    return [("politics", "politics"), ("finance", "finance")]


def _pipeline_schema_names() -> list[str]:
    return [schema for _, schema in _pipeline_domain_schema_pairs()]


def _log(section: str, location: str, message: str, data: dict) -> None:
    payload = {
        "section": section,
        "runId": RUN_ID,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    line = json.dumps(payload, default=str) + "\n"
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass
    print(line, end="")


def _scalar(cur, sql: str, params=()) -> int:
    cur.execute(sql, params)
    row = cur.fetchone()
    return int(row[0] or 0) if row else 0


def _tail_log(path: Path, lines: int = 5) -> list[str]:
    if not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return text[-lines:]
    except OSError:
        return []


def main() -> int:
    from shared.database.connection import get_db_connection_context

    summary: dict = {"ts": datetime.now(timezone.utc).isoformat()}
    _log("INIT", "diagnose_pipeline_pathways.py:main", "diagnostic_start", {"ts": summary["ts"]})

    with get_db_connection_context() as conn:
        if not conn:
            print(json.dumps({"ok": False, "error": "no_db"}))
            return 1

        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = '60s'")

            cur.execute(
                """
                SELECT phase_name, MAX(started_at), COUNT(*) FILTER (WHERE success)
                FROM public.automation_run_history
                WHERE phase_name IN (
                    'context_sync', 'nightly_enrichment_context', 'content_enrichment',
                    'collection_cycle', 'entity_extraction', 'embeddings_worker'
                )
                  AND started_at >= NOW() - INTERVAL '30 days'
                GROUP BY phase_name
                """
            )
            automation = {r[0]: {"last_run": str(r[1]), "success_count": r[2]} for r in cur.fetchall()}
            summary["automation_30d"] = automation
            _log("H1", "diagnose", "automation_runs", automation)

            cron_tail = _tail_log(WIDOW_ADJACENT_LOG, 8)
            summary["widow_db_adjacent_log_tail"] = cron_tail
            _log("H1b", "diagnose", "cron_context_sync_log", {"tail": cron_tail})

            gaps = {}
            for domain, schema in _pipeline_domain_schema_pairs():
                total = _scalar(cur, f"SELECT COUNT(*) FROM {schema}.articles")
                matched = _scalar(
                    cur,
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    WHERE EXISTS (
                        SELECT 1 FROM intelligence.contexts c
                        WHERE c.domain_key = %s AND c.metadata->>'url' = a.url
                    )
                    """,
                    (domain,),
                )
                recent_gap = _scalar(
                    cur,
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    WHERE a.created_at >= NOW() - INTERVAL '7 days'
                      AND NOT EXISTS (
                        SELECT 1 FROM intelligence.contexts c
                        WHERE c.domain_key = %s AND c.metadata->>'url' = a.url
                      )
                    """,
                    (domain,),
                )
                gaps[domain] = {
                    "articles": total,
                    "url_matched": matched,
                    "gap": total - matched,
                    "recent_7d_unsynced": recent_gap,
                }
            summary["context_gaps"] = gaps
            _log("H2", "diagnose", "context_gaps", gaps)

            from shared.pipeline_pass_marker import sql_article_pass_null

            entity = {}
            for schema in _pipeline_schema_names():
                needs = _scalar(
                    cur,
                    f"SELECT COUNT(*) FROM {schema}.articles a WHERE {sql_article_pass_null('entity_extraction', 'a')}",
                )
                false_legacy = _scalar(
                    cur,
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    LEFT JOIN {schema}.article_entities ae ON ae.article_id = a.id
                    WHERE ae.id IS NULL
                      AND (a.metadata::jsonb->'pipeline'->'entity_extraction'->>'last_outcome') = 'no_entities_stored'
                      AND LENGTH(COALESCE(a.content, '')) > 400
                    """,
                )
                entity[schema] = {"needs_processing": needs, "false_no_entities_stored": false_legacy}
            cur.execute(
                """
                SELECT COUNT(*) FROM public.automation_run_history
                WHERE phase_name = 'entity_extraction'
                  AND started_at >= NOW() - INTERVAL '14 days'
                """
            )
            entity["runs_14d"] = int(cur.fetchone()[0] or 0)
            summary["entity_extraction"] = entity
            _log("H3", "diagnose", "entity_extraction", entity)

            arrival_7d: dict[str, int] = {}
            for schema in _pipeline_schema_names():
                arrival_7d[schema] = _scalar(
                    cur,
                    f"SELECT COUNT(*) FROM {schema}.articles WHERE created_at >= NOW() - INTERVAL '7 days'",
                )
            cur.execute(
                """
                SELECT phase_name, COUNT(*)
                FROM public.automation_run_history
                WHERE success = true
                  AND started_at >= NOW() - INTERVAL '7 days'
                  AND phase_name IN (
                    'entity_extraction', 'claim_extraction', 'content_enrichment', 'collection_cycle'
                  )
                GROUP BY phase_name
                """
            )
            phase_runs_7d = {r[0]: int(r[1]) for r in cur.fetchall()}
            entity_batch = int(env_str("ENTITY_EXTRACTION_ARTICLES_PER_DOMAIN", "40"))
            try:
                from shared.domain_registry import get_pipeline_active_domain_keys

                n_domains = len(get_pipeline_active_domain_keys())
            except Exception:
                n_domains = 3
            summary["intake_vs_throughput_7d"] = {
                "articles_arrived": arrival_7d,
                "phase_success_runs": phase_runs_7d,
                "entity_batch_per_domain": entity_batch,
                "entity_throughput_estimate": (
                    phase_runs_7d.get("entity_extraction", 0) * entity_batch * n_domains
                ),
            }
            _log("H4b", "diagnose", "intake_throughput", summary["intake_vs_throughput_7d"])

            cur.execute(
                """
                SELECT
                  c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_outcome' AS o,
                  COUNT(*)
                FROM intelligence.contexts c
                WHERE c.source_type = 'article'
                  AND (c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_pass_at') IS NOT NULL
                GROUP BY 1 ORDER BY 2 DESC LIMIT 10
                """
            )
            claim_outcomes = {str(r[0]): r[1] for r in cur.fetchall()}
            summary["claim_outcomes"] = claim_outcomes
            _log("H4", "diagnose", "claim_outcomes", claim_outcomes)

            emb = _scalar(cur, "SELECT COUNT(*) FROM intelligence.embedding_chunks")
            orphan = {}
            for schema in _pipeline_schema_names():
                t = _scalar(cur, f"SELECT COUNT(*) FROM {schema}.articles")
                u = _scalar(
                    cur,
                    f"""
                    SELECT COUNT(*) FROM {schema}.articles a
                    WHERE NOT EXISTS (
                        SELECT 1 FROM {schema}.storyline_articles sa WHERE sa.article_id = a.id
                    )
                    """,
                )
                orphan[schema] = {"unlinked": u, "pct": round(100 * u / max(t, 1), 1)}
            summary["embeddings_chunks"] = emb
            summary["storyline_orphans"] = orphan
            _log("H5", "diagnose", "embeddings_storylines", {"embedding_chunks": emb, **orphan})

            try:
                from config.investigation_tables import T_WATERMARKS

                cur.execute(
                    f"SELECT name, last_value FROM {T_WATERMARKS} WHERE name = 'mention_resolver'"
                )
                row = cur.fetchone()
                wm = int(row[1]) if row else 0
                max_mention = _scalar(
                    cur, "SELECT COALESCE(MAX(id), 0) FROM intelligence.context_entity_mentions"
                )
                summary["nri"] = {
                    "mention_resolver_watermark": wm,
                    "max_context_entity_mention_id": max_mention,
                    "lag_ids": max_mention - wm,
                }
                _log("H8", "diagnose", "nri_watermark", summary["nri"])
            except Exception as e:
                summary["nri"] = {"error": str(e)[:120]}
                _log("H8", "diagnose", "nri_watermark_error", {"error": str(e)})

            cur.execute(
                """
                SELECT LEFT(error_message, 80), COUNT(*)
                FROM public.automation_run_history
                WHERE phase_name = 'health_check' AND success = false
                  AND started_at >= NOW() - INTERVAL '24 hours'
                GROUP BY 1 ORDER BY 2 DESC LIMIT 5
                """
            )
            hc_fail = {str(r[0]): r[1] for r in cur.fetchall()}
            summary["health_check_failures_24h"] = hc_fail
            _log("H7", "diagnose", "pool_health", hc_fail)

            try:
                from services.backlog_metrics import get_all_pending_counts, get_all_backlog_counts

                pending = get_all_pending_counts()
                backlog = get_all_backlog_counts()
                top = sorted(
                    ((k, backlog.get(k, 0)) for k in backlog),
                    key=lambda x: -x[1],
                )[:12]
                summary["top_backlogs"] = top
                summary["pending_entity_extraction"] = pending.get("entity_extraction")
                summary["pending_context_sync"] = pending.get("context_sync")
                _log("H7b", "diagnose", "backlog_metrics", {"top": top})
            except Exception as e:
                summary["backlog_metrics_error"] = str(e)[:200]

    try:
        from services.pipeline_schedule_service import pipeline_schedule_info

        summary["pipeline_schedule"] = pipeline_schedule_info()
        _log("H6", "diagnose", "schedule", summary["pipeline_schedule"])
    except Exception as e:
        summary["pipeline_schedule"] = {"error": str(e)}

    try:
        from services.pipeline_phase_heartbeat_service import list_phase_heartbeats, stalled_phases

        summary["phase_heartbeats"] = list_phase_heartbeats()
        summary["stalled_phases"] = stalled_phases()
    except Exception as e:
        summary["phase_heartbeats_error"] = str(e)[:120]

    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:8000/api/system_monitoring/backlog_status", timeout=60
        ) as resp:
            bl = json.loads(resp.read().decode())
        summary["steady_state_ok"] = (bl.get("data") or {}).get("steady_state", {}).get("ok")
    except Exception as e:
        summary["backlog_api_error"] = str(e)[:120]

    _log("DONE", "diagnose", "complete", {})
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
