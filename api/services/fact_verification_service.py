"""
Fact verification service — multi-source corroboration, contradiction detection,
source reliability scoring, and completeness assessment.

Operates on extracted_claims, article content, and entity data to assess factual
confidence. Corroboration blends orchestrator ``source_credibility`` tiers (YAML)
with legacy source labels, supports single authoritative sources, and optional
cross-checks: Wikipedia, Wikidata (incl. year overlap), GDELT mention density,
finance SEC-hosted articles, internal same-subject claims, and borderline LLM entailment.

T3.3 of V6_QUALITY_FIRST_TODO.md.
"""

import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)

# Minimum articles/sources needed to move from "unverified" to "corroborated"
MIN_CORROBORATION_SOURCES = 2
MIN_CORROBORATION_ARTICLES = 3

# Source reliability tiers (can be extended via config)
SOURCE_RELIABILITY_TIERS = {
    "tier_1": {
        "score": 0.95,
        "patterns": [
            "reuters",
            "associated press",
            "ap news",
            "bbc",
            "npr",
            "pbs",
            "c-span",
        ],
    },
    "tier_2": {
        "score": 0.85,
        "patterns": [
            "new york times",
            "washington post",
            "wall street journal",
            "financial times",
            "the economist",
            "bloomberg",
            "the guardian",
            "politico",
        ],
    },
    "tier_3": {
        "score": 0.70,
        "patterns": [
            "cnn",
            "abc news",
            "cbs news",
            "nbc news",
            "fox news",
            "usa today",
            "los angeles times",
        ],
    },
    "tier_4": {
        "score": 0.50,
        "patterns": [],  # everything else
    },
}

CONTRADICTION_PROMPT = """Analyze these two claims and determine if they contradict each other.

Claim A: {claim_a}
Claim B: {claim_b}

Respond with ONLY a JSON object:
{{"contradiction": true/false, "explanation": "brief explanation", "confidence": 0.0-1.0}}"""

COMPLETENESS_PROMPT = """Assess the completeness of coverage for this topic based on the available information.

Topic: {topic}
Number of sources: {source_count}
Number of articles: {article_count}
Key claims:
{claims_text}

Evaluate:
1. Are multiple perspectives represented?
2. Are there obvious gaps (missing context, unaddressed questions)?
3. Is the timeline of events clear?

Respond with ONLY a JSON object:
{{"completeness_score": 0.0-1.0, "perspectives_covered": ["list"], "gaps": ["list"], "assessment": "brief text"}}"""


# ---------------------------------------------------------------------------
# Source reliability scoring
# ---------------------------------------------------------------------------


def score_source_reliability(source_domain: str) -> dict[str, Any]:
    """
    Score a source domain's reliability based on known tiers.
    Returns {score: 0.0-1.0, tier: str, source: str}.
    """
    source_lower = (source_domain or "").lower().strip()
    if not source_lower:
        return {"score": 0.3, "tier": "unknown", "source": source_domain}

    for tier_name, tier_data in SOURCE_RELIABILITY_TIERS.items():
        for pattern in tier_data["patterns"]:
            if pattern in source_lower or source_lower in pattern:
                return {
                    "score": tier_data["score"],
                    "tier": tier_name,
                    "source": source_domain,
                }

    return {
        "score": SOURCE_RELIABILITY_TIERS["tier_4"]["score"],
        "tier": "tier_4",
        "source": source_domain,
    }


def score_source_reliability_batch(source_domains: list[str]) -> dict[str, dict[str, Any]]:
    """Score reliability for multiple sources."""
    return {s: score_source_reliability(s) for s in set(source_domains)}


def _governance_reliability_for_source(source_label: str) -> dict[str, Any]:
    """Blend orchestrator source_credibility (YAML) with legacy string tiers."""
    from shared.services.source_credibility_service import resolve_source_credibility

    gov = resolve_source_credibility("", source_label or "")
    legacy = score_source_reliability(source_label or "")
    eff = min(1.0, (float(gov.multiplier) + float(legacy["score"])) / 2.0)
    return {
        "governance_tier": gov.tier_id,
        "governance_multiplier": float(gov.multiplier),
        "requires_corroboration": gov.requires_corroboration,
        "legacy_score": legacy["score"],
        "legacy_tier": legacy["tier"],
        "effective_score": eff,
    }


def _originating_article_ids_for_claim(claim_id: int) -> set[int]:
    """Article IDs linked to the claim's context (exclude from corroboration counts)."""
    conn = get_db_connection()
    if not conn:
        return set()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT atc.article_id
                FROM intelligence.extracted_claims ec
                JOIN intelligence.article_to_context atc ON atc.context_id = ec.context_id
                WHERE ec.id = %s
                """,
                (claim_id,),
            )
            return {r[0] for r in cur.fetchall() if r[0] is not None}
    except Exception as e:
        logger.debug("originating_article_ids_for_claim: %s", e)
        return set()
    finally:
        conn.close()


def _flexible_tsquery_search(
    cur,
    schema: str,
    cutoff: datetime,
    key_terms: list[str],
    claim_text: str,
) -> tuple[list[tuple], str]:
    """Try strict AND (3,2,1 terms) then plainto_tsquery on claim prefix."""
    tried: list[str] = []
    for n in (3, 2, 1):
        if len(key_terms) < n:
            continue
        tsq = " & ".join(f"'{t}'" for t in key_terms[:n])
        if tsq in tried:
            continue
        tried.append(tsq)
        cur.execute(
            f"""
            SELECT a.id, a.title, a.source_domain, a.published_at,
                   LEFT(a.content, 500)
            FROM {schema}.articles a
            WHERE a.published_at >= %s
              AND to_tsvector('english', COALESCE(a.title, '') || ' ' || COALESCE(a.content, ''))
                  @@ to_tsquery('english', %s)
            ORDER BY a.published_at DESC
            LIMIT 50
            """,
            (cutoff, tsq),
        )
        rows = cur.fetchall()
        if rows:
            return rows, tsq

    plain = re.sub(r"\s+", " ", (claim_text or "")[:140]).strip()
    if len(plain) >= 8:
        cur.execute(
            f"""
            SELECT a.id, a.title, a.source_domain, a.published_at,
                   LEFT(a.content, 500)
            FROM {schema}.articles a
            WHERE a.published_at >= %s
              AND to_tsvector('english', COALESCE(a.title, '') || ' ' || COALESCE(a.content, ''))
                  @@ plainto_tsquery('english', %s)
            ORDER BY a.published_at DESC
            LIMIT 50
            """,
            (cutoff, plain),
        )
        rows = cur.fetchall()
        if rows:
            return rows, f"plain:{plain[:48]}"
    return [], ""


def _lexical_overlap(claim_text: str, reference: str) -> float:
    terms = set(_extract_key_terms(claim_text))
    if not terms:
        return 0.0
    ref_low = (reference or "").lower()
    hits = sum(1 for t in terms if t in ref_low)
    return hits / len(terms)


def wikipedia_reference_check(claim_text: str, subject: str | None = None) -> dict[str, Any]:
    """
    Search Wikipedia by subject (or claim prefix), compare lead extract to claim terms.
    Reference only — not ground truth.
    """
    out: dict[str, Any] = {
        "status": "skipped",
        "overlap": 0.0,
        "title": None,
        "url": None,
    }
    if os.environ.get("FACT_VERIFY_WIKIPEDIA", "true").lower() not in ("1", "true", "yes"):
        out["status"] = "disabled"
        return out
    query = (subject or "").strip() or (claim_text or "")[:100]
    if len(query) < 3:
        out["status"] = "no_query"
        return out
    try:
        from modules.ml.rag_external_services import WikipediaService

        wiki = WikipediaService()
        arts = wiki.search_articles(query, limit=3)
        if not arts:
            out["status"] = "no_article"
            return out
        title = arts[0].get("title") or ""
        summ = wiki.get_article_summary(title)
        if not summ:
            out["status"] = "no_summary"
            return out
        extract = summ.get("extract") or ""
        ov = _lexical_overlap(claim_text, extract)
        out.update(
            {
                "overlap": round(ov, 3),
                "title": title,
                "url": summ.get("url"),
                "status": (
                    "supported"
                    if ov >= 0.45
                    else "weak_support"
                    if ov >= 0.22
                    else "low_overlap"
                ),
            }
        )
    except Exception as e:
        logger.debug("wikipedia_reference_check: %s", e)
        out["status"] = "error"
        out["error"] = str(e)
    return out


def count_internal_similar_claims(
    claim_id: int,
    subject: str,
    domain_key: str,
    hours: int = 168,
) -> dict[str, Any]:
    """Other extracted_claims in the same domain with identical normalized subject."""
    conn = get_db_connection()
    if not conn:
        return {"count": 0, "error": "no_db"}
    try:
        subj = (subject or "").strip().lower()
        if len(subj) < 2:
            return {"count": 0, "window_hours": hours}
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) FROM intelligence.extracted_claims ec
                JOIN intelligence.contexts c ON c.id = ec.context_id
                WHERE c.domain_key = %s
                  AND ec.id != %s
                  AND ec.created_at >= NOW() - (%s * INTERVAL '1 hour')
                  AND LOWER(TRIM(ec.subject_text)) = %s
                """,
                (domain_key, claim_id, hours, subj),
            )
            cnt = cur.fetchone()[0]
            return {"count": int(cnt), "window_hours": hours}
    except Exception as e:
        logger.debug("count_internal_similar_claims: %s", e)
        return {"count": 0, "error": str(e)}
    finally:
        conn.close()


# Wikimedia-style User-Agent (required)
_EXTERNAL_HTTP_UA = (
    "NewsIntelligence/1.0 (fact verification; +https://github.com/news-intelligence)"
)


def wikidata_reference_check(claim_text: str, subject: str | None = None) -> dict[str, Any]:
    """
    Resolve subject via Wikidata search; compare English label + description to claim terms.
    If the claim contains years, reward overlap with years in the reference blob (dated events).
    """
    out: dict[str, Any] = {
        "status": "skipped",
        "overlap": 0.0,
        "id": None,
        "label": None,
        "dated_year_overlap": False,
    }
    if os.environ.get("FACT_VERIFY_WIKIDATA", "true").lower() not in ("1", "true", "yes"):
        out["status"] = "disabled"
        return out
    query = (subject or "").strip() or (claim_text or "")[:80]
    if len(query) < 2:
        out["status"] = "no_query"
        return out
    try:
        import requests

        r = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbsearchentities",
                "search": query[:240],
                "language": "en",
                "format": "json",
                "limit": 3,
            },
            headers={"User-Agent": _EXTERNAL_HTTP_UA},
            timeout=12,
        )
        r.raise_for_status()
        hits = r.json().get("search") or []
        if not hits:
            out["status"] = "no_entity"
            return out
        qid = hits[0].get("id")
        label = hits[0].get("label") or ""
        r2 = requests.get(
            "https://www.wikidata.org/w/api.php",
            params={
                "action": "wbgetentities",
                "ids": qid,
                "props": "descriptions|labels",
                "languages": "en",
                "format": "json",
            },
            headers={"User-Agent": _EXTERNAL_HTTP_UA},
            timeout=12,
        )
        r2.raise_for_status()
        entities = r2.json().get("entities") or {}
        ent = entities.get(qid) or {}
        desc = (ent.get("descriptions") or {}).get("en", {}).get("value") or ""
        lab = (ent.get("labels") or {}).get("en", {}).get("value") or label
        blob = f"{lab} {desc}"
        ov = _lexical_overlap(claim_text, blob)
        years_claim = set(re.findall(r"\b(?:19\d{2}|20\d{2})\b", claim_text or ""))
        years_ref = set(re.findall(r"\b(?:19\d{2}|20\d{2})\b", blob))
        dated_align = bool(years_claim & years_ref) if years_claim else False
        if ov >= 0.4 or (dated_align and ov >= 0.18):
            st = "supported"
        elif ov >= 0.18 or dated_align:
            st = "weak_support"
        else:
            st = "low_overlap"
        out.update(
            {
                "status": st,
                "overlap": round(ov, 3),
                "id": qid,
                "label": lab,
                "dated_year_overlap": dated_align,
                "years_in_claim": sorted(years_claim)[:6],
            }
        )
    except Exception as e:
        logger.debug("wikidata_reference_check: %s", e)
        out["status"] = "error"
        out["error"] = str(e)
    return out


def gdelt_mention_signal(
    claim_text: str,
    subject: str | None = None,
    days: int = 30,
) -> dict[str, Any]:
    """Low-weight global mention density from GDELT DOC API (not authoritative)."""
    out: dict[str, Any] = {"status": "skipped", "doc_count": 0, "signal_strength": 0.0}
    if os.environ.get("FACT_VERIFY_GDELT", "true").lower() not in ("1", "true", "yes"):
        out["status"] = "disabled"
        return out
    term = (subject or "").strip()
    if len(term) < 3:
        kt = _extract_key_terms(claim_text)
        term = " ".join(kt[:3]) if kt else ""
    if len(term) < 3:
        out["status"] = "no_query"
        return out
    try:
        import requests

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        params = {
            "query": term[:120],
            "format": "json",
            "maxrecords": 20,
            "startdatetime": start.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end.strftime("%Y%m%d%H%M%S"),
        }
        r = requests.get(
            "https://api.gdeltproject.org/api/v2/doc/doc",
            params=params,
            headers={"User-Agent": _EXTERNAL_HTTP_UA},
            timeout=15,
        )
        if r.status_code != 200:
            out["status"] = "http_error"
            out["http_status"] = r.status_code
            return out
        data = r.json()
        docs = data.get("articles") or data.get("docs") or []
        count = len(docs) if isinstance(docs, list) else 0
        strength = min(1.0, count / 12.0)
        out.update(
            {
                "status": "ok",
                "doc_count": count,
                "signal_strength": round(strength, 3),
                "query_used": term[:120],
            }
        )
    except Exception as e:
        logger.debug("gdelt_mention_signal: %s", e)
        out["status"] = "error"
        out["error"] = str(e)
    return out


def finance_sec_articles_signal(
    claim_text: str,
    domain_key: str,
    lookback_days: int = 120,
) -> dict[str, Any]:
    """Match claim terms against recent finance.articles whose URL looks SEC/EDGAR-hosted."""
    out: dict[str, Any] = {"status": "skipped", "match_count": 0}
    if domain_key != "finance":
        out["status"] = "skipped_domain"
        return out
    if os.environ.get("FACT_VERIFY_SEC_FINANCE", "true").lower() not in ("1", "true", "yes"):
        out["status"] = "disabled"
        return out
    terms = _extract_key_terms(claim_text)
    plain = " ".join(terms[:6]) if len(terms) >= 2 else re.sub(r"[^\w\s-]", " ", (claim_text or "")[:100]).strip()
    if len(plain) < 4:
        out["status"] = "no_query"
        return out
    schema = resolve_domain_schema("finance")
    conn = get_db_connection()
    if not conn:
        return {"status": "error", "match_count": 0, "error": "no_db"}
    try:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    f"""
                    SELECT COUNT(DISTINCT a.id)
                    FROM {schema}.articles a
                    WHERE a.published_at >= NOW() - (%s * INTERVAL '1 day')
                      AND (
                          a.url ILIKE %s
                          OR a.url ILIKE %s
                      )
                      AND to_tsvector('english',
                          COALESCE(a.title, '') || ' ' || COALESCE(LEFT(a.content, 3000), ''))
                          @@ plainto_tsquery('english', %s)
                    """,
                    (lookback_days, "%sec.gov%", "%sec.gov/Archives%", plain[:200]),
                )
                cnt = int(cur.fetchone()[0] or 0)
            except Exception:
                like_parts: list[str] = []
                params2: list[Any] = [lookback_days, "%sec.gov%", "%sec.gov/Archives%"]
                for t in terms[:5] if terms else [plain[:40]]:
                    if not (t or "").strip():
                        continue
                    like_parts.append("(a.title ILIKE %s OR LEFT(a.content, 2500) ILIKE %s)")
                    p = f"%{(t or '')[:80]}%"
                    params2.extend([p, p])
                if not like_parts:
                    cnt = 0
                else:
                    cur.execute(
                        f"""
                        SELECT COUNT(DISTINCT a.id)
                        FROM {schema}.articles a
                        WHERE a.published_at >= NOW() - (%s * INTERVAL '1 day')
                          AND (a.url ILIKE %s OR a.url ILIKE %s)
                          AND ({' OR '.join(like_parts)})
                        """,
                        tuple(params2),
                    )
                    cnt = int(cur.fetchone()[0] or 0)
        out.update({"status": "ok", "match_count": cnt, "plain_query": plain[:120]})
    except Exception as e:
        logger.debug("finance_sec_articles_signal: %s", e)
        out["status"] = "error"
        out["error"] = str(e)
    finally:
        conn.close()
    return out


def _corroboration_is_borderline(corroboration: dict[str, Any]) -> bool:
    st = corroboration.get("status") or ""
    cf = float(corroboration.get("confidence") or 0)
    if st in ("partially_corroborated", "single_established") and 0.40 <= cf <= 0.74:
        return True
    if st == "single_source" and 0.33 <= cf <= 0.58:
        return True
    return False


def entailment_llm_borderline_check(
    claim_text: str,
    corroboration: dict[str, Any],
    extra_context: str = "",
) -> dict[str, Any]:
    """
    Small LLM pass only when corroboration is borderline; returns verdict + confidence.
    Skips if asyncio event loop is already running (avoid asyncio.run conflict).
    """
    out: dict[str, Any] = {
        "status": "skipped",
        "verdict": None,
        "model_confidence": 0.0,
    }
    if os.environ.get("FACT_VERIFY_ENTAILMENT_LLM", "true").lower() not in ("1", "true", "yes"):
        out["status"] = "disabled"
        return out
    if not _corroboration_is_borderline(corroboration):
        out["status"] = "skipped_not_borderline"
        return out
    parts: list[str] = []
    for src in (corroboration.get("sources") or [])[:4]:
        parts.append(f"Source: {src.get('source')}")
        for art in (src.get("articles") or [])[:2]:
            parts.append(
                ((art.get("title") or "") + " " + (art.get("excerpt") or ""))[:320]
            )
    ctx = "\n".join(parts)[:1700]
    if extra_context:
        ctx = (extra_context.strip()[:700] + "\n" + ctx)[:2000]
    prompt = (
        "You assess whether CONTEXT supports a CLAIM (verification helper).\n"
        f"CLAIM: {claim_text[:650]}\n"
        f"CONTEXT:\n{ctx}\n"
        'Reply with ONLY JSON: {"verdict":"supports"|"contradicts"|"insufficient",'
        '"confidence":0.0-1.0}\n'
        'Use "supports" only if context clearly backs the claim; '
        '"insufficient" if unclear; "contradicts" if it conflicts.'
    )

    async def _run_llm() -> str:
        from shared.services.llm_service import LLMService, ModelType

        llm = LLMService()
        return await llm._call_ollama(ModelType.LLAMA_8B, prompt)

    raw: str = ""
    try:
        import asyncio

        try:
            asyncio.get_running_loop()
            out["status"] = "skipped_nested_event_loop"
            return out
        except RuntimeError:
            pass

        raw = asyncio.run(_run_llm())
        cleaned = (raw or "").strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
        parsed = json.loads(cleaned)
        verdict = str(parsed.get("verdict") or "insufficient").lower()
        mc = float(parsed.get("confidence") or 0)
        out.update(
            {
                "status": "ok",
                "verdict": verdict,
                "model_confidence": max(0.0, min(1.0, mc)),
            }
        )
    except json.JSONDecodeError:
        out["status"] = "parse_error"
        out["raw"] = raw[:400] if raw else ""
    except Exception as e:
        logger.debug("entailment_llm_borderline_check: %s", e)
        out["status"] = "error"
        out["error"] = str(e)
    return out


# ---------------------------------------------------------------------------
# Multi-source corroboration
# ---------------------------------------------------------------------------


def corroborate_claim(
    claim_text: str,
    domain_key: str,
    hours: int = 72,
    claim_id: int | None = None,
) -> dict[str, Any]:
    """
    Check if a claim is corroborated by domain articles, weighted by source_credibility.

    Excludes originating article(s) when ``claim_id`` is set. Uses flexible full-text
    (AND 3→2→1 key terms, then plainto_tsquery). Single tier_1 (government / wires)
    can yield ``authoritative_single``; single tier_2 → ``single_established``.

    Returns:
        status: corroborated | partially_corroborated | authoritative_single |
            single_established | single_source | unverified | error
    """
    schema = resolve_domain_schema(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"status": "error", "error": "Database connection failed"}

    try:
        key_terms = _extract_key_terms(claim_text)
        if not key_terms:
            conn.close()
            return {
                "status": "unverified",
                "source_count": 0,
                "article_count": 0,
                "sources": [],
                "confidence": 0.0,
                "reason": "Could not extract key terms from claim",
            }

        exclude_ids: set[int] = set()
        if claim_id is not None:
            exclude_ids = _originating_article_ids_for_claim(claim_id)

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        with conn.cursor() as cur:
            articles, query_used = _flexible_tsquery_search(
                cur, schema, cutoff, key_terms, claim_text
            )

        conn.close()

        if exclude_ids:
            articles = [a for a in articles if a[0] not in exclude_ids]

        if not articles:
            return {
                "status": "unverified",
                "source_count": 0,
                "article_count": 0,
                "sources": [],
                "confidence": 0.0,
                "key_terms_used": key_terms[:5],
                "search_query_used": query_used or None,
            }

        source_articles: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for aid, title, source, pub_at, excerpt in articles:
            source_articles[source or "unknown"].append(
                {
                    "article_id": aid,
                    "title": title or "",
                    "published_at": pub_at.isoformat() if pub_at else None,
                    "excerpt": (excerpt or "")[:200],
                }
            )

        sources: list[dict[str, Any]] = []
        for source, arts in source_articles.items():
            gr = _governance_reliability_for_source(source)
            weight = float(gr["effective_score"]) * (len(arts) ** 0.5)
            sources.append(
                {
                    "source": source,
                    "reliability_score": gr["effective_score"],
                    "tier": gr["legacy_tier"],
                    "governance_tier": gr["governance_tier"],
                    "governance_multiplier": gr["governance_multiplier"],
                    "requires_corroboration": gr["requires_corroboration"],
                    "article_count": len(arts),
                    "articles": arts[:3],
                    "_weight": weight,
                }
            )

        sources.sort(key=lambda s: (s["_weight"], s["reliability_score"]), reverse=True)
        for s in sources:
            del s["_weight"]

        source_count = len(sources)
        article_count = len(articles)
        top = sources[0] if sources else {}
        top_gov_tier = str(top.get("governance_tier") or "")
        top_mult = float(top.get("governance_multiplier") or 0)
        top_req_coro = bool(top.get("requires_corroboration"))

        if (
            source_count >= MIN_CORROBORATION_SOURCES
            and article_count >= MIN_CORROBORATION_ARTICLES
        ):
            status = "corroborated"
            avg_rel = sum(s["reliability_score"] for s in sources) / len(sources)
            confidence = min(1.0, avg_rel * (0.5 + 0.5 * min(source_count / 5, 1.0)))
        elif source_count >= 2:
            status = "partially_corroborated"
            confidence = min(
                0.72,
                sum(s["reliability_score"] for s in sources) / max(len(sources), 1),
            )
        elif article_count >= 1:
            eff = float(top.get("reliability_score") or 0)
            if top_gov_tier == "tier_1" and not top_req_coro:
                status = "authoritative_single"
                confidence = min(1.0, max(eff, top_mult * 0.92))
            elif top_gov_tier == "tier_2" or top_mult >= 0.85:
                status = "single_established"
                confidence = min(0.82, max(0.48, eff * 0.88))
            else:
                status = "single_source"
                confidence = max(0.25, eff * 0.55)
        else:
            status = "unverified"
            confidence = 0.0

        return {
            "status": status,
            "source_count": source_count,
            "article_count": article_count,
            "sources": sources[:10],
            "confidence": round(float(confidence), 2),
            "key_terms_used": key_terms[:5],
            "search_query_used": query_used or None,
        }
    except Exception as e:
        logger.warning("corroborate_claim: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"status": "error", "error": str(e)}


def _extract_key_terms(text: str) -> list[str]:
    """Extract significant terms from a claim for full-text search."""
    stop_words = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "up",
        "about",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "between",
        "out",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "he",
        "she",
        "they",
        "we",
        "his",
        "her",
        "their",
        "our",
        "my",
        "your",
        "and",
        "but",
        "or",
        "nor",
        "not",
        "no",
        "so",
        "if",
        "than",
        "too",
        "very",
        "said",
        "says",
        "according",
        "also",
        "just",
        "more",
        "some",
        "any",
        "other",
        "new",
        "been",
        "who",
        "which",
        "when",
        "where",
        "how",
    }
    words = re.findall(r"[a-zA-Z]+", text.lower())
    terms = [w for w in words if w not in stop_words and len(w) >= 3]
    # Deduplicate preserving order
    seen = set()
    unique = []
    for t in terms:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique[:10]


# ---------------------------------------------------------------------------
# Contradiction detection
# ---------------------------------------------------------------------------


def detect_contradictions(
    domain_key: str,
    claim_ids: list[int] | None = None,
    hours: int = 48,
    limit: int = 50,
) -> dict[str, Any]:
    """
    Find contradicting claims within a domain's recent extracted_claims.
    Groups claims by subject, then checks pairs for contradiction using
    heuristics and optionally LLM.

    Returns {contradictions: [{claim_a, claim_b, explanation, confidence}]}.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "contradictions": [], "error": "Database connection failed"}

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        with conn.cursor() as cur:
            if claim_ids:
                placeholders = ",".join(["%s"] * len(claim_ids))
                cur.execute(
                    f"""
                    SELECT ec.id, ec.subject_text, ec.predicate_text, ec.object_text,
                           ec.confidence, ec.context_id
                    FROM intelligence.extracted_claims ec
                    WHERE ec.id IN ({placeholders})
                    ORDER BY ec.created_at DESC
                    """,
                    tuple(claim_ids),
                )
            else:
                cur.execute(
                    """
                    SELECT ec.id, ec.subject_text, ec.predicate_text, ec.object_text,
                           ec.confidence, ec.context_id
                    FROM intelligence.extracted_claims ec
                    JOIN intelligence.contexts c ON c.id = ec.context_id
                    WHERE c.domain_key = %s
                      AND ec.created_at >= %s
                    ORDER BY ec.created_at DESC
                    LIMIT %s
                    """,
                    (domain_key, cutoff, limit * 2),
                )
            claims = cur.fetchall()

        conn.close()

        if len(claims) < 2:
            return {"success": True, "contradictions": [], "claims_checked": len(claims)}

        # Group by subject for efficient comparison
        subject_groups: dict[str, list[tuple]] = defaultdict(list)
        for claim in claims:
            subject = (claim[1] or "").lower().strip()
            if subject:
                # Normalize subject for grouping
                normalized = re.sub(r"\s+", " ", subject)
                subject_groups[normalized].append(claim)

        contradictions = []

        for subject, group_claims in subject_groups.items():
            if len(group_claims) < 2:
                continue

            for i in range(len(group_claims)):
                for j in range(i + 1, len(group_claims)):
                    ca = group_claims[i]
                    cb = group_claims[j]

                    pred_a = (ca[2] or "").lower()
                    pred_b = (cb[2] or "").lower()
                    obj_a = (ca[3] or "").lower()
                    obj_b = (cb[3] or "").lower()

                    contradiction = _check_contradiction_heuristic(
                        pred_a,
                        obj_a,
                        pred_b,
                        obj_b,
                    )

                    if contradiction:
                        contradictions.append(
                            {
                                "claim_a": {
                                    "id": ca[0],
                                    "subject": ca[1],
                                    "predicate": ca[2],
                                    "object": ca[3],
                                    "confidence": float(ca[4]) if ca[4] else None,
                                },
                                "claim_b": {
                                    "id": cb[0],
                                    "subject": cb[1],
                                    "predicate": cb[2],
                                    "object": cb[3],
                                    "confidence": float(cb[4]) if cb[4] else None,
                                },
                                "explanation": contradiction["explanation"],
                                "confidence": contradiction["confidence"],
                            }
                        )

                        if len(contradictions) >= limit:
                            break
                if len(contradictions) >= limit:
                    break
            if len(contradictions) >= limit:
                break

        return {
            "success": True,
            "contradictions": contradictions,
            "claims_checked": len(claims),
            "subjects_analyzed": len(subject_groups),
        }
    except Exception as e:
        logger.warning("detect_contradictions: %s", e)
        return {"success": False, "contradictions": [], "error": str(e)}


def _check_contradiction_heuristic(
    pred_a: str,
    obj_a: str,
    pred_b: str,
    obj_b: str,
) -> dict[str, Any] | None:
    """Heuristic contradiction detection between two claims about the same subject."""
    negation_pairs = [
        ("support", "oppose"),
        ("approve", "reject"),
        ("increase", "decrease"),
        ("rise", "fall"),
        ("gain", "lose"),
        ("win", "lose"),
        ("confirm", "deny"),
        ("agree", "disagree"),
        ("accept", "reject"),
        ("pass", "fail"),
        ("allow", "ban"),
        ("expand", "shrink"),
        ("strengthen", "weaken"),
        ("advance", "retreat"),
    ]

    for pos, neg in negation_pairs:
        if (pos in pred_a and neg in pred_b) or (neg in pred_a and pos in pred_b):
            return {
                "explanation": f"Opposing predicates: '{pred_a}' vs '{pred_b}'",
                "confidence": 0.8,
            }

    # Numeric contradiction: same predicate but different numbers
    nums_a = re.findall(r"\d+\.?\d*", obj_a)
    nums_b = re.findall(r"\d+\.?\d*", obj_b)
    if nums_a and nums_b and pred_a and pred_b:
        # Same verb/predicate but different numbers
        pred_words_a = set(pred_a.split())
        pred_words_b = set(pred_b.split())
        if pred_words_a & pred_words_b:
            try:
                val_a = float(nums_a[0])
                val_b = float(nums_b[0])
                if val_a != val_b and max(val_a, val_b) > 0:
                    diff_pct = abs(val_a - val_b) / max(val_a, val_b)
                    if diff_pct > 0.2:
                        return {
                            "explanation": f"Different figures: {val_a} vs {val_b} ({diff_pct:.0%} difference)",
                            "confidence": 0.6,
                        }
            except (ValueError, ZeroDivisionError):
                pass

    # Direct negation in predicate
    if "not " in pred_a and "not " not in pred_b and pred_a.replace("not ", "") == pred_b:
        return {"explanation": "Direct negation", "confidence": 0.9}
    if "not " in pred_b and "not " not in pred_a and pred_b.replace("not ", "") == pred_a:
        return {"explanation": "Direct negation", "confidence": 0.9}

    return None


# ---------------------------------------------------------------------------
# Completeness assessment
# ---------------------------------------------------------------------------


def assess_completeness(
    domain_key: str,
    topic: str | None = None,
    storyline_id: int | None = None,
    hours: int = 72,
) -> dict[str, Any]:
    """
    Assess how completely a topic or storyline is covered:
    - Number of distinct sources
    - Diversity of perspectives (sentiment spread)
    - Temporal coverage (are recent developments included?)
    - Key questions answered vs. unanswered

    Returns {completeness_score, source_diversity, temporal_coverage, gaps, assessment}.
    """
    schema = resolve_domain_schema(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    try:
        with conn.cursor() as cur:
            if storyline_id:
                # Articles from storyline
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.source_domain, a.published_at,
                           a.sentiment_score, COALESCE(a.metadata, '{{}}'::jsonb),
                           LEFT(a.content, 500)
                    FROM {schema}.storyline_articles sa
                    JOIN {schema}.articles a ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at DESC
                    """,
                    (storyline_id,),
                )
            elif topic:
                cur.execute(
                    f"""
                    SELECT a.id, a.title, a.source_domain, a.published_at,
                           a.sentiment_score, COALESCE(a.metadata, '{{}}'::jsonb),
                           LEFT(a.content, 500)
                    FROM {schema}.articles a
                    WHERE a.published_at >= %s
                      AND to_tsvector('english', COALESCE(a.title, '') || ' ' || COALESCE(a.content, ''))
                          @@ plainto_tsquery('english', %s)
                    ORDER BY a.published_at DESC
                    LIMIT 100
                    """,
                    (cutoff, topic),
                )
            else:
                conn.close()
                return {"success": False, "error": "Provide topic or storyline_id"}

            articles = cur.fetchall()

            # Get claims related to these articles
            article_ids = [a[0] for a in articles]
            claims = []
            if article_ids:
                cur.execute(
                    """
                    SELECT ec.subject_text, ec.predicate_text, ec.object_text, ec.confidence
                    FROM intelligence.extracted_claims ec
                    JOIN intelligence.contexts c ON c.id = ec.context_id
                    JOIN intelligence.article_to_context atc ON atc.context_id = c.id
                    WHERE atc.article_id = ANY(%s)
                    ORDER BY ec.confidence DESC NULLS LAST
                    LIMIT 30
                    """,
                    (article_ids,),
                )
                for row in cur.fetchall():
                    claims.append(
                        {
                            "subject": row[0] or "",
                            "predicate": row[1] or "",
                            "object": row[2] or "",
                            "confidence": float(row[3]) if row[3] is not None else None,
                        }
                    )

        conn.close()

        if not articles:
            return {
                "success": True,
                "completeness_score": 0.0,
                "source_diversity": {"unique_sources": 0, "score": 0.0},
                "temporal_coverage": {"score": 0.0},
                "sentiment_spread": {"score": 0.0},
                "gaps": ["No articles found for this topic"],
                "assessment": "No coverage found.",
                "article_count": 0,
            }

        # Source diversity
        sources = set()
        source_reliabilities = []
        for a in articles:
            src = a[2] or "unknown"
            sources.add(src)
            source_reliabilities.append(score_source_reliability(src)["score"])

        source_count = len(sources)
        source_diversity_score = min(1.0, source_count / 5)  # 5+ sources = perfect

        # Temporal coverage: how well-spread are articles over the time window?
        dates = [a[3] for a in articles if a[3]]
        if len(dates) >= 2:
            date_range = (max(dates) - min(dates)).total_seconds()
            window_seconds = hours * 3600
            temporal_score = min(1.0, date_range / max(window_seconds * 0.5, 1))
        elif dates:
            temporal_score = 0.3
        else:
            temporal_score = 0.0

        # Sentiment spread: diverse sentiments suggest multiple perspectives
        sentiments = [float(a[4]) for a in articles if a[4] is not None]
        if len(sentiments) >= 2:
            sent_range = max(sentiments) - min(sentiments)
            sentiment_score = min(1.0, sent_range / 0.5)  # 0.5+ range = diverse
        else:
            sentiment_score = 0.3

        # Identify gaps
        gaps = []
        if source_count < 3:
            gaps.append(f"Only {source_count} source(s) — limited corroboration potential")
        if len(articles) < 5:
            gaps.append(f"Only {len(articles)} article(s) — thin coverage")
        if temporal_score < 0.3:
            gaps.append("Temporal clustering — articles concentrated in a narrow time window")
        if sentiment_score < 0.3 and len(sentiments) >= 3:
            gaps.append("Uniform sentiment — missing alternative perspectives")
        if not claims:
            gaps.append("No structured claims extracted — factual analysis limited")

        # LLM completeness assessment (optional)
        llm_assessment = None
        if topic and claims:
            llm_assessment = _llm_completeness_check(
                topic,
                source_count,
                len(articles),
                claims,
            )

        # Composite score
        completeness_score = (
            source_diversity_score * 0.35
            + temporal_score * 0.25
            + sentiment_score * 0.2
            + (1.0 - min(len(gaps) / 5, 1.0)) * 0.2
        )

        assessment_text = llm_assessment.get("assessment", "") if llm_assessment else ""
        if not assessment_text:
            assessment_text = (
                f"Coverage from {source_count} source(s) across {len(articles)} articles. "
                f"{'Well-corroborated.' if source_count >= 3 else 'Limited source diversity.'} "
                f"{'Multiple perspectives represented.' if sentiment_score > 0.5 else 'Perspective diversity could be improved.'}"
            )

        return {
            "success": True,
            "completeness_score": round(completeness_score, 2),
            "source_diversity": {
                "unique_sources": source_count,
                "sources": list(sources),
                "average_reliability": round(
                    sum(source_reliabilities) / len(source_reliabilities), 2
                )
                if source_reliabilities
                else 0,
                "score": round(source_diversity_score, 2),
            },
            "temporal_coverage": {
                "article_count": len(articles),
                "date_range_hours": round((max(dates) - min(dates)).total_seconds() / 3600, 1)
                if len(dates) >= 2
                else 0,
                "score": round(temporal_score, 2),
            },
            "sentiment_spread": {
                "min": round(min(sentiments), 2) if sentiments else None,
                "max": round(max(sentiments), 2) if sentiments else None,
                "score": round(sentiment_score, 2),
            },
            "claims_count": len(claims),
            "gaps": gaps,
            "assessment": assessment_text,
            "llm_assessment": llm_assessment,
            "article_count": len(articles),
        }
    except Exception as e:
        logger.warning("assess_completeness: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def _llm_completeness_check(
    topic: str,
    source_count: int,
    article_count: int,
    claims: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Use LLM to assess completeness (optional enhancement)."""
    claims_text = "\n".join(f"- {c['subject']} {c['predicate']} {c['object']}" for c in claims[:10])

    try:
        from shared.services.llm_service import LLMService

        llm = LLMService()
        prompt = COMPLETENESS_PROMPT.format(
            topic=topic,
            source_count=source_count,
            article_count=article_count,
            claims_text=claims_text,
        )
        response = llm.generate(prompt, max_tokens=400)
        if response:
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0]
            return json.loads(cleaned)
    except Exception as e:
        logger.debug("LLM completeness check: %s", e)

    return None


# ---------------------------------------------------------------------------
# Verify a specific claim (full pipeline)
# ---------------------------------------------------------------------------


def verify_claim(
    claim_id: int,
    domain_key: str,
    hours: int = 72,
) -> dict[str, Any]:
    """
    Full verification pipeline for a single extracted claim:
      1. Load claim (+ originating article URL / feed name for credibility)
      2. Corroboration (governance-weighted, excludes originating article)
      3. Contradictions among recent claims
      4. Reference signals: Wikipedia, Wikidata (incl. year overlap), GDELT mention density,
         finance SEC-hosted articles (finance domain), internal same-subject claims
      5. Optional LLM entailment when corroboration is borderline
      6. Combined verification_status + confidence (caps on weak signals)
    """
    from shared.services.source_credibility_service import resolve_source_credibility

    schema = resolve_domain_schema(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, subject_text, predicate_text, object_text, confidence, context_id
                FROM intelligence.extracted_claims
                WHERE id = %s
                """,
                (claim_id,),
            )
            claim_row = cur.fetchone()
            if not claim_row:
                conn.close()
                return {"success": False, "error": f"Claim {claim_id} not found"}

            claim = {
                "id": claim_row[0],
                "subject": claim_row[1] or "",
                "predicate": claim_row[2] or "",
                "object": claim_row[3] or "",
                "confidence": float(claim_row[4]) if claim_row[4] else None,
                "context_id": claim_row[5],
            }

            source_type = None
            cur.execute(
                """
                SELECT c.source_type, c.domain_key FROM intelligence.contexts c
                WHERE c.id = %s
                """,
                (claim["context_id"],),
            )
            ctx_row = cur.fetchone()
            if ctx_row:
                source_type = ctx_row[0]

            orig_url = ""
            orig_feed_name = ""
            cur.execute(
                """
                SELECT atc.article_id FROM intelligence.article_to_context atc
                WHERE atc.context_id = %s
                LIMIT 1
                """,
                (claim["context_id"],),
            )
            link = cur.fetchone()
            if link and link[0]:
                aid = link[0]
                cur.execute(
                    f"""
                    SELECT url, source_domain FROM {schema}.articles
                    WHERE id = %s
                    """,
                    (aid,),
                )
                arow = cur.fetchone()
                if arow:
                    orig_url = (arow[0] or "")[:2000]
                    orig_feed_name = (arow[1] or "")[:500]

        conn.close()

        claim_text = f"{claim['subject']} {claim['predicate']} {claim['object']}"

        corroboration = corroborate_claim(claim_text, domain_key, hours=hours, claim_id=claim_id)

        contradictions = detect_contradictions(domain_key, hours=hours, limit=10)
        related_contradictions = [
            c
            for c in contradictions.get("contradictions", [])
            if c["claim_a"]["id"] == claim_id or c["claim_b"]["id"] == claim_id
        ]

        gov_orig = resolve_source_credibility(orig_url, orig_feed_name)
        legacy_orig = score_source_reliability(orig_feed_name or source_type or "")
        source_reliability = {
            "score": round(
                min(1.0, (float(gov_orig.multiplier) + float(legacy_orig["score"])) / 2.0),
                3,
            ),
            "tier": legacy_orig["tier"],
            "governance_tier": gov_orig.tier_id,
            "governance_multiplier": float(gov_orig.multiplier),
            "source": orig_feed_name or source_type,
        }

        cor_status = corroboration.get("status") or "unverified"
        cor_conf = float(corroboration.get("confidence") or 0)

        if related_contradictions:
            verification_status = "contested"
            verification_confidence = max(
                0.3,
                cor_conf - max(c["confidence"] for c in related_contradictions) * 0.3,
            )
        elif cor_status == "corroborated":
            verification_status = "corroborated"
            verification_confidence = cor_conf
        elif cor_status == "authoritative_single":
            verification_status = "corroborated"
            verification_confidence = cor_conf
        elif cor_status == "partially_corroborated":
            verification_status = "partially_verified"
            verification_confidence = cor_conf
        elif cor_status == "single_established":
            verification_status = "partially_verified"
            verification_confidence = cor_conf
        elif cor_status == "single_source" and cor_conf >= 0.35:
            verification_status = "partially_verified"
            verification_confidence = cor_conf
        else:
            verification_status = "unverified"
            verification_confidence = min(
                float(source_reliability["score"]) * 0.5,
                float(claim.get("confidence") or 0.5),
            )

        wiki_check = wikipedia_reference_check(claim_text, claim.get("subject"))
        wikidata_check = wikidata_reference_check(claim_text, claim.get("subject"))
        gdelt_check = gdelt_mention_signal(claim_text, claim.get("subject"))
        sec_check = (
            finance_sec_articles_signal(claim_text, domain_key)
            if domain_key == "finance"
            else {"status": "skipped_domain", "match_count": 0}
        )
        internal_sim = count_internal_similar_claims(
            claim_id, claim.get("subject") or "", domain_key, hours=max(24, hours * 2)
        )
        reference_checks = {
            "wikipedia": wiki_check,
            "wikidata": wikidata_check,
            "gdelt": gdelt_check,
            "finance_sec_articles": sec_check,
            "internal_similar_subject_claims": internal_sim,
        }

        boost_reason: list[str] = []
        if verification_status == "unverified":
            ws = wiki_check.get("status")
            if ws == "supported":
                verification_status = "partially_verified"
                verification_confidence = max(verification_confidence, 0.42)
                boost_reason.append("wikipedia_overlap_strong")
            elif ws == "weak_support":
                verification_status = "partially_verified"
                verification_confidence = max(verification_confidence, 0.36)
                boost_reason.append("wikipedia_overlap_weak")
            wd = wikidata_check.get("status")
            if wd == "supported":
                verification_status = "partially_verified"
                verification_confidence = max(verification_confidence, 0.43)
                boost_reason.append("wikidata_overlap_strong")
            elif wd == "weak_support":
                verification_status = "partially_verified"
                verification_confidence = max(verification_confidence, 0.37)
                boost_reason.append("wikidata_overlap_weak")
            elif wikidata_check.get("dated_year_overlap") and wd != "low_overlap":
                verification_status = "partially_verified"
                verification_confidence = max(verification_confidence, 0.35)
                boost_reason.append("wikidata_year_alignment")
            ic = int(internal_sim.get("count") or 0)
            if ic >= 2:
                verification_status = "partially_verified"
                verification_confidence = max(
                    verification_confidence,
                    min(0.55, 0.35 + 0.04 * min(ic, 5)),
                )
                boost_reason.append("internal_subject_peers")

        if verification_status == "partially_verified":
            if wikidata_check.get("status") == "supported":
                verification_confidence = min(
                    0.78, verification_confidence + 0.03
                )
                boost_reason.append("wikidata_partial_boost")

        if gdelt_check.get("status") == "ok" and int(gdelt_check.get("doc_count") or 0) >= 5:
            delta = min(
                0.04,
                float(gdelt_check.get("signal_strength") or 0) * 0.055,
            )
            if delta > 0.008:
                verification_confidence = min(0.82, verification_confidence + delta)
                boost_reason.append("gdelt_mention_density")

        if (
            sec_check.get("status") == "ok"
            and int(sec_check.get("match_count") or 0) >= 1
        ):
            verification_confidence = min(0.85, verification_confidence + 0.05)
            boost_reason.append("finance_sec_article_match")

        entailment_context_parts: list[str] = []
        if wiki_check.get("title"):
            entailment_context_parts.append(f"Wikipedia article: {wiki_check.get('title')}")
        if wikidata_check.get("label"):
            entailment_context_parts.append(
                f"Wikidata: {wikidata_check.get('label')} ({wikidata_check.get('id')})"
            )
        entailment_check = entailment_llm_borderline_check(
            claim_text,
            corroboration,
            extra_context="\n".join(entailment_context_parts),
        )
        reference_checks["entailment_llm"] = entailment_check

        if entailment_check.get("status") == "ok":
            ev = str(entailment_check.get("verdict") or "")
            emc = float(entailment_check.get("model_confidence") or 0)
            if ev == "supports" and emc >= 0.55:
                if verification_status == "unverified":
                    verification_status = "partially_verified"
                verification_confidence = max(
                    verification_confidence,
                    min(0.72, 0.45 + 0.22 * emc),
                )
                boost_reason.append("llm_entailment_supports")
            elif ev == "contradicts" and emc >= 0.72 and verification_status != "corroborated":
                verification_status = "contested"
                verification_confidence = min(verification_confidence, 0.38)
                boost_reason.append("llm_entailment_contradicts")

        return {
            "success": True,
            "claim": claim,
            "verification_status": verification_status,
            "verification_confidence": round(float(verification_confidence), 2),
            "corroboration": corroboration,
            "contradictions": related_contradictions,
            "source_reliability": source_reliability,
            "reference_checks": reference_checks,
            "reference_boosts": boost_reason,
        }
    except Exception as e:
        logger.warning("verify_claim: %s", e)
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Batch verification
# ---------------------------------------------------------------------------


def verify_recent_claims(
    domain_key: str,
    hours: int = 24,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Verify the most recent high-confidence claims in a domain.
    Returns summary statistics and per-claim verification results.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT ec.id
                FROM intelligence.extracted_claims ec
                JOIN intelligence.contexts c ON c.id = ec.context_id
                WHERE c.domain_key = %s
                  AND ec.created_at >= NOW() - (%s * INTERVAL '1 hour')
                  AND ec.confidence >= 0.5
                ORDER BY ec.confidence DESC, ec.created_at DESC
                LIMIT %s
                """,
                (domain_key, hours, limit),
            )
            claim_ids = [row[0] for row in cur.fetchall()]
        conn.close()

        if not claim_ids:
            return {"success": True, "claims_verified": 0, "results": []}

        results = []
        status_counts: dict[str, int] = defaultdict(int)

        for cid in claim_ids:
            r = verify_claim(cid, domain_key, hours=hours * 3)
            status = r.get("verification_status", "error")
            status_counts[status] += 1
            results.append(
                {
                    "claim_id": cid,
                    "claim_text": f"{r.get('claim', {}).get('subject', '')} {r.get('claim', {}).get('predicate', '')} {r.get('claim', {}).get('object', '')}",
                    "status": status,
                    "confidence": r.get("verification_confidence", 0),
                    "source_count": r.get("corroboration", {}).get("source_count", 0),
                    "contradiction_count": len(r.get("contradictions", [])),
                    "corroboration_status": r.get("corroboration", {}).get("status"),
                    "reference_boosts": r.get("reference_boosts") or [],
                }
            )

        return {
            "success": True,
            "claims_verified": len(results),
            "status_summary": dict(status_counts),
            "results": results,
        }
    except Exception as e:
        logger.warning("verify_recent_claims: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}
