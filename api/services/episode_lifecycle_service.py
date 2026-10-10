"""
Episode lifecycle + signature co-anchor growth + bifurcation split.

forming → active → cooling → dormant → concluded; late events reactivate.
Signature growth only when co-anchors appear with ≥N co-occurring events.
Bifurcation: two low-co-occurrence anchor groups → two episodes (not unlink-only).
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.domain_registry import resolve_domain_schema
from shared.episode_attach_gate import parse_anchor_signature

logger = logging.getLogger(__name__)

VALID_TRANSITIONS = {
    "forming": {"active", "dormant", "concluded"},
    "active": {"cooling", "dormant", "concluded"},
    "cooling": {"active", "dormant", "concluded"},
    "dormant": {"active", "concluded"},
    "concluded": {"active"},  # late event reactivation
}


def transition_episode_state(
    domain_key: str,
    episode_id: int,
    new_state: str,
    *,
    reason: str = "",
) -> bool:
    if new_state not in VALID_TRANSITIONS and new_state not in (
        "forming",
        "active",
        "cooling",
        "dormant",
        "concluded",
    ):
        return False
    schema = resolve_domain_schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT episode_state FROM {schema}.storylines WHERE id = %s",
                (int(episode_id),),
            )
            row = cur.fetchone()
            if not row:
                return False
            cur_state = (row[0] or "forming").strip()
            allowed = VALID_TRANSITIONS.get(cur_state, set())
            if new_state != cur_state and new_state not in allowed:
                logger.info(
                    "episode %s:%s refuse %s→%s",
                    domain_key,
                    episode_id,
                    cur_state,
                    new_state,
                )
                return False
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET episode_state = %s,
                    status = CASE
                        WHEN %s IN ('dormant', 'concluded') THEN 'dormant'
                        WHEN %s IN ('active', 'forming', 'cooling') THEN 'active'
                        ELSE status
                    END,
                    metadata = COALESCE(metadata, '{{}}'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    new_state,
                    new_state,
                    new_state,
                    json.dumps(
                        {
                            "episode_state_transition": {
                                "from": cur_state,
                                "to": new_state,
                                "reason": reason,
                            }
                        }
                    ),
                    int(episode_id),
                ),
            )
            conn.commit()
            return True


def grow_signature_from_coanchors(
    domain_key: str,
    episode_id: int,
    *,
    min_cooccurring_events: int = 3,
    apply: bool = False,
) -> dict[str, Any]:
    """
    Add supporting anchors that co-occur with existing signature on ≥N linked events.
    Never promotes hubs into identity.
    """
    schema = resolve_domain_schema(domain_key)
    result: dict[str, Any] = {"added": [], "signature": None}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT anchor_signature, signature_locked_at
                FROM {schema}.storylines WHERE id = %s
                """,
                (int(episode_id),),
            )
            row = cur.fetchone()
            if not row:
                return result
            sig = parse_anchor_signature(row[0])
            known = set(sig["identity"]) | set(sig["supporting"])
            cur.execute(
                """
                SELECT matched_anchors
                FROM intelligence.event_episode_links
                WHERE domain_key = %s AND episode_id = %s
                  AND inference_stage <> 'quarantined'
                """,
                (domain_key, int(episode_id)),
            )
            counts: dict[str, int] = defaultdict(int)
            for (raw,) in cur.fetchall() or []:
                anchors = raw
                if isinstance(anchors, str):
                    try:
                        anchors = json.loads(anchors)
                    except Exception:
                        anchors = []
                for a in anchors or []:
                    tok = str(a).strip().lower()
                    if tok and tok not in known and not tok.startswith("hub:"):
                        counts[tok] += 1
            candidates = [
                t for t, n in counts.items() if n >= min_cooccurring_events
            ]
            if not candidates:
                result["signature"] = sig
                return result
            new_sup = list(sig["supporting"]) + candidates[:8]
            # dedupe
            seen: set[str] = set()
            deduped: list[str] = []
            for t in new_sup:
                if t not in seen:
                    seen.add(t)
                    deduped.append(t)
            new_sig = {"identity": list(sig["identity"]), "supporting": deduped}
            result["added"] = candidates[:8]
            result["signature"] = new_sig
            if apply:
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET anchor_signature = %s::jsonb,
                        signature_locked_at = COALESCE(signature_locked_at, NOW()),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(new_sig), int(episode_id)),
                )
                conn.commit()
    return result


def propose_bifurcation_split(
    domain_key: str,
    episode_id: int,
    *,
    min_group_events: int = 3,
) -> list[dict[str, Any]]:
    """
    Detect two low-co-occurrence identity anchor groups on one episode.
    Returns proposals (does not apply).
    """
    schema = resolve_domain_schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT title, anchor_signature FROM {schema}.storylines WHERE id = %s",
                (int(episode_id),),
            )
            row = cur.fetchone()
            if not row:
                return []
            title, raw_sig = row
            sig = parse_anchor_signature(raw_sig)
            identities = list(sig.get("identity") or [])
            if len(identities) < 2:
                return []
            cur.execute(
                """
                SELECT event_id, matched_anchors
                FROM intelligence.event_episode_links
                WHERE domain_key = %s AND episode_id = %s
                  AND inference_stage <> 'quarantined'
                """,
                (domain_key, int(episode_id)),
            )
            # co-occurrence matrix among identity anchors
            co: dict[tuple[str, str], int] = defaultdict(int)
            solo: dict[str, int] = defaultdict(int)
            for _eid, raw in cur.fetchall() or []:
                anchors = raw
                if isinstance(anchors, str):
                    try:
                        anchors = json.loads(anchors)
                    except Exception:
                        anchors = []
                present = [a for a in identities if a in (anchors or [])]
                for a in present:
                    solo[a] += 1
                for i, a in enumerate(present):
                    for b in present[i + 1 :]:
                        key = tuple(sorted((a, b)))
                        co[key] += 1
            # Find pair with low co-occurrence but each has enough solo events
            proposals: list[dict[str, Any]] = []
            for i, a in enumerate(identities):
                for b in identities[i + 1 :]:
                    if solo[a] < min_group_events or solo[b] < min_group_events:
                        continue
                    together = co.get(tuple(sorted((a, b))), 0)
                    if together <= 1:
                        proposals.append(
                            {
                                "domain_key": domain_key,
                                "source_episode_id": int(episode_id),
                                "title": title,
                                "group_a": [a],
                                "group_b": [b],
                                "solo_a": solo[a],
                                "solo_b": solo[b],
                                "co_occurrence": together,
                                "action": "bifurcate",
                            }
                        )
            return proposals


def apply_bifurcation_split(
    domain_key: str,
    episode_id: int,
    group_a: list[str],
    group_b: list[str],
    *,
    unlink_source_membership: bool = False,
) -> dict[str, Any]:
    """
    Create a second episode for group_b; reassign event_episode_links by matched anchors.
    Source episode keeps group_a signature. Does not delete events.
    """
    schema = resolve_domain_schema(domain_key)
    out: dict[str, Any] = {"new_episode_id": None, "moved_links": 0}
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT title, description, story_kind, status, key_entities
                FROM {schema}.storylines WHERE id = %s
                """,
                (int(episode_id),),
            )
            row = cur.fetchone()
            if not row:
                return out
            title, desc, skind, status, key_ents = row
            new_title = f"{title} — {group_b[0]}" if group_b else f"{title} (split)"
            cur.execute(
                f"""
                INSERT INTO {schema}.storylines (
                    title, description, status,
                    episode_state, anchor_signature, signature_locked_at,
                    automation_enabled, key_entities, created_at, updated_at,
                    story_kind
                ) VALUES (
                    %s, %s, %s,
                    'active', %s::jsonb, NOW(),
                    FALSE, %s, NOW(), NOW(),
                    %s
                )
                RETURNING id
                """,
                (
                    new_title[:500],
                    desc,
                    status or "active",
                    json.dumps({"identity": list(group_b), "supporting": []}),
                    json.dumps(key_ents) if key_ents is not None else None,
                    skind or "event_narrative",
                ),
            )
            new_id = (cur.fetchone() or (None,))[0]
            if not new_id:
                conn.rollback()
                return out
            out["new_episode_id"] = int(new_id)
            cur.execute(
                f"""
                UPDATE {schema}.storylines
                SET anchor_signature = %s::jsonb,
                    signature_locked_at = COALESCE(signature_locked_at, NOW()),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    json.dumps({"identity": list(group_a), "supporting": []}),
                    int(episode_id),
                ),
            )
            # Move links whose matched_anchors hit group_b more than group_a
            cur.execute(
                """
                SELECT id, matched_anchors
                FROM intelligence.event_episode_links
                WHERE domain_key = %s AND episode_id = %s
                  AND inference_stage <> 'quarantined'
                """,
                (domain_key, int(episode_id)),
            )
            moved = 0
            for link_id, raw in cur.fetchall() or []:
                anchors = raw
                if isinstance(anchors, str):
                    try:
                        anchors = json.loads(anchors)
                    except Exception:
                        anchors = []
                aset = set(anchors or [])
                score_b = len(aset & set(group_b))
                score_a = len(aset & set(group_a))
                if score_b > score_a:
                    cur.execute(
                        """
                        UPDATE intelligence.event_episode_links
                        SET episode_id = %s,
                            link_type = 'founding',
                            updated_at = NOW(),
                            metadata = metadata || '{"bifurcated_from": %s}'::jsonb
                        WHERE id = %s
                        """,
                        (int(new_id), int(episode_id), int(link_id)),
                    )
                    moved += 1
            out["moved_links"] = moved
            if unlink_source_membership:
                # Do not strip articles by default — derived membership stays until remigrate
                pass
            conn.commit()
    logger.info(
        "bifurcation %s:%s → new %s moved=%s",
        domain_key,
        episode_id,
        out["new_episode_id"],
        out["moved_links"],
    )
    return out
