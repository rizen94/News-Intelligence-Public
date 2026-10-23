"""
Simple vault-note RAG index: fingerprint + token bag for match-after-write.

Prefer storyline/entity hard links in fan-out; this catches similar event notes
within a domain when no hard link exists.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from shared.database.connection import get_db_connection_context
from services.vault_note_patch import content_fingerprint, theme_tokens
from services.vault_notes_registry_service import mark_note_ready

logger = logging.getLogger(__name__)


def reindex_vault_note(
    vault_path: str,
    *,
    title: str,
    body: str,
    domain_key: str,
    note_type: str,
) -> dict[str, Any]:
    """Bump rag_indexed_at + store fingerprint and token bag in metadata."""
    fp = content_fingerprint(body)
    tokens = sorted(theme_tokens(title) | theme_tokens(body[:2000]))
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.vault_notes
                    SET rag_fingerprint = %s,
                        rag_indexed_at = NOW(),
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                        updated_at = NOW()
                    WHERE vault_path = %s
                    RETURNING id
                    """,
                    (
                        fp,
                        json.dumps(
                            {
                                "rag_tokens": tokens[:80],
                                "rag_domain": domain_key,
                                "rag_note_type": note_type,
                            }
                        ),
                        vault_path,
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if not row:
            mark_note_ready(vault_path, rag_fingerprint=fp)
        return {"ok": True, "fingerprint": fp, "token_count": len(tokens)}
    except Exception as e:
        logger.warning("vault note reindex failed %s: %s", vault_path, e)
        try:
            mark_note_ready(vault_path, rag_fingerprint=fp)
        except Exception:
            pass
        return {"ok": False, "error": str(e), "fingerprint": fp}


def find_similar_vault_notes(
    *,
    domain_key: str,
    note_type: str,
    query_text: str,
    exclude_path: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Token-overlap similarity within domain (storyline prior should run first)."""
    q_toks = theme_tokens(query_text)
    if not q_toks:
        return []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vault_path, title, note_status, lifecycle, metadata
                FROM intelligence.vault_notes
                WHERE domain_key = %s
                  AND note_type = %s
                  AND lifecycle <> 'frozen'
                ORDER BY note_updated_at DESC NULLS LAST
                LIMIT 200
                """,
                (domain_key, note_type),
            )
            rows = cur.fetchall()
    scored: list[tuple[float, dict[str, Any]]] = []
    for path, title, status, lifecycle, meta in rows:
        if exclude_path and path == exclude_path:
            continue
        meta = meta if isinstance(meta, dict) else {}
        stored = meta.get("rag_tokens") or []
        if isinstance(stored, list) and stored:
            bag = {str(t).lower() for t in stored}
        else:
            bag = theme_tokens(title or "")
        overlap = len(q_toks & bag)
        if overlap < 2:
            continue
        score = overlap / max(len(q_toks | bag), 1)
        scored.append(
            (
                score,
                {
                    "vault_path": path,
                    "title": title,
                    "note_status": status,
                    "lifecycle": lifecycle,
                    "score": round(score, 4),
                    "overlap": overlap,
                },
            )
        )
    scored.sort(key=lambda x: -x[0])
    return [s[1] for s in scored[:limit]]
