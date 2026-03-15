#!/usr/bin/env python3
"""Run migrations 140 through 154 in order.

From project root:
  PYTHONPATH=api .venv/bin/python3 api/scripts/run_migrations_140_to_152.py

Or from api dir:
  python3 scripts/run_migrations_140_to_152.py

Uses DB from env (DB_HOST, DB_NAME, DB_USER, DB_PASSWORD) or .db_password_widow.
Skips migrations whose file is missing. Stops on first error.
"""

import os
import re
import sys

try:
    from dotenv import load_dotenv
    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(api_dir, ".env"), override=False)
    load_dotenv(os.path.join(api_dir, "..", ".env"), override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD") and os.path.exists(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".db_password_widow")
):
    pw_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", ".db_password_widow")
    try:
        with open(pw_path) as f:
            os.environ["DB_PASSWORD"] = f.read().strip()
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ordered list: (number, filename). Two 146s: system_alerts then event_reports.
MIGRATIONS_140_152 = [
    (140, "140_orchestration_schema.sql"),
    (141, "141_intelligence_schema.sql"),
    (142, "142_context_centric_foundation.sql"),
    (143, "143_context_centric_entity_claims.sql"),
    (144, "144_v6_events_entity_dossiers.sql"),
    (145, "145_context_entity_mentions.sql"),
    (146, "146_system_alerts_health_monitor_columns.sql"),
    (146, "146_event_reports.sql"),
    (147, "147_performance_tuning.sql"),
    (148, "148_add_finance_rss_feeds.sql"),
    (149, "149_historic_context_schema.sql"),
    (150, "150_finance_research_topics.sql"),
    (151, "151_phase1_versioned_facts.sql"),
    (152, "152_story_state_update_triggers.sql"),
    (153, "153_storyline_states_phase2.sql"),
    (154, "154_watch_patterns_phase4.sql"),
]


def main():
    from shared.database.connection import get_db_connection

    start_from = 140
    if "--from" in sys.argv:
        i = sys.argv.index("--from")
        if i + 1 < len(sys.argv):
            try:
                start_from = int(sys.argv[i + 1])
            except ValueError:
                pass
    # Build list from start_from through 154
    run_list = [(num, name) for num, name in MIGRATIONS_140_152 if num >= start_from]
    if not run_list:
        print(f"No migrations to run (start_from={start_from}).")
        return

    api_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    migrations_dir = os.path.join(api_dir, "database", "migrations")

    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database (check DB_HOST, DB_NAME, DB_USER, DB_PASSWORD)")
        sys.exit(1)

    applied = 0
    for num, name in run_list:
        path = os.path.join(migrations_dir, name)
        if not os.path.exists(path):
            print(f"SKIP (file missing): {name}")
            continue
        with open(path, encoding="utf-8") as f:
            sql = f.read()
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            print(f"✅ {name}")
            applied += 1
        except Exception as e:
            conn.rollback()
            print(f"ERROR: {name} failed: {e}")
            sys.exit(1)

    conn.close()
    print(f"✅ Migrations {start_from}–154 complete. Applied {applied} file(s).")


if __name__ == "__main__":
    main()
