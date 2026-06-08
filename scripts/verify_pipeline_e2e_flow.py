#!/usr/bin/env python3
"""
End-to-end pipeline flow verification — real data, not just automation success flags.

Checks that each major phase:
  1. Is enabled (context_centric / automation schedules)
  2. Has recent automation_run_history (or explains SKIP_WHEN_EMPTY)
  3. Writes to expected tables with recent rows

From repo root:
  PYTHONPATH=api uv run python scripts/verify_pipeline_e2e_flow.py
  PYTHONPATH=api uv run python scripts/verify_pipeline_e2e_flow.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (str(ROOT), str(ROOT / "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / "api" / ".env", override=False)
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    pass

# Pipeline stages in rough ingest→intelligence order
STAGES: list[dict] = [
    {
        "phase": "collection_cycle",
        "label": "RSS / collection",
        "tables": [("{schema}", "articles", "created_at", "24 hours")],
        "orchestrator": True,
    },
    {
        "phase": "content_enrichment",
        "label": "Content enrichment",
        "tables": [("{schema}", "articles", "updated_at", "24 hours", "enrichment_status IS NOT NULL")],
    },
    {
        "phase": "context_sync",
        "label": "Context sync",
        "tables": [("intelligence", "contexts", "created_at", "7 days")],
        "context_centric": True,
    },
    {
        "phase": "entity_extraction",
        "label": "Entity extraction",
        "tables": [("{schema}", "article_entities", "created_at", "7 days")],
        "orchestrator": True,
    },
    {
        "phase": "entity_profile_sync",
        "label": "Entity profile sync",
        "tables": [("intelligence", "entity_profiles", "updated_at", "7 days")],
        "context_centric": True,
    },
    {
        "phase": "claim_extraction",
        "label": "Claim extraction",
        "tables": [("intelligence", "extracted_claims", "created_at", "7 days")],
        "context_centric": True,
        "orchestrator": True,
    },
    {
        "phase": "claims_to_facts",
        "label": "Claims → facts",
        "tables": [
            (
                "intelligence",
                "versioned_facts",
                "created_at",
                "7 days",
                "extraction_method = 'claim_extraction'",
            )
        ],
    },
    {
        "phase": "event_extraction",
        "label": "Event extraction",
        "tables": [("public", "chronological_events", "created_at", "7 days")],
    },
    {
        "phase": "topic_clustering",
        "label": "Topic clustering",
        "tables": [("{schema}", "topics", "created_at", "30 days")],
        "orchestrator": True,
    },
    {
        "phase": "storyline_discovery",
        "label": "Storyline discovery",
        "tables": [("{schema}", "storylines", "created_at", "30 days")],
    },
    {
        "phase": "embeddings_worker",
        "label": "Embeddings worker",
        "tables": [("intelligence", "embedding_chunks", "ingestion_date", "30 days")],
    },
]


def _load_orchestrator_phases() -> set[str]:
    path = ROOT / "api" / "config" / "orchestrator_governance.yaml"
    if not path.is_file():
        return set()
    try:
        import yaml

        data = yaml.safe_load(path.read_text()) or {}
        phases = (data.get("processing") or {}).get("phases") or []
        return {str(p) for p in phases}
    except Exception:
        return set()


def _context_centric_enabled(phase: str) -> bool | None:
    path = ROOT / "api" / "config" / "context_centric.yaml"
    if not path.is_file():
        return None
    try:
        import yaml

        tasks = (yaml.safe_load(path.read_text()) or {}).get("tasks") or {}
        if phase not in tasks:
            return None
        return bool(tasks[phase])
    except Exception:
        return None


def _count_recent(
    cur,
    schema: str,
    table: str,
    ts_col: str,
    interval: str,
    extra_where: str = "",
) -> int:
    where = f"{ts_col} >= NOW() - INTERVAL '{interval}'"
    if extra_where:
        where += f" AND ({extra_where})"
    cur.execute(f"SELECT COUNT(*) FROM {schema}.{table} WHERE {where}")
    return int(cur.fetchone()[0] or 0)


def _phase_runs(cur, phase: str, days: int = 7) -> dict:
    cur.execute(
        """
        SELECT COUNT(*),
               COUNT(*) FILTER (WHERE success = true),
               MAX(finished_at)
        FROM public.automation_run_history
        WHERE phase_name = %s
          AND started_at >= NOW() - make_interval(days => %s)
        """,
        (phase, days),
    )
    total, ok, last = cur.fetchone()
    return {"runs": int(total or 0), "success": int(ok or 0), "last_finished": last}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify E2E pipeline data flow")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    from shared.database.connection import get_db_connection_context
    from shared.domain_registry import get_pipeline_active_domain_keys, resolve_domain_schema

    orch_phases = _load_orchestrator_phases()
    domains = list(get_pipeline_active_domain_keys())
    schemas = [resolve_domain_schema(d) for d in domains]

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_domains": domains,
        "orchestrator_phases": sorted(orch_phases),
        "preflight": {},
        "stages": [],
        "domain_funnel": {},
        "warnings": [],
        "empty_success_risks": [],
    }

    # Preflight
    try:
        import requests

        ollama = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
        r = requests.get(f"{ollama.rstrip('/')}/api/tags", timeout=5)
        report["preflight"]["ollama"] = r.status_code == 200
    except Exception as e:
        report["preflight"]["ollama"] = False
        report["warnings"].append(f"Ollama unreachable: {e}")

    with get_db_connection_context() as conn:
        if not conn:
            print("ERROR: no database connection", file=sys.stderr)
            return 1
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            report["preflight"]["postgres"] = True

            # Domain funnel
            for dk in domains:
                sch = resolve_domain_schema(dk)
                funnel = {"domain_key": dk, "schema": sch}
                cur.execute(f"SELECT COUNT(*) FROM {sch}.articles")
                funnel["articles"] = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.contexts c
                    JOIN intelligence.article_to_context atc ON atc.context_id = c.id
                    WHERE atc.domain_key = %s
                    """,
                    (dk,),
                )
                funnel["contexts_linked"] = cur.fetchone()[0]
                cur.execute(f"SELECT COUNT(*) FROM {sch}.article_entities")
                funnel["article_entities"] = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(*) FROM intelligence.entity_profiles WHERE domain_key = %s",
                    (dk,),
                )
                funnel["entity_profiles"] = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.extracted_claims ec
                    JOIN intelligence.article_to_context atc ON atc.context_id = ec.context_id
                    WHERE atc.domain_key = %s
                    """,
                    (dk,),
                )
                funnel["extracted_claims"] = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT COUNT(*) FROM intelligence.versioned_facts vf
                    JOIN intelligence.entity_profiles ep ON ep.id = vf.entity_profile_id
                    WHERE ep.domain_key = %s AND vf.extraction_method = 'claim_extraction'
                    """,
                    (dk,),
                )
                funnel["versioned_facts"] = cur.fetchone()[0]
                report["domain_funnel"][dk] = funnel

            # Pass-marker empty outcomes (claim extraction)
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.contexts c
                LEFT JOIN intelligence.extracted_claims ec ON ec.context_id = c.id
                WHERE ec.id IS NULL
                  AND c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_outcome'
                      IN ('parsed_empty', 'no_claims_after_filters', 'skipped_short_text')
                """
            )
            pass_empty = int(cur.fetchone()[0] or 0)
            if pass_empty > 0:
                report["empty_success_risks"].append(
                    f"{pass_empty} contexts pass-marked without claims (may be legitimate filters or LLM empty parse)"
                )

            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.contexts c
                WHERE (c.metadata::jsonb->'pipeline'->'claim_extraction'->>'last_pass_at') IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM intelligence.extracted_claims ec WHERE ec.context_id = c.id)
                """
            )
            marked_no_claims = int(cur.fetchone()[0] or 0)
            report["claim_contexts_pass_marked_no_claims"] = marked_no_claims

            for stage in STAGES:
                phase = stage["phase"]
                entry = {
                    "phase": phase,
                    "label": stage["label"],
                    "orchestrator_can_request": phase in orch_phases or stage.get("orchestrator") is False,
                    "in_orchestrator_yaml": phase in orch_phases,
                    "context_centric_enabled": _context_centric_enabled(phase)
                    if stage.get("context_centric")
                    else None,
                    "automation_runs_7d": _phase_runs(cur, phase, args.days),
                    "recent_row_counts": {},
                    "status": "ok",
                    "notes": [],
                }

                if entry["context_centric_enabled"] is False:
                    entry["status"] = "disabled"
                    entry["notes"].append("context_centric.yaml task=false — handler may no-op")
                runs = entry["automation_runs_7d"]["runs"]
                recent_total = 0
                for spec in stage.get("tables", []):
                    schema_tok, table, ts_col, interval = spec[:4]
                    extra = spec[4] if len(spec) > 4 else ""
                    if schema_tok == "{schema}":
                        counts = {}
                        for sch in schemas:
                            try:
                                counts[sch] = _count_recent(cur, sch, table, ts_col, interval, extra)
                            except Exception as e:
                                counts[sch] = f"error:{e}"
                        entry["recent_row_counts"][table] = counts
                        recent_total += sum(c for c in counts.values() if isinstance(c, int))
                    else:
                        try:
                            n = _count_recent(cur, schema_tok, table, ts_col, interval, extra)
                        except Exception as e:
                            n = f"error:{e}"
                        entry["recent_row_counts"][f"{schema_tok}.{table}"] = n
                        if isinstance(n, int):
                            recent_total += n

                if runs == 0 and recent_total == 0:
                    entry["status"] = "idle"
                    entry["notes"].append("No automation runs and no recent rows — backlog empty or phase skipped")
                elif runs > 0 and recent_total == 0:
                    entry["status"] = "warn"
                    entry["notes"].append(
                        "Automation ran but no recent output rows — check pass markers, filters, or external API keys"
                    )
                elif runs == 0 and recent_total > 0:
                    entry["notes"].append("Recent data exists but no automation runs in window (manual/catchup?)")

                report["stages"].append(entry)

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"Pipeline E2E verification — {report['generated_at']}\n")
        print(f"Preflight: postgres={report['preflight'].get('postgres')} ollama={report['preflight'].get('ollama')}")
        print(f"Active domains: {', '.join(domains)}")
        print(f"Orchestrator phases ({len(orch_phases)}): {', '.join(sorted(orch_phases))}\n")

        print("=== Domain funnel ===")
        for dk, f in report["domain_funnel"].items():
            print(
                f"  {dk}: articles={f['articles']} contexts={f['contexts_linked']} "
                f"entities={f['article_entities']} profiles={f['entity_profiles']} "
                f"claims={f['extracted_claims']} facts={f['versioned_facts']}"
            )

        print("\n=== Pipeline stages ===")
        for s in report["stages"]:
            runs = s["automation_runs_7d"]
            flag = {"ok": "✓", "warn": "!", "idle": "○", "disabled": "×"}.get(s["status"], "?")
            print(f"  [{flag}] {s['label']} ({s['phase']})")
            print(f"      runs_7d={runs['runs']} success={runs['success']} last={runs['last_finished']}")
            if s.get("in_orchestrator_yaml"):
                print("      orchestrator: yes")
            if s.get("notes"):
                for n in s["notes"]:
                    print(f"      note: {n}")
            rc = s.get("recent_row_counts") or {}
            if rc:
                print(f"      recent_rows: {json.dumps(rc, default=str)[:200]}")

        if report["warnings"]:
            print("\n=== Warnings ===")
            for w in report["warnings"]:
                print(f"  - {w}")
        if report["empty_success_risks"]:
            print("\n=== Empty-success risks ===")
            for w in report["empty_success_risks"]:
                print(f"  - {w}")
        print(f"\nContexts pass-marked without claims: {report.get('claim_contexts_pass_marked_no_claims', 0)}")

    warn_count = sum(1 for s in report["stages"] if s["status"] in ("warn", "disabled"))
    idle_count = sum(1 for s in report["stages"] if s["status"] == "idle")
    return 1 if warn_count > 0 else (0 if idle_count < len(report["stages"]) else 0)


if __name__ == "__main__":
    raise SystemExit(main())
