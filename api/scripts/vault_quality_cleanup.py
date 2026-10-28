#!/usr/bin/env python3
"""One-time vault quality cleanup: index stubs, archive junk hubs, write MOCs.

Run on Widow:
  cd /opt/news-intelligence && PYTHONPATH=api .venv/bin/python \\
    api/scripts/vault_quality_cleanup.py
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "api"))
sys.path.insert(0, str(PROJECT_ROOT))

env_file = PROJECT_ROOT / ".env"
if env_file.exists():
    from dotenv import load_dotenv

    load_dotenv(env_file, override=False)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("vault_quality_cleanup")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def mark_stub_entities_index() -> int:
    from shared.database.connection import get_db_connection_context

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.vault_notes
                SET lifecycle = 'index',
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                      'quality_pass', 'stub_to_index',
                      'quality_pass_at', NOW()
                    )
                WHERE note_type = 'entity'
                  AND lifecycle IN ('stub', 'absent')
                  AND COALESCE(length(body_md), 0) < 80
                  AND COALESCE(length(summary_md), 0) < 40
                """
            )
            n = cur.rowcount
        conn.commit()
    return int(n or 0)


def archive_junk_cluster_hubs() -> list[str]:
    from services.vault_bridge_service import vault_root, vault_write_enabled
    from services.vault_quality_gates import is_junk_title
    from shared.database.connection import get_db_connection_context

    moved: list[str] = []
    if not vault_write_enabled():
        logger.warning("vault write disabled — PG archive only")
    root = vault_root()
    junk_dir = root / "90_Archive" / "junk"
    junk_dir.mkdir(parents=True, exist_ok=True)

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, vault_path, title
                FROM intelligence.vault_notes
                WHERE note_type = 'cluster'
                  AND lifecycle <> 'archived'
                """
            )
            rows = cur.fetchall()
            for vid, vpath, title in rows:
                if not is_junk_title(str(title or "")):
                    continue
                new_rel = f"90_Archive/junk/{Path(str(vpath or f'cluster-{vid}')).name}"
                src = root / str(vpath) if vpath else None
                if src and src.is_file():
                    dest = root / new_rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        src.replace(dest)
                    except Exception as e:
                        logger.warning("move %s: %s", vpath, e)
                        new_rel = str(vpath)
                cur.execute(
                    """
                    UPDATE intelligence.vault_notes
                    SET lifecycle = 'archived',
                        vault_path = %s,
                        updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                          'quality_pass', 'junk_title_archive',
                          'archived_at', NOW()
                        )
                    WHERE id = %s
                    """,
                    (new_rel, int(vid)),
                )
                moved.append(new_rel)
        conn.commit()
    return moved


def demote_uncited_daily_briefings() -> int:
    """Hide living day cards that fail NI_VAULT_BRIEFING_REQUIRE_CITATIONS."""
    from services.vault_quality_gates import (
        briefing_require_citations_enabled,
        daily_briefing_serve_allowed,
    )
    from shared.database.connection import get_db_connection_context

    if not briefing_require_citations_enabled():
        return 0
    n = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, COALESCE(body_md, summary_md, ''), metadata
                FROM intelligence.vault_notes
                WHERE note_type = 'daily_briefing'
                  AND COALESCE(lifecycle, 'living') = 'living'
                """
            )
            for vid, body, meta in cur.fetchall() or []:
                meta = meta if isinstance(meta, dict) else {}
                day = meta.get("briefing_day") or ""
                ok, reason = daily_briefing_serve_allowed(body or "", briefing_day=str(day or ""))
                if ok:
                    continue
                cur.execute(
                    """
                    UPDATE intelligence.vault_notes
                    SET lifecycle = 'index',
                        updated_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                          'quality_pass', 'uncited_briefing_demote',
                          'citation_fail_reason', %s,
                          'quality_pass_at', NOW()
                        )
                    WHERE id = %s
                    """,
                    (reason, int(vid)),
                )
                n += 1
        conn.commit()
    return n


def flag_mismatched_expansions() -> int:
    from services.vault_quality_gates import expansion_coherence_ok
    from shared.database.connection import get_db_connection_context

    n = 0
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, COALESCE(body_md, ''), COALESCE(summary_md, '')
                FROM intelligence.vault_notes
                WHERE note_type = 'expansion' AND lifecycle <> 'archived'
                """
            )
            for vid, title, body, summary in cur.fetchall():
                text = body or summary
                ok, reason = expansion_coherence_ok(title=str(title or ""), body=text)
                if ok:
                    continue
                cur.execute(
                    """
                    UPDATE intelligence.vault_notes
                    SET metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                          'coherence_fail', %s,
                          'coherence_fail_at', NOW(),
                          'needs_reprime', true
                        ),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (reason, int(vid)),
                )
                n += 1
        conn.commit()
    return n


def write_reading_mocs() -> dict[str, str]:
    from services.vault_bridge_service import vault_root, vault_write_enabled
    from shared.database.connection import get_db_connection_context

    if not vault_write_enabled():
        return {}
    root = vault_root()
    expansions: list[tuple[str, str]] = []
    dailies: list[tuple[str, str]] = []
    hubs: list[tuple[str, str]] = []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title, vault_path FROM intelligence.vault_notes
                WHERE note_type = 'expansion' AND lifecycle = 'living'
                  AND COALESCE(length(body_md), 0) > 120
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 40
                """
            )
            expansions = [(str(r[0] or "Untitled"), str(r[1])) for r in cur.fetchall()]
            cur.execute(
                """
                SELECT title, vault_path, COALESCE(body_md, summary_md, ''), metadata
                FROM intelligence.vault_notes
                WHERE note_type = 'daily_briefing' AND lifecycle = 'living'
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 8
                """
            )
            from services.vault_quality_gates import daily_briefing_serve_allowed

            dailies = []
            for title, path, body, meta in cur.fetchall() or []:
                meta = meta if isinstance(meta, dict) else {}
                day = str(meta.get("briefing_day") or "")
                ok, _ = daily_briefing_serve_allowed(body or "", briefing_day=day)
                if ok:
                    dailies.append((str(title or "Briefing"), str(path)))
                if len(dailies) >= 5:
                    break
            cur.execute(
                """
                SELECT title, vault_path FROM intelligence.vault_notes
                WHERE note_type = 'cluster'
                  AND lifecycle = 'living'
                  AND COALESCE((metadata->>'hub')::boolean, false) = true
                ORDER BY updated_at DESC NULLS LAST
                LIMIT 30
                """
            )
            hubs = [(str(r[0] or "Hub"), str(r[1])) for r in cur.fetchall() if r[1]]

    def _links(rows: list[tuple[str, str]]) -> str:
        lines = []
        for title, path in rows:
            # Obsidian wikilink by path stem / title
            name = Path(path).stem if path else title
            lines.append(f"- [[{name}|{title[:100]}]] — `{path}`")
        return "\n".join(lines) or "- _None yet._"

    reading = f"""---
ni_auto: true
note_type: moc
updated: {_now()}
---
# Reading

Human-readable Living notes only. Entity stubs live under Index — do not treat them as dossiers.

## Daily briefings

{_links(dailies)}

## Expansions

{_links(expansions)}

## Situation hubs

{_links(hubs)}
"""
    index = f"""---
ni_auto: true
note_type: moc
updated: {_now()}
---
# Index

`40_Reference/entities/` holds **index** cards (pipeline residue). Prefer [[00_Reading]] for Living expansions, daily briefs, and Situation hubs.

Entity markdown is created only when an entity is followed, a cluster hub seed, or hot (≥3 articles / 14 days). Empty stubs are lifecycle=`index`.
"""
    (root / "00_Reading.md").write_text(reading, encoding="utf-8")
    (root / "00_Index.md").write_text(index, encoding="utf-8")
    return {"00_Reading.md": reading[:200], "00_Index.md": index[:200]}


def main() -> int:
    # Apply lifecycle constraint migration if needed (best-effort)
    try:
        from shared.database.connection import get_db_connection_context

        sql_path = PROJECT_ROOT / "api/database/migrations/246_vault_notes_lifecycle_index_archived.sql"
        if sql_path.is_file():
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql_path.read_text(encoding="utf-8"))
                conn.commit()
            logger.info("applied migration 246 (lifecycle index/archived)")
    except Exception as e:
        logger.warning("migration 246: %s", e)

    indexed = mark_stub_entities_index()
    logger.info("stub entities → lifecycle=index: %s", indexed)
    demoted_briefs = demote_uncited_daily_briefings()
    logger.info("uncited daily_briefings → lifecycle=index: %s", demoted_briefs)
    moved = archive_junk_cluster_hubs()
    logger.info("junk hubs archived: %s", len(moved))
    for m in moved[:15]:
        logger.info("  archived %s", m)
    flagged = flag_mismatched_expansions()
    logger.info("expansions flagged needs_reprime: %s", flagged)
    mocs = write_reading_mocs()
    logger.info("MOCs written: %s", list(mocs.keys()))
    print(
        {
            "indexed_stubs": indexed,
            "demoted_uncited_briefings": demoted_briefs,
            "archived_hubs": len(moved),
            "flagged_expansions": flagged,
            "mocs": list(mocs.keys()),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
