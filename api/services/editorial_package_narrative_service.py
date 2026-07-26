"""
Editorial package Narrative modality (v11).

Assembles event/entity/article evidence onto an editorial_package (package
membership only — never deletes source rows). Discovers candidates via
search_attachable, event coreference, and causal edges; LLM proposes attaches,
roles, and links; then routes:

- changes > 0 → Reduction
- changes == 0 and last Reduction also 0 → Editor (cycle escape)
- changes == 0 and Reduction not yet run → Reduction once
- max rounds → Editor

Gated by EDITORIAL_NARRATIVE_ENABLED. LLM: PopOS STRUCTURED_EXTRACTION.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.runtime import env_bool, env_int
from shared.database.connection import get_ui_db_connection_context
from shared.editorial_package_vocab import (
    INFERENCE_STAGES,
    LINK_TYPES,
    NARRATIVE_MEMBER_TYPES,
)

logger = logging.getLogger(__name__)

PROMPT_VERSION = "package_narrative.v1"
PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "prompts"
    / "narrative"
    / "package_narrative.md"
)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_VALID_ROLES = frozenset({"anchor_event", "actor", "supporting"})
_REATTACH_MIN_CONF = 0.85


def is_enabled() -> bool:
    return env_bool("EDITORIAL_NARRATIVE_ENABLED", True)


def auto_apply_enabled() -> bool:
    return env_bool("EDITORIAL_NARRATIVE_AUTO_APPLY", True)


def max_rounds() -> int:
    return max(1, env_int("NARRATIVE_MAX_ROUNDS", 3))


def candidate_limit() -> int:
    return max(5, min(env_int("NARRATIVE_CANDIDATE_LIMIT", 40), 80))


def _load_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("narrative prompt missing: %s", e)
        return (
            "Assemble narrative package members and links. Output JSON with "
            "summary_stub, attach[], role_updates[], links[]. Never delete sources. "
            "caused_by requires edge_id; same_event requires coreference."
        )


def _parse_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    m = _JSON_FENCE.search(raw)
    if m:
        raw = m.group(1).strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            obj = json.loads(raw[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            obj = json.loads(value)
            return obj if isinstance(obj, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _merge_package_metadata(package_id: int, patch: dict[str, Any]) -> None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.editorial_packages
                SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (json.dumps(patch), package_id),
            )
            conn.commit()


def _append_summary_decision(
    package_id: int,
    *,
    action: str,
    rationale: str,
    metadata: dict[str, Any],
    model: str | None = None,
) -> None:
    from services.editorial_package_service import _append_decision

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            _append_decision(
                cur,
                package_id=package_id,
                action=action,
                actor="narrative_llm",
                modal="narrative",
                rationale=rationale,
                model_prompt_version=PROMPT_VERSION,
                metadata={**metadata, **({"model": model} if model else {})},
            )
            conn.commit()


def _candidate_key(member_type: str, member_id: int, domain_key: str | None = None) -> str:
    dk = (domain_key or "").strip()
    if dk and member_type in ("entity", "article", "graph_link", "context"):
        return f"{member_type}:{dk}:{int(member_id)}"
    return f"{member_type}:{int(member_id)}"


def _parse_legacy_seed(meta: dict[str, Any]) -> tuple[str | None, int | None]:
    seed = str(meta.get("legacy_seed") or "").strip()
    # storyline:politics:42
    if not seed.startswith("storyline:"):
        return None, None
    parts = seed.split(":")
    if len(parts) < 3:
        return None, None
    try:
        return parts[1], int(parts[2])
    except (TypeError, ValueError):
        return None, None


def _collect_search_candidates(
    package: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    from services.editorial_package_service import search_attachable

    title = str(package.get("working_title") or "").strip()
    summary = str(package.get("summary_stub") or "").strip()
    query = " ".join(x for x in (title, summary[:120]) if x).strip()
    if len(query) < 2:
        query = title or "event"
    domains = list(package.get("domain_keys") or []) or None
    try:
        result = search_attachable(
            modal="narrative",
            q=query[:200],
            domains=domains,
            limit=limit,
        )
    except Exception as e:
        logger.debug("narrative search_attachable failed: %s", e)
        return []
    hits = result.get("hits") or []
    out: list[dict[str, Any]] = []
    for h in hits:
        mt = str(h.get("member_type") or "")
        if mt not in NARRATIVE_MEMBER_TYPES:
            continue
        try:
            mid = int(h["member_id"])
        except (KeyError, TypeError, ValueError):
            continue
        dk = h.get("domain_key")
        key = _candidate_key(mt, mid, str(dk) if dk else None)
        out.append(
            {
                "candidate_key": key,
                "member_type": mt,
                "member_id": mid,
                "member_family": "narrative",
                "domain_key": dk,
                "role": h.get("role") or "supporting",
                "label": h.get("label"),
                "provenance": h.get("provenance") or {},
                "source": "search",
            }
        )
    return out


def _collect_coreference_candidates(
    members: list[dict[str, Any]],
    *,
    limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (candidates, cluster summaries) from attached chronological events."""
    from services.event_coreference_service import expand_event_cluster

    event_ids: list[int] = []
    for m in members:
        if m.get("status") != "active" or m.get("member_type") != "chronological_event":
            continue
        try:
            event_ids.append(int(m["member_id"]))
        except (TypeError, ValueError):
            continue
    if not event_ids:
        return [], []

    candidates: list[dict[str, Any]] = []
    clusters: list[dict[str, Any]] = []
    seen_ids: set[int] = set(event_ids)
    try:
        with get_ui_db_connection_context() as conn:
            for eid in event_ids[:12]:
                rows = expand_event_cluster(conn, eid, limit=min(15, limit))
                cluster_ids = [int(r["id"]) for r in rows if r.get("id") is not None]
                if cluster_ids:
                    clusters.append(
                        {
                            "root_event_id": eid,
                            "event_ids": cluster_ids,
                        }
                    )
                for r in rows:
                    rid = int(r["id"])
                    if rid in seen_ids:
                        continue
                    seen_ids.add(rid)
                    key = _candidate_key("chronological_event", rid)
                    candidates.append(
                        {
                            "candidate_key": key,
                            "member_type": "chronological_event",
                            "member_id": rid,
                            "member_family": "narrative",
                            "domain_key": None,
                            "role": "supporting",
                            "label": r.get("title"),
                            "provenance": {
                                "label": r.get("title"),
                                "event_date": r.get("event_date"),
                                "article_id": r.get("source_article_id"),
                                "coreference_of": eid,
                            },
                            "source": "coreference",
                        }
                    )
                    if len(candidates) >= limit:
                        return candidates, clusters
    except Exception as e:
        logger.debug("coreference candidate expand failed: %s", e)
    return candidates, clusters


def _collect_causal_edges(package: dict[str, Any]) -> list[dict[str, Any]]:
    from services.causal_edges_service import edges_for_storyline, list_causal_edges

    meta = _as_dict(package.get("metadata"))
    dk, sid = _parse_legacy_seed(meta)
    edges: list[dict[str, Any]] = []
    if dk and sid is not None:
        try:
            edges.extend(edges_for_storyline(dk, sid, limit=15))
        except Exception as e:
            logger.debug("edges_for_storyline: %s", e)
    domains = list(package.get("domain_keys") or [])
    for domain in domains[:3]:
        try:
            edges.extend(list_causal_edges(domain_key=domain, limit=10))
        except Exception as e:
            logger.debug("list_causal_edges(%s): %s", domain, e)
    # de-dupe
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for e in edges:
        try:
            eid = int(e.get("id"))
        except (TypeError, ValueError):
            continue
        if eid in seen:
            continue
        seen.add(eid)
        out.append(
            {
                "edge_id": eid,
                "cause_kind": e.get("cause_kind"),
                "cause_id": e.get("cause_id"),
                "effect_kind": e.get("effect_kind"),
                "effect_id": e.get("effect_id"),
                "relation": e.get("relation"),
                "confidence": e.get("confidence"),
                "domain_key": e.get("domain_key"),
            }
        )
        if len(out) >= 25:
            break
    return out


def build_narrative_payload(package: dict[str, Any]) -> dict[str, Any]:
    """Compact payload for LLM: members, candidates, clusters, causal edges, history."""
    members = list(package.get("members") or [])
    links = list(package.get("links") or [])
    active = [m for m in members if m.get("status") == "active"]
    uncoupled = [
        m
        for m in members
        if m.get("status") in ("removed", "quarantined")
        and m.get("member_type") in NARRATIVE_MEMBER_TYPES
    ]

    lim = candidate_limit()
    search_cands = _collect_search_candidates(package, limit=lim)
    coref_cands, clusters = _collect_coreference_candidates(active, limit=lim // 2)
    causal = _collect_causal_edges(package)

    # Dedupe candidates vs already-active members
    active_keys: set[str] = set()
    for m in active:
        mt = str(m.get("member_type") or "")
        try:
            mid = int(m["member_id"])
        except (TypeError, ValueError, KeyError):
            continue
        active_keys.add(_candidate_key(mt, mid, m.get("domain_key")))

    uncoupled_keys: set[str] = set()
    uncoupled_hist: list[dict[str, Any]] = []
    for m in uncoupled:
        mt = str(m.get("member_type") or "")
        try:
            mid = int(m["member_id"])
        except (TypeError, ValueError, KeyError):
            continue
        key = _candidate_key(mt, mid, m.get("domain_key"))
        uncoupled_keys.add(key)
        uncoupled_hist.append(
            {
                "candidate_key": key,
                "member_row_id": m.get("id"),
                "member_type": mt,
                "member_id": mid,
                "status": m.get("status"),
                "label": m.get("display_label"),
            }
        )

    candidates: list[dict[str, Any]] = []
    seen_keys: set[str] = set(active_keys)
    for c in coref_cands + search_cands:
        key = c["candidate_key"]
        if key in seen_keys:
            continue
        seen_keys.add(key)
        c = {**c, "was_uncoupled": key in uncoupled_keys}
        candidates.append(c)
        if len(candidates) >= lim:
            break

    member_rows = []
    for m in active:
        if m.get("member_type") not in NARRATIVE_MEMBER_TYPES and m.get(
            "member_family"
        ) != "narrative":
            # still include narrative-family articles/contexts
            if m.get("member_family") != "narrative":
                continue
        member_rows.append(
            {
                "member_row_id": int(m["id"]),
                "member_type": m.get("member_type"),
                "member_id": m.get("member_id"),
                "domain_key": m.get("domain_key"),
                "role": m.get("role"),
                "display_label": m.get("display_label"),
                "candidate_key": _candidate_key(
                    str(m.get("member_type")),
                    int(m["member_id"]),
                    m.get("domain_key"),
                )
                if m.get("member_id") is not None
                else None,
                "provenance": {
                    k: _as_dict(m.get("provenance")).get(k)
                    for k in (
                        "quote",
                        "source_url",
                        "location",
                        "key_actors",
                        "label",
                        "event_date",
                    )
                    if _as_dict(m.get("provenance")).get(k) is not None
                },
            }
        )

    link_rows = []
    for ln in links:
        if ln.get("status") != "active":
            continue
        link_rows.append(
            {
                "link_id": int(ln["id"]),
                "from_member_id": ln.get("from_member_id"),
                "to_member_id": ln.get("to_member_id"),
                "link_type": ln.get("link_type"),
                "inference_stage": ln.get("inference_stage"),
            }
        )

    return {
        "package_id": package.get("id"),
        "working_title": package.get("working_title"),
        "summary_stub": package.get("summary_stub"),
        "domain_keys": list(package.get("domain_keys") or []),
        "presentation_kind": package.get("presentation_kind"),
        "readiness": package.get("readiness"),
        "members": member_rows,
        "links": link_rows,
        "candidates": candidates,
        "coreference_clusters": clusters,
        "causal_edges": causal,
        "uncoupled_history": uncoupled_hist,
    }


def _event_ids_in_same_cluster(
    clusters: list[dict[str, Any]], a: int, b: int
) -> bool:
    for c in clusters:
        ids = {int(x) for x in (c.get("event_ids") or [])}
        if a in ids and b in ids:
            return True
    return False


def _resolve_ref(
    ref: str,
    *,
    member_by_row: dict[int, dict[str, Any]],
    candidate_by_key: dict[str, dict[str, Any]],
    attached_keys: dict[str, int],
) -> tuple[str, Any] | None:
    """Return ('member_row', id) or ('candidate', cand_dict) or None."""
    raw = (ref or "").strip()
    if raw.startswith("member:"):
        try:
            rid = int(raw.split(":", 1)[1])
        except (IndexError, ValueError):
            return None
        if rid in member_by_row or rid in attached_keys.values():
            return ("member_row", rid)
        return None
    if raw.startswith("candidate:"):
        key = raw[len("candidate:") :]
        if key in attached_keys:
            return ("member_row", attached_keys[key])
        cand = candidate_by_key.get(key)
        if cand:
            return ("candidate", cand)
        return None
    # bare candidate_key
    if raw in attached_keys:
        return ("member_row", attached_keys[raw])
    if raw in candidate_by_key:
        return ("candidate", candidate_by_key[raw])
    return None


def validate_narrative_payload(
    raw: dict[str, Any] | None,
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Coerce LLM output. Drop unknown IDs; gate same_event / caused_by;
    protect uncoupled history unless high-confidence + evidence.
    """
    if not isinstance(raw, dict):
        return {
            "summary_stub": None,
            "working_title": None,
            "insufficient_evidence": True,
            "gaps": ["empty LLM payload"],
            "attach": [],
            "role_updates": [],
            "links": [],
            "rejected": ["empty_payload"],
        }

    candidates = {c["candidate_key"]: c for c in payload.get("candidates") or []}
    members = {
        int(m["member_row_id"]): m for m in payload.get("members") or [] if m.get("member_row_id")
    }
    clusters = list(payload.get("coreference_clusters") or [])
    edge_ids = {
        int(e["edge_id"])
        for e in (payload.get("causal_edges") or [])
        if e.get("edge_id") is not None
    }
    uncoupled = {
        h["candidate_key"]: h for h in (payload.get("uncoupled_history") or []) if h.get("candidate_key")
    }
    # member_id lookup for events already on package
    member_event_id: dict[int, int] = {}
    for m in members.values():
        if m.get("member_type") == "chronological_event":
            try:
                member_event_id[int(m["member_row_id"])] = int(m["member_id"])
            except (TypeError, ValueError):
                pass

    rejected: list[str] = []
    attach: list[dict[str, Any]] = []
    seen_attach: set[str] = set()
    for item in raw.get("attach") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("candidate_key") or "").strip()
        if not key or key not in candidates or key in seen_attach:
            if key:
                rejected.append(f"attach_unknown:{key}")
            continue
        role = str(item.get("role") or "supporting").strip().lower()
        if role not in _VALID_ROLES:
            role = "supporting"
        try:
            conf = float(item.get("confidence") if item.get("confidence") is not None else 0.5)
        except (TypeError, ValueError):
            conf = 0.5
        conf = max(0.0, min(1.0, conf))
        if key in uncoupled:
            # Require strong evidence: coreference candidate source or high conf
            cand = candidates[key]
            ok = cand.get("source") == "coreference" and conf >= _REATTACH_MIN_CONF
            if not ok:
                rejected.append(f"reattach_blocked:{key}")
                continue
        seen_attach.add(key)
        attach.append(
            {
                "candidate_key": key,
                "role": role,
                "confidence": conf,
                "reason": str(item.get("reason") or "")[:500],
                "candidate": candidates[key],
            }
        )

    role_updates: list[dict[str, Any]] = []
    for item in raw.get("role_updates") or []:
        if not isinstance(item, dict):
            continue
        try:
            rid = int(item.get("member_row_id"))
        except (TypeError, ValueError):
            continue
        if rid not in members:
            rejected.append(f"role_unknown:{rid}")
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in _VALID_ROLES:
            rejected.append(f"role_invalid:{rid}")
            continue
        try:
            conf = float(item.get("confidence") if item.get("confidence") is not None else 0.5)
        except (TypeError, ValueError):
            conf = 0.5
        role_updates.append(
            {
                "member_row_id": rid,
                "role": role,
                "confidence": max(0.0, min(1.0, conf)),
                "reason": str(item.get("reason") or "")[:500],
            }
        )

    # Links may reference candidates that are also in this pass's attach list.
    pending_keys = {a["candidate_key"] for a in attach}
    member_by_key = {
        m["candidate_key"]: int(m["member_row_id"])
        for m in members.values()
        if m.get("candidate_key")
    }

    def _endpoint_event_id(ref_kind: str, ref_val: Any) -> int | None:
        if ref_kind == "member_row":
            return member_event_id.get(int(ref_val))
        if ref_kind == "candidate" and isinstance(ref_val, dict):
            if ref_val.get("member_type") == "chronological_event":
                try:
                    return int(ref_val["member_id"])
                except (TypeError, ValueError, KeyError):
                    return None
        return None

    links: list[dict[str, Any]] = []
    for item in raw.get("links") or []:
        if not isinstance(item, dict):
            continue
        link_type = str(item.get("link_type") or "").strip().lower()
        if link_type not in LINK_TYPES:
            rejected.append(f"link_type_invalid:{link_type}")
            continue
        stage = str(item.get("inference_stage") or "hypothesized").strip().lower()
        if stage not in INFERENCE_STAGES:
            stage = "hypothesized"
        # Resolve against already-attached members only; pending attaches stay as candidates.
        from_r = _resolve_ref(
            str(item.get("from_ref") or ""),
            member_by_row=members,
            candidate_by_key=candidates,
            attached_keys=member_by_key,
        )
        to_r = _resolve_ref(
            str(item.get("to_ref") or ""),
            member_by_row=members,
            candidate_by_key=candidates,
            attached_keys=member_by_key,
        )
        if not from_r or not to_r:
            rejected.append("link_endpoint_unknown")
            continue
        # Candidate endpoints must be in attach or already members
        skip_link = False
        for label, resolved in (("from", from_r), ("to", to_r)):
            if resolved[0] == "candidate":
                key = resolved[1]["candidate_key"]
                if key not in pending_keys and key not in member_by_key:
                    rejected.append(f"link_{label}_not_attached:{key}")
                    skip_link = True
                    break
        if skip_link:
            continue

        # Resolve concrete member/candidate endpoints; reject self-links early.
        if from_r[0] == "member_row" and to_r[0] == "member_row" and int(from_r[1]) == int(to_r[1]):
            rejected.append("link_self")
            continue
        if (
            from_r[0] == "candidate"
            and to_r[0] == "candidate"
            and from_r[1].get("candidate_key") == to_r[1].get("candidate_key")
        ):
            rejected.append("link_self")
            continue

        edge_id = item.get("edge_id")
        try:
            edge_id_int = int(edge_id) if edge_id is not None else None
        except (TypeError, ValueError):
            edge_id_int = None

        if link_type == "caused_by":
            if edge_id_int is None or edge_id_int not in edge_ids:
                # Downgrade to correlational
                link_type = "near_in_time"
                stage = "hypothesized"
                edge_id_int = None
                rejected.append("caused_by_downgraded")

        if link_type == "same_event":
            ea = _endpoint_event_id(from_r[0], from_r[1])
            eb = _endpoint_event_id(to_r[0], to_r[1])
            if ea is None or eb is None or not _event_ids_in_same_cluster(clusters, ea, eb):
                rejected.append(f"same_event_rejected:{ea}:{eb}")
                continue
            stage = "established"

        try:
            conf = float(item.get("confidence") if item.get("confidence") is not None else 0.5)
        except (TypeError, ValueError):
            conf = 0.5

        links.append(
            {
                "from_ref": from_r,
                "to_ref": to_r,
                "link_type": link_type,
                "inference_stage": stage,
                "edge_id": edge_id_int,
                "confidence": max(0.0, min(1.0, conf)),
                "reason": str(item.get("reason") or "")[:500],
            }
        )

    summary_stub = raw.get("summary_stub")
    if summary_stub is not None:
        summary_stub = str(summary_stub).strip()[:4000] or None
    working_title = raw.get("working_title")
    if working_title is not None:
        working_title = str(working_title).strip()[:500] or None

    insufficient = bool(raw.get("insufficient_evidence"))
    gaps = [str(g)[:300] for g in (raw.get("gaps") or []) if g][:20]

    # Need an anchor somewhere after attach/role updates, else mark insufficient
    has_anchor = any(a["role"] == "anchor_event" for a in attach) or any(
        r["role"] == "anchor_event" for r in role_updates
    ) or any(
        (m.get("role") == "anchor_event" or m.get("member_type") == "chronological_event")
        for m in members.values()
    )
    if not has_anchor and not attach:
        insufficient = True
        if not gaps:
            gaps.append("no_anchor_event")

    return {
        "summary_stub": summary_stub,
        "working_title": working_title,
        "insufficient_evidence": insufficient,
        "gaps": gaps,
        "attach": attach,
        "role_updates": role_updates,
        "links": links,
        "rejected": rejected,
    }


# Plan / tests alias
_validate_narrative_payload = validate_narrative_payload


def _deterministic_fallback(payload: dict[str, Any]) -> dict[str, Any]:
    """When LLM fails: attach top chronological_event candidates + coreference same_event."""
    attach: list[dict[str, Any]] = []
    events = [
        c
        for c in (payload.get("candidates") or [])
        if c.get("member_type") == "chronological_event" and not c.get("was_uncoupled")
    ]
    for i, c in enumerate(events[:5]):
        attach.append(
            {
                "candidate_key": c["candidate_key"],
                "role": "anchor_event" if i == 0 else "supporting",
                "confidence": 0.55,
                "reason": "deterministic:search/coreference fallback",
            }
        )
    # Promote existing chronological_event to anchor if none attached
    role_updates: list[dict[str, Any]] = []
    if not attach:
        for m in payload.get("members") or []:
            if m.get("member_type") == "chronological_event":
                role_updates.append(
                    {
                        "member_row_id": m["member_row_id"],
                        "role": "anchor_event",
                        "confidence": 0.6,
                        "reason": "deterministic:existing event as anchor",
                    }
                )
                break
    return {
        "summary_stub": payload.get("summary_stub")
        or payload.get("working_title")
        or "Narrative assembly fallback — review members.",
        "working_title": None,
        "insufficient_evidence": not attach and not role_updates,
        "gaps": ["llm_unavailable"] if not attach and not role_updates else [],
        "attach": attach,
        "role_updates": role_updates,
        "links": [],
    }


async def _call_narrative_llm(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    prompt = (
        f"{_load_prompt()}\n\n"
        f"## Package to assemble\n"
        f"```json\n{json.dumps(payload, default=str)[:100_000]}\n```\n"
    )
    try:
        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        result = await caller.generate(
            prompt,
            kind=InvocationKind.STRUCTURED_EXTRACTION,
            urgency="standard",
            approx_prompt_chars=len(prompt),
        )
        return _parse_json_object(result.text), getattr(result, "model", None)
    except Exception as e:
        logger.warning(
            "narrative LLM failed package_id=%s: %s", payload.get("package_id"), e
        )
        return None, None


def _apply_narrative(
    package_id: int,
    validated: dict[str, Any],
    *,
    package: dict[str, Any],
    dry_run: bool,
) -> dict[str, int]:
    """Apply attaches / role updates / links / summary. Returns change counts."""
    from services.editorial_package_service import (
        add_link,
        add_member,
        get_package,
        update_package,
    )

    counts = {
        "attached": 0,
        "role_updated": 0,
        "links_added": 0,
        "summary_updated": 0,
        "kind_updated": 0,
        "title_updated": 0,
    }
    if dry_run or not auto_apply_enabled():
        counts["attached"] = len(validated.get("attach") or [])
        counts["role_updated"] = len(validated.get("role_updates") or [])
        counts["links_added"] = len(validated.get("links") or [])
        if validated.get("summary_stub"):
            counts["summary_updated"] = 1
        if validated.get("working_title"):
            counts["title_updated"] = 1
        return counts

    key_to_row: dict[str, int] = {}
    for m in package.get("members") or []:
        if m.get("status") != "active" or m.get("member_id") is None:
            continue
        try:
            key = _candidate_key(
                str(m.get("member_type")),
                int(m["member_id"]),
                m.get("domain_key"),
            )
            key_to_row[key] = int(m["id"])
        except (TypeError, ValueError):
            continue

    for a in validated.get("attach") or []:
        cand = a["candidate"]
        try:
            member = add_member(
                package_id,
                member_type=cand["member_type"],
                member_id=int(cand["member_id"]),
                member_family="narrative",
                domain_key=cand.get("domain_key"),
                role=a.get("role") or "supporting",
                added_by_modal="narrative",
                added_by="narrative_llm",
                provenance={
                    **(cand.get("provenance") or {}),
                    "narrative_reason": a.get("reason"),
                    "narrative_confidence": a.get("confidence"),
                },
                actor="narrative_llm",
            )
            key_to_row[a["candidate_key"]] = int(member["id"])
            counts["attached"] += 1
        except Exception as e:
            logger.warning("narrative attach failed %s: %s", a.get("candidate_key"), e)

    for ru in validated.get("role_updates") or []:
        # Re-add with new role via add_member upsert (needs member_type/id)
        row_id = int(ru["member_row_id"])
        src = None
        for m in package.get("members") or []:
            if int(m.get("id") or 0) == row_id:
                src = m
                break
        if not src:
            continue
        try:
            add_member(
                package_id,
                member_type=str(src["member_type"]),
                member_id=int(src["member_id"]),
                member_family=str(src.get("member_family") or "narrative"),
                domain_key=src.get("domain_key"),
                role=ru["role"],
                added_by_modal="narrative",
                added_by="narrative_llm",
                provenance=_as_dict(src.get("provenance")),
                actor="narrative_llm",
            )
            counts["role_updated"] += 1
        except Exception as e:
            logger.warning("narrative role update failed row=%s: %s", row_id, e)

    # Refresh mapping after attaches
    refreshed = get_package(package_id, include=True) or package
    key_to_row = {}
    row_ids: set[int] = set()
    for m in refreshed.get("members") or []:
        if m.get("status") != "active" or m.get("member_id") is None:
            continue
        try:
            rid = int(m["id"])
            row_ids.add(rid)
            key = _candidate_key(
                str(m.get("member_type")),
                int(m["member_id"]),
                m.get("domain_key"),
            )
            key_to_row[key] = rid
        except (TypeError, ValueError):
            continue

    def _row_from_ref(ref: tuple[str, Any]) -> int | None:
        kind, val = ref
        if kind == "member_row":
            rid = int(val)
            return rid if rid in row_ids or rid > 0 else None
        if kind == "candidate" and isinstance(val, dict):
            return key_to_row.get(val["candidate_key"])
        return None

    existing_pairs: set[tuple[int, int, str]] = set()
    for ln in refreshed.get("links") or []:
        if ln.get("status") != "active":
            continue
        try:
            existing_pairs.add(
                (
                    int(ln["from_member_id"]),
                    int(ln["to_member_id"]),
                    str(ln.get("link_type")),
                )
            )
        except (TypeError, ValueError, KeyError):
            continue

    for link in validated.get("links") or []:
        frm = _row_from_ref(link["from_ref"])
        to = _row_from_ref(link["to_ref"])
        if frm is None or to is None or frm == to:
            continue
        lt = link["link_type"]
        if (frm, to, lt) in existing_pairs or (to, frm, lt) in existing_pairs:
            continue
        evidence = {
            "reason": link.get("reason"),
            "confidence": link.get("confidence"),
            "edge_id": link.get("edge_id"),
            "source": "narrative_pass",
        }
        try:
            add_link(
                package_id,
                from_member_id=frm,
                to_member_id=to,
                link_type=lt,
                evidence=evidence,
                inference_stage=link.get("inference_stage") or "hypothesized",
                actor="narrative_llm",
                modal="narrative",
            )
            existing_pairs.add((frm, to, lt))
            counts["links_added"] += 1
        except Exception as e:
            logger.warning("narrative link failed: %s", e)

    # Summary / title / presentation_kind
    readiness = _as_dict(refreshed.get("readiness"))
    kind = "event_narrative"
    if readiness.get("research_brief_ready") and readiness.get("event_narrative_ready"):
        kind = "hybrid"
    elif refreshed.get("presentation_kind") == "hybrid":
        kind = "hybrid"

    upd_kwargs: dict[str, Any] = {
        "primary_modal": "narrative",
        "actor": "narrative_llm",
        "modal": "narrative",
        "rationale": "narrative_pass",
    }
    if validated.get("summary_stub"):
        upd_kwargs["summary_stub"] = validated["summary_stub"]
        counts["summary_updated"] = 1
    if validated.get("working_title"):
        upd_kwargs["working_title"] = validated["working_title"]
        counts["title_updated"] = 1
    if refreshed.get("presentation_kind") in (None, "unset", "") or kind != refreshed.get(
        "presentation_kind"
    ):
        upd_kwargs["presentation_kind"] = kind
        counts["kind_updated"] = 1

    if any(
        k in upd_kwargs
        for k in ("summary_stub", "working_title", "presentation_kind")
    ):
        try:
            update_package(package_id, **upd_kwargs)
        except Exception as e:
            logger.warning("narrative update_package failed: %s", e)

    return counts


def resolve_narrative_route(
    *,
    changed: int,
    meta: dict[str, Any],
    round_n: int,
    max_r: int | None = None,
) -> str:
    """
    Return route target: 'reduction' | 'editor' | 'stay'.

    Escape: both Narrative and Reduction consecutive zero-change → editor.
    Max rounds → editor. Changes → reduction. Zero without prior Reduction → reduction.
    """
    max_r = max_r if max_r is not None else max_rounds()
    if round_n >= max_r:
        return "editor"
    if changed > 0:
        return "reduction"
    red_rounds = int(meta.get("reduction_rounds") or 0)
    last_red = meta.get("last_reduction_removed_count")
    try:
        last_red_n = int(last_red) if last_red is not None else None
    except (TypeError, ValueError):
        last_red_n = None
    if red_rounds >= 1 and last_red_n == 0:
        return "editor"
    # Reduction not yet confirmed zero — send once
    return "reduction"


def resolve_reduction_route_after_pass(
    *,
    changed: int,
    meta: dict[str, Any],
    round_n: int,
    max_r: int | None = None,
    default_return_modal: str = "narrative",
) -> str:
    """
    Reduction-side cycle escape helper.

    Returns 'editor' | return modal ('narrative'|'research').

    Partner counters: research_brief (or reduction_return_modal=research) uses
    research_rounds / last_research_change_count; otherwise Narrative counters.
    """
    max_r = max_r if max_r is not None else max(1, env_int("REDUCTION_MAX_ROUNDS", 3))
    if round_n >= max_r:
        return "editor"
    if changed > 0:
        return default_return_modal

    partner = (default_return_modal or "narrative").strip().lower()
    if partner == "research":
        partner_rounds = int(meta.get("research_rounds") or 0)
        last_partner = meta.get("last_research_change_count")
    else:
        partner_rounds = int(meta.get("narrative_rounds") or 0)
        last_partner = meta.get("last_narrative_change_count")
    try:
        last_partner_n = int(last_partner) if last_partner is not None else None
    except (TypeError, ValueError):
        last_partner_n = None
    if partner_rounds >= 1 and last_partner_n == 0:
        return "editor"
    return default_return_modal


async def run_narrative_pass(
    package_id: int,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    if not is_enabled() and not force:
        return {
            "skipped": True,
            "reason": "EDITORIAL_NARRATIVE_ENABLED=false",
            "package_id": package_id,
        }

    from services.editorial_package_service import get_package, mark_ready_for_editor
    from services.modal_handoff_service import request_rework

    pkg = get_package(package_id, include=True)
    if not pkg:
        return {"ok": False, "error": "not_found", "package_id": package_id}

    status = str(pkg.get("status") or "")
    if status != "in_narrative" and not force:
        return {
            "skipped": True,
            "reason": f"status={status} (expected in_narrative)",
            "package_id": package_id,
        }

    meta = _as_dict(pkg.get("metadata"))
    prior_rounds = int(meta.get("narrative_rounds") or 0)
    if prior_rounds >= max_rounds() and not force and not dry_run:
        # Max rounds → escape to editor
        mark_ready_for_editor(
            package_id,
            from_modal="narrative",
            actor="narrative_llm",
            rationale=f"narrative max rounds ({max_rounds()}) — escape to editor",
        )
        _append_summary_decision(
            package_id,
            action="converged",
            rationale="max_rounds escape to editor",
            metadata={"round": prior_rounds, "escape": "max_rounds"},
        )
        return {
            "ok": True,
            "package_id": package_id,
            "skipped": False,
            "converged": True,
            "route_target": "editor",
            "changed": 0,
            "reason": "max_rounds_reached",
        }

    payload = build_narrative_payload(pkg)
    parsed, model = await _call_narrative_llm(payload)
    used_fallback = False
    if not parsed:
        used_fallback = True
        parsed = _deterministic_fallback(payload)

    validated = validate_narrative_payload(parsed, payload=payload)

    # If the LLM forgot to attach an anchor but search found chronological_event
    # candidates, merge the deterministic attach list so we do not starve forever
    # on no_anchor_event (common right after CE restore / legacy seed).
    if (
        validated.get("insufficient_evidence")
        and not validated.get("attach")
        and any(
            c.get("member_type") == "chronological_event"
            for c in (payload.get("candidates") or [])
        )
    ):
        fb = _deterministic_fallback(payload)
        if fb.get("attach"):
            validated = validate_narrative_payload(
                {
                    **(parsed or {}),
                    "attach": fb["attach"],
                    "role_updates": list(validated.get("role_updates") or [])
                    + list(fb.get("role_updates") or []),
                    "links": validated.get("links") or [],
                    "insufficient_evidence": False,
                    "gaps": [],
                },
                payload=payload,
            )
            used_fallback = True

    # Hard stay if insufficient and nothing to attach
    if validated.get("insufficient_evidence") and not validated.get("attach") and not validated.get(
        "role_updates"
    ):
        round_n = prior_rounds + (0 if dry_run else 1)
        if not dry_run:
            _merge_package_metadata(
                package_id,
                {
                    "narrative_rounds": round_n,
                    "last_narrative_change_count": 0,
                    "last_narrative_insufficient": True,
                    "last_narrative_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            _append_summary_decision(
                package_id,
                action="narrative_pass",
                rationale="insufficient_evidence — staying in_narrative",
                metadata={
                    "gaps": validated.get("gaps"),
                    "rejected": validated.get("rejected"),
                    "used_fallback": used_fallback,
                    "narrative_rounds": round_n,
                },
                model=model,
            )
            if round_n >= max_rounds():
                mark_ready_for_editor(
                    package_id,
                    from_modal="narrative",
                    actor="narrative_llm",
                    rationale=(
                        f"narrative max rounds ({max_rounds()}) after "
                        "insufficient_evidence — escape to editor"
                    ),
                )
                _append_summary_decision(
                    package_id,
                    action="converged",
                    rationale="max_rounds escape to editor (insufficient_evidence)",
                    metadata={"round": round_n, "escape": "max_rounds"},
                )
                return {
                    "ok": True,
                    "package_id": package_id,
                    "insufficient_evidence": True,
                    "gaps": validated.get("gaps"),
                    "route_target": "editor",
                    "changed": 0,
                    "converged": True,
                    "reason": "max_rounds_reached",
                    "narrative_rounds": round_n,
                    "used_fallback": used_fallback,
                    "model": model,
                    "prompt_version": PROMPT_VERSION,
                }
        return {
            "ok": True,
            "package_id": package_id,
            "insufficient_evidence": True,
            "gaps": validated.get("gaps"),
            "route_target": "stay",
            "changed": 0,
            "narrative_rounds": round_n,
            "used_fallback": used_fallback,
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "validated": {
                "attach": validated.get("attach"),
                "links": [
                    {
                        "link_type": ln.get("link_type"),
                        "reason": ln.get("reason"),
                    }
                    for ln in (validated.get("links") or [])
                ],
            },
        }

    apply_dry = dry_run or not auto_apply_enabled()
    counts = _apply_narrative(
        package_id, validated, package=pkg, dry_run=apply_dry
    )
    changed = (
        counts["attached"]
        + counts["role_updated"]
        + counts["links_added"]
        + counts["summary_updated"]
        + counts["kind_updated"]
        + counts["title_updated"]
    )
    round_n = prior_rounds + (0 if apply_dry else 1)
    route_target: str | None = None
    routed: dict[str, Any] | None = None

    if not apply_dry:
        patch = {
            "narrative_rounds": round_n,
            "last_narrative_change_count": changed,
            "last_narrative_at": datetime.now(timezone.utc).isoformat(),
        }
        _merge_package_metadata(package_id, patch)
        # Re-read meta with reduction counters for routing
        meta_after = {**meta, **patch}
        route_target = resolve_narrative_route(
            changed=changed, meta=meta_after, round_n=round_n
        )

        _append_summary_decision(
            package_id,
            action="narrative_pass",
            rationale=validated.get("summary_stub")
            or f"narrative pass round {round_n}",
            metadata={
                "round": round_n,
                "counts": counts,
                "changed": changed,
                "rejected": validated.get("rejected"),
                "gaps": validated.get("gaps"),
                "used_fallback": used_fallback,
                "route_target": route_target,
            },
            model=model,
        )

        if route_target == "editor":
            _append_summary_decision(
                package_id,
                action="converged",
                rationale="narrative↔reduction escape — both zero-change or max rounds",
                metadata={
                    "round": round_n,
                    "changed": changed,
                    "last_reduction_removed_count": meta.get(
                        "last_reduction_removed_count"
                    ),
                },
                model=model,
            )
            try:
                routed = mark_ready_for_editor(
                    package_id,
                    from_modal="narrative",
                    actor="narrative_llm",
                    rationale="cycle escape → editor",
                )
            except Exception as e:
                logger.warning("narrative escape to editor failed: %s", e)
                routed = {"error": str(e)}
        elif route_target == "reduction":
            try:
                routed = request_rework(
                    package_id,
                    target_modal="reduction",
                    note=f"post-narrative round {round_n}",
                    actor="narrative_llm",
                    source_modal="narrative",
                )
            except Exception as e:
                logger.warning("narrative→reduction route failed: %s", e)
                routed = {"error": str(e)}

    return {
        "ok": True,
        "package_id": package_id,
        "dry_run": apply_dry,
        "used_fallback": used_fallback,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "summary_stub": validated.get("summary_stub"),
        "counts": counts,
        "changed": changed,
        "narrative_rounds": round_n if not apply_dry else prior_rounds,
        "route_target": route_target,
        "routed": routed,
        "rejected": validated.get("rejected"),
        "gaps": validated.get("gaps"),
        "candidate_count": len(payload.get("candidates") or []),
    }


def run_narrative_pass_sync(
    package_id: int,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(
                    run_narrative_pass(package_id, dry_run=dry_run, force=force)
                )
            ).result()
    return asyncio.run(run_narrative_pass(package_id, dry_run=dry_run, force=force))


def list_narrative_due(*, limit: int = 10) -> list[int]:
    lim = max(1, min(int(limit), 50))
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM intelligence.editorial_packages
                WHERE status = 'in_narrative'
                  AND COALESCE((metadata->>'narrative_rounds')::int, 0) < %s
                ORDER BY updated_at ASC, id ASC
                LIMIT %s
                """,
                (max_rounds(), lim),
            )
            return [int(r[0]) for r in cur.fetchall()]


def run_narrative_batch(*, limit: int | None = None) -> dict[str, Any]:
    if not is_enabled():
        return {
            "skipped": True,
            "reason": "EDITORIAL_NARRATIVE_ENABLED=false",
            "processed": 0,
        }
    batch = limit if limit is not None else env_int("EDITORIAL_NARRATIVE_BATCH", 5)
    ids = list_narrative_due(limit=batch)
    results: list[dict[str, Any]] = []
    for pid in ids:
        try:
            results.append(run_narrative_pass_sync(pid))
        except Exception as e:
            logger.warning("narrative batch item failed package_id=%s: %s", pid, e)
            results.append({"ok": False, "package_id": pid, "error": str(e)})
    return {
        "processed": len(results),
        "package_ids": ids,
        "results": results,
        "changed_total": sum(int(r.get("changed") or 0) for r in results),
    }


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Run editorial narrative pass")
    parser.add_argument("--package-id", type=int, default=None)
    parser.add_argument("--batch", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.force:
        os.environ["EDITORIAL_NARRATIVE_ENABLED"] = "1"
    if args.batch:
        print(json.dumps(run_narrative_batch(limit=args.batch), indent=2, default=str))
    elif args.package_id:
        print(
            json.dumps(
                run_narrative_pass_sync(
                    args.package_id, dry_run=args.dry_run, force=args.force
                ),
                indent=2,
                default=str,
            )
        )
    else:
        parser.error("provide --package-id or --batch")
