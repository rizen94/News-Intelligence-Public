"""
Editorial room loop — iterative Ollama + Obsidian vault for unstructured connections.

Headless port of OWUI + vault tracking discovery workflow.
Includes T2 entity disambiguation and break/quarantine actions for the quality loop.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.runtime import env_bool, env_str
from shared.pipeline_batch_drain import DrainStallTracker, RunBudget

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "config" / "prompts" / "editorial_room"

ENTITY_DISAMBIG_APPLY_MIN = 0.72


def _max_rounds() -> int:
    try:
        return max(1, min(20, int(env_str("EDITORIAL_ROOM_LOOP_MAX_ROUNDS", "5"))))
    except ValueError:
        return 5


def _proposal_min_confidence() -> float:
    try:
        return float(env_str("EDITORIAL_ROOM_PROPOSAL_MIN_CONFIDENCE", "0.65"))
    except ValueError:
        return 0.65


def _load_prompt(name: str) -> str:
    path = _PROMPTS_DIR / f"{name}.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return f"You are an editorial analyst. Respond with JSON actions only. Template {name} missing."


def _parse_actions(raw: str) -> list[dict[str, Any]]:
    text = (raw or "").strip()
    if not text:
        return []
    fence = re.search(r"```(?:json)?\s*(\{.*\}|\[.*\])\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return []
        else:
            return []
    if isinstance(data, dict):
        actions = data.get("actions")
        if isinstance(actions, list):
            return [a for a in actions if isinstance(a, dict)]
        return [data] if data.get("type") else []
    if isinstance(data, list):
        return [a for a in data if isinstance(a, dict)]
    return []


async def _call_editorial_llm(prompt: str) -> tuple[str, int]:
    from shared.services.llm_service import LLMService, ModelType

    llm = LLMService()
    result = await llm.generate_text(prompt, model=ModelType.LLAMA_8B)
    if isinstance(result, dict):
        text = (result.get("text") or result.get("response") or "").strip()
    else:
        text = str(result or "").strip()
    return text, 1


def _entity_merge_proposals(open_proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in open_proposals:
        if str(p.get("proposal_kind") or "") != "merge":
            continue
        ep = p.get("endpoints") or {}
        if isinstance(ep, dict) and isinstance(ep.get("entity_ids"), list) and len(ep["entity_ids"]) >= 2:
            out.append(p)
    return out


def _contested_claim_ids(limit: int = 20) -> list[dict[str, Any]]:
    """Surface contested/unverified verification writebacks for editorial pack."""
    try:
        from shared.database.connection import get_db_connection_context

        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id AS claim_id,
                           metadata->>'verification_status' AS verification_status,
                           context_id
                    FROM intelligence.extracted_claims
                    WHERE (metadata->>'verification_status') IN (
                        'contested', 'unverified', 'partially_verified'
                    )
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (max(1, min(50, limit)),),
                )
                cols = ["claim_id", "verification_status", "context_id"]
                rows = [dict(zip(cols, r)) for r in cur.fetchall()]
                if rows:
                    return rows
                cur.execute(
                    """
                    SELECT vf.id AS fact_id,
                           vf.metadata->>'verification_status' AS verification_status,
                           COALESCE(vf.metadata->>'claim_id', vf.metadata->>'source_claim_id') AS claim_id
                    FROM intelligence.versioned_facts vf
                    WHERE (vf.metadata->>'verification_status') IN (
                        'contested', 'unverified', 'partially_verified'
                    )
                      AND (vf.metadata->>'superseded_by_fact_id') IS NULL
                    ORDER BY vf.updated_at DESC NULLS LAST
                    LIMIT %s
                    """,
                    (max(1, min(50, limit)),),
                )
                cols2 = ["fact_id", "verification_status", "claim_id"]
                return [dict(zip(cols2, r)) for r in cur.fetchall()]
    except Exception as e:
        logger.debug("contested_claim_ids: %s", e)
        return []


async def run_editorial_room_loop(*, shadow: bool = False) -> dict[str, Any]:
    """
    One editorial room cycle: discovery seed → proposals context → iterative LLM rounds.
    Runs a T2 entity_disambig pass when pending entity merges exist.
    """
    if shadow:
        return {"shadow": True, "rounds": 0}

    from services import tracking_discovery_service as discovery
    from services import vault_bridge_service as vault
    from services.link_indexer_service import export_open_proposals

    budget = RunBudget(int(env_str("EDITORIAL_ROOM_LOOP_BUDGET_SECONDS", "0") or 0))
    stall = DrainStallTracker()
    stats: dict[str, Any] = {
        "rounds": 0,
        "connections_written": 0,
        "investigations_written": 0,
        "editor_tags": 0,
        "proposals_upserted": 0,
        "disambig_actions": 0,
        "merges_applied": 0,
        "breaks": 0,
        "quarantines": 0,
        "ollama_calls": 0,
        "promotions": 0,
    }

    cursors = vault.read_cursors()
    since = cursors.get("last_connection_loop_at") or cursors.get("last_tracking_scan_at")
    now = datetime.now(timezone.utc).isoformat()
    discovery_result = discovery.run_tracking_discovery(since=since, include_vault_reconcile=True)
    candidates = discovery_result.get("items") or []
    if candidates and vault.vault_write_enabled():
        vault.write_candidates(
            candidates,
            scan_since=str(discovery_result.get("scan_since") or now),
            domains_scanned=list(discovery_result.get("domains_scanned") or []),
        )

    open_proposals = export_open_proposals(limit=40)
    merge_proposals = _entity_merge_proposals(open_proposals)
    contested = _contested_claim_ids(20)
    coverage = vault.build_coverage_set()
    context_pack = {
        "open_proposals": open_proposals[:15],
        "entity_merge_candidates": merge_proposals[:12],
        "contested_facts": contested[:15],
        "candidates": candidates[:10],
        "coverage_counts": {k: len(v) for k, v in coverage.items()},
        "scan_since": discovery_result.get("scan_since"),
        "do_not_promote_on_contested": True,
    }

    # --- T2 entity disambiguation round (when merge candidates exist) ---
    if merge_proposals and not budget.expired():
        disambig_template = _load_prompt("entity_disambig")
        pairs = []
        for p in merge_proposals[:10]:
            ep = p.get("endpoints") or {}
            ev = p.get("evidence") or {}
            pairs.append(
                {
                    "proposal_id": p.get("id"),
                    "domain_key": p.get("domain_key"),
                    "confidence": p.get("confidence"),
                    "source_name": (ev or {}).get("source_name") or (ev or {}).get("name_a"),
                    "target_name": (ev or {}).get("target_name") or (ev or {}).get("name_b"),
                    "keep_id": (ev or {}).get("keep_canonical_id")
                    or (ep.get("entity_ids") or [None])[0],
                    "merge_id": (ev or {}).get("merge_canonical_id")
                    or (
                        (ep.get("entity_ids") or [None, None])[1]
                        if len(ep.get("entity_ids") or []) > 1
                        else None
                    ),
                    "reason": (ev or {}).get("reason") or p.get("subject_summary"),
                    "mention_counts": (ev or {}).get("mention_counts"),
                }
            )
        prompt = (
            f"{disambig_template}\n\n"
            f"## Ambiguous entity pairs\n{json.dumps(pairs, indent=2, default=str)[:10000]}\n"
        )
        raw, calls = await _call_editorial_llm(prompt)
        stats["ollama_calls"] += calls
        for action in _parse_actions(raw):
            if (action.get("type") or "").strip().lower() != "entity_disambig":
                continue
            if _apply_entity_disambig(action, stats):
                stats["disambig_actions"] += 1

    template = _load_prompt("connection_loop")
    recent_notes: list[str] = []
    max_rounds = _max_rounds()

    for rnd in range(1, max_rounds + 1):
        if budget.expired():
            break
        stats["rounds"] = rnd
        prompt = (
            f"{template}\n\n"
            f"## Context pack (round {rnd}/{max_rounds})\n"
            f"{json.dumps(context_pack, indent=2, default=str)[:12000]}\n\n"
            f"## Recent vault connection notes\n"
            f"{json.dumps(recent_notes[-5:], indent=2)}\n\n"
            "Respond with JSON: {\"actions\": [{\"type\": "
            "\"draft_connection\"|\"promote_proposal\"|\"break_connection\"|"
            "\"quarantine_connection\"|\"skip\", ...}]}"
        )
        raw, calls = await _call_editorial_llm(prompt)
        stats["ollama_calls"] += calls
        actions = _parse_actions(raw)
        round_progress = 0

        for action in actions:
            atype = (action.get("type") or "").strip().lower()
            if atype == "skip":
                continue
            if atype == "draft_connection":
                written = vault.write_connection_note(action)
                if written.get("ok"):
                    stats["connections_written"] += 1
                    round_progress += 1
                    if written.get("path"):
                        recent_notes.append(written["path"])
            elif atype == "promote_proposal":
                conf = float(action.get("confidence") or 0)
                if conf >= _proposal_min_confidence():
                    pid = _upsert_proposal_from_action(action)
                    if pid:
                        stats["proposals_upserted"] += 1
                        round_progress += 1
            elif atype == "break_connection":
                if _apply_break_or_quarantine(action, quarantine=False, vault=vault):
                    stats["breaks"] += 1
                    round_progress += 1
            elif atype == "quarantine_connection":
                if _apply_break_or_quarantine(action, quarantine=True, vault=vault):
                    stats["quarantines"] += 1
                    round_progress += 1

        if stall.record_round(processed=round_progress, had_pending=bool(actions)):
            break
        if round_progress == 0 and rnd > 1:
            break

    # --- Investigation thread round (vault-first; no DB long-form promote) ---
    if env_bool("EDITORIAL_ROOM_INVESTIGATION_ROUND_ENABLED", False) and not budget.expired():
        inv_stats = await _run_investigation_round(
            vault=vault,
            context_pack=context_pack,
            recent_notes=recent_notes,
            stats=stats,
        )
        stats.update(inv_stats)

    # --- Editor lens: tag only; never promote long-form to DB ---
    if env_bool("EDITORIAL_ROOM_EDITOR_LENS_ENABLED", False) and not budget.expired():
        lens_stats = await _run_editor_lens_round(vault=vault, context_pack=context_pack, stats=stats)
        stats.update(lens_stats)

    now = datetime.now(timezone.utc).isoformat()
    if vault.vault_write_enabled():
        cursor_kwargs: dict[str, str] = {
            "last_connection_loop_at": now,
            "last_tracking_scan_at": now,
        }
        if int(stats.get("investigations_written") or 0) > 0 or env_bool(
            "EDITORIAL_ROOM_INVESTIGATION_ROUND_ENABLED", False
        ):
            cursor_kwargs["last_investigation_loop_at"] = now
        vault.update_cursors(**cursor_kwargs)
        vault.append_session_log(
            f"editorial room: rounds={stats['rounds']} connections={stats['connections_written']} "
            f"investigations={stats.get('investigations_written', 0)} "
            f"editor_tags={stats.get('editor_tags', 0)} "
            f"proposals={stats['proposals_upserted']} disambig={stats['disambig_actions']} "
            f"breaks={stats['breaks']} quarantine={stats['quarantines']} ollama={stats['ollama_calls']}"
        )

    try:
        from services import tracking_promotion_service as promotion

        promo = await promotion.apply_promotions(
            candidates,
            top_n=int(env_str("EDITORIAL_ROOM_PROMOTION_TOP_N", "3") or 3),
        )
        stats["promotions"] = int(promo.get("promoted_count") or 0)
    except Exception as e:
        logger.debug("editorial room promotion: %s", e)

    try:
        from services.assembly_throughput_metrics import record_editorial_room_cycle

        record_editorial_room_cycle(stats)
    except Exception:
        pass

    logger.info("editorial_room_loop: %s", stats)
    return stats


def _apply_entity_disambig(action: dict[str, Any], stats: dict[str, Any]) -> bool:
    """Require keep_id/merge_id; apply merge only when apply_merge and conf >= 0.72."""
    from services.graph_connection_processor_service import _apply_entity_merge
    from services.graph_connection_queue_service import (
        endpoint_key_from_endpoints,
        mark_proposal_resolved,
        record_pattern_refusal,
    )

    keep_id = action.get("keep_id")
    merge_id = action.get("merge_id")
    if keep_id is None or merge_id is None:
        logger.debug("entity_disambig skipped: missing keep_id/merge_id")
        return False
    try:
        keep_id = int(keep_id)
        merge_id = int(merge_id)
    except (TypeError, ValueError):
        return False
    domain_key = action.get("domain_key")
    if not domain_key:
        return False
    conf = float(action.get("confidence") or 0)
    apply_merge = bool(action.get("apply_merge")) and conf >= ENTITY_DISAMBIG_APPLY_MIN
    pid = action.get("proposal_id")
    endpoints = {"domain_key": domain_key, "entity_ids": [keep_id, merge_id]}
    ek = endpoint_key_from_endpoints(domain_key, endpoints)

    if apply_merge:
        if _apply_entity_merge(str(domain_key), keep_id, merge_id):
            stats["merges_applied"] += 1
            if pid is not None:
                mark_proposal_resolved(int(pid), "applied_manual", f"editorial_merge_into={keep_id}")
            return True
        return False

    # Refuse or leave pending with rationale — do not auto-merge below threshold.
    if ek:
        record_pattern_refusal(
            endpoint_key=ek,
            status="refuse",
            reason=str(action.get("rationale") or "editorial_disambig_no_merge")[:500],
            domain_key=str(domain_key),
            endpoints=endpoints,
            source="editorial_entity_disambig",
            proposal_id=int(pid) if pid is not None else None,
        )
    if pid is not None:
        mark_proposal_resolved(
            int(pid),
            "rejected",
            str(action.get("rationale") or "editorial_disambig_refused")[:500],
        )
    return True


def _apply_break_or_quarantine(action: dict[str, Any], *, quarantine: bool, vault: Any) -> bool:
    from services.graph_connection_queue_service import (
        break_graph_connection_link,
        endpoint_key_from_endpoints,
        mark_proposal_resolved,
        record_pattern_refusal,
    )

    endpoints = action.get("endpoints") or {}
    if not isinstance(endpoints, dict):
        endpoints = {}
    domain_key = action.get("domain_key") or endpoints.get("domain_key")
    reason = str(action.get("rationale") or action.get("reason") or "editorial_break")[:500]

    vault_path = None
    if quarantine or action.get("vault_path"):
        q = vault.quarantine_connection_note(
            action.get("vault_path") or action.get("title"),
            reason=reason,
            action=action,
        )
        if q.get("ok"):
            vault_path = q.get("path")

    eids = endpoints.get("entity_ids") or []
    sids = endpoints.get("storyline_ids") or []
    broken = False
    if isinstance(eids, list) and len(eids) >= 2:
        broken = break_graph_connection_link(
            left_kind="entity",
            left_id=int(eids[0]),
            right_kind="entity",
            right_id=int(eids[1]),
            link_role=str(action.get("link_role") or "associated"),
            reason=reason,
            quarantine=quarantine,
            domain_key=domain_key,
        )
    elif isinstance(sids, list) and len(sids) >= 2:
        broken = break_graph_connection_link(
            left_kind="storyline",
            left_id=int(sids[0]),
            right_kind="storyline",
            right_id=int(sids[1]),
            link_role=str(action.get("link_role") or "associated"),
            reason=reason,
            quarantine=quarantine,
            domain_key=domain_key,
        )
    else:
        ek = endpoint_key_from_endpoints(domain_key, endpoints) or str(
            action.get("dedupe_key") or action.get("subject_summary") or ""
        )[:120]
        if ek:
            record_pattern_refusal(
                endpoint_key=ek,
                status="quarantine" if quarantine else "refuse",
                reason=reason,
                domain_key=domain_key,
                endpoints=endpoints,
                source="editorial_room_loop",
                vault_path=vault_path,
            )
            broken = True

    pid = action.get("proposal_id")
    if pid is not None:
        mark_proposal_resolved(
            int(pid),
            "superseded" if quarantine else "rejected",
            reason,
        )
    return broken


def _upsert_proposal_from_action(action: dict[str, Any]) -> int | None:
    from services.graph_connection_queue_service import upsert_graph_connection_proposal

    endpoints = action.get("endpoints") or {}
    if not isinstance(endpoints, dict):
        endpoints = {}
    evidence = action.get("evidence") or {}
    if not isinstance(evidence, dict):
        evidence = {}
    dedupe = str(action.get("dedupe_key") or action.get("subject_summary") or "")[:120]
    if not dedupe:
        return None
    return upsert_graph_connection_proposal(
        dedupe_key=f"editorial_room|{dedupe}",
        proposal_kind=str(action.get("proposal_kind") or "associate"),
        domain_key=action.get("domain_key"),
        confidence=float(action.get("confidence") or _proposal_min_confidence()),
        source="editorial_room_loop",
        endpoints=endpoints,
        evidence=evidence,
        subject_summary=str(action.get("subject_summary") or "")[:255] or None,
    )


async def _run_investigation_round(
    *,
    vault: Any,
    context_pack: dict[str, Any],
    recent_notes: list[str],
    stats: dict[str, Any],
) -> dict[str, Any]:
    """Second LLM round: draft investigation threads into 20_Investigations/."""
    template = _load_prompt("investigation_thread")
    inv_paths = [p for p in recent_notes if "20_Investigations" in p][-5:]
    if not inv_paths:
        try:
            inv_paths = [n["path"] for n in vault.list_recent_investigation_notes(8)]
        except Exception:
            inv_paths = []
    prompt = (
        f"{template}\n\n"
        f"## Context pack\n{json.dumps(context_pack, indent=2, default=str)[:12000]}\n\n"
        f"## Existing investigation notes\n{json.dumps(inv_paths, indent=2)}\n\n"
        'Respond with JSON: {"actions": [{"type": "draft_investigation"|"skip", ...}]}'
    )
    raw, calls = await _call_editorial_llm(prompt)
    stats["ollama_calls"] = int(stats.get("ollama_calls") or 0) + calls
    written = 0
    for action in _parse_actions(raw):
        atype = (action.get("type") or "").strip().lower()
        if atype != "draft_investigation":
            continue
        result = vault.write_investigation_note(action)
        if result.get("ok"):
            written += 1
            if result.get("path"):
                recent_notes.append(result["path"])
    return {"investigations_written": int(stats.get("investigations_written") or 0) + written}


async def _run_editor_lens_round(
    *,
    vault: Any,
    context_pack: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, Any]:
    """Tag vault notes / proposals for review — never promotes long-form to DB."""
    template = _load_prompt("editor_lens")
    try:
        inv_notes = vault.list_recent_investigation_notes(12)
    except Exception:
        inv_notes = []
    pack = {
        "investigation_notes": inv_notes,
        "open_proposals": (context_pack.get("open_proposals") or [])[:10],
        "contested_facts": (context_pack.get("contested_facts") or [])[:8],
    }
    prompt = (
        f"{template}\n\n"
        f"## Review pack\n{json.dumps(pack, indent=2, default=str)[:10000]}\n"
    )
    raw, calls = await _call_editorial_llm(prompt)
    stats["ollama_calls"] = int(stats.get("ollama_calls") or 0) + calls
    tags = 0
    for action in _parse_actions(raw):
        atype = (action.get("type") or "").strip().lower()
        if atype == "tag_investigation":
            path = str(action.get("vault_path") or "").strip()
            status = str(action.get("status") or "needs_review").strip().lower()
            if status not in ("open", "needs_review", "ready_to_promote"):
                status = "needs_review"
            if path and path.startswith("20_Investigations/"):
                updates: dict[str, Any] = {
                    "status": status,
                    "editor_rationale": str(action.get("editor_rationale") or "")[:500],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                if vault.update_vault_note_frontmatter(path, updates).get("ok"):
                    tags += 1
        elif atype == "quarantine_candidate":
            # Soft quarantine: record refusal + mark proposal; do not invent vault paths
            pid = action.get("proposal_id")
            reason = str(action.get("rationale") or "editor_lens_quarantine")[:500]
            if pid is not None:
                from services.graph_connection_queue_service import mark_proposal_resolved

                if mark_proposal_resolved(int(pid), "superseded", reason):
                    tags += 1
                    stats["quarantines"] = int(stats.get("quarantines") or 0) + 1
    return {"editor_tags": int(stats.get("editor_tags") or 0) + tags}
