"""
Episode attach gate — Event → Episode membership SSOT.

Articles never attach directly. Events match a fixed episode anchor_signature
(hubs stripped). Hub-only → container context association, not episode admit.

Feature: episode_container_assembly / EPISODE_CONTAINER_ASSEMBLY_ENABLED.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from config.runtime import env_bool

logger = logging.getLogger(__name__)

EPISODE_STATES = frozenset(
    {"forming", "active", "cooling", "dormant", "concluded"}
)
LINK_TYPES = frozenset({"founding", "continuation", "development"})
ANCHOR_CLASSES = frozenset({"identity", "supporting", "hub"})


def episode_container_assembly_enabled() -> bool:
    if env_bool("EPISODE_CONTAINER_ASSEMBLY_ENABLED", False):
        return True
    try:
        from config.feature_registry import is_feature_enabled

        return bool(is_feature_enabled("episode_container_assembly", default=False))
    except Exception:
        return False


def _hub_name_set(domain_key: str) -> frozenset[str]:
    try:
        from services.domain_synthesis_config import get_domain_synthesis_config

        return get_domain_synthesis_config(domain_key).hub_name_set()
    except Exception:
        return frozenset()


# Institutions / genre glue — not episode particulars unless catalog says otherwise.
_INSTITUTIONAL_RE = re.compile(
    r"\b("
    r"ministry|department|agency|government|administration|parliament|"
    r"congress|senate|assembly|authority|bureau|commission|committee|"
    r"office of|united nations|\bun\b|nato|supreme court|scotus|"
    r"white house|republicans?|democrats?|\bgop\b|labour party|labor party|"
    r"defence forces?|defense forces?|armed forces|military|army|navy|air force|"
    r"police|emergency services|homeowners association|\bhoa\b|"
    r"think tank|news network|broadcasting|"
    r"federal reserve|\bfed\b|bank of england|central bank|ecb|"
    r"world bank|imf|international monetary fund"
    r")\b",
    re.I,
)

_JUNK_IDENTITY_RE = re.compile(
    r"(no mention|full name|unknown person|n/?a\b|not specified|unnamed)",
    re.I,
)


def _looks_institutional(name_l: str) -> bool:
    if not name_l or len(name_l) < 4:
        return False
    return bool(_INSTITUTIONAL_RE.search(name_l))


def _looks_junk_identity(name_l: str) -> bool:
    if not name_l or len(name_l) < 3:
        return True
    return bool(_JUNK_IDENTITY_RE.search(name_l))


def _normalize_anchor_token(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return f"cid:{value}"
    s = str(value).strip().lower()
    if not s:
        return ""
    if s.isdigit():
        return f"cid:{int(s)}"
    return s


def parse_anchor_signature(raw: Any) -> dict[str, list[str]]:
    """Normalize signature to {identity: [...], supporting: [...]} of tokens."""
    if raw is None:
        return {"identity": [], "supporting": []}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {"identity": [], "supporting": []}
    if not isinstance(raw, dict):
        return {"identity": [], "supporting": []}
    identity = [
        _normalize_anchor_token(x)
        for x in (raw.get("identity") or [])
        if _normalize_anchor_token(x)
    ]
    supporting = [
        _normalize_anchor_token(x)
        for x in (raw.get("supporting") or [])
        if _normalize_anchor_token(x)
    ]
    # Dedupe preserve order
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for i in items:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    return {"identity": _dedupe(identity), "supporting": _dedupe(supporting)}


def classify_event_anchors(
    conn,
    *,
    domain_key: str,
    schema: str,
    event_id: int | None = None,
    article_id: int | None = None,
    entity_names: list[str] | None = None,
) -> dict[str, list[str]]:
    """
    Classify anchors for an event/article into identity / supporting / hub.

    Policy (Mode B particulars):
    - Catalog / hub_facets → hub (never episode identity alone)
    - person / case_number / legislation_id → identity
    - distinctive named orgs → identity; institutional orgs → supporting
    - bare ``cid:N`` without a particular type/name → supporting (not identity)
    - topical / junk strings dropped

    Uses intelligence.entity_anchor_class when present, else hub_facets + types.
    """
    hub_names = _hub_name_set(domain_key)
    identity: list[str] = []
    supporting: list[str] = []
    hubs: list[str] = []

    catalog_by_name: dict[str, str] = {}
    catalog_by_cid: dict[int, str] = {}
    pairs: list[tuple[Any, Any, Any]] = []  # cid, type, name

    try:
        from shared.assembly_link_funnel import is_durable_entity_type
    except Exception:

        def is_durable_entity_type(_et: str | None) -> bool:  # type: ignore
            return True

    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT lower(entity_name), anchor_class, canonical_entity_id
                    FROM intelligence.entity_anchor_class
                    WHERE domain_key IS NULL OR domain_key = %s
                    """,
                    (domain_key,),
                )
                for name, aclass, cid in cur.fetchall() or []:
                    if name:
                        catalog_by_name[str(name).strip().lower()] = str(aclass)
                    if cid is not None:
                        try:
                            catalog_by_cid[int(cid)] = str(aclass)
                        except (TypeError, ValueError):
                            pass
            except Exception:
                pass

            aid = article_id
            if aid is None and event_id is not None:
                cur.execute(
                    """
                    SELECT source_article_id FROM public.chronological_events
                    WHERE id = %s
                    """,
                    (int(event_id),),
                )
                row = cur.fetchone()
                if row and row[0] is not None:
                    aid = int(row[0])
            if aid is not None:
                cur.execute(
                    f"""
                    SELECT ae.canonical_entity_id, ae.entity_type, ae.entity_name
                    FROM {schema}.article_entities ae
                    WHERE ae.article_id = %s
                    """,
                    (int(aid),),
                )
                pairs.extend(cur.fetchall() or [])
    except Exception as exc:
        logger.debug("classify_event_anchors query: %s", exc)

    for name in entity_names or []:
        pairs.append((None, None, name))

    def _is_hub_name(name_l: str) -> bool:
        if not name_l:
            return False
        try:
            from shared.hub_denylist import is_blocked_hub_name

            if is_blocked_hub_name(name_l):
                return True
        except Exception:
            pass
        if name_l in hub_names:
            return True
        return any(len(h) >= 5 and (h in name_l or name_l in h) for h in hub_names)

    PARTICULAR_TYPES = frozenset(
        {"person", "case_number", "legislation_id", "legal_entity", "company"}
    )

    for cid, etype, ename in pairs:
        name_l = (str(ename or "")).strip().lower()
        et = (str(etype or "")).strip().lower()
        token = _normalize_anchor_token(cid if cid is not None else ename)
        if not token:
            continue
        if name_l and _looks_junk_identity(name_l):
            continue

        aclass: str | None = None
        if cid is not None:
            try:
                aclass = catalog_by_cid.get(int(cid))
            except (TypeError, ValueError):
                aclass = None
        if aclass is None and name_l:
            aclass = catalog_by_name.get(name_l)
        if aclass is None and token:
            aclass = catalog_by_name.get(str(token).strip().lower())
        if aclass is None and _is_hub_name(name_l):
            aclass = "hub"

        if aclass is None:
            if not et:
                # Name-only seeds (e.g. discovery common_entities) have no DB type.
                if _is_hub_name(name_l):
                    aclass = "hub"
                elif name_l and _looks_institutional(name_l):
                    aclass = "supporting"
                elif name_l and not _looks_junk_identity(name_l):
                    aclass = "identity"
                else:
                    continue
            elif not is_durable_entity_type(et):
                # Non-durable topical glue — skip entirely
                continue
            elif et in PARTICULAR_TYPES and name_l and not _looks_institutional(name_l):
                aclass = "identity"
            elif et in PARTICULAR_TYPES and token.startswith("cid:"):
                # Resolved person/case even without a clean display name
                aclass = "identity"
            elif name_l and _looks_institutional(name_l):
                aclass = "supporting"
            elif name_l and len(name_l) >= 8 and not _looks_institutional(name_l):
                # Distinctive named org / place-like label
                aclass = (
                    "identity"
                    if et in {"organization", "company", "legal_entity"}
                    else "supporting"
                )
            elif token.startswith("cid:"):
                # Bare canonical id with no particular type/name → supporting only.
                # Promoting every cid to identity created overnight magnets.
                aclass = "supporting"
            else:
                aclass = "supporting"

        if aclass == "hub":
            hubs.append(token if token.startswith("cid:") else (name_l or token))
        elif aclass == "identity":
            # Prefer storing both cid and name so signatures match either surface
            if token.startswith("cid:"):
                identity.append(token)
                if name_l and not _looks_institutional(name_l) and not _looks_junk_identity(name_l):
                    identity.append(name_l)
            else:
                identity.append(token)
        else:
            supporting.append(token if token.startswith("cid:") else (name_l or token))

    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for i in items:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    # Cap identity width — prefer named particulars over long cid tails
    ident = _dedupe(identity)
    named = [t for t in ident if not t.startswith("cid:")]
    cids = [t for t in ident if t.startswith("cid:")]
    ident = (named + cids)[:8]

    return {
        "identity": ident,
        "supporting": _dedupe(supporting)[:12],
        "hub": _dedupe(hubs),
    }


def signature_match(
    signature: dict[str, list[str]],
    event_anchors: dict[str, list[str]],
    *,
    min_supporting: int = 2,
    min_identity: int = 2,
) -> tuple[bool, list[str], str]:
    """
    Return (ok, matched_tokens, reason).

    Admit if ≥min_identity identity overlap OR ≥min_supporting supporting overlap.
    Single-token identity hits are magnet fuel — never candidacy alone.
    Hubs never count.
    """
    sig = parse_anchor_signature(signature)
    id_sig = set(sig.get("identity") or [])
    sup_sig = set(sig.get("supporting") or [])
    id_ev = set(event_anchors.get("identity") or [])
    sup_ev = set(event_anchors.get("supporting") or [])
    hub_ev = set(event_anchors.get("hub") or [])

    if not id_ev and not sup_ev:
        if hub_ev and not id_sig and not sup_sig:
            return False, [], "hub_only_no_signature"
        if hub_ev and not (id_ev | sup_ev):
            return False, [], "hub_only_context"
        return False, [], "no_non_hub_anchors"

    matched_id = sorted(id_sig & id_ev)
    matched_sup = sorted(sup_sig & (sup_ev | id_ev))  # identity can satisfy supporting slot

    need_id = max(1, int(min_identity))
    if len(matched_id) >= need_id:
        return True, matched_id, "identity_match"
    if len(matched_sup) >= min_supporting:
        return True, matched_sup, "supporting_match"
    if matched_id and len(matched_id) < need_id:
        return False, matched_id, "identity_too_thin"
    if hub_ev and not matched_id and not matched_sup:
        return False, [], "hub_only_context"
    return False, [], "signature_mismatch"


def is_container_episode(row: dict[str, Any] | None) -> bool:
    if not row:
        return False
    kind = (row.get("story_kind") or "").strip().lower()
    if kind == "container_index":
        return True
    if row.get("is_mega_storyline"):
        # Prefer explicit story_kind after migrate; mega alone is a soft signal
        meta = row.get("metadata") or {}
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        if isinstance(meta, dict) and meta.get("assembly_role") == "container_index":
            return True
        if kind == "container_index":
            return True
    return kind == "container_index"


def allow_event_episode_attach(
    conn,
    *,
    domain_key: str,
    schema: str,
    episode_id: int,
    event_id: int,
    article_id: int | None = None,
    blend_rank: float | None = None,
    min_supporting: int = 2,
) -> tuple[bool, str, dict[str, Any]]:
    """
    Master gate: may this event join this episode?

    Returns (ok, reason, details) where details includes matched_anchors / signature.
    """
    details: dict[str, Any] = {}
    with conn.cursor() as cur:
        try:
            cur.execute(
                f"""
                SELECT id, title, story_kind,
                       COALESCE(is_mega_storyline, FALSE) AS is_mega_storyline,
                       episode_state, anchor_signature, signature_locked_at, metadata
                FROM {schema}.storylines
                WHERE id = %s
                """,
                (int(episode_id),),
            )
        except Exception:
            cur.execute(
                f"""
                SELECT id, title,
                       NULL::text AS story_kind,
                       COALESCE(is_mega_storyline, FALSE) AS is_mega_storyline,
                       NULL::text AS episode_state,
                       '{{}}'::jsonb AS anchor_signature,
                       NULL::timestamptz AS signature_locked_at,
                       metadata
                FROM {schema}.storylines
                WHERE id = %s
                """,
                (int(episode_id),),
            )
        cols = [d[0] for d in cur.description] if cur.description else []
        row_t = cur.fetchone()
        if not row_t:
            return False, "episode_missing", details
        row = dict(zip(cols, row_t))

    if is_container_episode(row):
        return False, "container_no_membership", {"story_kind": row.get("story_kind")}

    signature = parse_anchor_signature(row.get("anchor_signature"))
    details["signature"] = signature

    # Empty signature: founding path only if we can seed from event identity
    event_anchors = classify_event_anchors(
        conn,
        domain_key=domain_key,
        schema=schema,
        event_id=int(event_id),
        article_id=int(article_id) if article_id is not None else None,
    )
    details["event_anchors"] = {
        k: v for k, v in event_anchors.items() if k != "hub"
    }
    details["hub_anchors"] = event_anchors.get("hub") or []

    empty_sig = not signature["identity"] and not signature["supporting"]
    if empty_sig:
        if event_anchors.get("identity"):
            details["matched_anchors"] = list(event_anchors["identity"][:8])
            details["link_type"] = "founding"
            details["seed_signature"] = {
                "identity": list(event_anchors["identity"][:12]),
                "supporting": list(event_anchors.get("supporting") or [])[:12],
            }
            return True, "founding_identity", details
        if len(event_anchors.get("supporting") or []) >= min_supporting:
            details["matched_anchors"] = list(event_anchors["supporting"][:8])
            details["link_type"] = "founding"
            details["seed_signature"] = {
                "identity": [],
                "supporting": list(event_anchors["supporting"][:12]),
            }
            return True, "founding_supporting", details
        if event_anchors.get("hub") and not event_anchors.get("identity"):
            return False, "hub_only_context", details
        return False, "cannot_found_episode", details

    ok, matched, reason = signature_match(
        signature,
        event_anchors,
        min_supporting=min_supporting,
        min_identity=2,
    )
    details["matched_anchors"] = matched
    details["link_type"] = "continuation"
    if blend_rank is not None:
        details["blend_rank"] = float(blend_rank)
    return ok, reason, details


def insert_event_episode_link(
    cur,
    *,
    event_id: int,
    domain_key: str,
    episode_id: int,
    link_type: str,
    matched_anchors: list[str],
    inference_stage: str = "candidate",
    blend_rank: float | None = None,
    added_by: str = "episode_attach_gate",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """INSERT event_episode_links. Caller owns transaction."""
    if link_type not in LINK_TYPES:
        link_type = "continuation"
    if inference_stage not in (
        "hypothesized",
        "candidate",
        "established",
        "quarantined",
    ):
        inference_stage = "candidate"
    meta = metadata or {}
    try:
        cur.execute(
            """
            INSERT INTO intelligence.event_episode_links (
                event_id, domain_key, episode_id, link_type,
                matched_anchors, inference_stage, blend_rank, added_by, metadata
            ) VALUES (
                %s, %s, %s, %s,
                %s::jsonb, %s, %s, %s, %s::jsonb
            )
            ON CONFLICT (event_id, domain_key, episode_id) DO UPDATE SET
                matched_anchors = EXCLUDED.matched_anchors,
                inference_stage = EXCLUDED.inference_stage,
                blend_rank = COALESCE(EXCLUDED.blend_rank, intelligence.event_episode_links.blend_rank),
                updated_at = NOW(),
                metadata = intelligence.event_episode_links.metadata || EXCLUDED.metadata
            """,
            (
                int(event_id),
                domain_key,
                int(episode_id),
                link_type,
                json.dumps(matched_anchors or []),
                inference_stage,
                blend_rank,
                added_by,
                json.dumps(meta),
            ),
        )
        return True
    except Exception as exc:
        logger.warning("insert_event_episode_link failed: %s", exc)
        return False


def lock_episode_signature(
    cur,
    schema: str,
    episode_id: int,
    signature: dict[str, list[str]],
    *,
    max_identity: int = 8,
    max_supporting: int = 8,
) -> None:
    """Persist and lock anchor_signature on founding.

    Caps identity/supporting width so sprawling bags cannot become magnets.
    """
    sig = parse_anchor_signature(signature)
    sig["identity"] = list(sig.get("identity") or [])[: max(1, int(max_identity))]
    sig["supporting"] = list(sig.get("supporting") or [])[: max(0, int(max_supporting))]
    cur.execute(
        f"""
        UPDATE {schema}.storylines
        SET anchor_signature = %s::jsonb,
            signature_locked_at = COALESCE(signature_locked_at, NOW()),
            episode_state = CASE
                WHEN episode_state = 'forming' THEN 'active'
                ELSE episode_state
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (json.dumps(sig), int(episode_id)),
    )


def attach_article_events_to_episode(
    conn,
    *,
    domain_key: str,
    schema: str,
    episode_id: int,
    article_id: int,
    blend_rank: float | None = None,
    added_by: str = "episode_attach_gate",
    derive_storyline_article: bool | None = None,
) -> tuple[int, str]:
    """
    Attach an article to an episode via its chronological_events (not bag absorb).

    Returns (events_linked_count, reason). When episode_container_assembly is off,
    returns (0, \"feature_off\").
    """
    if not episode_container_assembly_enabled():
        return 0, "feature_off"
    if derive_storyline_article is None:
        try:
            from shared.assembly_link_funnel import storyline_articles_dual_write_enabled

            derive_storyline_article = storyline_articles_dual_write_enabled()
        except Exception:
            derive_storyline_article = False
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM public.chronological_events
            WHERE source_article_id = %s
            ORDER BY id
            LIMIT 25
            """,
            (int(article_id),),
        )
        event_ids = [int(r[0]) for r in (cur.fetchall() or [])]
    if not event_ids:
        return 0, "no_events_for_article"

    linked = 0
    last_reason = "no_match"
    with conn.cursor() as cur:
        for eid in event_ids:
            ok, reason, details = allow_event_episode_attach(
                conn,
                domain_key=domain_key,
                schema=schema,
                episode_id=int(episode_id),
                event_id=int(eid),
                article_id=int(article_id),
                blend_rank=blend_rank,
            )
            last_reason = reason
            if not ok:
                continue
            seed = details.get("seed_signature")
            if seed:
                lock_episode_signature(cur, schema, int(episode_id), seed)
            if insert_event_episode_link(
                cur,
                event_id=int(eid),
                domain_key=domain_key,
                episode_id=int(episode_id),
                link_type=str(details.get("link_type") or "continuation"),
                matched_anchors=list(details.get("matched_anchors") or []),
                inference_stage="candidate",
                blend_rank=blend_rank,
                added_by=added_by,
                metadata={"gate_reason": reason, "article_id": int(article_id)},
            ):
                linked += 1
                cur.execute(
                    """
                    UPDATE public.chronological_events
                    SET storyline_id = %s::text
                    WHERE id = %s AND (storyline_id IS NULL OR storyline_id = '')
                    """,
                    (str(int(episode_id)), int(eid)),
                )
        if linked and derive_storyline_article:
            from shared.membership_store import insert_derived_bag_row

            insert_derived_bag_row(
                cur,
                schema=schema,
                storyline_id=int(episode_id),
                article_id=int(article_id),
                relevance_score=float(blend_rank or 0.0),
                added_by=added_by,
                metadata={
                    "derived_from": "event_episode_link",
                    "events_linked": linked,
                },
            )
            try:
                cur.execute(
                    f"""
                    UPDATE {schema}.storylines
                    SET article_count = (
                            SELECT COUNT(*) FROM {schema}.storyline_articles
                            WHERE storyline_id = %s
                        ),
                        total_articles = (
                            SELECT COUNT(*) FROM {schema}.storyline_articles
                            WHERE storyline_id = %s
                        ),
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (int(episode_id), int(episode_id), int(episode_id)),
                )
            except Exception:
                pass
    if linked:
        return linked, "ok"
    return 0, last_reason


def admit_article_to_episode_or_storyline(
    conn,
    *,
    domain_key: str,
    schema: str,
    storyline_id: int,
    article_id: int,
    blend_score: float = 0.0,
    added_by: str = "membership_admit",
    link_mode: str | None = None,
) -> tuple[bool, str]:
    """
    SSOT membership admit — delegates to membership_store.admit().

    Prefer importing membership_store directly in new code.
    """
    from shared.membership_store import MembershipIntent, admit

    return admit(
        conn,
        domain_key=domain_key,
        schema=schema,
        episode_id=int(storyline_id),
        article_id=int(article_id),
        intent=MembershipIntent.MEMBERSHIP_ADMIT,
        blend_score=float(blend_score or 0.0),
        added_by=added_by,
        link_mode=link_mode,
    )


def project_hub_container_context(
    event_anchors: dict[str, list[str]],
    *,
    domain_key: str,
) -> list[str]:
    """Hub tokens that may associate with container context feeds (never membership)."""
    hubs = list(event_anchors.get("hub") or [])
    hub_names = _hub_name_set(domain_key)
    # Also map name-like tokens already in hub set
    return sorted(set(hubs) | {h for h in hub_names if h in hubs})
