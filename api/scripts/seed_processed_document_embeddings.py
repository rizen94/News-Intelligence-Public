#!/usr/bin/env python3
"""Seed intelligence.embedding_chunks for processed_documents (local/dev).

Uses nomic-embed-text (768-d) to match the pgvector column. Skips when Ollama
is unavailable. Refuses Widow when ENVIRONMENT=development.

  set -a; source .env.dev; set +a
  PYTHONPATH=api python3 api/scripts/seed_processed_document_embeddings.py --limit 20
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _API)

from shared.dev_guard import DevGuardError, assert_dev_db_host_safe  # noqa: E402
from shared.database.connection import get_db_connection_context  # noqa: E402


def _section_text(sections) -> str:
    if not sections:
        return ""
    if isinstance(sections, str):
        return sections
    parts: list[str] = []
    if isinstance(sections, list):
        for s in sections:
            if isinstance(s, str):
                parts.append(s)
            elif isinstance(s, dict):
                parts.append(str(s.get("text") or s.get("content") or ""))
    return "\n\n".join(p for p in parts if p).strip()


def main() -> int:
    try:
        assert_dev_db_host_safe()
    except DevGuardError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2

    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    try:
        from services.ai_storyline_discovery import get_embedding_single
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"embedding import failed: {e}"}))
        return 1

    inserted = 0
    skipped = 0
    with get_db_connection_context() as conn:
        if not conn:
            print("no db", file=sys.stderr)
            return 1
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT pd.id, pd.title, pd.extracted_sections
                FROM intelligence.processed_documents pd
                WHERE COALESCE(pd.extracted_sections, '[]'::jsonb) <> '[]'::jsonb
                  AND NOT EXISTS (
                    SELECT 1 FROM intelligence.embedding_chunks ec
                    WHERE ec.source_type = 'processed_document'
                      AND ec.source_id = pd.id
                  )
                ORDER BY pd.id DESC
                LIMIT %s
                """,
                (int(args.limit),),
            )
            rows = cur.fetchall() or []
            for doc_id, title, sections in rows:
                text = _section_text(sections)
                if not text:
                    skipped += 1
                    continue
                chunk = f"{title or ''}\n\n{text}"[:6000]
                try:
                    emb = get_embedding_single(chunk)
                except Exception as e:
                    print(f"embed fail doc={doc_id}: {e}", file=sys.stderr)
                    skipped += 1
                    continue
                if not emb or len(emb) not in (768, 1024):
                    print(
                        f"unexpected embedding dim={len(emb) if emb else 0} doc={doc_id}",
                        file=sys.stderr,
                    )
                    skipped += 1
                    continue
                if len(emb) != 768:
                    print(
                        f"skip doc={doc_id}: need 768-d (nomic); got {len(emb)}",
                        file=sys.stderr,
                    )
                    skipped += 1
                    continue
                if args.dry_run:
                    inserted += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO intelligence.embedding_chunks
                        (source_type, source_id, domain_key, chunk_index, chunk_text, embedding, metadata)
                    VALUES ('processed_document', %s, NULL, 0, %s, %s::vector, %s::jsonb)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        int(doc_id),
                        chunk[:4000],
                        emb,
                        json.dumps({"seed": "processed_document_v11", "title": title}),
                    ),
                )
                inserted += max(0, cur.rowcount or 0)
        if not args.dry_run:
            conn.commit()
    print(
        json.dumps(
            {
                "ok": True,
                "dry_run": bool(args.dry_run),
                "inserted": inserted,
                "skipped": skipped,
                "note": "embedding_chunks uses vector(768); prefer EMBEDDING_MODEL=nomic-embed-text",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
