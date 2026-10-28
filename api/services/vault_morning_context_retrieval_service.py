"""
Vault-wide context retrieval for morning storyline expansions.

Read-only: hard links + token/entity soft search across vault_notes.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.vault_note_contract import (
    MORNING_VAULT_RETRIEVAL_CHARS,
    MORNING_VAULT_RETRIEVAL_LIMIT,
)

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]{2,}", re.I)


def _tokens(text: str) -> set[str]:
    return {m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")}


def retrieve_vault_context_for_storyline(
    *,
    domain_key: str,
    storyline_id: int,
    title: str,
    article_id: int | None = None,
    anchor_entities: list[str] | None = None,
    limit: int = MORNING_VAULT_RETRIEVAL_LIMIT,
    max_chars: int = MORNING_VAULT_RETRIEVAL_CHARS,
) -> dict[str, Any]:
    """Ranked vault evidence pack for one expansion prompt."""
    query = " ".join(
        [
            title or "",
            " ".join(anchor_entities or []),
            f"storyline {storyline_id}",
        ]
    ).strip()
    q_toks = _tokens(query)
    scored: list[tuple[float, dict[str, Any]]] = []
    fp_parts: list[str] = [f"sl:{domain_key}:{storyline_id}"]

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                # Hard: storyline / cluster / expansion / clipping for this arc or article
                cur.execute(
                    """
                    SELECT vault_path, title, note_type,
                           COALESCE(summary_md, LEFT(COALESCE(body_md, ''), 900)),
                           note_updated_at, metadata, domain_key
                    FROM intelligence.vault_notes
                    WHERE lifecycle IS DISTINCT FROM 'frozen'
                      AND (
                        (note_type IN ('storyline', 'expansion', 'cluster')
                         AND object_id = %s AND domain_key = %s)
                        OR (note_type = 'clipping' AND domain_key = %s AND (
                              object_id = %s
                              OR (metadata->>'article_id') = %s
                              OR (metadata->>'storyline_id') = %s
                           ))
                      )
                    ORDER BY note_updated_at DESC NULLS LAST
                    LIMIT 8
                    """,
                    (
                        int(storyline_id),
                        domain_key,
                        domain_key,
                        int(article_id or 0),
                        str(int(article_id or 0)),
                        str(int(storyline_id)),
                    ),
                )
                for path, ntitle, ntype, summary, updated, meta, dk in cur.fetchall() or []:
                    scored.append(
                        (
                            1.0,
                            {
                                "vault_path": path,
                                "title": ntitle,
                                "note_type": ntype,
                                "excerpt": (summary or "")[:900],
                                "domain_key": dk,
                                "rank": "hard_link",
                            },
                        )
                    )
                    fp_parts.append(f"hard:{path}:{updated}")

                # Soft: recent notes any type — token overlap (cross-domain allowed lightly)
                cur.execute(
                    """
                    SELECT vault_path, title, note_type,
                           COALESCE(summary_md, LEFT(COALESCE(body_md, ''), 700)),
                           note_updated_at, metadata, domain_key
                    FROM intelligence.vault_notes
                    WHERE lifecycle IS DISTINCT FROM 'frozen'
                      AND note_type IN (
                        'entity', 'cluster', 'storyline', 'event',
                        'clipping', 'connection', 'expansion'
                      )
                      AND note_updated_at >= NOW() - INTERVAL '30 days'
                    ORDER BY note_updated_at DESC NULLS LAST
                    LIMIT 250
                    """,
                )
                seen_paths = {s[1]["vault_path"] for s in scored}
                for path, ntitle, ntype, summary, updated, meta, dk in cur.fetchall() or []:
                    if path in seen_paths:
                        continue
                    meta = meta if isinstance(meta, dict) else {}
                    stored = meta.get("rag_tokens") or []
                    if isinstance(stored, list) and stored:
                        bag = {str(t).lower() for t in stored}
                    else:
                        bag = _tokens(f"{ntitle or ''} {summary or ''}")
                    if not q_toks or not bag:
                        continue
                    overlap = len(q_toks & bag)
                    if overlap < 2:
                        continue
                    score = overlap / max(len(q_toks | bag), 1)
                    # Prefer same domain
                    if dk == domain_key:
                        score += 0.05
                    # Prefer entity/cluster for background
                    if ntype in ("entity", "cluster", "event"):
                        score += 0.02
                    scored.append(
                        (
                            score,
                            {
                                "vault_path": path,
                                "title": ntitle,
                                "note_type": ntype,
                                "excerpt": (summary or "")[:700],
                                "domain_key": dk,
                                "rank": "soft",
                                "score": round(score, 4),
                            },
                        )
                    )
                    fp_parts.append(f"soft:{path}:{updated}")
    except Exception as e:
        logger.warning("retrieve_vault_context_for_storyline: %s", e)
        return {
            "ok": False,
            "error": str(e),
            "evidence_text": "",
            "notes": [],
            "fingerprint_parts": fp_parts,
        }

    scored.sort(key=lambda x: (-x[0], x[1].get("vault_path") or ""))
    notes: list[dict[str, Any]] = []
    chunks: list[str] = []
    used = 0
    for _sc, note in scored:
        if len(notes) >= max(1, int(limit)):
            break
        block = (
            f"[{note.get('note_type')}] {note.get('title') or note.get('vault_path')}\n"
            f"{note.get('excerpt') or ''}"
        )
        if used + len(block) > max_chars and notes:
            break
        notes.append(note)
        chunks.append(block)
        used += len(block)

    return {
        "ok": True,
        "evidence_text": "\n\n".join(chunks)[:max_chars],
        "notes": notes,
        "fingerprint_parts": fp_parts[:40],
        "note_count": len(notes),
    }
