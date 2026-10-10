"""
Morning vault priming: batch expansions + daily briefing for the reader web.

Web reads cached artifacts only. This job writes Obsidian + PG mirrors.
Feature: vault_morning_prime / NI_VAULT_MORNING_PRIME.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from typing import Any

from shared.database.connection import get_db_connection_context
from shared.vault_note_contract import (
    MAX_MORNING_NEWS_EXPANSIONS,
    MAX_MORNING_SCIENCE_EXPANSIONS,
    MORNING_BRIEF_ACTIVITY_DAYS,
    MORNING_DELTA_DAYS,
    SCIENCE_VAULT_DOMAINS,
    daily_briefing_object_id,
    daily_briefing_vault_rel_path,
    expansion_vault_rel_path,
    is_science_vault_domain,
    structural_tags_for_note,
)

logger = logging.getLogger(__name__)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

NEWS_DOMAINS_DEFAULT = ("politics", "finance")
SCIENCE_DOMAINS_DEFAULT = tuple(sorted(SCIENCE_VAULT_DOMAINS))



def vault_morning_prime_enabled() -> bool:
    raw = os.environ.get("NI_VAULT_MORNING_PRIME", "").strip().lower()
    if raw in ("0", "false", "no"):
        return False
    if raw in ("1", "true", "yes"):
        return True
    try:
        from config.feature_registry import is_feature_enabled

        return is_feature_enabled("vault_morning_prime", default=True)
    except Exception:
        return True


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _schema(domain_key: str) -> str:
    return domain_key.replace("-", "_")


def _expansion_async_timeout_s() -> float:
    """Thread-pool wait must exceed httpx OLLAMA_TIMEOUT or we abort mid-request."""
    try:
        from config.settings import OLLAMA_TIMEOUT

        base = float(OLLAMA_TIMEOUT)
    except Exception:
        base = 300.0
    try:
        override = float(os.environ.get("NI_VAULT_MORNING_EXPANSION_TIMEOUT", "").strip() or "0")
    except ValueError:
        override = 0.0
    return max(base + 60.0, override, 360.0)


def _run_async(coro):
    wait_s = _expansion_async_timeout_s()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(lambda: asyncio.run(coro)).result(timeout=wait_s)
    return asyncio.run(coro)


def _fingerprint(parts: list[str]) -> str:
    blob = "|".join(p or "" for p in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


def _dek_from_body(body: str, *, max_len: int = 280) -> str:
    """Plain-text standfirst for reader cards (StoryUnit renders dek as text, not MD)."""
    from shared.llm_text_sanitize import sanitize_reader_dek

    text = (body or "").strip()
    if not text:
        return ""
    # Prefer the first real update paragraph when the LLM opens with a banner title
    for marker in ("Here's today's update", "Here is today's update"):
        idx = text.find(marker)
        if idx >= 0:
            text = text[idx:]
            break
    return sanitize_reader_dek(text, max_length=max_len)


def scan_active_leads(
    *,
    delta_days: int = MORNING_BRIEF_ACTIVITY_DAYS,
    news_limit: int = MAX_MORNING_NEWS_EXPANSIONS,
    science_limit: int = MAX_MORNING_SCIENCE_EXPANSIONS,
) -> dict[str, list[dict[str, Any]]]:
    """Candidate pool: active-recent storylines (manager selects subset)."""
    since = datetime.now(timezone.utc) - timedelta(days=max(1, int(delta_days)))
    news: list[dict[str, Any]] = []
    science: list[dict[str, Any]] = []
    # Soft caps for candidate pool size (manager + concurrency), not hard product limit
    pool_news = max(news_limit * 3, 60)
    pool_science = max(science_limit * 3, 20)

    for domain_key in list(NEWS_DOMAINS_DEFAULT) + list(SCIENCE_DOMAINS_DEFAULT):
        schema = _schema(domain_key)
        try:
            with get_db_connection_context() as conn:
                with conn.cursor() as cur:
                    cur.execute("SET LOCAL statement_timeout = '15000'")
                    cur.execute(
                        f"""
                        SELECT s.id, s.title, COALESCE(s.article_count, 0)::int,
                               s.updated_at, lead.article_id AS lead_article_id,
                               s.created_at,
                               EXISTS (
                                 SELECT 1 FROM intelligence.vault_notes vn
                                 WHERE vn.domain_key = %s
                                   AND vn.note_type = 'expansion'
                                   AND vn.object_id = s.id
                                   AND COALESCE(vn.body_md, vn.summary_md, '') <> ''
                               ) AS has_prior_expansion,
                               (
                                 SELECT COUNT(*)::int
                                 FROM {schema}.storyline_articles sa2
                                 JOIN {schema}.articles a2 ON a2.id = sa2.article_id
                                 WHERE sa2.storyline_id = s.id
                                   AND COALESCE(a2.published_at, a2.created_at)
                                       >= NOW() - INTERVAL '2 days'
                               ) AS new_members_2d,
                               COALESCE(s.quality_score, 0)::float AS quality_score
                        FROM {schema}.storylines s
                        LEFT JOIN LATERAL (
                          SELECT a.id AS article_id
                          FROM {schema}.storyline_articles sa
                          JOIN {schema}.articles a ON a.id = sa.article_id
                          WHERE sa.storyline_id = s.id
                            AND (a.enrichment_status IS NULL
                                 OR a.enrichment_status != 'removed')
                          ORDER BY a.published_at DESC NULLS LAST, a.id DESC
                          LIMIT 1
                        ) lead ON TRUE
                        WHERE s.merged_into_id IS NULL
                          AND s.status = 'active'
                          AND COALESCE(s.is_mega_storyline, FALSE) = FALSE
                          AND COALESCE(s.story_kind, '') <> 'container_index'
                          AND COALESCE(s.article_count, 0) >= 2
                          AND COALESCE(s.updated_at, s.created_at) >= %s
                        ORDER BY
                          (
                            SELECT COUNT(*)::int
                            FROM {schema}.storyline_articles sa3
                            JOIN {schema}.articles a3 ON a3.id = sa3.article_id
                            WHERE sa3.storyline_id = s.id
                              AND COALESCE(a3.published_at, a3.created_at)
                                  >= NOW() - INTERVAL '2 days'
                          ) DESC,
                          COALESCE(s.updated_at, s.created_at) DESC NULLS LAST,
                          COALESCE(s.quality_score, 0) DESC,
                          COALESCE(s.article_count, 0) DESC
                        LIMIT %s
                        """,
                        (
                            domain_key,
                            since,
                            pool_science
                            if is_science_vault_domain(domain_key)
                            else pool_news,
                        ),
                    )
                    rows = cur.fetchall() or []
        except Exception as e:
            logger.debug("scan leads %s: %s", domain_key, e)
            continue

        bucket = science if is_science_vault_domain(domain_key) else news
        for row in rows:
            (
                sid,
                title,
                acount,
                updated,
                lead_aid,
                created,
                has_prior,
                new_members_2d,
                quality_score,
            ) = row
            if not lead_aid:
                continue
            created_dt = created or updated
            age_days = 0
            if created_dt:
                try:
                    age_days = max(
                        0,
                        (datetime.now(timezone.utc) - created_dt.replace(tzinfo=timezone.utc)).days
                        if created_dt.tzinfo is None
                        else (datetime.now(timezone.utc) - created_dt).days,
                    )
                except Exception:
                    age_days = 0
            bucket.append(
                {
                    "domain_key": domain_key,
                    "storyline_id": int(sid),
                    "title": title or f"Storyline {sid}",
                    "article_count": int(acount or 0),
                    "updated_at": updated.isoformat() if updated else None,
                    "source_article_id": int(lead_aid),
                    "branch": "science" if is_science_vault_domain(domain_key) else "news",
                    "has_prior_expansion": bool(has_prior),
                    "age_days": int(age_days),
                    "new_members_2d": int(new_members_2d or 0),
                    "quality_score": float(quality_score or 0),
                }
            )

    out = {"news": news, "science": science}
    return out


def _load_article_excerpt(domain_key: str, article_id: int) -> dict[str, Any] | None:
    schema = _schema(domain_key)
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, title, url,
                       LEFT(COALESCE(content, summary, ''), 6000),
                       LEFT(COALESCE(summary, ''), 2000),
                       published_at
                FROM {schema}.articles
                WHERE id = %s
                """,
                (int(article_id),),
            )
            row = cur.fetchone()
    if not row:
        return None
    return {
        "id": int(row[0]),
        "title": row[1] or "",
        "url": row[2] or "",
        "body": row[3] or "",
        "summary": row[4] or "",
        "published": row[5].isoformat() if row[5] else None,
    }


def _clipping_and_wiki_evidence(
    domain_key: str, *, article_id: int, storyline_id: int
) -> tuple[str, list[str]]:
    """Return evidence text + fingerprint parts from vault registry."""
    parts: list[str] = []
    chunks: list[str] = []
    with get_db_connection_context() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT vault_path, title, COALESCE(summary_md, LEFT(COALESCE(body_md, ''), 800)),
                       note_updated_at, metadata
                FROM intelligence.vault_notes
                WHERE domain_key = %s
                  AND note_type = 'clipping'
                  AND (
                    object_id = %s
                    OR (metadata->>'article_id') = %s
                  )
                ORDER BY note_updated_at DESC NULLS LAST
                LIMIT 3
                """,
                (domain_key, int(article_id), str(int(article_id))),
            )
            for path, title, summary, updated, meta in cur.fetchall() or []:
                chunks.append(
                    f"Clipping: {title or path}\n{(summary or '')[:800]}"
                )
                parts.append(f"clip:{path}:{updated}")

            cur.execute(
                """
                SELECT vault_path, title, note_type, note_updated_at,
                       COALESCE(metadata->>'current_brief', '')
                FROM intelligence.vault_notes
                WHERE domain_key = %s
                  AND note_type IN ('entity', 'cluster', 'storyline', 'event')
                  AND note_updated_at >= NOW() - INTERVAL '5 days'
                ORDER BY note_updated_at DESC NULLS LAST
                LIMIT 12
                """,
                (domain_key,),
            )
            for path, title, ntype, updated, brief in cur.fetchall() or []:
                bits = f"Wiki {ntype}: {title or path}"
                if brief:
                    bits += f"\nBrief: {brief[:500]}"
                chunks.append(bits)
                parts.append(f"wiki:{path}:{updated}")

            # Storyline object itself
            parts.append(f"sl:{domain_key}:{storyline_id}")
    return "\n\n".join(chunks)[:12000], parts


def _vault_pack_excerpt(domain_key: str, article_id: int) -> str:
    try:
        from domains.reader.services.vault_context_pack import build_vault_context_pack
        from shared.domain_registry import resolve_domain_schema

        schema = resolve_domain_schema(domain_key) or _schema(domain_key)
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT DISTINCT ae.canonical_entity_id
                    FROM {schema}.article_entities ae
                    WHERE ae.article_id = %s AND ae.canonical_entity_id IS NOT NULL
                    LIMIT 10
                    """,
                    (int(article_id),),
                )
                eids = [int(r[0]) for r in cur.fetchall() or []]
        if not eids:
            return ""
        pack = build_vault_context_pack(
            domain_key=domain_key, entity_ids=eids, hops=2, max_notes=8
        )
        notes = pack.get("notes") or []
        lines = []
        for n in notes[:8]:
            title = n.get("title") or n.get("vault_path")
            sig = n.get("significance") or n.get("excerpt") or ""
            lines.append(f"- {title}: {str(sig)[:400]}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug("expansion vault pack skip: %s", e)
        return ""


async def _llm_expansion(prompt: str) -> str:
    from shared.services.ollama_model_caller import get_ollama_model_caller
    from shared.services.ollama_model_policy import InvocationKind

    # LONG_SYNTHESIS: higher num_predict / ctx than INTERACTIVE_SUMMARY (800 tok),
    # but still primary/8b lane — not the narrative-finisher 70b path.
    caller = get_ollama_model_caller()
    result = await caller.generate(
        prompt,
        kind=InvocationKind.LONG_SYNTHESIS,
        urgency="standard",
        approx_prompt_chars=len(prompt),
    )
    return (result.text or "").strip()


def _stub_expansion_body(*, title: str, article: dict[str, Any]) -> str:
    """Cacheable brief when LLM times out — title + cleaned lead excerpt only."""
    from shared.llm_text_sanitize import html_to_visible_text

    excerpt = html_to_visible_text(
        (article.get("summary") or article.get("body") or "").strip(),
        max_length=1600,
    )
    cleaned_lines: list[str] = []
    for line in excerpt.splitlines():
        s = line.strip()
        if not s or s.lower() in ("- published", "published"):
            continue
        if s.startswith("#") and title and title.lower() in s.lower():
            continue
        cleaned_lines.append(line)
    excerpt = "\n".join(cleaned_lines).strip()[:1600]
    if excerpt:
        return excerpt
    return f"_Brief pending for «{title}» — full expansion on next LLM pass._\n"


def write_or_refresh_expansion(
    lead: dict[str, Any],
    *,
    force: bool = False,
    skip_llm: bool = False,
) -> dict[str, Any]:
    """Write one storyline expansion to vault + registry when fingerprint drifts."""
    from services.vault_bridge_service import _render_frontmatter, vault_root, vault_write_enabled
    from services.vault_note_rag_service import reindex_vault_note
    from services.vault_notes_registry_service import get_vault_note, upsert_vault_note

    if not vault_write_enabled():
        return {"ok": False, "error": "vault_write_disabled"}

    domain_key = str(lead["domain_key"])
    storyline_id = int(lead["storyline_id"])
    article_id = int(lead["source_article_id"])
    title = str(lead.get("title") or f"Storyline {storyline_id}")

    article = _load_article_excerpt(domain_key, article_id)
    if not article:
        return {"ok": False, "error": "article_not_found", "storyline_id": storyline_id}

    briefing_lane = str(lead.get("briefing_lane") or "new")
    if briefing_lane not in ("ongoing", "new"):
        briefing_lane = "new"

    from services.vault_morning_context_retrieval_service import (
        retrieve_vault_context_for_storyline,
    )
    from services.vault_morning_web_research_service import research_web_for_storyline

    vault_pack = retrieve_vault_context_for_storyline(
        domain_key=domain_key,
        storyline_id=storyline_id,
        title=title,
        article_id=article_id,
    )
    vault_ev = vault_pack.get("evidence_text") or ""
    fp_parts = list(vault_pack.get("fingerprint_parts") or [])
    web_pack = {"evidence_text": "", "urls": [], "skipped": True}
    if not skip_llm:
        try:
            web_pack = research_web_for_storyline(
                title=title,
                domain_key=domain_key,
                storyline_id=storyline_id,
            )
        except Exception as e:
            logger.debug("web research skip: %s", e)
    web_ev = web_pack.get("evidence_text") or ""
    fp_parts.extend(
        [
            f"article:{article_id}",
            f"acount:{lead.get('article_count')}",
            f"title:{title}",
            f"lane:{briefing_lane}",
            hashlib.sha256((web_ev or "")[:1500].encode()).hexdigest()[:12],
        ]
    )
    fingerprint = _fingerprint(fp_parts)

    existing = get_vault_note(
        domain_key=domain_key, note_type="expansion", object_id=storyline_id
    )
    meta = (existing or {}).get("metadata") or {}
    if (
        not force
        and existing
        and str(meta.get("evidence_fingerprint") or "") == fingerprint
        and (existing.get("body_md") or meta.get("expansion_md"))
    ):
        return {
            "ok": True,
            "skipped": True,
            "reason": "fingerprint_match",
            "storyline_id": storyline_id,
            "domain_key": domain_key,
            "title": title,
            "vault_path": existing.get("vault_path"),
            "summary_md": existing.get("summary_md") or meta.get("summary_md"),
            "briefing_lane": briefing_lane,
        }

    window_end = date.today().isoformat()
    window_start = (date.today() - timedelta(days=MORNING_DELTA_DAYS)).isoformat()

    if briefing_lane == "ongoing":
        tone = (
            f"Write TODAY'S UPDATE on the ongoing narrative «{title}». "
            "Lead with what changed recently; then give background and competing views."
        )
    else:
        tone = (
            f"Write a NEW ITEM OF NOTE brief on «{title}». "
            "Keep it self-contained with enough background for a first-time reader."
        )

    # Mirror narrative-finisher desk quality: update + background + opinions.
    # Do NOT emit ---JSON--- or code fences — expansions are reader prose only.
    prompt = f"""You are a senior news desk analyst writing a reader-facing EXPANSION.

{tone}

Ground ONLY in the evidence below. Use these markdown headings in order
(omit a section only if evidence is truly absent — then one honest sentence):

## Lede
One short beat: what happened.

## Why this is in play
Why this dispute / decision / development matters *now*.

## Background
Durable context from vault / prior coverage (do not invent history).

## What happened
The update and sequence of moves.

## Competing views
At least two labeled perspectives when sources disagree or are thin
(each: claim + supporting signal + counter-signal). If sources agree, say so briefly.

## Why it matters / watch next
Stakes and plausible next steps.

Rules:
- Plain markdown prose. 350–550 words.
- No invented facts, quotes, dates, or plan clauses.
- No ---JSON---, no code fences, no raw HTML, no inventory dumps.
- Label web corroboration clearly when using Web evidence.

Storyline: {title}
Domain: {domain_key}
Lane: {briefing_lane}
Lead article: {article.get('title')}
Lead excerpt:
{(article.get('summary') or article.get('body') or '')[:1800]}

Vault evidence:
{vault_ev[:2800] or '_No vault evidence._'}

Web evidence:
{web_ev[:1600] or '_No web evidence._'}
"""

    used_stub = False
    if skip_llm:
        body = _stub_expansion_body(title=title, article=article)
        used_stub = True
    else:
        try:
            body = _run_async(_llm_expansion(prompt))
        except Exception as e:
            logger.warning(
                "expansion LLM %s/%s: %s — writing stub so morning cycle continues",
                domain_key,
                storyline_id,
                e,
            )
            body = _stub_expansion_body(title=title, article=article)
            used_stub = True
        if not body:
            body = _stub_expansion_body(title=title, article=article)
            used_stub = True

    body = body.strip()[:12000]
    from services.vault_quality_gates import (
        expansion_coherence_ok,
        load_storyline_member_titles,
        sanitize_vault_prose,
    )

    body = sanitize_vault_prose(body, max_length=12000)
    member_titles = load_storyline_member_titles(domain_key, storyline_id)
    coherent, coh_reason = expansion_coherence_ok(
        title=title,
        body=body,
        member_titles=member_titles,
        article_count=int(lead.get("article_count") or len(member_titles) or 0),
    )
    if not coherent:
        logger.info(
            "expansion coherence reject %s/%s: %s (keep prior if any)",
            domain_key,
            storyline_id,
            coh_reason,
        )
        return {
            "ok": False,
            "skipped": True,
            "reason": f"coherence:{coh_reason}",
            "storyline_id": storyline_id,
            "domain_key": domain_key,
            "title": title,
            "vault_path": (existing or {}).get("vault_path") if existing else None,
            "briefing_lane": briefing_lane,
        }

    summary = _dek_from_body(body)
    # Stub fingerprints never match a live LLM pass, so the next prime retries.
    if used_stub:
        fingerprint = f"{fingerprint}:stub"
    rel = expansion_vault_rel_path(
        domain_key=domain_key,
        object_id=storyline_id,
        title=title,
        anchor="storyline",
    )
    tags = structural_tags_for_note(
        note_type="expansion",
        domain_key=domain_key,
        extra=["expansion", "prime/morning", f"lane/{briefing_lane}"],
    )
    fm = {
        "ni_domain": domain_key,
        "note_type": "expansion",
        "object_id": storyline_id,
        "storyline_id": storyline_id,
        "source_article_id": article_id,
        "evidence_fingerprint": fingerprint,
        "window_start": window_start,
        "window_end": window_end,
        "briefing_lane": briefing_lane,
        "lifecycle": "living",
        "status": "note_ready",
        "ni_auto": True,
        "updated": _now_iso()[:10],
        "created": _now_iso()[:10],
        "tags": tags,
    }
    md = _render_frontmatter(fm) + f"# {title}\n\n{body}\n"
    path = vault_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")

    upsert_vault_note(
        domain_key=domain_key,
        note_type="expansion",
        object_id=storyline_id,
        vault_path=rel,
        title=title,
        note_status="note_ready",
        lifecycle="living",
        last_article_id=article_id,
        tags=tags,
        body_md=body,
        summary_md=summary,
        metadata={
            "source_article_id": article_id,
            "storyline_id": storyline_id,
            "evidence_fingerprint": fingerprint,
            "window_start": window_start,
            "window_end": window_end,
            "briefing_lane": briefing_lane,
            "briefing_day": window_end,
            "web_urls": (web_pack.get("urls") or [])[:5],
            "expansion": True,
            "llm_stub": used_stub,
        },
        tags_source="ni_structural",
    )
    try:
        reindex_vault_note(
            rel, title=title, body=body, domain_key=domain_key, note_type="expansion"
        )
    except Exception:
        pass
    return {
        "ok": True,
        "stub": used_stub,
        "storyline_id": storyline_id,
        "domain_key": domain_key,
        "title": title,
        "vault_path": rel,
        "fingerprint": fingerprint,
        "summary_md": summary,
        "chars": len(body),
        "briefing_lane": briefing_lane,
    }


def compose_daily_briefing(
    *,
    day: str | None = None,
    branch: str = "news",
    expansions: list[dict[str, Any]] | None = None,
    skip_llm: bool = False,
    slate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose 10_Daily two-lane briefing via Morning Briefing Manager."""
    from services.morning_briefing_manager_service import assemble_two_lane_briefing
    from services.vault_bridge_service import _render_frontmatter, vault_root, vault_write_enabled
    from services.vault_note_rag_service import reindex_vault_note
    from services.vault_notes_registry_service import upsert_vault_note

    if not vault_write_enabled():
        return {"ok": False, "error": "vault_write_disabled"}

    briefing_day = (day or date.today().isoformat())[:10]
    domain_key = "science" if branch == "science" else "global"
    expansions = expansions or []

    assembled = assemble_two_lane_briefing(
        expansions=expansions,
        briefing_day=briefing_day,
        branch=branch,
        skip_llm=skip_llm,
        slate=slate,
    )
    body = (assembled.get("body_md") or "").strip()[:14000]
    from services.vault_quality_gates import briefing_citations_ok, sanitize_vault_prose

    body = sanitize_vault_prose(body, max_length=14000)
    ok_cite, cite_reason = briefing_citations_ok(body, expansions=expansions)
    if not ok_cite:
        logger.warning(
            "daily briefing skip branch=%s day=%s reason=%s",
            branch,
            briefing_day,
            cite_reason,
        )
        return {
            "ok": False,
            "skipped": True,
            "reason": f"citation_gate:{cite_reason}",
            "briefing_day": briefing_day,
            "branch": branch,
        }
    summary = _dek_from_body(body, max_len=320)
    rel = daily_briefing_vault_rel_path(briefing_day, branch=branch)
    oid = daily_briefing_object_id(briefing_day)
    tags = structural_tags_for_note(
        note_type="daily_briefing",
        domain_key=domain_key,
        extra=["daily_briefing", "prime/morning", f"branch/{branch}", "lanes/two"],
    )
    title = (
        f"Science briefing — {briefing_day}"
        if branch == "science"
        else f"Morning briefing — {briefing_day}"
    )
    fm = {
        "ni_domain": domain_key,
        "note_type": "daily_briefing",
        "object_id": oid,
        "briefing_day": briefing_day,
        "branch": branch,
        "lifecycle": "living",
        "status": "note_ready",
        "ni_auto": True,
        "updated": _now_iso()[:10],
        "created": briefing_day,
        "tags": tags,
    }
    md = _render_frontmatter(fm) + f"# {title}\n\n{body}\n"
    path = vault_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")

    expansion_paths = [e.get("vault_path") for e in expansions if e.get("vault_path")]
    upsert_vault_note(
        domain_key=domain_key,
        note_type="daily_briefing",
        object_id=oid,
        vault_path=rel,
        title=title,
        note_status="note_ready",
        lifecycle="living",
        tags=tags,
        body_md=body,
        summary_md=summary,
        metadata={
            "briefing_day": briefing_day,
            "branch": branch,
            "expansion_paths": expansion_paths,
            "daily_briefing": True,
            "two_lane": True,
            "ongoing_count": assembled.get("ongoing_count"),
            "new_count": assembled.get("new_count"),
            "slate_source": (slate or {}).get("source"),
        },
        tags_source="ni_structural",
    )
    try:
        reindex_vault_note(
            rel, title=title, body=body, domain_key=domain_key, note_type="daily_briefing"
        )
    except Exception:
        pass
    return {
        "ok": True,
        "vault_path": rel,
        "domain_key": domain_key,
        "briefing_day": briefing_day,
        "branch": branch,
        "summary_md": summary,
        "chars": len(body),
        "ongoing_count": assembled.get("ongoing_count"),
        "new_count": assembled.get("new_count"),
    }


def run_vault_morning_prime(
    *,
    delta_days: int = MORNING_BRIEF_ACTIVITY_DAYS,
    force: bool = False,
    skip_llm: bool = False,
    refresh_hub_briefs: bool = True,
) -> dict[str, Any]:
    """Full morning cycle: scan → manager slate → expansions → two-lane briefings."""
    from services.morning_briefing_manager_service import (
        propose_brief_slate,
        selected_leads_from_slate,
    )

    if not vault_morning_prime_enabled():
        return {"ok": False, "skipped": True, "reason": "disabled"}

    leads = scan_active_leads(delta_days=delta_days)
    candidates = leads["news"] + leads["science"]
    slate = propose_brief_slate(candidates, skip_llm=skip_llm)
    selected = selected_leads_from_slate(slate)

    stats: dict[str, Any] = {
        "ok": True,
        "leads_news": len(leads["news"]),
        "leads_science": len(leads["science"]),
        "candidates": len(candidates),
        "selected": len(selected),
        "slate_source": slate.get("source"),
        "ongoing_selected": len(slate.get("ongoing") or []),
        "new_selected": len(slate.get("new_of_note") or []),
        "expansions": [],
        "hub_briefs": None,
        "briefings": [],
    }

    all_written: list[dict[str, Any]] = []
    for lead in selected:
        try:
            r = write_or_refresh_expansion(lead, force=force, skip_llm=skip_llm)
            r["title"] = lead.get("title") or r.get("title")
            r["branch"] = lead.get("branch")
            r["briefing_lane"] = lead.get("briefing_lane") or r.get("briefing_lane")
            stats["expansions"].append(r)
            if r.get("ok"):
                all_written.append({**lead, **r})
        except Exception as e:
            logger.warning("expansion lead %s: %s", lead.get("storyline_id"), e)
            stats["expansions"].append(
                {"ok": False, "error": str(e), "storyline_id": lead.get("storyline_id")}
            )

    if refresh_hub_briefs:
        try:
            from services.vault_hub_brief_service import refresh_stale_hub_briefs

            stats["hub_briefs"] = refresh_stale_hub_briefs(force=force)
        except Exception as e:
            logger.warning("morning hub briefs: %s", e)
            stats["hub_briefs"] = {"ok": False, "error": str(e)}

    news_ex = [e for e in all_written if e.get("branch") != "science"]
    sci_ex = [e for e in all_written if e.get("branch") == "science"]
    try:
        stats["briefings"].append(
            compose_daily_briefing(
                branch="news",
                expansions=news_ex,
                skip_llm=skip_llm,
                slate=slate,
            )
        )
    except Exception as e:
        logger.warning("news daily briefing: %s", e)
        stats["briefings"].append({"ok": False, "branch": "news", "error": str(e)})
    # Only compose science when we have expansions (empty slate was a guaranteed citation_gate skip)
    if sci_ex:
        try:
            stats["briefings"].append(
                compose_daily_briefing(
                    branch="science",
                    expansions=sci_ex,
                    skip_llm=skip_llm,
                    slate=slate,
                )
            )
        except Exception as e:
            logger.warning("science daily briefing: %s", e)
            stats["briefings"].append(
                {"ok": False, "branch": "science", "error": str(e)}
            )
    elif any(is_science_vault_domain(d) for d in SCIENCE_DOMAINS_DEFAULT):
        stats["briefings"].append(
            {
                "ok": False,
                "skipped": True,
                "reason": "no_science_expansions",
                "branch": "science",
            }
        )

    written = sum(1 for e in stats["expansions"] if e.get("ok") and not e.get("skipped"))
    skipped = sum(1 for e in stats["expansions"] if e.get("skipped"))
    stats["expansions_written"] = written
    stats["expansions_skipped"] = skipped
    logger.info(
        "vault_morning_prime: candidates=%s selected=%s/%s written=%s skipped=%s slate=%s",
        stats["candidates"],
        stats["ongoing_selected"],
        stats["new_selected"],
        written,
        skipped,
        stats["slate_source"],
    )
    return stats
