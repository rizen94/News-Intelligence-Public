#!/usr/bin/env python3
"""
Capture live Widow/host ground truth for documentation fact-checks.

Read-only. From repo root:
  PYTHONPATH=api python3 scripts/verify_documentation_ground_truth.py
  PYTHONPATH=api python3 scripts/verify_documentation_ground_truth.py --write-report

Writes markdown to docs/generated/WIDOW_GROUND_TRUTH_YYYY-MM-DD.md when --write-report is set.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import date, datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (ROOT, os.path.join(ROOT, "api")):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, "api", ".env"), override=False)
    load_dotenv(os.path.join(ROOT, ".env"), override=False)
except ImportError:
    pass

ENV_KEYS = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "PIPELINE_INCLUDE_DOMAIN_KEYS",
    "PIPELINE_EXCLUDE_DOMAIN_KEYS",
    "RSS_INGEST_MIRROR_PIPELINE",
    "AUTOMATION_SKIP_RSS_IN_COLLECTION_CYCLE",
    "AUTOMATION_DISABLED_SCHEDULES",
    "AUTOMATION_MAX_CONCURRENT_TASKS",
    "OLLAMA_HOST",
    "OLLAMA_POP_OS_HOST",
    "OLLAMA_DUAL_HOST_ROUTING_ENABLED",
    "USE_INVESTIGATION_PREFIXED_TABLES",
)

SYSTEMD_UNITS = (
    "news-intelligence-api-public",
    "nri-api",
    "newsplatform-secondary",
)

TOPIC_TABLES = ("topic_clusters", "topic_keywords", "article_topic_clusters", "mv_topic_index")


def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=15).strip()
    except Exception as e:
        return f"(unavailable: {e})"


def _systemd_state(unit: str) -> dict[str, str]:
    active = _run(["systemctl", "is-active", unit])
    enabled = _run(["systemctl", "is-enabled", unit])
    return {"active": active, "enabled": enabled}


def _cron_files() -> list[str]:
    out: list[str] = []
    cron_dir = "/etc/cron.d"
    if os.path.isdir(cron_dir):
        for name in sorted(os.listdir(cron_dir)):
            if "news" in name.lower() or "widow" in name.lower():
                out.append(os.path.join(cron_dir, name))
    return out


def collect_snapshot() -> dict:
    from shared.database.connection import get_db_connection
    from shared.domain_registry import (
        get_active_domain_keys,
        get_pipeline_active_domain_keys,
        get_pipeline_excluded_domain_keys,
        get_pipeline_included_domain_keys,
        pipeline_url_schema_pairs,
        resolve_domain_schema,
    )

    snap: dict = {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "hostname": _run(["hostname"]) or os.uname().nodename,
        "env": {k: os.environ.get(k, "") for k in ENV_KEYS},
        "registry": {},
        "schemas": {},
        "migrations": {},
        "systemd": {},
        "cron_files": _cron_files(),
    }

    snap["registry"] = {
        "active_domain_keys": list(get_active_domain_keys()),
        "pipeline_active_domain_keys": list(get_pipeline_active_domain_keys()),
        "pipeline_include_env": sorted(get_pipeline_included_domain_keys() or []),
        "pipeline_exclude_env": sorted(get_pipeline_excluded_domain_keys()),
        "url_schema_pairs": list(pipeline_url_schema_pairs()),
    }

    conn = get_db_connection()
    if not conn:
        snap["db_error"] = "no connection"
        return snap

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT domain_key, schema_name, is_active, display_order
                FROM public.domains
                ORDER BY display_order NULLS LAST, domain_key
                """
            )
            snap["public_domains"] = [
                {
                    "domain_key": r[0],
                    "schema_name": r[1],
                    "is_active": r[2],
                    "display_order": r[3],
                }
                for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT migration_id, applied_at::text
                FROM public.applied_migrations
                ORDER BY applied_at DESC
                LIMIT 15
                """
            )
            snap["migrations"]["recent_ledger"] = [
                {"migration_id": r[0], "applied_at": r[1]} for r in cur.fetchall()
            ]

            cur.execute(
                """
                SELECT migration_id FROM public.applied_migrations
                WHERE migration_id ~ '^[0-9]+$'
                ORDER BY migration_id::int DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()
            snap["migrations"]["ledger_max_numeric"] = row[0] if row else None

            mig_dir = os.path.join(ROOT, "api", "database", "migrations")
            if os.path.isdir(mig_dir):
                disk = []
                for name in sorted(os.listdir(mig_dir)):
                    if name.endswith(".sql") and name[0].isdigit():
                        disk.append(name.split("_")[0])
                snap["migrations"]["disk_max_numeric"] = max((int(x) for x in disk), default=None)

            cur.execute(
                "SELECT nspname FROM pg_namespace WHERE nspname LIKE '%science%' ORDER BY 1"
            )
            snap["science_namespaces"] = [r[0] for r in cur.fetchall()]

            for dk in get_pipeline_active_domain_keys():
                sch = resolve_domain_schema(dk)
                tables: dict[str, bool] = {}
                for tbl in TOPIC_TABLES:
                    cur.execute("SELECT to_regclass(%s)", (f"{sch}.{tbl}",))
                    tables[tbl] = cur.fetchone()[0] is not None
                snap["schemas"][sch] = {"domain_key": dk, "tables": tables}
    finally:
        conn.close()

    for unit in SYSTEMD_UNITS:
        snap["systemd"][unit] = _systemd_state(unit)

    return snap


def render_markdown(snap: dict) -> str:
    lines = [
        f"# Widow ground truth snapshot",
        "",
        f"**Captured:** {snap.get('captured_at_utc')} UTC  ",
        f"**Host:** `{snap.get('hostname', '?')}`",
        "",
        "<!-- Auto-generated by scripts/verify_documentation_ground_truth.py -->",
        "",
        "## Domain registry (code)",
        "",
        f"- **Active:** `{snap['registry'].get('active_domain_keys')}`",
        f"- **Pipeline-active:** `{snap['registry'].get('pipeline_active_domain_keys')}`",
        f"- **PIPELINE_INCLUDE (parsed):** `{snap['registry'].get('pipeline_include_env') or '(unset — all active)'}`",
        f"- **PIPELINE_EXCLUDE:** `{snap['registry'].get('pipeline_exclude_env') or '(unset)'}`",
        "",
        "## public.domains (database)",
        "",
        "| domain_key | schema | is_active |",
        "|------------|--------|-----------|",
    ]
    for row in snap.get("public_domains", []):
        lines.append(
            f"| {row['domain_key']} | {row['schema_name']} | {row['is_active']} |"
        )

    lines.extend(
        [
            "",
            "## Topic cluster tables per schema",
            "",
            "| schema | topic_clusters | topic_keywords | article_topic_clusters | mv_topic_index |",
            "|--------|----------------|----------------|----------------------|----------------|",
        ]
    )
    for sch, info in sorted(snap.get("schemas", {}).items()):
        t = info.get("tables", {})
        lines.append(
            f"| {sch} | {t.get('topic_clusters')} | {t.get('topic_keywords')} | "
            f"{t.get('article_topic_clusters')} | {t.get('mv_topic_index')} |"
        )

    lines.extend(["", "## Environment (subset)", "", "```", json.dumps(snap.get("env", {}), indent=2), "```"])

    lines.extend(["", "## systemd", ""])
    for unit, st in snap.get("systemd", {}).items():
        lines.append(f"- `{unit}`: active={st.get('active')}, enabled={st.get('enabled')}")

    lines.extend(["", "## Cron files", ""])
    for path in snap.get("cron_files", []):
        lines.append(f"- `{path}`")

    mig = snap.get("migrations", {})
    lines.extend(
        [
            "",
            "## Migrations ledger",
            "",
            f"- Ledger max (numeric id): **{mig.get('ledger_max_numeric')}**",
            f"- Disk max migration file: **{mig.get('disk_max_numeric')}**",
            "",
            "Recent ledger entries:",
            "",
        ]
    )
    for row in mig.get("recent_ledger", []):
        lines.append(f"- `{row['migration_id']}` @ {row['applied_at']}")

    lines.append("")
    lines.append(f"- science-tech namespaces: `{snap.get('science_namespaces', [])}`")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", action="store_true", help="Write docs/generated/WIDOW_GROUND_TRUTH_*.md")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout")
    args = parser.parse_args()

    snap = collect_snapshot()
    md = render_markdown(snap)

    if args.json:
        print(json.dumps(snap, indent=2))
    else:
        print(md)

    if args.write_report:
        out_dir = os.path.join(ROOT, "docs", "generated")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"WIDOW_GROUND_TRUTH_{date.today().isoformat()}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"\nWrote {path}", file=sys.stderr)

    ledger_max = snap.get("migrations", {}).get("ledger_max_numeric")
    disk_max = snap.get("migrations", {}).get("disk_max_numeric")
    if ledger_max and disk_max and int(ledger_max) < int(disk_max):
        print(
            f"WARN: ledger behind disk ({ledger_max} < {disk_max}) — register missing migrations",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
