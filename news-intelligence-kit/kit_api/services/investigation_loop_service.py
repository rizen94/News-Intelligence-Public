"""Simplified investigation loop: gather DB context → vault note."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from kit_api.services.vault_service import slugify, write_note

logger = logging.getLogger(__name__)


async def run_investigation_loop(
    *,
    query: str,
    domain_key: str | None = None,
    entity_id: int | None = None,
    event_id: int | None = None,
) -> dict[str, Any]:
    lines = [f"# Investigation: {query}", "", f"_Generated {datetime.now(timezone.utc).isoformat()}_", ""]
    evidence: list[str] = []

    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                if entity_id:
                    cur.execute(
                        """
                        SELECT id, display_name, domain_key, metadata
                        FROM intelligence.entity_profiles WHERE id = %s
                        """,
                        (entity_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        evidence.append(f"- Entity {row[0]}: {row[1]} ({row[2]})")
                if event_id:
                    cur.execute(
                        """
                        SELECT id, title, event_date, domain_key
                        FROM intelligence.chronological_events WHERE id = %s
                        """,
                        (event_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        evidence.append(f"- Event {row[0]}: {row[1]} ({row[3]})")
                if domain_key:
                    cur.execute(
                        """
                        SELECT domain_key, name FROM public.domains
                        WHERE domain_key = %s AND is_active
                        """,
                        (domain_key,),
                    )
                    row = cur.fetchone()
                    if row:
                        evidence.append(f"- Domain: {row[1]}")
    except Exception as e:
        logger.warning("investigation gather: %s", e)
        evidence.append(f"- (DB gather partial: {e})")

    lines.append("## Evidence")
    lines.extend(evidence or ["- No structured matches; expand search in Open WebUI."])
    lines.extend(["", "## Notes", "", query, ""])

    slug = slugify(query[:60])
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rel = f"threads/{date}-{slug}.md"
    wr = write_note(rel, "\n".join(lines))
    return {"vault_path": wr.get("path"), "evidence_count": len(evidence), "query": query}
