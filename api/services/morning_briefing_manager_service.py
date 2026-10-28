"""
Morning Briefing Manager — advanced-model curator for daily reader slate.

Uses PopOS 70b narrative-finisher lane when available; MemPalace for editorial
memory (watches / diary). Selects ongoing vs new_of_note lanes.
Feature: vault_morning_briefing_manager / NI_VAULT_MORNING_BRIEFING_MANAGER.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

from shared.vault_note_contract import (
    MAX_MORNING_NEWS_EXPANSIONS,
    MAX_MORNING_SCIENCE_EXPANSIONS,
    MORNING_NEW_OF_NOTE_CAP,
    MORNING_ONGOING_CAP,
    is_science_vault_domain,
)

logger = logging.getLogger(__name__)

_JSON_ARRAY_RE = re.compile(r"\{[\s\S]*\}")


def briefing_manager_enabled() -> bool:
    raw = os.environ.get("NI_VAULT_MORNING_BRIEFING_MANAGER", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    try:
        from config.feature_registry import is_feature_enabled

        return is_feature_enabled("vault_morning_briefing_manager", default=True)
    except Exception:
        return True


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result(timeout=360)
    return asyncio.run(coro)


async def _llm_manager(prompt: str) -> str:
    from shared.services.ollama_model_caller import get_ollama_model_caller
    from shared.services.ollama_model_policy import InvocationKind

    caller = get_ollama_model_caller()
    result = await caller.generate(
        prompt,
        kind=InvocationKind.STORYLINE_NARRATIVE_FINISH,
        urgency="standard",
        approx_prompt_chars=len(prompt),
    )
    return (result.text or "").strip()


async def _llm_assemble(prompt: str) -> str:
    """Assemble uses advanced lane too when manager enabled."""
    return await _llm_manager(prompt)


def classify_lane_heuristic(lead: dict[str, Any]) -> str:
    """ongoing_narrative vs new_item without LLM."""
    if lead.get("briefing_lane") in ("ongoing", "new"):
        return "ongoing" if lead["briefing_lane"] == "ongoing" else "new"
    has_prior = bool(lead.get("has_prior_expansion"))
    age_days = int(lead.get("age_days") or 0)
    acount = int(lead.get("article_count") or 0)
    watched = bool(lead.get("watched"))
    if watched or has_prior or age_days >= 3 or acount >= 8:
        return "ongoing"
    return "new"


def _magnet_member_cap() -> int:
    try:
        raw = int(os.environ.get("NI_VAULT_MAGNET_MAX_MEMBERS", "32") or "32")
        return max(8, raw)
    except Exception:
        return 32


def heuristic_slate(
    candidates: list[dict[str, Any]],
    *,
    news_cap: int = MAX_MORNING_NEWS_EXPANSIONS,
    science_cap: int = MAX_MORNING_SCIENCE_EXPANSIONS,
    ongoing_cap: int = MORNING_ONGOING_CAP,
    new_cap: int = MORNING_NEW_OF_NOTE_CAP,
) -> dict[str, Any]:
    """Fallback slate when manager LLM / MemPalace unavailable.

    Novelty-first: watched → new members in 2d → prior expansion → updated_at;
    quality_score is a soft tie-break only. Oversized magnet bags are skipped.

    News and science are filled in separate passes so politics cannot starve the
    science branch (shared ongoing/new caps previously took all slots).
    """
    ongoing: list[dict[str, Any]] = []
    new_items: list[dict[str, Any]] = []
    news_n = science_n = 0
    magnet_cap = _magnet_member_cap()
    skipped: list[dict[str, Any]] = []

    def _updated_key(c: dict[str, Any]) -> int:
        digits = "".join(ch for ch in str(c.get("updated_at") or "") if ch.isdigit())[:14]
        try:
            return int(digits or "0")
        except ValueError:
            return 0

    def _rank_key(c: dict[str, Any]) -> tuple:
        return (
            0 if c.get("watched") else 1,
            -(int(c.get("new_members_2d") or 0)),
            0 if c.get("has_prior_expansion") else 1,
            -_updated_key(c),
            -(float(c.get("quality_score") or 0)),  # soft tie-break
        )

    def _fill(pool: list[dict[str, Any]], *, science: bool, branch_cap: int) -> None:
        nonlocal news_n, science_n
        taken = 0
        for c in sorted(pool, key=_rank_key):
            if taken >= branch_cap:
                break
            acount = int(c.get("article_count") or 0)
            if acount >= magnet_cap:
                skipped.append({**c, "reason": "magnet_bag"})
                continue
            lane = classify_lane_heuristic(c)
            item = {**c, "briefing_lane": lane, "reason": "heuristic_novelty"}
            if lane == "ongoing" and len(ongoing) < ongoing_cap:
                ongoing.append(item)
            elif lane == "new" and len(new_items) < new_cap:
                new_items.append(item)
            else:
                continue
            taken += 1
            if science:
                science_n += 1
            else:
                news_n += 1

    news_pool = [c for c in candidates if not is_science_vault_domain(str(c.get("domain_key") or ""))]
    sci_pool = [c for c in candidates if is_science_vault_domain(str(c.get("domain_key") or ""))]
    # Science first so reserved science_cap slots are not displaced by news ongoing fill.
    _fill(sci_pool, science=True, branch_cap=science_cap)
    _fill(news_pool, science=False, branch_cap=news_cap)

    return {
        "ok": True,
        "source": "heuristic",
        "ongoing": ongoing,
        "new_of_note": new_items,
        "skip": skipped[:40],
        "watches_delta": [],
        "rationale": "heuristic_novelty_first",
        "news_selected": news_n,
        "science_selected": science_n,
    }


def _parse_slate_json(raw: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not raw:
        return None
    text = raw.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if m:
            text = m.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = _JSON_ARRAY_RE.search(text)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None

    by_key = {
        (str(c.get("domain_key")), int(c.get("storyline_id"))): c for c in candidates
    }

    def _resolve(items: Any, lane: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not isinstance(items, list):
            return out
        for row in items:
            if not isinstance(row, dict):
                continue
            try:
                dk = str(row.get("domain_key") or "")
                sid = int(row.get("storyline_id"))
            except (TypeError, ValueError):
                continue
            base = by_key.get((dk, sid))
            if not base:
                # try id-only match
                for (dk2, sid2), c in by_key.items():
                    if sid2 == sid:
                        base = c
                        dk = dk2
                        break
            if not base:
                continue
            out.append(
                {
                    **base,
                    "briefing_lane": lane,
                    "reason": str(row.get("reason") or "")[:240],
                }
            )
        return out

    ongoing = _resolve(data.get("ongoing"), "ongoing")[:MORNING_ONGOING_CAP]
    new_of_note = _resolve(data.get("new_of_note") or data.get("new"), "new")[
        :MORNING_NEW_OF_NOTE_CAP
    ]
    return {
        "ok": True,
        "source": "manager_llm",
        "ongoing": ongoing,
        "new_of_note": new_of_note,
        "skip": data.get("skip") if isinstance(data.get("skip"), list) else [],
        "watches_delta": (
            data.get("watches_delta")
            if isinstance(data.get("watches_delta"), list)
            else []
        ),
        "rationale": str(data.get("rationale") or "")[:800],
    }


def propose_brief_slate(
    candidates: list[dict[str, Any]],
    *,
    skip_llm: bool = False,
) -> dict[str, Any]:
    """Curate today's expansion slate using MemPalace memory + advanced LLM."""
    from services.mempalace_brief_memory import (
        apply_watches_delta,
        load_editorial_memory,
    )

    memory = load_editorial_memory()
    # Mark watched candidates from MemPalace snippets
    watch_blob = " ".join(
        (memory.get("watches") or [])
        + (memory.get("preferred") or [])
        + (memory.get("diary") or [])
    ).lower()
    skip_blob = " ".join(memory.get("skip") or []).lower()
    magnet_cap = _magnet_member_cap()
    enriched: list[dict[str, Any]] = []
    for c in candidates:
        title = str(c.get("title") or "").lower()
        sid = str(c.get("storyline_id") or "")
        watched = bool(sid and sid in watch_blob) or any(
            tok and tok in watch_blob for tok in title.split()[:4] if len(tok) > 4
        )
        skipped = bool(sid and sid in skip_blob)
        is_magnet = int(c.get("article_count") or 0) >= magnet_cap
        enriched.append(
            {
                **c,
                "watched": watched,
                "mem_skip": skipped or is_magnet,
                "magnet_bag": is_magnet,
            }
        )

    if skip_llm or not briefing_manager_enabled():
        slate = heuristic_slate([c for c in enriched if not c.get("mem_skip")])
        return slate

    cand_lines = []
    for c in enriched[:80]:
        if c.get("mem_skip"):
            continue
        cand_lines.append(
            f"- {c.get('domain_key')}/{c.get('storyline_id')}: {c.get('title')} "
            f"(new_members_2d={c.get('new_members_2d')}, articles={c.get('article_count')}, "
            f"age_days={c.get('age_days')}, prior_exp={c.get('has_prior_expansion')}, "
            f"watched={c.get('watched')}, quality={c.get('quality_score')})"
        )
    mem_block = {
        "watches": (memory.get("watches") or [])[:6],
        "preferred": (memory.get("preferred") or [])[:6],
        "skip": (memory.get("skip") or [])[:6],
        "diary": (memory.get("diary") or [])[:4],
    }
    prompt = f"""You are the Morning Briefing Manager for a news intelligence product.
Curate TODAY's reader slate. Prefer continuity on important ongoing narratives and a
SHORT list of unrelated new items of note.

Selection priority (in order):
1) Watched / preferred from memory
2) Novelty: high new_members_2d (fresh members since yesterday)
3) Ongoing arcs with prior expansions that moved today
4) quality_score only as a soft tie-break — never pick a bag just because score is high
Skip kitchen-sink / oversized magnet bags.

MemPalace editorial memory (JSON):
{json.dumps(mem_block)[:4000]}

Candidates:
{chr(10).join(cand_lines) or '- none'}

Reply JSON only:
{{
  "ongoing": [{{"domain_key":"politics","storyline_id":123,"reason":"today's update on …"}}],
  "new_of_note": [{{"domain_key":"finance","storyline_id":456,"reason":"new item …"}}],
  "skip": [{{"domain_key":"politics","storyline_id":789,"reason":"noise"}}],
  "watches_delta": [{{"action":"watch|prefer|skip","domain_key":"…","storyline_id":1,"title":"…","reason":"…"}}],
  "rationale": "one short sentence"
}}
Caps: ongoing ≤ {MORNING_ONGOING_CAP}, new_of_note ≤ {MORNING_NEW_OF_NOTE_CAP}.
Only use storyline_ids from the candidate list.
"""
    try:
        raw = _run_async(_llm_manager(prompt))
        parsed = _parse_slate_json(raw, enriched)
        if parsed and (parsed["ongoing"] or parsed["new_of_note"]):
            try:
                apply_watches_delta(parsed.get("watches_delta") or [])
            except Exception as e:
                logger.debug("watches_delta: %s", e)
            # Top-up science if manager ignored the branch despite candidates
            sci_have = sum(
                1
                for r in (parsed.get("ongoing") or []) + (parsed.get("new_of_note") or [])
                if is_science_vault_domain(str(r.get("domain_key") or ""))
            )
            if sci_have == 0:
                h = heuristic_slate([c for c in enriched if not c.get("mem_skip")])
                sci_add = [
                    r
                    for r in (h.get("ongoing") or []) + (h.get("new_of_note") or [])
                    if is_science_vault_domain(str(r.get("domain_key") or ""))
                ]
                if sci_add:
                    for row in sci_add:
                        lane = row.get("briefing_lane") or "new"
                        if lane == "ongoing":
                            parsed.setdefault("ongoing", []).append(row)
                        else:
                            parsed.setdefault("new_of_note", []).append(row)
                    parsed["source"] = "manager_llm+science_topup"
                    parsed["ongoing"] = (parsed.get("ongoing") or [])[:MORNING_ONGOING_CAP]
                    parsed["new_of_note"] = (parsed.get("new_of_note") or [])[
                        :MORNING_NEW_OF_NOTE_CAP
                    ]
            return parsed
        logger.warning("manager slate empty/unparsed; falling back to heuristic")
    except Exception as e:
        logger.warning("propose_brief_slate LLM failed: %s", e)
    slate = heuristic_slate([c for c in enriched if not c.get("mem_skip")])
    return slate


def selected_leads_from_slate(slate: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten ongoing + new into expansion lead list (order preserved)."""
    out: list[dict[str, Any]] = []
    for row in (slate.get("ongoing") or []) + (slate.get("new_of_note") or []):
        out.append(row)
    return out


def assemble_two_lane_briefing(
    *,
    expansions: list[dict[str, Any]],
    briefing_day: str | None = None,
    branch: str = "news",
    skip_llm: bool = False,
    slate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose two-lane morning briefing body from expansion results."""
    day = (briefing_day or date.today().isoformat())[:10]
    ongoing_lines: list[str] = []
    new_lines: list[str] = []
    for ex in expansions:
        if not ex.get("ok") and not ex.get("summary_md"):
            continue
        title = ex.get("title") or f"Storyline {ex.get('storyline_id')}"
        dek = (ex.get("summary_md") or "").strip()
        href = f"{ex.get('domain_key')}/{ex.get('storyline_id')}"
        line = f"- **{title}** ({href}): {dek}" if dek else f"- **{title}** ({href})"
        lane = ex.get("briefing_lane") or "new"
        if lane == "ongoing":
            ongoing_lines.append(line)
        else:
            new_lines.append(line)

    if slate:
        # Prefer slate order if expansions missing lane
        pass

    outline = f"""Day: {day}
Branch: {branch}

## Ongoing updates
{chr(10).join(ongoing_lines) or '- _None this cycle._'}

## New of note
{chr(10).join(new_lines) or '- _None this cycle._'}
"""
    if skip_llm:
        body = outline
    else:
        prompt = f"""Write a morning intelligence briefing for readers from this curated outline.

Structure exactly:
## Ongoing updates
(short paragraphs: "Here's today's update on …" for each ongoing item)

## New of note
(short bullets for unrelated new items)

Tone: clear, grounded, newspaper-briefing. No speculation. Max ~700 words.
Use only the outline facts.
CRITICAL: Keep every storyline citation marker exactly as written, e.g. (politics/12345).
Do not invent stories, orgs, or science claims not in the outline.

Outline:
{outline[:9000]}
"""
        try:
            body = _run_async(_llm_assemble(prompt)) or outline
        except Exception as e:
            logger.warning("assemble_two_lane_briefing LLM: %s", e)
            body = outline
        if not body.strip():
            body = outline
        # Prefer grounded outline over uncited LLM prose (skip-vs-invent).
        try:
            from services.vault_quality_gates import briefing_citations_ok

            ok_cite, cite_reason = briefing_citations_ok(body, expansions=expansions)
            if not ok_cite:
                logger.warning(
                    "assemble_two_lane_briefing citation fail day=%s reason=%s — using outline",
                    day,
                    cite_reason,
                )
                body = outline
        except Exception:
            body = outline

    # Diary
    try:
        from services.mempalace_brief_memory import diary_write_brief

        diary_write_brief(
            briefing_day=day,
            ongoing=[
                e
                for e in expansions
                if e.get("briefing_lane") == "ongoing" and e.get("ok")
            ],
            new_of_note=[
                e for e in expansions if e.get("briefing_lane") != "ongoing" and e.get("ok")
            ],
            rationale=(slate or {}).get("rationale") or "",
        )
    except Exception as e:
        logger.debug("diary after assemble: %s", e)

    return {
        "ok": True,
        "body_md": body.strip()[:14000],
        "outline": outline,
        "ongoing_count": len(ongoing_lines),
        "new_count": len(new_lines),
        "briefing_day": day,
        "branch": branch,
    }
