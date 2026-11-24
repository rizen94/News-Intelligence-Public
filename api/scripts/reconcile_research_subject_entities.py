#!/usr/bin/env python3
"""
Reconcile duplicate research-board entities and knowledge_profiles.

Fixes duplicate /research cards when:
  - knowledge_profiles.canonical_entity_id != vault subject entity_canonical.id
  - two published profiles share the same curated title (e.g. Clinical Trials)

Default is dry-run. Use --apply on Widow after deploy + API restart (not during live catch-up).

  cd /opt/news-intelligence && set -a && source .env && set +a
  PYTHONPATH=api python3 api/scripts/reconcile_research_subject_entities.py
  PYTHONPATH=api python3 api/scripts/reconcile_research_subject_entities.py --apply
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

_API = Path(__file__).resolve().parents[1]
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from api.shared.database import get_db_connection_context, get_ui_db_connection_context
from api.shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)

# Curated title -> keeper canonical_entity_id (from knowledge_profiles + vault seeds).
_DEFAULT_KEEPERS: dict[str, dict[str, int]] = {
    "neurodiversity": {"adhd": 90579, "autism": 90575},
    "medicine": {"clinical trials": 94681},
}


def _load_keepers_from_vault() -> dict[str, dict[str, int]]:
    """Prefer vault_notes.object_id for ni_research_board entity notes."""
    out: dict[str, dict[str, int]] = {k: dict(v) for k, v in _DEFAULT_KEEPERS.items()}
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT domain_key, lower(trim(title)) AS t, object_id
                    FROM intelligence.vault_notes
                    WHERE note_type = 'entity'
                      AND COALESCE(metadata->>'ni_research_board', 'false') IN ('true', '1')
                      AND object_id IS NOT NULL
                    """
                )
                for row in cur.fetchall():
                    dk, t, oid = str(row[0]), str(row[1]), int(row[2])
                    out.setdefault(dk, {})[t] = oid
    except Exception as e:
        logger.debug("vault keeper load: %s", e)
    return out


def _entity_ids_for_title(schema: str, title: str) -> list[tuple[int, str, str]]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, canonical_name, coalesce(entity_type, '')
                FROM {schema}.entity_canonical
                WHERE lower(trim(canonical_name)) = lower(trim(%s))
                ORDER BY
                  CASE WHEN lower(coalesce(entity_type,'')) = 'subject' THEN 0 ELSE 1 END,
                  id ASC
                """,
                (title,),
            )
            return [(int(r[0]), str(r[1]), str(r[2])) for r in cur.fetchall()]


def _entity_profile_id(domain_key: str, canonical_entity_id: int) -> int | None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM intelligence.entity_profiles
                WHERE domain_key = %s AND canonical_entity_id = %s
                ORDER BY id ASC LIMIT 1
                """,
                (domain_key, int(canonical_entity_id)),
            )
            row = cur.fetchone()
            return int(row[0]) if row else None


def _profiles_for_title(domain_key: str, title: str) -> list[dict[str, Any]]:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, canonical_entity_id, title, status,
                       is_assertions, is_not_assertions, open_questions, material_updated_at
                FROM intelligence.knowledge_profiles
                WHERE domain_key = %s AND lower(trim(title)) = lower(trim(%s))
                ORDER BY material_updated_at DESC NULLS LAST, id DESC
                """,
                (domain_key, title),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _merge_json_arrays(a: Any, b: Any) -> list:
    from services.knowledge_profile_service import _assertion_key, _merge_assertion_lists

    la = list(a or []) if isinstance(a, list) else []
    lb = list(b or []) if isinstance(b, list) else []
    return _merge_assertion_lists(la, lb)


def reconcile(*, apply: bool) -> dict[str, Any]:
    from services.research_subject_topics import domain_fallback_subjects

    keepers = _load_keepers_from_vault()
    actions: list[dict[str, Any]] = []

    for domain_key, subjects in domain_fallback_subjects().items():
        schema = resolve_domain_schema(domain_key)
        domain_keepers = keepers.get(domain_key, {})

        for title in subjects:
            tkey = title.lower()
            keeper_eid = domain_keepers.get(tkey)
            rows = _entity_ids_for_title(schema, title)
            if len(rows) > 1:
                if keeper_eid is None:
                    keeper_eid = rows[0][0]
                keeper_profile_id = _entity_profile_id(domain_key, keeper_eid)
                for eid, cname, etype in rows:
                    if eid == keeper_eid:
                        continue
                    if keeper_profile_id is None:
                        continue
                    actions.append(
                        {
                            "action": "map_old_entity",
                            "domain_key": domain_key,
                            "title": title,
                            "old_entity_id": eid,
                            "keeper_entity_id": keeper_eid,
                            "entity_profile_id": keeper_profile_id,
                            "canonical_name": cname,
                            "entity_type": etype,
                        }
                    )

            profiles = _profiles_for_title(domain_key, title)
            if len(profiles) > 1:
                keeper_profile = profiles[0]
                if keeper_eid:
                    keeper_profile = next(
                        (p for p in profiles if int(p["canonical_entity_id"]) == keeper_eid),
                        profiles[0],
                    )
                for p in profiles:
                    if int(p["id"]) == int(keeper_profile["id"]):
                        continue
                    actions.append(
                        {
                            "action": "merge_profile",
                            "domain_key": domain_key,
                            "title": title,
                            "loser_profile_id": int(p["id"]),
                            "loser_entity_id": int(p["canonical_entity_id"]),
                            "keeper_profile_id": int(keeper_profile["id"]),
                            "keeper_entity_id": int(keeper_profile["canonical_entity_id"]),
                        }
                    )
            elif len(profiles) == 1 and keeper_eid:
                p = profiles[0]
                if int(p["canonical_entity_id"]) != int(keeper_eid):
                    actions.append(
                        {
                            "action": "repoint_profile_entity",
                            "domain_key": domain_key,
                            "title": title,
                            "profile_id": int(p["id"]),
                            "from_entity_id": int(p["canonical_entity_id"]),
                            "to_entity_id": int(keeper_eid),
                        }
                    )

    if not apply:
        return {"dry_run": True, "actions": actions, "count": len(actions)}

    applied = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            for act in actions:
                if act["action"] == "map_old_entity":
                    cur.execute(
                        """
                        INSERT INTO intelligence.old_entity_to_new
                            (domain_key, old_entity_id, entity_profile_id)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (domain_key, old_entity_id) DO UPDATE
                          SET entity_profile_id = EXCLUDED.entity_profile_id
                        """,
                        (
                            act["domain_key"],
                            act["old_entity_id"],
                            act["entity_profile_id"],
                        ),
                    )
                    applied += 1
                elif act["action"] == "repoint_profile_entity":
                    # Target entity must not already have a profile row (unique domain+entity).
                    cur.execute(
                        """
                        SELECT id FROM intelligence.knowledge_profiles
                        WHERE domain_key = %s AND canonical_entity_id = %s
                        """,
                        (act["domain_key"], act["to_entity_id"]),
                    )
                    if cur.fetchone():
                        logger.warning(
                            "skip repoint profile %s — keeper entity %s already has profile",
                            act["profile_id"],
                            act["to_entity_id"],
                        )
                        continue
                    cur.execute(
                        """
                        UPDATE intelligence.knowledge_profiles
                        SET canonical_entity_id = %s, updated_at = NOW()
                        WHERE id = %s AND domain_key = %s
                        """,
                        (act["to_entity_id"], act["profile_id"], act["domain_key"]),
                    )
                    applied += 1
                elif act["action"] == "merge_profile":
                    cur.execute(
                        """
                        SELECT is_assertions, is_not_assertions, open_questions
                        FROM intelligence.knowledge_profiles WHERE id = %s
                        """,
                        (act["loser_profile_id"],),
                    )
                    loser = cur.fetchone()
                    cur.execute(
                        """
                        SELECT is_assertions, is_not_assertions, open_questions
                        FROM intelligence.knowledge_profiles WHERE id = %s
                        """,
                        (act["keeper_profile_id"],),
                    )
                    keeper = cur.fetchone()
                    if loser and keeper:
                        merged_is = _merge_json_arrays(keeper[0], loser[0])
                        merged_not = _merge_json_arrays(keeper[1], loser[1])
                        merged_open = _merge_json_arrays(keeper[2], loser[2])
                        cur.execute(
                            """
                            UPDATE intelligence.knowledge_profiles
                            SET is_assertions = %s::jsonb,
                                is_not_assertions = %s::jsonb,
                                open_questions = %s::jsonb,
                                material_updated_at = NOW(),
                                updated_at = NOW()
                            WHERE id = %s
                            """,
                            (
                                json.dumps(merged_is),
                                json.dumps(merged_not),
                                json.dumps(merged_open),
                                act["keeper_profile_id"],
                            ),
                        )
                        cur.execute(
                            "DELETE FROM intelligence.knowledge_profiles WHERE id = %s",
                            (act["loser_profile_id"],),
                        )
                        cur.execute(
                            """
                            UPDATE intelligence.research_claim_ledger
                            SET canonical_entity_id = %s
                            WHERE domain_key = %s AND canonical_entity_id = %s
                            """,
                            (
                                act["keeper_entity_id"],
                                act["domain_key"],
                                act["loser_entity_id"],
                            ),
                        )
                    applied += 1
        conn.commit()
    return {"dry_run": False, "applied": applied, "actions": actions}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Reconcile research subject entities")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Execute writes (default: dry-run only)",
    )
    args = parser.parse_args()
    result = reconcile(apply=bool(args.apply))
    print(json.dumps(result, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())