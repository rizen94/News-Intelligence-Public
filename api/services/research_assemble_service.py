"""Query-driven research assembly — idea → package + spine + draft sections.

Optional LLM interpret step expands a rough idea into entities, assumptions,
and search queries before retrieval. Does not invent importance.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from services.discovery_finding_quality import RESEARCH_SEED_DOMAINS
from shared.post_processing_modals import modals_for_domain

logger = logging.getLogger(__name__)

_PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "prompts"
    / "research"
    / "assemble_interpret.md"
)
_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _seed_readable_draft_story(
    package_id: int,
    *,
    title: str,
    lede: str,
    body_md: str,
    actor: str,
) -> dict[str, Any]:
    """Persist brief markdown as a draft news_story so the SPA can open the reader."""
    if not body_md.strip():
        return {}
    try:
        from services.news_story_service import create_or_update_draft

        story = create_or_update_draft(
            int(package_id),
            title=(title or "Research draft")[:280],
            lede=(lede or "")[:500] or None,
            body_md=body_md,
            presentation_kind="research_brief",
            actor=actor,
            advance_status=False,
        )
        sid = story.get("id") if isinstance(story, dict) else None
        return {"story_id": int(sid)} if sid is not None else {}
    except Exception as exc:
        logger.warning("assemble draft story seed failed for package %s: %s", package_id, exc)
        return {"story_seed_error": str(exc)[:200]}

_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "about",
        "into",
        "over",
        "after",
        "before",
        "can",
        "we",
        "i",
        "you",
        "it",
        "that",
        "this",
        "these",
        "those",
        "more",
        "learn",
        "get",
        "saw",
        "news",
        "story",
        "topic",
        "historic",
        "view",
        "so",
        "my",
        "me",
    }
)

# Headline / wire-style capitals that are not entities. Searching these
# (e.g. "Revealed", "How") matches any event that happens to use the verb.
_HEADLINE_BAIT = frozenset(
    {
        "revealed",
        "reveal",
        "how",
        "why",
        "what",
        "when",
        "where",
        "who",
        "whom",
        "whose",
        "which",
        "breaking",
        "exclusive",
        "update",
        "updates",
        "updated",
        "report",
        "reports",
        "reporting",
        "analysis",
        "study",
        "studies",
        "new",
        "latest",
        "live",
        "watch",
        "read",
        "inside",
        "meet",
        "says",
        "said",
        "here",
        "there",
        "today",
        "tonight",
        "now",
        "just",
        "after",
        "before",
        "against",
        "amid",
        "despite",
        "undercover",  # adjective alone — prefer full interpret queries
        "agents",
        "protesters",
        "protest",
        "protests",
    }
)

_VALID_DOMAINS = frozenset(
    {
        "finance",
        "politics",
        "legal",
        "medicine",
        "neurodiversity",
        "artificial-intelligence",
    }
)


def _target_modal(domain_key: str | None) -> str:
    if not domain_key:
        return "research"
    mods = modals_for_domain(domain_key)
    if "research" in mods:
        return "research"
    if "narrative" in mods:
        return "narrative"
    return "research"


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


def _load_interpret_prompt() -> str:
    try:
        return _PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return (
            "Turn the user idea into JSON with keys: working_title, research_question, "
            "domain_key, entities, key_assumptions, facts_to_verify, search_queries, "
            "time_scope, exclusions, open_questions. Do not invent citations."
        )


def _normalize_interpret_brief(
    raw: dict[str, Any] | None,
    *,
    idea: str,
    domain_key: str | None,
) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    entities: list[dict[str, str]] = []
    for e in data.get("entities") or []:
        if not isinstance(e, dict):
            continue
        name = str(e.get("name") or "").strip()
        if len(name) < 2:
            continue
        et = str(e.get("entity_type") or "organization").strip().lower()
        if et not in ("person", "organization", "subject", "family", "recurring_event"):
            et = "organization"
        entities.append(
            {
                "name": name[:120],
                "entity_type": et,
                "role": str(e.get("role") or "actor")[:80],
            }
        )

    def _str_list(key: str, *, limit: int = 12) -> list[str]:
        out: list[str] = []
        for x in data.get(key) or []:
            s = str(x or "").strip()
            if s:
                out.append(s[:300])
            if len(out) >= limit:
                break
        return out

    dk = str(data.get("domain_key") or domain_key or "").strip() or None
    if dk and dk not in _VALID_DOMAINS:
        dk = domain_key

    title = str(data.get("working_title") or "").strip()[:200]
    question = str(data.get("research_question") or "").strip()[:500]
    if not title:
        title = (idea or "")[:200]
    if not question:
        question = (idea or "")[:500]

    queries = _str_list("search_queries", limit=10)
    if not queries:
        queries = [idea[:200]]

    return {
        "working_title": title,
        "research_question": question,
        "domain_key": dk,
        "entities": entities,
        "key_assumptions": _str_list("key_assumptions"),
        "facts_to_verify": _str_list("facts_to_verify"),
        "search_queries": queries,
        "time_scope": str(data.get("time_scope") or "").strip()[:200] or None,
        "exclusions": _str_list("exclusions", limit=8),
        "open_questions": _str_list("open_questions"),
        "source": "llm" if raw else "fallback",
    }


def _heuristic_interpret_brief(
    idea: str,
    *,
    domain_key: str | None,
) -> dict[str, Any]:
    """Fallback when LLM is unavailable — still expands search surface a bit."""
    mentions = _extract_mention_candidates(idea)
    queries = [idea[:200]]
    lower = idea.lower()
    for phrase, q in (
        ("bond", "US Treasury holdings China"),
        ("gold", "official gold reserves China"),
        ("treasury", "foreign official Treasury holdings"),
        ("china", "China foreign exchange reserves"),
    ):
        if phrase in lower:
            queries.append(q)
    return _normalize_interpret_brief(
        {
            "working_title": idea[:120],
            "research_question": idea[:400],
            "domain_key": domain_key,
            "entities": [
                {"name": m["name"], "entity_type": m["entity_type"], "role": "mention"}
                for m in mentions[:8]
            ],
            "key_assumptions": [
                "Interpret the request as a research brief; assumptions not verified yet."
            ],
            "facts_to_verify": [f"Evidence related to: {idea[:180]}"],
            "search_queries": queries[:8],
            "time_scope": "recent years unless corpus is older",
            "exclusions": [],
            "open_questions": ["What exact actors and time window does the user mean?"],
        },
        idea=idea,
        domain_key=domain_key,
    )


async def interpret_research_idea(
    idea: str,
    *,
    domain_key: str | None = None,
) -> dict[str, Any]:
    """LLM expands a rough idea into a retrieval brief (entities, assumptions, queries)."""
    text = (idea or "").strip()
    if len(text) < 8:
        return {"ok": False, "error": "idea must be at least 8 characters"}

    prompt = (
        f"{_load_interpret_prompt()}\n\n"
        f"## User idea\n{text}\n\n"
        f"## Hinted domain\n{domain_key or '(none)'}\n"
    )
    model = None
    parsed: dict[str, Any] | None = None
    err: str | None = None
    try:
        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        result = await caller.generate(
            prompt,
            kind=InvocationKind.STRUCTURED_EXTRACTION,
            urgency="real_time",
            approx_prompt_chars=len(prompt),
        )
        model = getattr(result, "model", None)
        parsed = _parse_json_object(result.text)
        if not parsed:
            err = "llm_returned_non_json"
    except Exception as exc:
        err = str(exc)[:200]
        logger.warning("interpret_research_idea LLM failed: %s", exc)

    if parsed:
        brief = _normalize_interpret_brief(parsed, idea=text, domain_key=domain_key)
        brief["ok"] = True
        brief["model"] = model
        return brief

    brief = _heuristic_interpret_brief(text, domain_key=domain_key)
    brief["ok"] = True
    brief["model"] = model
    brief["fallback_reason"] = err or "llm_unavailable"
    return brief


def _extract_mention_candidates(idea: str) -> list[dict[str, str]]:
    """Cheap mention candidates from NL (pattern NER + multi-word capitals)."""
    text = (idea or "").strip()
    found: list[dict[str, str]] = []
    seen: set[str] = set()

    def _add(name: str, etype: str) -> None:
        n = re.sub(r"\s+", " ", (name or "").strip())
        if len(n) < 2:
            return
        key = n.lower()
        if key in seen or key in _STOP or key in _HEADLINE_BAIT:
            return
        seen.add(key)
        found.append({"name": n, "entity_type": etype})

    try:
        from services.pattern_entity_extractor import PatternEntityExtractor

        extracted = PatternEntityExtractor().extract_entities(text) or {}
        for etype, names in extracted.items():
            key = str(etype or "").lower()
            if key.startswith("people") or key == "person":
                et = "person"
            elif key.startswith("location"):
                et = "location"
            else:
                et = "organization"
            # entity_resolution uses organization/person/subject — map location→organization
            if et == "location":
                et = "organization"
            for name in names or []:
                _add(str(name), et)
    except Exception as exc:
        logger.debug("pattern extract: %s", exc)

    # Capitalized multi-word phrases + ALL-CAPS acronyms from the idea.
    for m in re.finditer(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){1,3})\b", text):
        _add(m.group(1), "organization")
    for m in re.finditer(r"\b([A-Z]{2,6})\b", text):
        _add(m.group(1), "organization")
    for token in (
        "China",
        "United States",
        "US",
        "U.S.",
        "gold",
        "Treasury",
        "Treasuries",
        "bonds",
        "Federal Reserve",
        "PBOC",
        "Minnesota",
        "ICE",
    ):
        if re.search(rf"\b{re.escape(token)}\b", text, re.I):
            _add(token, "organization")

    # Significant lowercase content words as last-resort search queries.
    for w in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", text):
        if w.lower() not in _STOP and w[0].isupper():
            continue
        if w.lower() not in _STOP and len(w) >= 5 and w.lower() in {
            "bonds",
            "treasury",
            "treasuries",
            "reserves",
            "deleveraging",
        }:
            _add(w, "organization")

    return found[:24]


def _resolve_entities(
    mentions: list[dict[str, str]],
    *,
    domain_keys: list[str],
) -> list[dict[str, Any]]:
    from services.entity_resolution_service import resolve_with_candidates

    resolved: list[dict[str, Any]] = []
    for m in mentions:
        name = m["name"]
        etype = m.get("entity_type") or "organization"
        type_order = [etype, "organization", "person", "subject"]
        # unique preserve order
        seen_t: list[str] = []
        for t in type_order:
            if t not in seen_t:
                seen_t.append(t)
        best: dict[str, Any] | None = None
        for dk in domain_keys:
            for try_type in seen_t:
                try:
                    out = resolve_with_candidates(dk, name, try_type, limit=5)
                except Exception as exc:
                    logger.debug("resolve %s/%s/%s: %s", dk, name, try_type, exc)
                    continue
                match = out.get("match") if isinstance(out, dict) else None
                if match and match.get("id") is not None:
                    conf = float(match.get("confidence") or 0)
                    cand = {
                        "domain_key": dk,
                        "canonical_entity_id": int(match["id"]),
                        "canonical_name": match.get("canonical_name") or name,
                        "confidence": conf,
                        "mention": name,
                        "entity_type": try_type,
                    }
                    if best is None or conf > float(best.get("confidence") or 0):
                        best = cand
                    break
                for c in (out.get("candidates") or [])[:1]:
                    if c.get("id") is None:
                        continue
                    cand = {
                        "domain_key": dk,
                        "canonical_entity_id": int(c["id"]),
                        "canonical_name": c.get("canonical_name") or name,
                        "confidence": float(c.get("confidence") or 0.4),
                        "mention": name,
                        "entity_type": try_type,
                    }
                    if best is None or float(cand["confidence"]) > float(
                        best.get("confidence") or 0
                    ):
                        best = cand
                    break
            if best and float(best.get("confidence") or 0) >= 0.7:
                break
        if best:
            resolved.append(best)
    # Dedupe by domain+canonical
    uniq: dict[tuple[str, int], dict[str, Any]] = {}
    for r in resolved:
        uniq[(r["domain_key"], int(r["canonical_entity_id"]))] = r
    return list(uniq.values())


def _draft_sections(package: dict[str, Any], *, idea: str) -> dict[str, Any]:
    members = [m for m in (package.get("members") or []) if m.get("status") in (None, "active")]
    claims: list[str] = []
    events: list[str] = []
    articles: list[str] = []
    entities: list[str] = []
    for m in members:
        mt = str(m.get("member_type") or "")
        prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
        label = str(
            prov.get("label")
            or prov.get("quote")
            or prov.get("title")
            or m.get("label")
            or ""
        ).strip()
        if not label:
            mid = m.get("member_id")
            label = f"{mt} #{mid}" if mid is not None else mt
        if not label:
            continue
        if mt in ("extracted_claim", "versioned_fact", "claim_evidence_appraisal", "hypothesis"):
            claims.append(label[:280])
        elif mt == "chronological_event":
            events.append(label[:280])
        elif mt in ("article", "processed_document"):
            articles.append(label[:280])
        elif mt == "entity":
            entities.append(label[:280])

    whats_new = claims[:6] or articles[:6] or events[:6] or entities[:6] or [
        "No claim/article spine attached yet."
    ]
    timeline = events[:8] or articles[:8] or ["No chronological events attached yet."]
    why = [
        f"Operator seed: {idea.strip()[:300]}",
        f"Package members: {len(members)} active "
        f"({len(claims)} claimish, {len(events)} events, {len(articles)} articles/docs"
        f"{', ' + str(len(entities)) + ' entities' if entities else ''}).",
    ]
    watch = [
        "Confirm entity resolution matches the intended actors.",
        "Run research/narrative pass to deepen citations.",
        "Pin standing topics you care about; do not rely on unsupervised discovery.",
    ]

    def _bullets(items: list[str]) -> str:
        return "\n".join(f"- {x}" for x in items)

    brief_md = (
        f"## What's new\n{_bullets(whats_new)}\n\n"
        f"## Why this matters\n{_bullets(why)}\n\n"
        f"## Timeline\n{_bullets(timeline)}\n\n"
        f"## What to watch\n{_bullets(watch)}\n"
    )
    return {
        "whats_new": whats_new,
        "why_this_matters": why,
        "timeline": timeline,
        "what_to_watch": watch,
        "brief_md": brief_md,
    }


def assemble_from_idea(
    idea: str,
    *,
    domain_key: str | None = None,
    actor: str = "research_assemble",
    attach_limit: int = 30,
    run_spine: bool = False,
    dry_run: bool = False,
    brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create/seed a package from a natural-language idea and attach a spine.

    If ``brief`` is provided (from ``interpret_research_idea``), use its entities,
    search queries, and title instead of raw lexical extraction alone.
    """
    from services.editorial_package_service import (
        attach_search_hits,
        create_package,
        ensure_package_from_entity,
        get_package,
        search_attachable,
    )
    from services.package_evidence_brief_service import get_or_create_brief, update_brief
    from shared.domain_registry import get_pipeline_active_domain_keys

    text = (idea or "").strip()
    if len(text) < 8:
        return {"ok": False, "error": "idea must be at least 8 characters"}

    interpret = brief if isinstance(brief, dict) and brief.get("ok") is not False else None
    preferred = (
        str((interpret or {}).get("domain_key") or domain_key or "").strip() or None
    )
    domains = [preferred] if preferred else list(get_pipeline_active_domain_keys())
    domains = [d for d in domains if d]
    if not domains:
        domains = ["finance"]

    mentions = _extract_mention_candidates(text)
    if interpret:
        for e in interpret.get("entities") or []:
            mentions.append(
                {
                    "name": str(e.get("name") or ""),
                    "entity_type": str(e.get("entity_type") or "organization"),
                }
            )
    # Dedupe mentions
    seen_m: set[str] = set()
    uniq_mentions: list[dict[str, str]] = []
    for m in mentions:
        key = (m.get("name") or "").strip().lower()
        if len(key) < 2 or key in seen_m:
            continue
        seen_m.add(key)
        uniq_mentions.append(m)
    mentions = uniq_mentions

    resolved = _resolve_entities(mentions, domain_keys=domains)

    # Prefer research-seed domain entity when available.
    seed_entity = None
    for r in sorted(resolved, key=lambda x: float(x.get("confidence") or 0), reverse=True):
        if r["domain_key"] in RESEARCH_SEED_DOMAINS:
            seed_entity = r
            break
    if seed_entity is None and resolved:
        seed_entity = max(resolved, key=lambda x: float(x.get("confidence") or 0))

    primary_dk = (seed_entity or {}).get("domain_key") or preferred or domains[0]
    modal = _target_modal(primary_dk)
    create_status = "in_research" if modal == "research" else "in_narrative"

    working_title = str((interpret or {}).get("working_title") or text)[:200]
    research_question = str((interpret or {}).get("research_question") or text)[:500]
    search_queries = list((interpret or {}).get("search_queries") or []) or [text]

    if dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "idea": text,
            "domain_key": primary_dk,
            "target_modal": modal,
            "mentions": mentions,
            "entities_resolved": resolved,
            "seed_entity": seed_entity,
            "interpret": interpret,
            "working_title": working_title,
            "research_question": research_question,
            "search_queries": search_queries,
        }

    package_id: int | None = None
    created = False
    if seed_entity and seed_entity["domain_key"] in RESEARCH_SEED_DOMAINS:
        try:
            pkg = ensure_package_from_entity(
                domain_key=seed_entity["domain_key"],
                canonical_entity_id=int(seed_entity["canonical_entity_id"]),
                actor=actor,
                refresh_members=True,
            )
            package_id = int(pkg["id"])
            primary_dk = seed_entity["domain_key"]
            modal = "research"
            create_status = "in_research"
        except Exception as exc:
            logger.info("assemble entity seed failed: %s", exc)

    if package_id is None:
        pkg = create_package(
            working_title=working_title,
            summary_stub=research_question,
            primary_modal=modal,
            domain_keys=[primary_dk],
            status=create_status,
            actor=actor,
            created_by=actor,
            metadata={
                "source": "research_assemble",
                "prompt": text[:2000],
                "research_question": research_question,
                "interpret": interpret,
                "seed_entity": seed_entity,
            },
        )
        package_id = int(pkg["id"])
        created = True

    # Lexical attach: interpret search queries + interpret entities first.
    # Do NOT backfill from bare headline tokens (Revealed/How) or the raw idea
    # string when an interpret brief already supplied targeted queries.
    interpret_entity_names = [
        str(e.get("name") or "").strip()
        for e in ((interpret or {}).get("entities") or [])
        if str(e.get("name") or "").strip()
        and str(e.get("name") or "").strip().lower() not in _HEADLINE_BAIT
    ]

    def _filter_query_list(raw: list[str]) -> list[str]:
        seen_q: set[str] = set()
        out: list[str] = []
        for q in raw:
            key = (q or "").strip().lower()
            if len(key) < 2 or key in seen_q or key in _HEADLINE_BAIT:
                continue
            if " " not in key and len(key) <= 3 and key not in {"ice", "us", "un", "eu", "uk"}:
                continue
            seen_q.add(key)
            out.append(q.strip())
        return out[:16]

    primary_queries = _filter_query_list(list(search_queries))
    entity_queries = _filter_query_list(interpret_entity_names)
    mention_queries = _filter_query_list([m["name"] for m in mentions[:6]])
    if not (interpret and search_queries):
        # No interpret brief — allow filtered mentions + idea as last resort.
        mention_queries = _filter_query_list(
            [m["name"] for m in mentions[:6]] + ([text] if text else [])
        )

    exclusions = [str(x).lower() for x in ((interpret or {}).get("exclusions") or []) if x]
    attached = 0
    seen_hits: set[tuple[str, int]] = set()

    def _prefer_hit(h: dict[str, Any]) -> tuple:
        mt = str(h.get("member_type") or "")
        label = str(h.get("label") or "").lower()
        excluded = 1 if any(x and x in label for x in exclusions) else 0
        rank = {
            "extracted_claim": 0,
            "versioned_fact": 0,
            "claim_evidence_appraisal": 0,
            "article": 1,
            "processed_document": 1,
            "chronological_event": 2,
            "entity": 3,
        }.get(mt, 9)
        return (excluded, rank, label)

    def _run_query_batch(batch: list[str]) -> int:
        nonlocal attached
        batch_added = 0
        for q in batch:
            if attached >= attach_limit:
                break
            try:
                search = search_attachable(
                    modal=modal,
                    q=q,
                    domains=[primary_dk] if primary_dk else None,
                    limit=min(20, attach_limit),
                )
            except Exception as exc:
                logger.debug("search_attachable: %s", exc)
                continue
            ranked = sorted(list(search.get("hits") or []), key=_prefer_hit)
            hits = []
            for h in ranked:
                label = str(h.get("label") or "").lower()
                if any(x and x in label for x in exclusions):
                    continue
                key = (str(h.get("member_type")), int(h.get("member_id") or 0))
                if key in seen_hits or key[1] <= 0:
                    continue
                seen_hits.add(key)
                hits.append(h)
                if len(hits) >= attach_limit:
                    break
            if not hits:
                continue
            try:
                added = attach_search_hits(
                    package_id,
                    hits[: max(1, attach_limit - attached)],
                    modal=modal,
                    actor=actor,
                )
                n = len(added)
                attached += n
                batch_added += n
            except Exception as exc:
                logger.debug("attach hits: %s", exc)
        return batch_added

    # 1) Interpret search queries (targeted).
    _run_query_batch(primary_queries)

    # 2) Interpret entity names (ICE, Minnesota) — intentional, not headline bait.
    if attached < attach_limit and entity_queries:
        _run_query_batch(entity_queries)

    # 3) If interpret brief existed and nothing theme-gated through → fail thin.
    #    Do not backfill from leftover capital tokens or raw idea ILIKE.
    if interpret and search_queries and attached == 0:
        thin_reason = "assemble_no_on_theme_hits"
        try:
            from services.editorial_package_service import close_package_thin

            close_package_thin(
                package_id,
                actor=actor,
                rationale=(
                    "Research assemble: interpret search queries returned no "
                    "on-theme attachable hits; refusing headline-token backfill"
                ),
                reason=thin_reason,
                from_modal=modal,
            )
        except Exception as exc:
            logger.warning("assemble thin close failed package=%s: %s", package_id, exc)
        package = get_package(package_id, include=True) or {}
        return {
            "ok": True,
            "thin": True,
            "package_id": package_id,
            "story_id": None,
            "created": created,
            "domain_key": primary_dk,
            "target_modal": modal,
            "status": package.get("status") or "closed_thin",
            "working_title": package.get("working_title") or working_title,
            "research_question": research_question,
            "interpret": interpret,
            "mentions": mentions,
            "entities_resolved": resolved,
            "seed_entity": seed_entity,
            "search_queries": search_queries,
            "member_count": 0,
            "claimish_count": 0,
            "spine": {"attached_search_hits": 0, "thin_reason": thin_reason},
            "draft_sections": {},
            "brief_md": "",
            "next": {
                "story_url_hint": None,
                "package_url_hint": f"/{primary_dk}/editor/packages/{package_id}",
                "get_package": f"GET /api/editorial/packages/{package_id}",
            },
        }

    # 4) Mentions: top-up only when we already have on-theme spine; OR primary
    #    attach path when there was no interpret search-query brief.
    has_interpret_queries = bool(interpret and search_queries)
    if attached < attach_limit and mention_queries and (
        attached > 0 or not has_interpret_queries
    ):
        _run_query_batch(
            [
                q
                for q in mention_queries
                if q.lower() not in {x.lower() for x in entity_queries}
            ]
        )

    # Direct article title ILIKE from interpret queries / idea keywords.
    # Only when we already have some on-theme members (avoid OR-token spam).
    if attached > 0 and attached < attach_limit and primary_dk:
        try:
            from shared.database.connection import get_db_connection_context
            from shared.domain_registry import resolve_domain_schema

            schema = resolve_domain_schema(primary_dk)
            like_terms: list[str] = []
            for q in search_queries[:6]:
                for tok in re.findall(r"[A-Za-z][A-Za-z\-]{3,}", q):
                    if tok.lower() not in _STOP and tok.lower() not in {
                        t.lower() for t in like_terms
                    }:
                        like_terms.append(tok)
                    if len(like_terms) >= 6:
                        break
                if len(like_terms) >= 6:
                    break
            if schema and like_terms:
                with get_db_connection_context() as conn:
                    with conn.cursor() as cur:
                        clauses = " OR ".join(["a.title ILIKE %s"] * len(like_terms))
                        params = [f"%{t}%" for t in like_terms] + [
                            max(5, attach_limit - attached)
                        ]
                        cur.execute(
                            f"""
                            SELECT a.id, a.title, a.url
                            FROM {schema}.articles a
                            WHERE ({clauses})
                            ORDER BY COALESCE(a.published_at, a.created_at) DESC NULLS LAST
                            LIMIT %s
                            """,
                            params,
                        )
                        art_hits = []
                        for aid, title, url in cur.fetchall() or []:
                            title_l = (title or "").lower()
                            if any(x and x in title_l for x in exclusions):
                                continue
                            key = ("article", int(aid))
                            if key in seen_hits:
                                continue
                            seen_hits.add(key)
                            art_hits.append(
                                {
                                    "member_family": "narrative"
                                    if modal == "narrative"
                                    else "research",
                                    "member_type": "article",
                                    "member_id": int(aid),
                                    "domain_key": primary_dk,
                                    "label": (title or "")[:240],
                                    "role": "supporting",
                                    "provenance": {
                                        "label": (title or "")[:240],
                                        "source_url": url,
                                    },
                                }
                            )
                        if art_hits:
                            added = attach_search_hits(
                                package_id, art_hits, modal=modal, actor=actor
                            )
                            attached += len(added)
        except Exception as exc:
            logger.debug("direct article attach: %s", exc)

    spine_stats: dict[str, Any] = {"attached_search_hits": attached}
    if run_spine and modal == "research":
        try:
            import asyncio

            from services.editorial_package_research_service import run_research_spine

            pkg_for_spine = get_package(package_id, include=True) or {}

            async def _spine() -> dict[str, Any]:
                return await run_research_spine(pkg_for_spine)

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None
            if loop and loop.is_running():
                spine_stats["spine"] = {"skipped": "running_loop"}
            else:
                spine_stats["spine"] = asyncio.run(_spine())
        except Exception as exc:
            spine_stats["spine_error"] = str(exc)[:200]

    package = get_package(package_id, include=True) or {}
    sections = _draft_sections(package, idea=research_question or text)
    if interpret:
        # Prefaces draft with interpreted brief so the operator sees the expansion.
        why = list(sections["why_this_matters"])
        for a in (interpret.get("key_assumptions") or [])[:4]:
            why.append(f"Assumption: {a}")
        for f in (interpret.get("facts_to_verify") or [])[:4]:
            why.append(f"Verify: {f}")
        watch = list(sections["what_to_watch"])
        for q in (interpret.get("open_questions") or [])[:4]:
            watch.append(q)
        if interpret.get("time_scope"):
            why.insert(0, f"Time scope: {interpret['time_scope']}")
        sections["why_this_matters"] = why
        sections["what_to_watch"] = watch

        def _bullets(items: list[str]) -> str:
            return "\n".join(f"- {x}" for x in items)

        sections["brief_md"] = (
            f"## What's new\n{_bullets(sections['whats_new'])}\n\n"
            f"## Why this matters\n{_bullets(why)}\n\n"
            f"## Timeline\n{_bullets(sections['timeline'])}\n\n"
            f"## What to watch\n{_bullets(watch)}\n"
        )

    try:
        get_or_create_brief(package_id, actor=actor)
        update_brief(
            package_id,
            brief_md=sections["brief_md"],
            lede=research_question[:280],
            open_questions=list(sections["what_to_watch"]),
            status="draft",
            actor=actor,
            metadata_patch={
                "source": "research_assemble",
                "interpret_source": (interpret or {}).get("source"),
            },
        )
    except Exception as exc:
        logger.debug("brief write: %s", exc)

    story_meta = _seed_readable_draft_story(
        package_id,
        title=str(package.get("working_title") or working_title or "Research draft"),
        lede=research_question[:280],
        body_md=str(sections.get("brief_md") or ""),
        actor=actor,
    )

    members = [m for m in (package.get("members") or []) if m.get("status") in (None, "active")]
    claimish = sum(
        1
        for m in members
        if str(m.get("member_type") or "")
        in ("extracted_claim", "versioned_fact", "claim_evidence_appraisal", "hypothesis")
    )
    story_id = story_meta.get("story_id")
    return {
        "ok": True,
        "package_id": package_id,
        "story_id": story_id,
        "created": created,
        "domain_key": primary_dk,
        "target_modal": modal,
        "status": package.get("status") or create_status,
        "working_title": package.get("working_title") or working_title,
        "research_question": research_question,
        "interpret": interpret,
        "mentions": mentions,
        "entities_resolved": resolved,
        "seed_entity": seed_entity,
        "search_queries": search_queries,
        "member_count": len(members),
        "claimish_count": claimish,
        "spine": spine_stats,
        "draft_sections": {
            "whats_new": sections["whats_new"],
            "why_this_matters": sections["why_this_matters"],
            "timeline": sections["timeline"],
            "what_to_watch": sections["what_to_watch"],
        },
        "brief_md": sections["brief_md"],
        "next": {
            "story_url_hint": (
                f"/{primary_dk}/editor/stories/{story_id}" if story_id else None
            ),
            "package_url_hint": f"/{primary_dk}/editor/packages/{package_id}",
            "research_run": f"POST /api/editorial/packages/{package_id}/research/run",
            "get_package": f"GET /api/editorial/packages/{package_id}",
        },
    }


async def assemble_from_idea_async(
    idea: str,
    *,
    domain_key: str | None = None,
    actor: str = "research_assemble",
    attach_limit: int = 30,
    run_spine: bool = True,
    dry_run: bool = False,
    interpret: bool = True,
) -> dict[str, Any]:
    """Async assemble: optional LLM interpret → retrieve/attach → optional research spine."""
    brief: dict[str, Any] | None = None
    if interpret:
        brief = await interpret_research_idea(idea, domain_key=domain_key)

    result = assemble_from_idea(
        idea,
        domain_key=domain_key,
        actor=actor,
        attach_limit=attach_limit,
        run_spine=False,
        dry_run=dry_run,
        brief=brief,
    )
    if dry_run or not result.get("ok") or not run_spine:
        return result
    if result.get("target_modal") != "research":
        return result
    package_id = int(result["package_id"])
    try:
        from services.editorial_package_research_service import run_research_spine
        from services.editorial_package_service import get_package

        pkg = get_package(package_id, include=True) or {}
        spine = await run_research_spine(pkg)
        result.setdefault("spine", {})["spine"] = spine
        package = get_package(package_id, include=True) or {}
        question = str(result.get("research_question") or idea)
        sections = _draft_sections(package, idea=question)
        result["draft_sections"] = {
            "whats_new": sections["whats_new"],
            "why_this_matters": sections["why_this_matters"],
            "timeline": sections["timeline"],
            "what_to_watch": sections["what_to_watch"],
        }
        result["brief_md"] = sections["brief_md"]
        result["member_count"] = len(
            [m for m in (package.get("members") or []) if m.get("status") in (None, "active")]
        )
        try:
            from services.package_evidence_brief_service import update_brief

            update_brief(
                package_id,
                brief_md=sections["brief_md"],
                lede=question[:280],
                open_questions=list(sections["what_to_watch"]),
                status="draft",
                actor=actor,
            )
        except Exception:
            pass
        story_meta = _seed_readable_draft_story(
            package_id,
            title=str(result.get("working_title") or "Research draft"),
            lede=question[:280],
            body_md=str(sections.get("brief_md") or ""),
            actor=actor,
        )
        if story_meta.get("story_id"):
            result["story_id"] = story_meta["story_id"]
            next_hints = result.setdefault("next", {})
            if isinstance(next_hints, dict):
                dk = str(result.get("domain_key") or "politics")
                next_hints["story_url_hint"] = f"/{dk}/editor/stories/{story_meta['story_id']}"
                next_hints["package_url_hint"] = f"/{dk}/editor/packages/{package_id}"
    except Exception as exc:
        result.setdefault("spine", {})["spine_error"] = str(exc)[:200]
    return result
