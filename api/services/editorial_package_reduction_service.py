"""
Editorial package Reduction modality (v11).

Reads package title + summary, scores members/links (deterministic hints + LLM),
then **uncouples** unrelated / weak / geo+entity-mismatched evidence from this
package only (reductive-first). Source articles, events, entities, and claims are
never deleted — only ``editorial_package_members`` / ``editorial_package_links``
status changes. After the pass, routes the package back to research or narrative —
or marks converged.

Gated by EDITORIAL_REDUCTION_ENABLED (default true when feature registry on).
LLM host: PopOS via get_ollama_model_caller (STRUCTURED_EXTRACTION).
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.runtime import env_bool, env_int
from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)

PROMPT_VERSION = "package_reduction.v1"
PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "prompts"
    / "reduction"
    / "package_reduction.md"
)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")

_VALID_TARGETS = frozenset({"member", "link"})
_VALID_ACTIONS = frozenset({"remove", "quarantine", "keep"})
_VALID_FLAGS = frozenset(
    {"unrelated", "weak_link", "entity_mismatch", "geo_mismatch", "theme_mismatch"}
)
_HARD_REMOVE_FLAGS = frozenset({"geo_mismatch", "entity_mismatch", "theme_mismatch"})

# Common place tokens that should not alone decide geo fit (too generic).
_GEO_STOP = frozenset(
    {
        "united",
        "states",
        "america",
        "us",
        "usa",
        "uk",
        "europe",
        "asia",
        "africa",
        "world",
        "global",
        "international",
        "north",
        "south",
        "east",
        "west",
        "city",
        "county",
        "state",
        "province",
        "region",
    }
)


def is_enabled() -> bool:
    return env_bool("EDITORIAL_REDUCTION_ENABLED", True)


def auto_apply_enabled() -> bool:
    return env_bool("EDITORIAL_REDUCTION_AUTO_APPLY", True)


def max_rounds() -> int:
    return max(1, env_int("REDUCTION_MAX_ROUNDS", 3))


def _load_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("reduction prompt missing: %s", e)
        return (
            "You are a strict editorial reducer. Prefer removing unrelated, weak, "
            "or geographically/entity-inconsistent members and links. Output JSON "
            "with summary and actions[{target,id,action,flags,reason,confidence}]."
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


def _tokenize(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return float(inter) / float(union) if union else 0.0


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


def _member_text(m: dict[str, Any]) -> str:
    bits = [
        str(m.get("display_label") or ""),
        str(m.get("role") or ""),
    ]
    prov = _as_dict(m.get("provenance"))
    for key in ("label", "quote", "location", "entity_type"):
        if prov.get(key):
            bits.append(str(prov[key]))
    actors = prov.get("key_actors")
    if isinstance(actors, list):
        bits.extend(str(a) for a in actors if a)
    elif actors:
        bits.append(str(actors))
    extra = m.get("article_snippet") or m.get("article_title")
    if extra:
        bits.append(str(extra))
    return " ".join(bits)


def _member_location_tokens(m: dict[str, Any]) -> set[str]:
    prov = _as_dict(m.get("provenance"))
    raw = " ".join(
        [
            str(prov.get("location") or ""),
            str(m.get("display_label") or "") if m.get("member_type") == "location" else "",
        ]
    )
    return {t for t in _tokenize(raw) if t not in _GEO_STOP}


def _dominant_location_tokens(members: list[dict[str, Any]]) -> set[str]:
    counts: Counter[str] = Counter()
    for m in members:
        if m.get("status") != "active":
            continue
        for t in _member_location_tokens(m):
            counts[t] += 1
    if not counts:
        return set()
    # Keep tokens that appear at least twice, or the top few if sparse.
    dominant = {t for t, c in counts.items() if c >= 2}
    if dominant:
        return dominant
    return {t for t, _ in counts.most_common(5)}


def _enrich_article_snippets(members: list[dict[str, Any]]) -> None:
    """Attach article_title / article_snippet for article members (in-place)."""
    by_domain: dict[str, list[int]] = {}
    for m in members:
        if m.get("member_type") != "article" or m.get("status") != "active":
            continue
        dk = (m.get("domain_key") or "").strip()
        mid = m.get("member_id")
        if not dk or mid is None:
            continue
        try:
            by_domain.setdefault(dk, []).append(int(mid))
        except (TypeError, ValueError):
            continue
    if not by_domain:
        return
    lookup: dict[tuple[str, int], dict[str, str]] = {}
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                for dk, ids in by_domain.items():
                    try:
                        schema = resolve_domain_schema(dk)
                    except Exception:
                        continue
                    uniq = list(dict.fromkeys(ids))
                    cur.execute(
                        f"""
                        SELECT id, title,
                               LEFT(COALESCE(content, ''), 400) AS snippet
                        FROM {schema}.articles
                        WHERE id = ANY(%s)
                        """,
                        (uniq,),
                    )
                    for row in cur.fetchall():
                        lookup[(dk, int(row[0]))] = {
                            "article_title": str(row[1] or "")[:240],
                            "article_snippet": str(row[2] or "")[:400],
                        }
    except Exception as e:
        logger.debug("article snippet enrich skipped: %s", e)
        return
    for m in members:
        if m.get("member_type") != "article":
            continue
        dk = (m.get("domain_key") or "").strip()
        try:
            mid = int(m.get("member_id"))
        except (TypeError, ValueError):
            continue
        hit = lookup.get((dk, mid))
        if hit:
            m["article_title"] = hit["article_title"]
            m["article_snippet"] = hit["article_snippet"]
            if hit["article_title"] and (
                not m.get("display_label")
                or str(m.get("display_label", "")).startswith("article#")
            ):
                m["display_label"] = hit["article_title"]


def build_review_payload(package: dict[str, Any]) -> dict[str, Any]:
    """Compact JSON payload for LLM + deterministic pre-flags."""
    from shared.editorial_package_theme import is_theme_mismatch, package_spine_tokens

    members = list(package.get("members") or [])
    links = list(package.get("links") or [])
    _enrich_article_snippets(members)

    active_members = [m for m in members if m.get("status") == "active"]
    active_links = [ln for ln in links if ln.get("status") == "active"]
    core_text = f"{package.get('working_title') or ''} {package.get('summary_stub') or ''}"
    core_tokens = _tokenize(core_text)
    dominant_geo = _dominant_location_tokens(active_members)
    title = str(package.get("working_title") or "")
    stub = str(package.get("summary_stub") or "")
    spine = package_spine_tokens(title, stub)

    member_rows: list[dict[str, Any]] = []
    for m in active_members:
        text_tokens = _tokenize(_member_text(m))
        title_j = _jaccard(core_tokens, text_tokens)
        loc_tokens = _member_location_tokens(m)
        pre_flags: list[str] = []
        member_blob = " ".join(
            [
                _member_text(m),
                str(m.get("article_title") or ""),
                str(m.get("article_snippet") or ""),
                str(_as_dict(m.get("provenance")).get("label") or ""),
                str(_as_dict(m.get("provenance")).get("quote") or ""),
                str(_as_dict(m.get("provenance")).get("outcome") or ""),
                " ".join(
                    str(x)
                    for x in (_as_dict(m.get("provenance")).get("parties") or [])
                ),
            ]
        )
        if is_theme_mismatch(member_blob, title=title, stub=stub):
            pre_flags.append("theme_mismatch")
        if (
            "theme_mismatch" not in pre_flags
            and core_tokens
            and title_j < 0.08
            and len(text_tokens) >= 3
        ):
            pre_flags.append("unrelated")
        if (
            dominant_geo
            and loc_tokens
            and not (loc_tokens & dominant_geo)
            and len(loc_tokens) >= 1
        ):
            pre_flags.append("geo_mismatch")
        if m.get("member_type") == "entity":
            # Entity with no token overlap vs core actors in title/summary.
            if core_tokens and _jaccard(core_tokens, text_tokens) < 0.05:
                pre_flags.append("entity_mismatch")
        member_rows.append(
            {
                "member_row_id": int(m["id"]),
                "member_type": m.get("member_type"),
                "member_family": m.get("member_family"),
                "role": m.get("role"),
                "domain_key": m.get("domain_key"),
                "display_label": m.get("display_label"),
                "article_title": m.get("article_title"),
                "article_snippet": m.get("article_snippet"),
                "provenance": {
                    k: _as_dict(m.get("provenance")).get(k)
                    for k in (
                        "quote",
                        "source_url",
                        "location",
                        "key_actors",
                        "parties",
                        "outcome",
                        "holding",
                        "entity_type",
                        "evidence_grade",
                        "label",
                    )
                    if _as_dict(m.get("provenance")).get(k) is not None
                },
                "title_jaccard": round(title_j, 4),
                "spine_token_count": len(spine),
                "pre_flags": pre_flags,
            }
        )

    label_by_id = {
        int(m["id"]): m.get("display_label") or f"member#{m['id']}"
        for m in members
        if m.get("id") is not None
    }
    link_rows: list[dict[str, Any]] = []
    for ln in active_links:
        stage = (ln.get("inference_stage") or "").strip().lower()
        pre_flags = ["weak_link"] if stage in ("hypothesized", "quarantined") else []
        link_rows.append(
            {
                "link_id": int(ln["id"]),
                "link_type": ln.get("link_type"),
                "inference_stage": stage,
                "from_member_id": ln.get("from_member_id"),
                "to_member_id": ln.get("to_member_id"),
                "from_label": label_by_id.get(int(ln["from_member_id"]))
                if ln.get("from_member_id") is not None
                else None,
                "to_label": label_by_id.get(int(ln["to_member_id"]))
                if ln.get("to_member_id") is not None
                else None,
                "pre_flags": pre_flags,
            }
        )

    return {
        "package_id": package.get("id"),
        "working_title": package.get("working_title"),
        "summary_stub": package.get("summary_stub"),
        "domain_keys": list(package.get("domain_keys") or []),
        "presentation_kind": package.get("presentation_kind"),
        "dominant_location_tokens": sorted(dominant_geo),
        "members": member_rows,
        "links": link_rows,
    }


def _deterministic_flags(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Build proposal actions from pre_flags (used as LLM hints + LLM-failure fallback)."""
    actions: list[dict[str, Any]] = []
    for m in payload.get("members") or []:
        flags = list(m.get("pre_flags") or [])
        if not flags:
            continue
        action = "remove" if (_HARD_REMOVE_FLAGS & set(flags)) or "unrelated" in flags else "quarantine"
        if _HARD_REMOVE_FLAGS & set(flags):
            action = "remove"
        actions.append(
            {
                "target": "member",
                "id": int(m["member_row_id"]),
                "action": action,
                "flags": flags,
                "reason": f"deterministic:{','.join(flags)}",
                "confidence": 0.65 if "unrelated" in flags else 0.8,
            }
        )
    for ln in payload.get("links") or []:
        flags = list(ln.get("pre_flags") or [])
        if "weak_link" not in flags:
            continue
        actions.append(
            {
                "target": "link",
                "id": int(ln["link_id"]),
                "action": "remove",
                "flags": flags,
                "reason": "deterministic:weak_link",
                "confidence": 0.6,
            }
        )
    return actions


def _action_priority(action: str) -> int:
    """Higher wins when merging deterministic + LLM proposals."""
    a = (action or "keep").strip().lower()
    if a == "remove":
        return 3
    if a == "quarantine":
        return 2
    return 1


def merge_reduction_actions(
    deterministic: list[dict[str, Any]],
    llm_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Union of deterministic pre_flag removals and LLM proposals.

    Prefer the more aggressive action when both mention the same target id.
    LLM ``keep`` must not override a deterministic ``remove``/``quarantine``.
    """
    merged: dict[tuple[str, int], dict[str, Any]] = {}
    for src in (deterministic, llm_actions):
        for item in src or []:
            if not isinstance(item, dict):
                continue
            target = str(item.get("target") or "").strip().lower()
            if target not in _VALID_TARGETS:
                continue
            try:
                rid = int(item["id"])
            except (KeyError, TypeError, ValueError):
                continue
            key = (target, rid)
            action = str(item.get("action") or "keep").strip().lower()
            if action not in _VALID_ACTIONS:
                action = "keep"
            candidate = {
                **item,
                "target": target,
                "id": rid,
                "action": action,
                "flags": list(item.get("flags") or []),
                "reason": str(item.get("reason") or "")[:500],
                "confidence": float(item.get("confidence") if item.get("confidence") is not None else 0.5),
            }
            existing = merged.get(key)
            if existing is None or _action_priority(candidate["action"]) > _action_priority(
                existing["action"]
            ):
                if existing and candidate["action"] != existing["action"]:
                    # Preserve both flag sets when escalating aggressiveness.
                    flags = list(dict.fromkeys([*(existing.get("flags") or []), *candidate["flags"]]))
                    candidate["flags"] = flags
                    if existing.get("reason") and "deterministic:" in str(existing.get("reason")):
                        candidate["reason"] = (
                            f"{existing['reason']}; {candidate['reason']}".strip("; ")
                        )[:500]
                merged[key] = candidate
            elif existing is not None:
                # Same or weaker action — still union flags for audit.
                existing["flags"] = list(
                    dict.fromkeys([*(existing.get("flags") or []), *candidate["flags"]])
                )
    # Drop pure keeps from the apply list (missing id already defaults to keep).
    return [a for a in merged.values() if a.get("action") != "keep"]


def slim_payload_for_llm(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Drop members already hard-pre-flagged so the LLM focuses on ambiguous rows and
    the prompt stays under the truncation budget.
    """
    members = list(payload.get("members") or [])
    ambiguous = [m for m in members if not m.get("pre_flags")]
    # Also include a small sample of pre-flagged for model confirmation context.
    flagged = [m for m in members if m.get("pre_flags")]
    sample_flagged = flagged[: min(12, len(flagged))]
    slim_members = ambiguous + sample_flagged
    # Cap absolute size for pathological packages.
    max_members = max(20, env_int("REDUCTION_LLM_MAX_MEMBERS", 80))
    if len(slim_members) > max_members:
        slim_members = slim_members[:max_members]
    keep_ids = {int(m["member_row_id"]) for m in slim_members}
    links = [
        ln
        for ln in (payload.get("links") or [])
        if not ln.get("pre_flags")
        or (
            int(ln.get("from_member_id") or 0) in keep_ids
            or int(ln.get("to_member_id") or 0) in keep_ids
        )
    ]
    max_links = max(10, env_int("REDUCTION_LLM_MAX_LINKS", 60))
    out = dict(payload)
    out["members"] = slim_members
    out["links"] = links[:max_links]
    out["auto_remove_pre_flagged_count"] = len(flagged)
    out["llm_member_count"] = len(slim_members)
    return out


def validate_reduction_payload(
    raw: dict[str, Any] | None,
    *,
    known_member_ids: set[int],
    known_link_ids: set[int],
) -> dict[str, Any]:
    """
    Coerce LLM (or deterministic) output into a safe actions list.
    Drops unknown ids; clamps actions/flags; forces geo/entity → remove
    (uncouple from package; never deletes source rows).
    """
    if not isinstance(raw, dict):
        return {"summary": "", "actions": []}
    summary = str(raw.get("summary") or "")[:2000]
    out_actions: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for item in raw.get("actions") or []:
        if not isinstance(item, dict):
            continue
        target = str(item.get("target") or "").strip().lower()
        if target not in _VALID_TARGETS:
            continue
        try:
            rid = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if target == "member" and rid not in known_member_ids:
            continue
        if target == "link" and rid not in known_link_ids:
            continue
        key = (target, rid)
        if key in seen:
            continue
        seen.add(key)

        action = str(item.get("action") or "keep").strip().lower()
        if action not in _VALID_ACTIONS:
            action = "keep"
        flags = []
        for f in item.get("flags") or []:
            fs = str(f).strip().lower()
            if fs in _VALID_FLAGS and fs not in flags:
                flags.append(fs)
        if target == "link":
            # Links only support remove/keep (set_link_status has no quarantine).
            if action == "quarantine":
                action = "remove"
            if action not in ("remove", "keep"):
                action = "keep"
            if flags and action == "keep" and "weak_link" in flags:
                action = "remove"
        if _HARD_REMOVE_FLAGS & set(flags):
            action = "remove"
        try:
            conf = float(item.get("confidence") if item.get("confidence") is not None else 0.5)
        except (TypeError, ValueError):
            conf = 0.5
        conf = max(0.0, min(1.0, conf))
        out_actions.append(
            {
                "target": target,
                "id": rid,
                "action": action,
                "flags": flags,
                "reason": str(item.get("reason") or "")[:500],
                "confidence": conf,
            }
        )
    return {"summary": summary, "actions": out_actions}


# Back-compat alias used in plan / tests
_validate_reduction_payload = validate_reduction_payload


def resolve_return_modal(package: dict[str, Any]) -> str:
    """Pick research|narrative for post-reduction rework."""
    meta = _as_dict(package.get("metadata"))
    override = str(meta.get("reduction_return_modal") or "").strip().lower()
    if override in ("research", "narrative"):
        return override
    kind = str(package.get("presentation_kind") or "unset").strip().lower()
    if kind == "research_brief":
        return "research"
    return "narrative"


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
                actor="reduction_llm",
                modal="reduction",
                rationale=rationale,
                model_prompt_version=PROMPT_VERSION,
                metadata={**metadata, **({"model": model} if model else {})},
            )
            conn.commit()


def _route_after_reduction(
    package_id: int,
    *,
    target_modal: str,
    round_n: int,
) -> dict[str, Any]:
    from services.modal_handoff_service import request_rework

    return request_rework(
        package_id,
        target_modal=target_modal,
        note=f"post-reduction round {round_n}",
        actor="reduction_llm",
        source_modal="reduction",
    )


async def _call_reduction_llm(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    llm_payload = slim_payload_for_llm(payload)
    prompt = (
        f"{_load_prompt()}\n\n"
        f"## Package to reduce\n"
        f"Note: {llm_payload.get('auto_remove_pre_flagged_count', 0)} members already have "
        f"deterministic remove pre_flags and will be uncoupled automatically — focus on the "
        f"remaining ambiguous members/links below.\n"
        f"```json\n{json.dumps(llm_payload, default=str)[:100_000]}\n```\n"
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
        parsed = _parse_json_object(result.text)
        return parsed, getattr(result, "model", None)
    except Exception as e:
        logger.warning("reduction LLM failed package_id=%s: %s", payload.get("package_id"), e)
        return None, None


def _apply_actions(
    package_id: int,
    actions: list[dict[str, Any]],
    *,
    dry_run: bool,
) -> dict[str, int]:
    """Apply package-membership changes only (uncouple / quarantine). Never DELETE sources."""
    from services.editorial_package_service import set_link_status, set_member_status

    counts = {"removed": 0, "quarantined": 0, "unlinked": 0, "kept": 0}
    if dry_run or not auto_apply_enabled():
        for a in actions:
            if a["action"] == "keep":
                counts["kept"] += 1
            elif a["target"] == "link" and a["action"] == "remove":
                counts["unlinked"] += 1
            elif a["action"] == "remove":
                counts["removed"] += 1
            elif a["action"] == "quarantine":
                counts["quarantined"] += 1
        return counts

    for a in actions:
        if a["action"] == "keep":
            counts["kept"] += 1
            continue
        reason = a.get("reason") or f"reduction:{','.join(a.get('flags') or [])}"
        # Prefix makes audit trail explicit: package membership only.
        if not reason.lower().startswith("uncouple"):
            reason = f"uncouple from package: {reason}"
        try:
            if a["target"] == "link" and a["action"] == "remove":
                set_link_status(
                    package_id,
                    a["id"],
                    status="removed",
                    actor="reduction_llm",
                    modal="reduction",
                    rationale=reason,
                )
                counts["unlinked"] += 1
            elif a["target"] == "member" and a["action"] == "remove":
                set_member_status(
                    package_id,
                    a["id"],
                    status="removed",
                    actor="reduction_llm",
                    modal="reduction",
                    rationale=reason,
                )
                counts["removed"] += 1
            elif a["target"] == "member" and a["action"] == "quarantine":
                set_member_status(
                    package_id,
                    a["id"],
                    status="quarantined",
                    actor="reduction_llm",
                    modal="reduction",
                    rationale=reason,
                )
                counts["quarantined"] += 1
        except Exception as e:
            logger.warning(
                "reduction apply failed package_id=%s target=%s id=%s: %s",
                package_id,
                a.get("target"),
                a.get("id"),
                e,
            )
    return counts


def _flags_histogram(actions: list[dict[str, Any]]) -> dict[str, int]:
    hist: Counter[str] = Counter()
    for a in actions:
        for f in a.get("flags") or []:
            hist[str(f)] += 1
        hist[f"action:{a.get('action')}"] += 1
    return dict(hist)


async def run_reduction_pass(
    package_id: int,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """
    Run one reduction pass on a package.

    Returns summary with applied/proposed actions and route target (if any).
    """
    if not is_enabled() and not force:
        return {
            "skipped": True,
            "reason": "EDITORIAL_REDUCTION_ENABLED=false",
            "package_id": package_id,
        }

    from services.editorial_package_service import get_package

    pkg = get_package(package_id, include=True)
    if not pkg:
        return {"ok": False, "error": "not_found", "package_id": package_id}

    status = str(pkg.get("status") or "")
    if status != "in_reduction" and not force:
        return {
            "skipped": True,
            "reason": f"status={status} (expected in_reduction)",
            "package_id": package_id,
        }

    meta = _as_dict(pkg.get("metadata"))
    if meta.get("reduction_converged") and not force and not dry_run:
        # Converged but still in_reduction: escape to editor (list_due used to
        # exclude these, so they could stall forever).
        from services.editorial_package_service import reduction_clear_or_block

        try:
            reduction_clear_or_block(
                package_id,
                clear=True,
                actor="reduction_llm",
                rationale="reduction_converged — escape to editor",
            )
            _append_summary_decision(
                package_id,
                action="converged",
                rationale="already_converged escape to editor",
                metadata={"escape": "already_converged"},
            )
        except Exception as e:
            logger.warning("converged editor escape failed: %s", e)
        return {
            "ok": True,
            "package_id": package_id,
            "converged": True,
            "route_target": "editor",
            "reason": "already_converged",
            "changed": 0,
        }

    prior_rounds = int(meta.get("reduction_rounds") or 0)
    if prior_rounds >= max_rounds() and not force and not dry_run:
        from services.editorial_package_service import close_package_thin

        try:
            close_package_thin(
                package_id,
                actor="reduction_llm",
                rationale=f"reduction max rounds ({max_rounds()}) — closed_thin",
                reason="max_rounds",
                from_modal="reduction",
            )
            _append_summary_decision(
                package_id,
                action="converged",
                rationale="max_rounds escape → closed_thin",
                metadata={"round": prior_rounds, "escape": "max_rounds", "status": "closed_thin"},
            )
        except Exception as e:
            logger.warning("max_rounds thin close failed: %s", e)
        return {
            "ok": True,
            "package_id": package_id,
            "converged": True,
            "route_target": "closed_thin",
            "reduction_rounds": prior_rounds,
            "reason": "max_rounds_reached",
            "changed": 0,
        }

    payload = build_review_payload(pkg)
    known_members = {int(m["member_row_id"]) for m in payload["members"]}
    known_links = {int(ln["link_id"]) for ln in payload["links"]}

    parsed, model = await _call_reduction_llm(payload)
    used_fallback = False
    det_actions = _deterministic_flags(payload)
    if not parsed:
        used_fallback = True
        parsed = {
            "summary": "LLM unavailable; uncoupled deterministic unrelated/geo/weak flags from package.",
            "actions": det_actions,
        }

    raw_actions = list((parsed or {}).get("actions") or []) if isinstance(parsed, dict) else []
    # Empty LLM action lists still parse as success — treat as incomplete and
    # always union with deterministic pre_flag removals (LLM keep cannot veto).
    if not used_fallback and not raw_actions:
        used_fallback = True
        if isinstance(parsed, dict) and not (parsed.get("summary") or "").strip():
            parsed["summary"] = (
                "LLM returned no actions; applied deterministic unrelated/geo/weak uncouples."
            )

    validated = validate_reduction_payload(
        parsed,
        known_member_ids=known_members,
        known_link_ids=known_links,
    )
    llm_actions = validated["actions"]
    actions = merge_reduction_actions(det_actions, llm_actions)
    apply_dry = dry_run or not auto_apply_enabled()
    counts = _apply_actions(package_id, actions, dry_run=apply_dry)
    changed = counts["removed"] + counts["quarantined"] + counts["unlinked"]
    round_n = prior_rounds + (0 if apply_dry else 1)
    return_modal = resolve_return_modal(pkg)
    routed: dict[str, Any] | None = None
    route_target: str | None = None

    if not apply_dry:
        # Cycle escape: consult Narrative change counters (shared helper).
        from services.editorial_package_narrative_service import (
            resolve_reduction_route_after_pass,
        )

        patch = {
            "reduction_rounds": round_n,
            "last_reduction_removed_count": changed,
            "last_reduction_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_after = {**meta, **patch}
        route_target = resolve_reduction_route_after_pass(
            changed=changed,
            meta=meta_after,
            round_n=round_n,
            max_r=max_rounds(),
            default_return_modal=return_modal,
        )
        # reduction_converged only when escaping to editor (not when bouncing back)
        patch["reduction_converged"] = route_target == "editor"
        _merge_package_metadata(package_id, patch)
        flags_hist = _flags_histogram(actions)
        _append_summary_decision(
            package_id,
            action="reduction_pass",
            rationale=validated.get("summary") or f"reduction pass round {round_n}",
            metadata={
                "round": round_n,
                "removed": counts["removed"],
                "quarantined": counts["quarantined"],
                "unlinked": counts["unlinked"],
                "kept": counts["kept"],
                "flags_histogram": flags_hist,
                "used_fallback": used_fallback,
                "dry_run": False,
                "route_target": route_target,
                "changed": changed,
            },
            model=model,
        )
        if route_target == "closed_thin":
            from services.editorial_package_service import close_package_thin

            _append_summary_decision(
                package_id,
                action="converged",
                rationale=f"max rounds ({max_rounds()}) — closed_thin",
                metadata={
                    "round": round_n,
                    "changed": changed,
                    "escape": "max_rounds",
                    "status": "closed_thin",
                },
                model=model,
            )
            try:
                routed = close_package_thin(
                    package_id,
                    actor="reduction_llm",
                    rationale="max rounds → closed_thin",
                    reason="max_rounds",
                    from_modal="reduction",
                )
            except Exception as e:
                logger.warning(
                    "reduction closed_thin failed package_id=%s: %s",
                    package_id,
                    e,
                )
                routed = {"error": str(e)}
        elif route_target == "editor":
            from services.editorial_package_service import reduction_clear_or_block

            _append_summary_decision(
                package_id,
                action="converged",
                rationale="narrative↔reduction escape — both zero-change",
                metadata={
                    "round": round_n,
                    "changed": changed,
                    "last_narrative_change_count": meta.get(
                        "last_narrative_change_count"
                    ),
                    "escape": "both_zero",
                },
                model=model,
            )
            try:
                routed = reduction_clear_or_block(
                    package_id,
                    clear=True,
                    actor="reduction_llm",
                    rationale="cycle escape → editor",
                )
            except Exception as e:
                logger.warning(
                    "reduction escape to editor failed package_id=%s: %s",
                    package_id,
                    e,
                )
                routed = {"error": str(e)}
        else:
            # Bounce to narrative/research for another round
            try:
                routed = _route_after_reduction(
                    package_id, target_modal=route_target, round_n=round_n
                )
            except Exception as e:
                logger.warning(
                    "post-reduction route failed package_id=%s → %s: %s",
                    package_id,
                    route_target,
                    e,
                )
                routed = {"error": str(e)}

    return {
        "ok": True,
        "package_id": package_id,
        "dry_run": apply_dry,
        "used_fallback": used_fallback,
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "summary": validated.get("summary"),
        "actions": actions,
        "counts": counts,
        "changed": changed,
        "reduction_rounds": round_n if not apply_dry else prior_rounds,
        "converged": (route_target in ("editor", "closed_thin")) if not apply_dry else False,
        "route_target": route_target,
        "routed": routed,
        "pre_flag_count": sum(
            1 for m in payload["members"] if m.get("pre_flags")
        )
        + sum(1 for ln in payload["links"] if ln.get("pre_flags")),
    }


def run_reduction_pass_sync(
    package_id: int,
    *,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Sync wrapper for automation / CLI."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        # Nested event loop (rare) — schedule as thread-safe future is complex;
        # callers in async context should await run_reduction_pass directly.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(
                    run_reduction_pass(package_id, dry_run=dry_run, force=force)
                )
            ).result()
    return asyncio.run(run_reduction_pass(package_id, dry_run=dry_run, force=force))


def list_reduction_due(*, limit: int = 10) -> list[int]:
    """Package ids with status=in_reduction that are not marked converged."""
    lim = max(1, min(int(limit), 50))
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM intelligence.editorial_packages
                WHERE status = 'in_reduction'
                ORDER BY updated_at ASC, id ASC
                LIMIT %s
                """,
                (lim,),
            )
            return [int(r[0]) for r in cur.fetchall()]


def run_reduction_batch(*, limit: int | None = None) -> dict[str, Any]:
    """Drain up to ``limit`` in_reduction packages (sync, for automation)."""
    if not is_enabled():
        return {"skipped": True, "reason": "EDITORIAL_REDUCTION_ENABLED=false", "processed": 0}
    batch = limit if limit is not None else env_int("EDITORIAL_REDUCTION_BATCH", 5)
    ids = list_reduction_due(limit=batch)
    results: list[dict[str, Any]] = []
    for pid in ids:
        try:
            results.append(run_reduction_pass_sync(pid))
        except Exception as e:
            logger.warning("reduction batch item failed package_id=%s: %s", pid, e)
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

    parser = argparse.ArgumentParser(description="Run editorial reduction pass")
    parser.add_argument("--package-id", type=int, default=None)
    parser.add_argument("--batch", type=int, default=0, help="Drain N in_reduction packages")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.force:
        os.environ["EDITORIAL_REDUCTION_ENABLED"] = "1"
    if args.batch:
        print(json.dumps(run_reduction_batch(limit=args.batch), indent=2, default=str))
    elif args.package_id:
        print(
            json.dumps(
                run_reduction_pass_sync(
                    args.package_id, dry_run=args.dry_run, force=args.force
                ),
                indent=2,
                default=str,
            )
        )
    else:
        parser.error("provide --package-id or --batch")
