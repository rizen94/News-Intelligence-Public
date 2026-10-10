"""
Post-extract vault note fan-out: select targets, match, enqueue create/update.

Matching order (plan): storyline/episode hard link → entity registry → RAG → create if tier.
Fan-out caps: ≤3 entity + ≤1 event/arc + ≤1 connection per article.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from config.feature_registry import is_feature_enabled
from shared.database.connection import get_db_connection_context
from shared.vault_note_contract import (
    DEFAULT_COOLDOWN_HOURS,
    DEFAULT_LIVING_MENTION_TIER,
    DEFAULT_STUB_MENTION_TIER,
    MAX_CONNECTION_NOTES_PER_ARTICLE,
    MAX_ENTITY_NOTES_PER_ARTICLE,
    MAX_EVENT_NOTES_PER_ARTICLE,
    connection_vault_rel_path,
    entity_vault_rel_path,
    event_vault_rel_path,
    storyline_vault_rel_path,
)
from services.vault_note_rag_service import find_similar_vault_notes
from services.vault_notes_registry_service import get_vault_note, upsert_vault_note
from services.vault_update_queue_service import enqueue_vault_update

logger = logging.getLogger(__name__)


def vault_notes_pipeline_enabled() -> bool:
    if os.environ.get("NI_VAULT_NOTES_ENABLED", "").lower() in ("0", "false", "no"):
        return False
    if os.environ.get("NI_VAULT_NOTES_ENABLED", "").lower() in ("1", "true", "yes"):
        return True
    return is_feature_enabled("vault_notes_pipeline", default=True)


def _stub_tier() -> int:
    return int(os.environ.get("NI_VAULT_STUB_MENTION_TIER", str(DEFAULT_STUB_MENTION_TIER)))


def _living_tier() -> int:
    return int(os.environ.get("NI_VAULT_LIVING_MENTION_TIER", str(DEFAULT_LIVING_MENTION_TIER)))


def _cooldown_hours() -> int:
    return int(os.environ.get("NI_VAULT_COOLDOWN_HOURS", str(DEFAULT_COOLDOWN_HOURS)))


def _schema(domain_key: str) -> str:
    return domain_key.replace("-", "_")


def _lifecycle_for_mentions(n: int) -> str:
    if n >= _living_tier():
        return "living"
    if n >= _stub_tier():
        return "seeded"
    return "stub"


def _in_cooldown(note: dict[str, Any] | None) -> bool:
    if not note or not note.get("note_updated_at"):
        return False
    try:
        raw = note["note_updated_at"]
        if isinstance(raw, str):
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            ts = raw
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - ts < timedelta(hours=_cooldown_hours())
    except Exception:
        return False


def fetch_article_anchors(domain_key: str, article_id: int) -> dict[str, Any]:
    """Primary entities, storyline links, and event ids for one article."""
    schema = _schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT a.title, a.published_at::date,
                       LEFT(COALESCE(a.content, a.summary, ''), 500)
                FROM {schema}.articles a
                WHERE a.id = %s
                """,
                (article_id,),
            )
            art = cur.fetchone()
            cur.execute(
                f"""
                SELECT ae.canonical_entity_id, ec.canonical_name, ec.entity_type,
                       COUNT(*) OVER (PARTITION BY ae.canonical_entity_id) AS hit,
                       COALESCE((
                         SELECT COUNT(*)::int FROM {schema}.article_entities x
                         WHERE x.canonical_entity_id = ae.canonical_entity_id
                       ), 0) AS mentions
                FROM {schema}.article_entities ae
                JOIN {schema}.entity_canonical ec ON ec.id = ae.canonical_entity_id
                WHERE ae.article_id = %s AND ae.canonical_entity_id IS NOT NULL
                ORDER BY mentions DESC, ae.id ASC
                LIMIT 20
                """,
                (article_id,),
            )
            ents = cur.fetchall()
            cur.execute(
                f"""
                SELECT DISTINCT sa.storyline_id, s.title, COALESCE(s.article_count, 0)
                FROM {schema}.storyline_articles sa
                JOIN {schema}.storylines s ON s.id = sa.storyline_id
                WHERE sa.article_id = %s AND s.merged_into_id IS NULL
                ORDER BY COALESCE(s.article_count, 0) DESC
                LIMIT 5
                """,
                (article_id,),
            )
            storylines = cur.fetchall()
            cur.execute(
                f"""
                SELECT id, LEFT(COALESCE(title, summary, ''), 200)
                FROM {schema}.chronological_events
                WHERE article_id = %s
                ORDER BY id DESC
                LIMIT 5
                """,
                (article_id,),
            )
            events = cur.fetchall()
    entities = []
    seen: set[int] = set()
    for eid, name, etype, _hit, mentions in ents:
        if eid in seen:
            continue
        seen.add(int(eid))
        entities.append(
            {
                "id": int(eid),
                "name": str(name),
                "entity_type": etype,
                "mentions": int(mentions or 0),
            }
        )
    return {
        "article_id": article_id,
        "domain_key": domain_key,
        "title": (art[0] if art else "") or "",
        "published": art[1].isoformat() if art and art[1] else None,
        "snippet": (art[2] if art else "") or "",
        "entities": entities,
        "storylines": [
            {"id": int(r[0]), "title": r[1] or f"Storyline {r[0]}", "article_count": int(r[2] or 0)}
            for r in storylines
        ],
        "events": [{"id": int(r[0]), "title": r[1] or f"Event {r[0]}"} for r in events],
    }


def select_note_targets(anchors: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply tier + fan-out caps. Quiet entities never get notes."""
    domain_key = anchors["domain_key"]
    article_id = anchors["article_id"]
    targets: list[dict[str, Any]] = []

    # Entities above stub tier, capped
    for ent in anchors.get("entities") or []:
        if len([t for t in targets if t["note_type"] == "entity"]) >= MAX_ENTITY_NOTES_PER_ARTICLE:
            break
        mentions = int(ent.get("mentions") or 0)
        if mentions < _stub_tier():
            continue
        path = entity_vault_rel_path(
            ent["name"],
            domain_key=domain_key,
            entity_type=ent.get("entity_type"),
        )
        lifecycle = _lifecycle_for_mentions(mentions)
        existing = get_vault_note(
            domain_key=domain_key, note_type="entity", object_id=ent["id"]
        )
        if existing and existing.get("vault_path"):
            path = existing["vault_path"]
        if existing and existing.get("lifecycle") == "frozen":
            continue
        if existing and existing.get("lifecycle") == "living" and _in_cooldown(existing):
            continue
        action = "update" if existing and existing.get("note_status") == "note_ready" else "create"
        if existing is None and lifecycle == "stub" and mentions < _living_tier():
            # Structure-only until seeded threshold for brand-new quiet-ish entities
            # (already above stub_tier so create stub)
            action = "create"
        targets.append(
            {
                "note_type": "entity",
                "object_id": ent["id"],
                "vault_path": path,
                "title": ent["name"],
                "action": action,
                "lifecycle": lifecycle,
                "mention_count": mentions,
                "priority": "high" if lifecycle == "living" else "medium",
                "section": "timeline",
            }
        )

    # Storyline / event arc — prefer hard-linked storyline; else top event
    story_targets = 0
    for sl in anchors.get("storylines") or []:
        if story_targets >= MAX_EVENT_NOTES_PER_ARTICLE:
            break
        if int(sl.get("article_count") or 0) < 5:
            continue
        path = storyline_vault_rel_path(domain_key, sl["id"], sl["title"])
        existing = get_vault_note(
            domain_key=domain_key, note_type="storyline", object_id=sl["id"]
        )
        if existing and existing.get("lifecycle") == "frozen":
            continue
        action = "update" if existing else "create"
        # RAG second chance for create of thin new storylines
        if not existing:
            sims = find_similar_vault_notes(
                domain_key=domain_key,
                note_type="storyline",
                query_text=f"{sl['title']} {anchors.get('title') or ''}",
            )
            if sims and sims[0]["score"] >= 0.15:
                path = sims[0]["vault_path"]
                action = "update"
                # Keep object_id as this storyline for payload; path may map to older note
        targets.append(
            {
                "note_type": "storyline",
                "object_id": sl["id"],
                "vault_path": path,
                "title": sl["title"],
                "action": action,
                "lifecycle": "seeded",
                "mention_count": int(sl.get("article_count") or 0),
                "priority": "medium",
                "section": "timeline",
            }
        )
        story_targets += 1

    if story_targets < MAX_EVENT_NOTES_PER_ARTICLE:
        for ev in anchors.get("events") or []:
            if story_targets >= MAX_EVENT_NOTES_PER_ARTICLE:
                break
            path = event_vault_rel_path(domain_key, ev["id"], ev["title"])
            existing = get_vault_note(
                domain_key=domain_key, note_type="event", object_id=ev["id"]
            )
            sims = []
            if not existing:
                sims = find_similar_vault_notes(
                    domain_key=domain_key,
                    note_type="event",
                    query_text=f"{ev['title']} {anchors.get('title') or ''}",
                )
            if sims and sims[0]["score"] >= 0.18:
                path = sims[0]["vault_path"]
                action = "update"
            else:
                action = "update" if existing else "create"
            # Only create event notes when importance-ish (linked storyline exists)
            if action == "create" and not (anchors.get("storylines") or []):
                continue
            targets.append(
                {
                    "note_type": "event",
                    "object_id": ev["id"],
                    "vault_path": path,
                    "title": ev["title"],
                    "action": action,
                    "lifecycle": "seeded",
                    "mention_count": 1,
                    "priority": "low",
                    "section": "timeline",
                }
            )
            story_targets += 1

    # Connection: two living entities co-anchoring
    living_ents = [
        e
        for e in (anchors.get("entities") or [])
        if int(e.get("mentions") or 0) >= _living_tier()
    ][:4]
    conn_n = 0
    for i in range(len(living_ents)):
        for j in range(i + 1, len(living_ents)):
            if conn_n >= MAX_CONNECTION_NOTES_PER_ARTICLE:
                break
            a, b = living_ents[i], living_ents[j]
            # Prefer when article also on a shared storyline
            if not (anchors.get("storylines") or []):
                continue
            path = connection_vault_rel_path(a["name"], b["name"])
            id_a, id_b = sorted([a["id"], b["id"]])
            existing = get_vault_note(
                domain_key=domain_key,
                note_type="connection",
                object_id=id_a,
                object_id_secondary=id_b,
            )
            targets.append(
                {
                    "note_type": "connection",
                    "object_id": id_a,
                    "object_id_secondary": id_b,
                    "vault_path": path,
                    "title": f"{a['name']} ↔ {b['name']}",
                    "action": "update" if existing else "create",
                    "lifecycle": "seeded",
                    "mention_count": 0,
                    "priority": "medium",
                    "section": "timeline",
                    "name_a": a["name"],
                    "name_b": b["name"],
                }
            )
            conn_n += 1
        if conn_n >= MAX_CONNECTION_NOTES_PER_ARTICLE:
            break

    for t in targets:
        t["article_id"] = article_id
        t["domain_key"] = domain_key
        t["article_title"] = anchors.get("title")
        t["published"] = anchors.get("published")
    return targets


def enqueue_targets(targets: list[dict[str, Any]]) -> dict[str, Any]:
    queued = 0
    skipped = 0
    for t in targets:
        article_id = int(t["article_id"])
        path = t["vault_path"]
        section = t.get("section") or "timeline"
        idem = f"{article_id}:{path}:{section}"
        # Ensure registry row exists (structure pointer before note ready)
        upsert_vault_note(
            domain_key=t["domain_key"],
            note_type=t["note_type"],
            object_id=int(t["object_id"]),
            object_id_secondary=t.get("object_id_secondary"),
            vault_path=path,
            title=t.get("title"),
            note_status="note_pending",
            lifecycle=t.get("lifecycle") or "stub",
            mention_count=int(t.get("mention_count") or 0),
            last_article_id=article_id,
            metadata={"fanout": True},
        )
        result = enqueue_vault_update(
            domain_key=t["domain_key"],
            note_type=t["note_type"],
            object_id=int(t["object_id"]),
            object_id_secondary=t.get("object_id_secondary"),
            vault_path=path,
            action=t.get("action") or "update",
            idempotency_key=idem,
            priority=t.get("priority") or "medium",
            payload={
                "article_id": article_id,
                "article_title": t.get("article_title"),
                "published": t.get("published"),
                "section": section,
                "title": t.get("title"),
                "lifecycle": t.get("lifecycle"),
                "name_a": t.get("name_a"),
                "name_b": t.get("name_b"),
            },
        )
        if result.get("already_queued"):
            skipped += 1
        else:
            queued += 1
    return {"queued": queued, "skipped": skipped, "targets": len(targets)}


def fanout_article_to_vault_queue(
    domain_key: str, article_id: int
) -> dict[str, Any]:
    """Main entry: article → select → enqueue. Safe no-op when feature off."""
    if not vault_notes_pipeline_enabled():
        return {"ok": True, "skipped": True, "reason": "disabled"}
    try:
        anchors = fetch_article_anchors(domain_key, int(article_id))
        targets = select_note_targets(anchors)
        if not targets:
            return {
                "ok": True,
                "queued": 0,
                "targets": 0,
                "reason": "no_targets",
                "entity_count": len(anchors.get("entities") or []),
            }
        stats = enqueue_targets(targets)
        stats["ok"] = True
        return stats
    except Exception as e:
        logger.warning("vault fanout failed article=%s: %s", article_id, e)
        return {"ok": False, "error": str(e)}
