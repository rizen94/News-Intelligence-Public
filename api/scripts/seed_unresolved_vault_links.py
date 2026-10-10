#!/usr/bin/env python3
"""Seed / alias vault notes for top unresolved wikilink titles (density pass).

Only creates stubs when a politics.entity_canonical row exists. Avoids full-tree
sync (object_id=0 collisions). Prefer aliasing titles onto existing notes.
"""

from __future__ import annotations

import logging
import os
import sys

_API_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("seed_unresolved_vault_links")

PRIORITY_TITLES = (
    "Joe Biden",
    "Donald Trump",
    "Trump administration",
    "Keir Starmer",
    "Benjamin Netanyahu",
)


def main() -> int:
    os.environ.setdefault("NEWS_INTEL_VAULT_PATH", "/mnt/news-intelligence-vault")
    os.environ.setdefault("NEWS_INTEL_VAULT_WRITE", "true")
    os.environ.setdefault("DB_PORT", os.environ.get("DB_PORT", "6432"))

    from services.vault_bridge_service import (
        _render_frontmatter,
        vault_root,
        vault_write_enabled,
    )
    from services.vault_notes_registry_service import (
        get_vault_note,
        resolve_title_to_vault_path,
        upsert_vault_note,
    )
    from services.vault_tag_link_sync_service import sync_vault_file
    from shared.database.connection import get_db_connection_context
    from shared.vault_note_contract import (
        entity_vault_rel_path,
        structural_tags_for_note,
    )

    if not vault_write_enabled():
        logger.error("NEWS_INTEL_VAULT_WRITE not enabled")
        return 1

    root = vault_root()
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT dst_title
                FROM intelligence.vault_note_links
                WHERE dst_vault_path IS NULL
                  AND link_kind = 'wikilink'
                  AND dst_title IS NOT NULL
                  AND dst_title NOT LIKE '#%%'
                GROUP BY dst_title
                ORDER BY COUNT(*) DESC
                LIMIT 25
                """
            )
            unresolved = [r[0] for r in cur.fetchall()]

    titles = list(dict.fromkeys([*PRIORITY_TITLES, *unresolved]))
    created = 0
    for title in titles:
        if resolve_title_to_vault_path(title):
            logger.info("resolved already: %s", title)
            continue
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, canonical_name, entity_type
                    FROM politics.entity_canonical
                    WHERE lower(canonical_name) = lower(%s)
                       OR canonical_name ILIKE %s
                    ORDER BY CASE WHEN lower(canonical_name) = lower(%s) THEN 0 ELSE 1 END, id
                    LIMIT 1
                    """,
                    (title, f"{title}%", title),
                )
                ent = cur.fetchone()
        if not ent:
            logger.info("skip (no entity): %s", title)
            continue
        eid, name, etype = int(ent[0]), str(ent[1]), ent[2] or "person"
        existing = get_vault_note(
            domain_key="politics", note_type="entity", object_id=eid
        )
        if existing and existing.get("vault_path"):
            rel = existing["vault_path"]
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE intelligence.vault_notes
                        SET title = %s, updated_at = NOW()
                        WHERE vault_path = %s
                        """,
                        (title, rel),
                    )
                conn.commit()
            path = root / rel
            if path.is_file():
                sync_vault_file(path, root=root)
            logger.info("aliased title %s -> %s", title, rel)
            continue

        rel = entity_vault_rel_path(name)
        path = root / rel
        structural = structural_tags_for_note(
            note_type="entity", domain_key="politics"
        )
        if not path.is_file():
            fm = {
                "title": title,
                "ni_domain": "politics",
                "note_type": "entity",
                "ni_auto": True,
                "ni_entity_id": eid,
                "tags": structural,
            }
            body = (
                f"# {title}\n\nStub for wikilink resolution.\n\n"
                "<!-- ni:auto:significance -->\nMesh density stub.\n"
                "<!-- /ni:auto:significance -->\n"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_render_frontmatter(fm) + "\n" + body, encoding="utf-8")
            created += 1
        upsert_vault_note(
            domain_key="politics",
            note_type="entity",
            object_id=eid,
            vault_path=rel,
            title=title,
            note_status="note_ready",
            lifecycle="stub",
            tags=structural,
            metadata={"seed": "unresolved_wikilink", "entity_type": etype},
        )
        sync_vault_file(path, root=root)
        logger.info("created %s", rel)

    for rel in (
        "40_Reference/entities/donald_j_trump.md",
        "40_Reference/entities/iran.md",
    ):
        p = root / rel
        if p.is_file():
            sync_vault_file(p, root=root)

    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FILTER (WHERE dst_vault_path IS NULL),
                       COUNT(*) FILTER (WHERE dst_vault_path IS NOT NULL)
                FROM intelligence.vault_note_links
                WHERE link_kind = 'wikilink'
                """
            )
            u, r = cur.fetchone()
    logger.info("done created=%s unresolved=%s resolved=%s", created, u, r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
