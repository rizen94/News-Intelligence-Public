"""
Editorial room loop — iterative Ollama + Obsidian vault for unstructured connections.

Headless port of OWUI + vault tracking discovery workflow.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.runtime import env_str
from shared.pipeline_batch_drain import DrainStallTracker, RunBudget

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).resolve().parents[1] / "config" / "prompts" / "editorial_room"


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


async def run_editorial_room_loop(*, shadow: bool = False) -> dict[str, Any]:
    """
    One editorial room cycle: discovery seed → proposals context → iterative LLM rounds.
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
        "proposals_upserted": 0,
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

    open_proposals = export_open_proposals(limit=30)
    coverage = vault.build_coverage_set()
    context_pack = {
        "open_proposals": open_proposals[:15],
        "candidates": candidates[:10],
        "coverage_counts": {k: len(v) for k, v in coverage.items()},
        "scan_since": discovery_result.get("scan_since"),
    }

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
            "Respond with JSON: {\"actions\": [{\"type\": \"draft_connection\"|\"promote_proposal\"|\"skip\", ...}]}"
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

        if stall.record_round(processed=round_progress, had_pending=bool(actions)):
            break
        if round_progress == 0 and rnd > 1:
            break

    now = datetime.now(timezone.utc).isoformat()
    if vault.vault_write_enabled():
        vault.update_cursors(last_connection_loop_at=now, last_tracking_scan_at=now)
        vault.append_session_log(
            f"editorial room: rounds={stats['rounds']} connections={stats['connections_written']} "
            f"proposals={stats['proposals_upserted']} ollama={stats['ollama_calls']}"
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
