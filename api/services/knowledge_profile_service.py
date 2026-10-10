"""
Knowledge profiles — entity-keyed research product (v11).

Standing is/is-not ledger + cited scientific report for medicine,
neurodiversity, and artificial-intelligence. Fed by entity-seeded Research
packages; auto-merge after research pass (no Reduction/Editor gate).
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from shared.database.connection import get_ui_db_connection_context
from shared.domain_registry import resolve_domain_schema
from shared.editorial_package_vocab import provenance_has_citeable_source
from shared.evidence_grade import normalize_evidence_grade

logger = logging.getLogger(__name__)

KNOWLEDGE_PROFILE_DOMAINS = frozenset(
    {"medicine", "neurodiversity", "artificial-intelligence"}
)

_IS_VERDICTS = frozenset({"proved", "substantiated"})
_IS_NOT_VERDICTS = frozenset({"disproved"})
_OPEN_VERDICTS = frozenset({"inconclusive", "not_applicable", "needs_follow_up"})
# Promote to is/is-not only at limited+ (exclude preliminary / unsubstantiated)
_GRADE_FLOOR = frozenset({"strong", "moderate", "limited"})

PROMPT_VERSION = "package_knowledge_profile.v1"
PROMPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "config"
    / "prompts"
    / "research"
    / "package_knowledge_profile.md"
)

_JSON_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _jsonb(val: Any) -> str:
    return json.dumps(val if val is not None else {})


def _row(cur) -> dict[str, Any] | None:
    r = cur.fetchone()
    if r is None:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, r))


def _rows(cur) -> list[dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def legacy_seed_for_entity(domain_key: str, canonical_entity_id: int) -> str:
    return f"entity:{(domain_key or '').strip()}:{int(canonical_entity_id)}"


def parse_entity_legacy_seed(seed: str) -> tuple[str, int] | None:
    s = (seed or "").strip()
    if not s.startswith("entity:"):
        return None
    parts = s.split(":")
    if len(parts) < 3:
        return None
    try:
        return parts[1].strip(), int(parts[2])
    except (TypeError, ValueError):
        return None


def get_or_create_profile(
    domain_key: str,
    canonical_entity_id: int,
    *,
    title: str | None = None,
    entity_profile_id: int | None = None,
    package_id: int | None = None,
    actor: str = "system",
) -> dict[str, Any]:
    dk = (domain_key or "").strip()
    if dk not in KNOWLEDGE_PROFILE_DOMAINS:
        raise ValueError(f"domain_key not allowed for knowledge profiles: {dk}")
    eid = int(canonical_entity_id)
    seed = legacy_seed_for_entity(dk, eid)
    display = (title or "").strip() or f"Entity {eid}"

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM intelligence.knowledge_profiles
                WHERE domain_key = %s AND canonical_entity_id = %s
                """,
                (dk, eid),
            )
            existing = _row(cur)
            if existing:
                if package_id and not existing.get("package_id"):
                    cur.execute(
                        """
                        UPDATE intelligence.knowledge_profiles
                        SET package_id = %s, updated_at = NOW()
                        WHERE id = %s
                        RETURNING *
                        """,
                        (int(package_id), int(existing["id"])),
                    )
                    existing = _row(cur) or existing
                    conn.commit()
                return existing

            cur.execute(
                """
                INSERT INTO intelligence.knowledge_profiles (
                    domain_key, canonical_entity_id, entity_profile_id,
                    title, status, package_id, created_by, metadata
                ) VALUES (
                    %s, %s, %s, %s, 'draft', %s, %s, %s::jsonb
                )
                ON CONFLICT (domain_key, canonical_entity_id) DO UPDATE SET
                    updated_at = NOW()
                RETURNING *
                """,
                (
                    dk,
                    eid,
                    entity_profile_id,
                    display[:500],
                    package_id,
                    actor,
                    _jsonb(
                        {
                            "legacy_seed": seed,
                            "source_domain_key": dk,
                            "source_canonical_entity_id": eid,
                        }
                    ),
                ),
            )
            row = _row(cur)
            conn.commit()
            assert row is not None
            return row


def get_profile(
    profile_id: int | None = None,
    *,
    domain_key: str | None = None,
    canonical_entity_id: int | None = None,
    include_citations: bool = True,
) -> dict[str, Any] | None:
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            if profile_id is not None:
                cur.execute(
                    "SELECT * FROM intelligence.knowledge_profiles WHERE id = %s",
                    (int(profile_id),),
                )
            elif domain_key and canonical_entity_id is not None:
                cur.execute(
                    """
                    SELECT * FROM intelligence.knowledge_profiles
                    WHERE domain_key = %s AND canonical_entity_id = %s
                    """,
                    (domain_key.strip(), int(canonical_entity_id)),
                )
            else:
                return None
            profile = _row(cur)
            if not profile:
                return None
            if include_citations:
                cur.execute(
                    """
                    SELECT * FROM intelligence.knowledge_profile_citations
                    WHERE profile_id = %s ORDER BY id
                    """,
                    (int(profile["id"]),),
                )
                profile["citations"] = _rows(cur)
            return profile


def list_profiles(
    *,
    domain_key: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    filters = ["1=1"]
    args: list[Any] = []
    if domain_key:
        filters.append("domain_key = %s")
        args.append(domain_key.strip())
    if status:
        filters.append("status = %s")
        args.append(status.strip())
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT * FROM intelligence.knowledge_profiles
                WHERE {" AND ".join(filters)}
                ORDER BY material_updated_at DESC, id DESC
                LIMIT %s
                """,
                [*args, max(1, min(int(limit), 200))],
            )
            return _rows(cur)


def _assertion_key(a: dict[str, Any]) -> str:
    aid = a.get("appraisal_id") or a.get("claim_id") or a.get("member_row_id")
    text = (a.get("text") or "").strip().lower()[:200]
    return f"{aid}:{text}"


def _normalize_assertion(raw: dict[str, Any], *, side: str) -> dict[str, Any] | None:
    text = (raw.get("text") or raw.get("finding_summary") or raw.get("hypothesis_text") or "").strip()
    if not text:
        return None
    verdict = (raw.get("verdict") or "inconclusive").strip().lower()
    grade = normalize_evidence_grade(raw.get("evidence_grade") or raw.get("evidence_strength"))
    if side in ("is", "is_not") and grade not in _GRADE_FLOOR:
        return None
    prov = raw.get("source_refs") if isinstance(raw.get("source_refs"), dict) else {}
    if not provenance_has_citeable_source(
        {
            "quote": raw.get("quote") or prov.get("quote"),
            "source_url": raw.get("source_url") or prov.get("source_url") or prov.get("url"),
            "label": text[:240],
        },
        for_publish=True,
    ):
        # Soft allow if we at least have a document/article id for operator follow-up
        if not (raw.get("document_id") or raw.get("article_id") or raw.get("source_url")):
            return None
    return {
        "claim_id": raw.get("claim_id"),
        "appraisal_id": raw.get("appraisal_id"),
        "member_row_id": raw.get("member_row_id"),
        "text": text[:2000],
        "verdict": verdict,
        "evidence_grade": grade or "unsubstantiated",
        "source_refs": {
            "source_url": raw.get("source_url") or prov.get("source_url") or prov.get("url"),
            "quote": (raw.get("quote") or prov.get("quote") or "")[:800] or None,
            "document_id": raw.get("document_id"),
            "article_id": raw.get("article_id"),
            "package_member_id": raw.get("member_row_id"),
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _merge_assertion_lists(
    existing: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    for a in existing or []:
        if isinstance(a, dict) and a.get("text"):
            by_key[_assertion_key(a)] = a
    for a in incoming or []:
        if not isinstance(a, dict):
            continue
        k = _assertion_key(a)
        prev = by_key.get(k)
        if prev:
            # Prefer stronger grade / later update
            by_key[k] = {**prev, **a}
        else:
            by_key[k] = a
    return list(by_key.values())


def _assertions_from_package_members(
    package: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    is_list: list[dict[str, Any]] = []
    is_not_list: list[dict[str, Any]] = []
    open_list: list[dict[str, Any]] = []

    for m in package.get("members") or []:
        if m.get("status") != "active":
            continue
        mt = m.get("member_type")
        prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
        mid = int(m["id"])
        base = {
            "member_row_id": mid,
            "text": (prov.get("label") or prov.get("quote") or "")[:2000],
            "quote": prov.get("quote"),
            "source_url": prov.get("source_url") or prov.get("url"),
            "document_id": prov.get("document_id") or (
                m.get("member_id") if mt == "processed_document" else None
            ),
            "article_id": prov.get("article_id") or (
                m.get("member_id") if mt == "article" else None
            ),
            "appraisal_id": m.get("member_id") if mt == "claim_evidence_appraisal" else None,
            "claim_id": m.get("member_id") if mt == "extracted_claim" else None,
            "evidence_grade": prov.get("evidence_grade") or prov.get("evidence_strength"),
            "verdict": (prov.get("verdict") or prov.get("replication_status") or "inconclusive"),
        }

        if mt == "claim_evidence_appraisal":
            # Load appraisal row for richer fields
            with get_ui_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, finding_text, hypothesis_text, evidence_grade,
                               replication_status, paper_support, document_id,
                               evidence_quotes, article_id, limitations_quote
                        FROM intelligence.claim_evidence_appraisal
                        WHERE id = %s
                        """,
                        (int(m["member_id"]),),
                    )
                    row = cur.fetchone()
                    if row:
                        base["appraisal_id"] = int(row[0])
                        base["text"] = (row[1] or row[2] or base["text"] or "")[:2000]
                        base["evidence_grade"] = row[3] or base["evidence_grade"]
                        base["verdict"] = _verdict_from_appraisal(
                            row[3], row[4], paper_support=row[5]
                        )
                        base["document_id"] = row[6]
                        base["article_id"] = row[8] or base.get("article_id")
                        quotes = row[7]
                        quote_s = _first_evidence_quote(quotes) or (row[9] or "")
                        if quote_s:
                            base["quote"] = str(quote_s)[:800]

        verdict = str(base.get("verdict") or "inconclusive").lower()
        if verdict in _IS_VERDICTS:
            side = "is"
        elif verdict in _IS_NOT_VERDICTS:
            side = "is_not"
        else:
            side = "open"

        norm = _normalize_assertion(base, side=side if side != "open" else "open")
        if not norm:
            # Park thin evidence as open question if we have text
            if base.get("text"):
                open_list.append(
                    {
                        **base,
                        "verdict": "inconclusive",
                        "text": base["text"],
                        "source_refs": {
                            "source_url": base.get("source_url"),
                            "quote": base.get("quote"),
                            "package_member_id": mid,
                        },
                    }
                )
            continue
        if side == "is":
            is_list.append(norm)
        elif side == "is_not":
            is_not_list.append(norm)
        else:
            open_list.append(norm)

    return is_list, is_not_list, open_list


def _first_evidence_quote(quotes: Any) -> str | None:
    if isinstance(quotes, list) and quotes:
        first = quotes[0]
        if isinstance(first, dict):
            return str(first.get("quote") or first.get("text") or "")[:800] or None
        return str(first)[:800] or None
    if isinstance(quotes, dict):
        return str(quotes.get("quote") or quotes.get("text") or "")[:800] or None
    if isinstance(quotes, str) and quotes.strip():
        return quotes.strip()[:800]
    return None


def _verdict_from_appraisal(
    evidence_grade: Any,
    replication_status: Any,
    *,
    paper_support: Any = None,
) -> str:
    grade = normalize_evidence_grade(evidence_grade) or ""
    repl = (str(replication_status or "")).strip().lower()
    support = (str(paper_support or "")).strip().lower()
    if repl == "contradicted" or support == "not_supported_by_own_evidence":
        return "disproved"
    if grade == "unsubstantiated" or support == "insufficient_reporting":
        return "inconclusive"
    if repl == "needs_follow_up":
        return "inconclusive"
    if grade == "strong" and support in (
        "supported_by_own_evidence",
        "partially_supported",
        "",
    ):
        return "proved"
    if grade in _GRADE_FLOOR and support != "not_supported_by_own_evidence":
        return "substantiated"
    return "inconclusive"


def build_deterministic_report(
    *,
    title: str,
    entity_name: str,
    is_assertions: list[dict[str, Any]],
    is_not_assertions: list[dict[str, Any]],
    open_questions: list[dict[str, Any]],
) -> str:
    lines: list[str] = [
        f"# {title or entity_name}",
        "",
        f"Standing research profile for **{entity_name}**. "
        "Assertions below are drawn only from package members with citeable provenance.",
        "",
        "## What it is (supported)",
        "",
    ]
    if is_assertions:
        for i, a in enumerate(is_assertions, 1):
            mid = a.get("member_row_id")
            marker = f" [@m{mid}]" if mid else ""
            lines.append(
                f"{i}. {a.get('text')} "
                f"_(verdict={a.get('verdict')}, grade={a.get('evidence_grade')})_{marker}"
            )
            lines.append("")
    else:
        lines.append("_No substantiated is-assertions yet._")
        lines.append("")

    lines.extend(["## What it is not (disproved or contradicted)", ""])
    if is_not_assertions:
        for i, a in enumerate(is_not_assertions, 1):
            mid = a.get("member_row_id")
            marker = f" [@m{mid}]" if mid else ""
            lines.append(
                f"{i}. {a.get('text')} "
                f"_(verdict={a.get('verdict')}, grade={a.get('evidence_grade')})_{marker}"
            )
            lines.append("")
    else:
        lines.append("_No disproved assertions yet._")
        lines.append("")

    lines.extend(["## Open questions", ""])
    if open_questions:
        for i, a in enumerate(open_questions[:20], 1):
            mid = a.get("member_row_id")
            marker = f" [@m{mid}]" if mid else ""
            lines.append(f"{i}. {a.get('text')}{marker}")
            lines.append("")
    else:
        lines.append("_No open questions parked._")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def regenerate_report_md(
    profile_id: int,
    *,
    entity_name: str | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Rebuild body_md from assertions. LLM optional; always falls back to deterministic."""
    profile = get_profile(profile_id)
    if not profile:
        raise LookupError(f"Profile {profile_id} not found")

    is_a = list(profile.get("is_assertions") or [])
    is_not = list(profile.get("is_not_assertions") or [])
    open_q = list(profile.get("open_questions") or [])
    name = entity_name or profile.get("title") or f"Entity {profile.get('canonical_entity_id')}"
    body = build_deterministic_report(
        title=str(profile.get("title") or name),
        entity_name=str(name),
        is_assertions=is_a,
        is_not_assertions=is_not,
        open_questions=open_q,
    )
    used_llm = False

    if use_llm and (is_a or is_not or open_q):
        try:
            body_llm = _llm_synthesize_report(profile, entity_name=str(name))
            if body_llm and len(body_llm.strip()) > 80:
                body = body_llm.strip() + "\n"
                used_llm = True
        except Exception as e:
            logger.warning("knowledge profile LLM regenerate failed: %s", e)

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.knowledge_profiles
                SET body_md = %s,
                    material_updated_at = NOW(),
                    updated_at = NOW(),
                    readiness = COALESCE(readiness, '{}'::jsonb)
                        || %s::jsonb
                WHERE id = %s
                RETURNING *
                """,
                (
                    body,
                    _jsonb(
                        {
                            "report_prompt_version": PROMPT_VERSION if used_llm else "deterministic",
                            "assertion_counts": {
                                "is": len(is_a),
                                "is_not": len(is_not),
                                "open": len(open_q),
                            },
                        }
                    ),
                    int(profile_id),
                ),
            )
            updated = _row(cur)
            conn.commit()
    return {"profile": updated, "used_llm": used_llm, "body_len": len(body)}


def _llm_synthesize_report(profile: dict[str, Any], *, entity_name: str) -> str | None:
    import asyncio

    try:
        prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("knowledge profile prompt missing (%s); using bare input JSON", e)
        prompt_template = (
            "Write a standing research profile from the assertions only. "
            "Return JSON with body_md using ## What it is (supported), "
            "## What it is not (disproved or contradicted), ## Open questions. "
            "Do not invent findings or [@m…] markers."
        )
    payload = {
        "entity_name": entity_name,
        "title": profile.get("title"),
        "domain_key": profile.get("domain_key"),
        "is_assertions": profile.get("is_assertions") or [],
        "is_not_assertions": profile.get("is_not_assertions") or [],
        "open_questions": (profile.get("open_questions") or [])[:20],
    }
    user = (
        f"{prompt_template}\n\n## Input JSON\n\n```json\n"
        f"{json.dumps(payload, default=str)[:12000]}\n```\n"
    )

    async def _run() -> str | None:
        from shared.services.ollama_model_caller import get_ollama_model_caller
        from shared.services.ollama_model_policy import InvocationKind

        caller = get_ollama_model_caller()
        result = await caller.generate(
            user,
            kind=InvocationKind.STRUCTURED_EXTRACTION,
            urgency="standard",
            approx_prompt_chars=len(user),
        )
        return (result.text or "").strip() or None

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            raw = pool.submit(lambda: asyncio.run(_run())).result(timeout=180)
    else:
        raw = asyncio.run(_run())

    if not raw:
        return None
    text = str(raw).strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict) and data.get("body_md"):
            return str(data["body_md"])
    except json.JSONDecodeError:
        if text.startswith("#") or "What it is" in text:
            return text
    return None


def _sync_ledger_from_assertions(
    *,
    domain_key: str,
    canonical_entity_id: int,
    assertions: list[dict[str, Any]],
    side: str,
) -> int:
    from services.research_subject_ledger_service import upsert_research_claim

    n = 0
    for a in assertions:
        verdict = (a.get("verdict") or "inconclusive").lower()
        if side == "is" and verdict not in _IS_VERDICTS:
            verdict = "substantiated"
        if side == "is_not":
            verdict = "disproved"
        if side == "open" and verdict not in _OPEN_VERDICTS:
            verdict = "inconclusive"
        refs = a.get("source_refs") if isinstance(a.get("source_refs"), dict) else {}
        try:
            upsert_research_claim(
                domain_key=domain_key,
                canonical_entity_id=int(canonical_entity_id),
                hypothesis_text=a.get("text"),
                finding_summary=a.get("text"),
                verdict=verdict,
                article_id=refs.get("article_id") or a.get("article_id"),
                document_id=refs.get("document_id") or a.get("document_id"),
                evidence_strength=a.get("evidence_grade"),
                metadata={
                    "knowledge_profile_side": side,
                    "appraisal_id": a.get("appraisal_id"),
                    "member_row_id": a.get("member_row_id"),
                    "source_url": refs.get("source_url"),
                },
            )
            n += 1
        except Exception as e:
            logger.debug("ledger upsert skip: %s", e)
    return n


def _replace_citations(
    cur,
    *,
    profile_id: int,
    package: dict[str, Any] | None,
    body_md: str,
) -> int:
    cur.execute(
        "DELETE FROM intelligence.knowledge_profile_citations WHERE profile_id = %s",
        (int(profile_id),),
    )
    if not package:
        return 0
    members = {
        int(m["id"]): m
        for m in (package.get("members") or [])
        if m.get("status") == "active"
    }
    markers = [int(x) for x in re.findall(r"\[@m(\d+)\]", body_md or "")]
    n = 0
    for mid in markers:
        m = members.get(mid)
        if not m:
            continue
        prov = m.get("provenance") if isinstance(m.get("provenance"), dict) else {}
        cur.execute(
            """
            INSERT INTO intelligence.knowledge_profile_citations (
                profile_id, package_member_id, citation_marker,
                source_table, source_row_id, source_url, quote
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                int(profile_id),
                mid,
                f"[@m{mid}]",
                m.get("member_type"),
                m.get("member_id"),
                prov.get("source_url") or prov.get("url"),
                (prov.get("quote") or "")[:800] or None,
            ),
        )
        n += 1
    return n


def auto_merge_from_package(
    package_id: int,
    *,
    actor: str = "research_llm",
    publish: bool = True,
    regenerate: bool = True,
) -> dict[str, Any]:
    """
    Merge research package members into the standing knowledge_profile for the
    entity seed on the package. Keeps published status when already published.
    """
    from services.editorial_package_service import get_package

    pkg = get_package(int(package_id))
    if not pkg:
        return {"skipped": True, "reason": "package_missing", "package_id": package_id}

    meta = pkg.get("metadata") if isinstance(pkg.get("metadata"), dict) else {}
    seed = str(meta.get("legacy_seed") or "")
    parsed = parse_entity_legacy_seed(seed)
    if not parsed:
        return {
            "skipped": True,
            "reason": "not_entity_seeded_package",
            "package_id": package_id,
            "legacy_seed": seed or None,
        }

    domain_key, entity_id = parsed
    if domain_key not in KNOWLEDGE_PROFILE_DOMAINS:
        return {"skipped": True, "reason": "domain_not_allowed", "domain_key": domain_key}

    entity_name = _resolve_entity_name(domain_key, entity_id) or pkg.get("working_title") or f"Entity {entity_id}"
    profile = get_or_create_profile(
        domain_key,
        entity_id,
        title=str(entity_name),
        package_id=int(package_id),
        actor=actor,
    )

    new_is, new_is_not, new_open = _assertions_from_package_members(pkg)
    merged_is = _merge_assertion_lists(list(profile.get("is_assertions") or []), new_is)
    merged_is_not = _merge_assertion_lists(list(profile.get("is_not_assertions") or []), new_is_not)
    merged_open = _merge_assertion_lists(list(profile.get("open_questions") or []), new_open)

    # Drop from open if promoted to is/is-not
    is_keys = {_assertion_key(a) for a in merged_is}
    is_not_keys = {_assertion_key(a) for a in merged_is_not}
    merged_open = [
        a for a in merged_open if _assertion_key(a) not in is_keys and _assertion_key(a) not in is_not_keys
    ]

    was_published = (profile.get("status") or "") == "published"
    new_status = "published" if (publish or was_published) else (profile.get("status") or "draft")

    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.knowledge_profiles
                SET title = COALESCE(NULLIF(%s, ''), title),
                    is_assertions = %s::jsonb,
                    is_not_assertions = %s::jsonb,
                    open_questions = %s::jsonb,
                    package_id = %s,
                    status = %s,
                    published_at = CASE
                        WHEN %s = 'published' AND published_at IS NULL THEN NOW()
                        WHEN %s = 'published' THEN NOW()
                        ELSE published_at
                    END,
                    material_updated_at = NOW(),
                    updated_at = NOW(),
                    readiness = COALESCE(readiness, '{}'::jsonb) || %s::jsonb
                WHERE id = %s
                RETURNING *
                """,
                (
                    str(entity_name)[:500],
                    _jsonb(merged_is),
                    _jsonb(merged_is_not),
                    _jsonb(merged_open),
                    int(package_id),
                    new_status,
                    new_status,
                    new_status,
                    _jsonb(
                        {
                            "last_merge_actor": actor,
                            "last_merge_package_id": int(package_id),
                            "assertion_counts": {
                                "is": len(merged_is),
                                "is_not": len(merged_is_not),
                                "open": len(merged_open),
                            },
                        }
                    ),
                    int(profile["id"]),
                ),
            )
            updated = _row(cur)
            assert updated is not None
            cur.execute(
                """
                INSERT INTO intelligence.knowledge_profile_revisions (
                    profile_id, title, body_md, is_assertions, is_not_assertions,
                    open_questions, editor_actor, model_prompt_version, metadata
                ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb)
                """,
                (
                    int(updated["id"]),
                    updated.get("title"),
                    updated.get("body_md") or "",
                    _jsonb(merged_is),
                    _jsonb(merged_is_not),
                    _jsonb(merged_open),
                    actor,
                    PROMPT_VERSION,
                    _jsonb({"auto_merge": True, "package_id": int(package_id)}),
                ),
            )
            conn.commit()

    if regenerate:
        regen = regenerate_report_md(
            int(updated["id"]),
            entity_name=str(entity_name),
            use_llm=False,  # deterministic by default in merge path; operator can force LLM
        )
        updated = regen.get("profile") or updated
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                _replace_citations(
                    cur,
                    profile_id=int(updated["id"]),
                    package=pkg,
                    body_md=str(updated.get("body_md") or ""),
                )
                conn.commit()

    ledger_n = 0
    ledger_n += _sync_ledger_from_assertions(
        domain_key=domain_key,
        canonical_entity_id=entity_id,
        assertions=new_is,
        side="is",
    )
    ledger_n += _sync_ledger_from_assertions(
        domain_key=domain_key,
        canonical_entity_id=entity_id,
        assertions=new_is_not,
        side="is_not",
    )

    return {
        "skipped": False,
        "profile_id": int(updated["id"]),
        "package_id": int(package_id),
        "domain_key": domain_key,
        "canonical_entity_id": entity_id,
        "status": updated.get("status"),
        "counts": {
            "is": len(merged_is),
            "is_not": len(merged_is_not),
            "open": len(merged_open),
            "ledger_upserts": ledger_n,
            "added_is": len(new_is),
            "added_is_not": len(new_is_not),
            "added_open": len(new_open),
        },
        "profile": get_profile(int(updated["id"])),
    }


def _domain_fallback_subjects() -> dict[str, list[str]]:
    try:
        from services.research_subject_topics import domain_fallback_subjects

        return domain_fallback_subjects()
    except Exception:
        return {
            "neurodiversity": ["Autism", "ADHD", "AuDHD", "Neurodiversity"],
            "artificial-intelligence": [
                "Artificial Intelligence",
                "Large Language Models",
                "Computer Vision",
                "AI Alignment",
                "Robotics",
            ],
            "medicine": ["Clinical Trials", "Epidemiology"],
        }


# Kept as module-level name for importers (research_subjects route).
_DOMAIN_FALLBACK_SUBJECTS = _domain_fallback_subjects()


# Curated-board aliases used when matching papers → standing subjects.
# Keep in sync with seed_world_entities.yaml subject aliases where practical.
_SUBJECT_MATCH_ALIASES: dict[str, tuple[str, ...]] = {
    "Autism": (
        "autism",
        "asd",
        "autistic",
        "autism spectrum",
        "autism spectrum disorder",
    ),
    "ADHD": (
        "adhd",
        "attention deficit",
        "attention-deficit",
        "attention deficit hyperactivity",
    ),
    "AuDHD": ("audhd", "autism-adhd", "autism and adhd", "autism adhd"),
    "Neurodiversity": ("neurodiversity", "neurodivergent", "neurodivergence"),
    "Artificial Intelligence": (
        "artificial intelligence",
        "machine learning",
        "deep learning",
    ),
    "Large Language Models": (
        "large language model",
        "llm",
        "llms",
        "foundation model",
        "language model",
    ),
    "Computer Vision": (
        "computer vision",
        "image recognition",
        "object detection",
        "visual language",
        "vision-language",
        "vlm",
    ),
    "AI Alignment": ("alignment", "ai safety", "ai alignment", "rlhf"),
    "Robotics": ("robot", "robotics", "embodied"),
    "Clinical Trials": (
        "clinical trial",
        "randomized",
        "rct",
        "phase 1",
        "phase 2",
        "phase 3",
        "nct",
    ),
    "Epidemiology": ("epidemiolog", "incidence", "prevalence", "cohort study"),
    "Oncology": ("oncolog", "cancer", "tumor", "tumour", "carcinoma", "melanoma"),
    "Infectious Disease": (
        "infectious",
        "pathogen",
        "virus",
        "bacterial",
        "antimicrobial",
        "vaccine",
    ),
    "Public Health": ("public health", "population health", "health policy"),
    "Genomics": ("genomic", "genome", "exome", "gwas", "variant", "sequenc"),
}


def _haystack_for_subject_match(
    *,
    domain_key: str,
    appraisal: dict[str, Any],
    article_id: int | None,
    names: list[str],
) -> str:
    """Build a lowercase match blob from subjects + title + appraisal text."""
    parts: list[str] = list(names)
    meta = appraisal.get("metadata") if isinstance(appraisal.get("metadata"), dict) else {}
    for key in ("title", "document_title", "paper_title"):
        t = meta.get(key)
        if t:
            parts.append(str(t))
    for key in ("finding_text", "hypothesis_text"):
        t = appraisal.get(key)
        if t:
            parts.append(str(t)[:400])
    if article_id is not None:
        try:
            from shared.domain_registry import resolve_domain_schema

            schema = resolve_domain_schema(domain_key)
            with get_ui_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT title FROM {schema}.articles WHERE id = %s
                        """,
                        (int(article_id),),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        parts.append(str(row[0]))
                    cur.execute(
                        """
                        SELECT subjects_studied, research_question
                        FROM intelligence.research_paper_profiles
                        WHERE domain_key = %s AND article_id = %s
                        """,
                        (domain_key, int(article_id)),
                    )
                    prow = cur.fetchone()
                    if prow:
                        subjects = prow[0]
                        if isinstance(subjects, str):
                            try:
                                subjects = json.loads(subjects)
                            except json.JSONDecodeError:
                                subjects = []
                        if isinstance(subjects, list):
                            parts.extend(str(x) for x in subjects if x)
                        if prow[1]:
                            parts.append(str(prow[1])[:300])
        except Exception as e:
            logger.debug("subject match haystack load failed: %s", e)
    return " ".join(parts).lower()


def _curated_subject_matches(domain_key: str, haystack: str) -> list[str]:
    """Return curated board titles that match haystack (aliases + substring)."""
    if not haystack.strip():
        return []
    curated = _domain_fallback_subjects().get(domain_key) or []
    preferred: list[str] = []
    for fb in curated:
        aliases = _SUBJECT_MATCH_ALIASES.get(fb) or (fb.lower(),)
        tokens = tuple(dict.fromkeys((fb.lower(),) + tuple(aliases)))
        if any(tok and tok in haystack for tok in tokens):
            preferred.append(fb)
    # AuDHD only if both autism-ish and adhd-ish when explicit alias missed
    if (
        "AuDHD" in curated
        and "AuDHD" not in preferred
        and any(t in haystack for t in ("autism", "asd", "autistic"))
        and any(t in haystack for t in ("adhd", "attention deficit"))
    ):
        preferred.append("AuDHD")
    return preferred[:3]


def _subject_names_from_appraisal_and_profile(
    *,
    domain_key: str,
    appraisal: dict[str, Any],
    article_id: int | None,
) -> list[str]:
    names: list[str] = []
    meta = appraisal.get("metadata") if isinstance(appraisal.get("metadata"), dict) else {}
    for key in ("subjects", "subjects_studied", "entities"):
        raw = meta.get(key) or appraisal.get(key)
        if isinstance(raw, list):
            names.extend(str(x).strip() for x in raw if str(x).strip())
        elif isinstance(raw, str) and raw.strip():
            names.append(raw.strip())

    if article_id is not None:
        try:
            with get_ui_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT subjects_studied
                        FROM intelligence.research_paper_profiles
                        WHERE domain_key = %s AND article_id = %s
                        """,
                        (domain_key, int(article_id)),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        subjects = row[0]
                        if isinstance(subjects, str):
                            try:
                                subjects = json.loads(subjects)
                            except json.JSONDecodeError:
                                subjects = []
                        if isinstance(subjects, list):
                            names.extend(str(x).strip() for x in subjects if str(x).strip())
        except Exception as e:
            logger.debug("subjects_studied load failed: %s", e)

    # Match curated standing boards via subjects + title + aliases.
    # Do **not** fall back to the domain's first board (Autism / Artificial
    # Intelligence) — that polluted boards with off-topic appraisals.
    haystack = _haystack_for_subject_match(
        domain_key=domain_key,
        appraisal=appraisal,
        article_id=article_id,
        names=names,
    )
    preferred = _curated_subject_matches(domain_key, haystack)
    if preferred:
        return preferred
    return []


def _resolve_subject_entity_ids(domain_key: str, names: list[str]) -> list[tuple[int, str]]:
    from services.entity_resolution_service import resolve_to_canonical

    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    for name in names:
        eid = resolve_to_canonical(
            domain_key, name, "subject", create_if_missing=True
        )
        if eid is None or eid in seen:
            continue
        seen.add(int(eid))
        out.append((int(eid), name))
    return out


def _assertions_from_appraisal_row(
    appraisal: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    finding = (appraisal.get("finding_text") or "").strip()
    hypothesis = (appraisal.get("hypothesis_text") or "").strip()
    text = finding or hypothesis
    if not text:
        return [], [], []

    verdict = _verdict_from_appraisal(
        appraisal.get("evidence_grade"),
        appraisal.get("replication_status"),
        paper_support=appraisal.get("paper_support"),
    )
    quote = _first_evidence_quote(appraisal.get("evidence_quotes")) or (
        (appraisal.get("limitations_quote") or "")[:800] or None
    )
    base = {
        "appraisal_id": int(appraisal["id"]),
        "text": text[:2000],
        "quote": quote,
        "source_url": None,
        "document_id": appraisal.get("document_id"),
        "article_id": appraisal.get("article_id"),
        "evidence_grade": appraisal.get("evidence_grade"),
        "verdict": verdict,
    }
    # Enrich source_url from processed_documents when available
    if appraisal.get("document_id"):
        try:
            with get_ui_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT source_url FROM intelligence.processed_documents
                        WHERE id = %s
                        """,
                        (int(appraisal["document_id"]),),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        base["source_url"] = str(row[0])
        except Exception:
            pass

    is_list: list[dict[str, Any]] = []
    is_not_list: list[dict[str, Any]] = []
    open_list: list[dict[str, Any]] = []

    def _looks_like_open_question(s: str) -> bool:
        t = (s or "").strip().lower()
        if not t:
            return False
        if "?" in t:
            return True
        return t.startswith(
            (
                "whether ",
                "how ",
                "what ",
                "why ",
                "can ",
                "does ",
                "do ",
                "is ",
                "are ",
                "to what ",
                "under what ",
            )
        )

    if verdict in _IS_VERDICTS:
        norm = _normalize_assertion(base, side="is")
        if norm:
            is_list.append(norm)
        else:
            # Grade/provenance too weak for supported — keep as open once.
            open_list.append({**base, "verdict": "inconclusive"})
        # Only park a separate hypothesis when it is clearly an open question.
        if (
            hypothesis
            and hypothesis != text
            and _looks_like_open_question(hypothesis)
        ):
            open_list.append(
                {
                    **base,
                    "text": hypothesis[:2000],
                    "verdict": "inconclusive",
                    "appraisal_id": int(appraisal["id"]),
                }
            )
    elif verdict in _IS_NOT_VERDICTS:
        norm = _normalize_assertion(base, side="is_not")
        if norm:
            is_not_list.append(norm)
        else:
            open_list.append({**base, "verdict": "inconclusive"})
    else:
        # Inconclusive: one open row for the primary text. Add hypothesis only
        # when it reads as a distinct question (avoids doubling findings into Open).
        open_list.append({**base, "verdict": "inconclusive"})
        if (
            hypothesis
            and hypothesis != text
            and _looks_like_open_question(hypothesis)
        ):
            open_list.append(
                {
                    **base,
                    "text": hypothesis[:2000],
                    "verdict": "inconclusive",
                    "appraisal_id": int(appraisal["id"]),
                }
            )

    return is_list, is_not_list, open_list


def auto_merge_from_appraisal(
    appraisal_id: int,
    *,
    actor: str = "claim_evidence_appraisal",
    publish: bool = True,
) -> dict[str, Any]:
    """
    Merge one claim_evidence_appraisal row into entity-rooted knowledge_profiles
    and research_claim_ledger. Merges assertions; never wholesale-replaces arrays.
    """
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, domain_key, document_id, article_id,
                       finding_text, hypothesis_text, study_design,
                       peer_review_status, paper_support, replication_status,
                       evidence_grade, sample_size_text, reported_effect_text,
                       limitations_quote, evidence_quotes, metadata
                FROM intelligence.claim_evidence_appraisal
                WHERE id = %s
                """,
                (int(appraisal_id),),
            )
            row = _row(cur)
    if not row:
        return {"skipped": True, "reason": "appraisal_missing", "appraisal_id": appraisal_id}

    domain_key = (row.get("domain_key") or "").strip()
    if domain_key not in KNOWLEDGE_PROFILE_DOMAINS:
        return {
            "skipped": True,
            "reason": "domain_not_allowed",
            "domain_key": domain_key,
            "appraisal_id": appraisal_id,
        }

    meta = row.get("metadata")
    if isinstance(meta, str):
        try:
            row["metadata"] = json.loads(meta)
        except json.JSONDecodeError:
            row["metadata"] = {}
    elif not isinstance(meta, dict):
        row["metadata"] = {}

    new_is, new_is_not, new_open = _assertions_from_appraisal_row(row)
    if not (new_is or new_is_not or new_open):
        return {
            "skipped": True,
            "reason": "no_assertion_text",
            "appraisal_id": appraisal_id,
        }

    names = _subject_names_from_appraisal_and_profile(
        domain_key=domain_key,
        appraisal=row,
        article_id=row.get("article_id"),
    )
    entities = _resolve_subject_entity_ids(domain_key, names)
    if not entities:
        return {
            "skipped": True,
            "reason": "no_subject_entities",
            "appraisal_id": appraisal_id,
            "subject_names": names,
        }

    merges: list[dict[str, Any]] = []
    for entity_id, entity_name in entities:
        profile = get_or_create_profile(
            domain_key,
            entity_id,
            title=str(entity_name),
            actor=actor,
        )
        merged_is = _merge_assertion_lists(list(profile.get("is_assertions") or []), new_is)
        merged_is_not = _merge_assertion_lists(
            list(profile.get("is_not_assertions") or []), new_is_not
        )
        merged_open = _merge_assertion_lists(list(profile.get("open_questions") or []), new_open)
        is_keys = {_assertion_key(a) for a in merged_is}
        is_not_keys = {_assertion_key(a) for a in merged_is_not}
        merged_open = [
            a
            for a in merged_open
            if _assertion_key(a) not in is_keys and _assertion_key(a) not in is_not_keys
        ]

        was_published = (profile.get("status") or "") == "published"
        new_status = (
            "published" if (publish or was_published) else (profile.get("status") or "draft")
        )

        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE intelligence.knowledge_profiles
                    SET title = COALESCE(NULLIF(%s, ''), title),
                        is_assertions = %s::jsonb,
                        is_not_assertions = %s::jsonb,
                        open_questions = %s::jsonb,
                        status = %s,
                        published_at = CASE
                            WHEN %s = 'published' AND published_at IS NULL THEN NOW()
                            WHEN %s = 'published' THEN NOW()
                            ELSE published_at
                        END,
                        material_updated_at = NOW(),
                        updated_at = NOW(),
                        readiness = COALESCE(readiness, '{}'::jsonb) || %s::jsonb
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        str(entity_name)[:500],
                        _jsonb(merged_is),
                        _jsonb(merged_is_not),
                        _jsonb(merged_open),
                        new_status,
                        new_status,
                        new_status,
                        _jsonb(
                            {
                                "last_merge_actor": actor,
                                "last_merge_appraisal_id": int(appraisal_id),
                                "assertion_counts": {
                                    "is": len(merged_is),
                                    "is_not": len(merged_is_not),
                                    "open": len(merged_open),
                                },
                            }
                        ),
                        int(profile["id"]),
                    ),
                )
                updated = _row(cur)
                assert updated is not None
                cur.execute(
                    """
                    INSERT INTO intelligence.knowledge_profile_revisions (
                        profile_id, title, body_md, is_assertions, is_not_assertions,
                        open_questions, editor_actor, model_prompt_version, metadata
                    ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s, %s::jsonb)
                    """,
                    (
                        int(updated["id"]),
                        updated.get("title"),
                        updated.get("body_md") or "",
                        _jsonb(merged_is),
                        _jsonb(merged_is_not),
                        _jsonb(merged_open),
                        actor,
                        PROMPT_VERSION,
                        _jsonb({"auto_merge": True, "appraisal_id": int(appraisal_id)}),
                    ),
                )
                conn.commit()

        ledger_n = 0
        ledger_n += _sync_ledger_from_assertions(
            domain_key=domain_key,
            canonical_entity_id=entity_id,
            assertions=new_is,
            side="is",
        )
        ledger_n += _sync_ledger_from_assertions(
            domain_key=domain_key,
            canonical_entity_id=entity_id,
            assertions=new_is_not,
            side="is_not",
        )
        ledger_n += _sync_ledger_from_assertions(
            domain_key=domain_key,
            canonical_entity_id=entity_id,
            assertions=new_open,
            side="open",
        )
        merges.append(
            {
                "profile_id": int(updated["id"]),
                "canonical_entity_id": entity_id,
                "entity_name": entity_name,
                "status": new_status,
                "counts": {
                    "is": len(merged_is),
                    "is_not": len(merged_is_not),
                    "open": len(merged_open),
                    "ledger_upserts": ledger_n,
                },
            }
        )

    return {
        "skipped": False,
        "appraisal_id": int(appraisal_id),
        "domain_key": domain_key,
        "merges": merges,
        "subject_names": names,
    }


def publish_profile(profile_id: int, *, actor: str = "operator") -> dict[str, Any]:
    profile = get_profile(profile_id, include_citations=False)
    if not profile:
        raise LookupError(f"Profile {profile_id} not found")
    with get_ui_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE intelligence.knowledge_profiles
                SET status = 'published',
                    published_at = NOW(),
                    material_updated_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                RETURNING *
                """,
                (int(profile_id),),
            )
            row = _row(cur)
            cur.execute(
                """
                INSERT INTO intelligence.knowledge_profile_revisions (
                    profile_id, title, body_md, is_assertions, is_not_assertions,
                    open_questions, editor_actor, metadata
                ) VALUES (%s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s::jsonb)
                """,
                (
                    int(profile_id),
                    row.get("title") if row else None,
                    (row or {}).get("body_md") or "",
                    _jsonb((row or {}).get("is_assertions") or []),
                    _jsonb((row or {}).get("is_not_assertions") or []),
                    _jsonb((row or {}).get("open_questions") or []),
                    actor,
                    _jsonb({"action": "publish"}),
                ),
            )
            conn.commit()
    return {"published": True, "profile": get_profile(int(profile_id))}


def _resolve_entity_name(domain_key: str, canonical_entity_id: int) -> str | None:
    schema = resolve_domain_schema(domain_key)
    try:
        with get_ui_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT canonical_name FROM {schema}.entity_canonical
                    WHERE id = %s
                    """,
                    (int(canonical_entity_id),),
                )
                row = cur.fetchone()
                return str(row[0]) if row and row[0] else None
    except Exception:
        logger.debug("entity name resolve failed %s/%s", domain_key, canonical_entity_id, exc_info=True)
        return None
