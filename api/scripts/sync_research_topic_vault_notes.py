#!/usr/bin/env python3
"""
Upsert vault science-topic notes + registry rows for curated research subjects.

Writes under 50_Science/40_Topics/ and tags with domain keywords for the
/research index.

  PYTHONPATH=api uv run python api/scripts/sync_research_topic_vault_notes.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = API_ROOT.parent
sys.path.insert(0, str(API_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(API_ROOT / ".env", override=False)
    load_dotenv(PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

if not os.environ.get("DB_PASSWORD"):
    pw = PROJECT_ROOT / ".db_password_widow"
    if pw.is_file():
        os.environ["DB_PASSWORD"] = pw.read_text().strip()


def _note_body(*, title: str, domain_key: str, keywords: list[str], subjects: list[str]) -> str:
    tags = " ".join(f"#{k.replace(' ', '_')}" for k in keywords[:12])
    subject_links = ", ".join(f"[[{s}]]" for s in subjects)
    return f"""---
title: {title}
domain: {domain_key}
note_type: research_topic
tags: [{", ".join(repr(k) for k in keywords[:12])}]
ni_research_board: true
---

# {title}

Standing research topic for the News Intelligence **What we know** board
(`/{domain_key}` → subject fact sheet).

## Keywords

{tags}

## Related subjects

{subject_links}

## Notes

Accumulating evidence (supported / not supported / open) comes from appraised
papers in the research pathway — not news headlines.
"""


def main() -> int:
    from shared.domain_registry import resolve_domain_schema
    from shared.vault_note_contract import entity_vault_rel_path
    from services.research_subject_topics import load_research_subject_topics
    from services.vault_notes_registry_service import upsert_vault_note
    from shared.database.connection import get_db_connection_context

    # Optional Obsidian write via local path if mounted
    vault_root = os.environ.get("NEWS_VAULT_ROOT") or os.environ.get("OBSIDIAN_NEWS_VAULT")
    cfg = load_research_subject_topics()
    written = 0
    registered = 0

    for domain_key, block in cfg.items():
        keywords = list(block.get("keywords") or [])
        subjects = list(block.get("subjects") or [])
        schema = resolve_domain_schema(domain_key)

        for title in subjects:
            # Resolve entity id when present
            object_id = 0
            try:
                with get_db_connection_context() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            f"""
                            SELECT id FROM {schema}.entity_canonical
                            WHERE lower(trim(canonical_name)) = lower(trim(%s))
                            ORDER BY
                              CASE WHEN lower(coalesce(entity_type,'')) = 'subject' THEN 0 ELSE 1 END,
                              id ASC
                            LIMIT 1
                            """,
                            (title,),
                        )
                        row = cur.fetchone()
                        if row:
                            object_id = int(row[0])
            except Exception as e:
                print(f"entity lookup {domain_key}/{title}: {e}")

            if object_id <= 0:
                print(f"skip (no entity_canonical): {domain_key}/{title}")
                continue

            # Prefer existing registry path (unique on domain/note_type/object_id).
            vault_path = entity_vault_rel_path(
                title, domain_key=domain_key, entity_type="subject"
            )
            try:
                with get_db_connection_context() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT vault_path FROM intelligence.vault_notes
                            WHERE domain_key = %s
                              AND note_type = 'entity'
                              AND object_id = %s
                              AND COALESCE(object_id_secondary, 0) = 0
                            LIMIT 1
                            """,
                            (domain_key, object_id),
                        )
                        existing = cur.fetchone()
                        if existing and existing[0]:
                            vault_path = str(existing[0])
            except Exception as e:
                print(f"existing vault path lookup {domain_key}/{title}: {e}")

            body = _note_body(
                title=title,
                domain_key=domain_key,
                keywords=keywords,
                subjects=subjects,
            )

            try:
                upsert_vault_note(
                    domain_key=domain_key,
                    note_type="entity",
                    object_id=object_id,
                    vault_path=vault_path,
                    title=title,
                    note_status="seeded",
                    lifecycle="seeded",
                    tags=keywords,
                    tags_source="ni_structural",
                    body_md=body,
                    summary_md=f"Research topic board: {title}",
                    metadata={
                        "research_board": True,
                        "keywords": keywords,
                    },
                )
                registered += 1
            except Exception as e:
                print(f"upsert failed {domain_key}/{title}: {e}")
                continue

            if vault_root:
                abs_path = Path(vault_root) / vault_path
                abs_path.parent.mkdir(parents=True, exist_ok=True)
                abs_path.write_text(body, encoding="utf-8")
                written += 1
            else:
                # Try Obsidian MCP path is remote; still register DB. Local write
                # via default NI vault if present.
                for candidate in (
                    PROJECT_ROOT / "vault-news",
                    Path("/vault-news"),
                    Path.home() / "Documents" / "Obsidian" / "News Intelligence",
                ):
                    if candidate.is_dir():
                        abs_path = candidate / vault_path
                        abs_path.parent.mkdir(parents=True, exist_ok=True)
                        abs_path.write_text(body, encoding="utf-8")
                        written += 1
                        break

            print(f"ok {domain_key}/{title} → {vault_path}")

    print(f"Done: registered={registered} files_written={written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
