"""
Watch pattern service — Phase 4 RAG. Defines pattern types by story category,
matches them against recent content, records pattern_matches, and generates
watchlist_alerts when significance exceeds threshold.
See docs/RAG_ENHANCEMENT_ROADMAP.md.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

# Default keywords by story_type for keyword pattern matching
PATTERN_KEYWORDS_BY_STORY_TYPE: dict[str, list[str]] = {
    "court_case": [
        "verdict",
        "ruling",
        "decision",
        "convict",
        "acquit",
        "sentence",
        "testify",
        "testimony",
        "hearing",
        "filing",
        "brief",
        "motion",
        "appeal",
        "indictment",
        "settlement",
        "trial",
    ],
    "election": [
        "poll",
        "polls",
        "debate",
        "primary",
        "convention",
        "endorsement",
        "endorse",
        "announce",
        "candidate",
        "vote",
        "ballot",
        "result",
    ],
    "person_tenure": [
        "resign",
        "resignation",
        "appoint",
        "appointment",
        "nominate",
        "confirm",
        "oust",
        "remove",
        "replace",
        "successor",
    ],
    "economic_event": [
        "merger",
        "acquisition",
        "bankruptcy",
        "earnings",
        "forecast",
        "guidance",
        "layoff",
        "cut",
        "rate",
        "fed",
        "interest",
    ],
}

DEFAULT_STORY_TYPE = "person_tenure"
SIGNIFICANCE_THRESHOLD_ALERT = 0.5
MATCH_LOOKBACK_HOURS = 24


def _match_keywords(text: str, keywords: list[str]) -> list[tuple[str, float]]:
    """Return list of (matched_phrase, significance) for keywords found in text (case-insensitive)."""
    if not text or not keywords:
        return []
    text_lower = text.lower()
    results = []
    for kw in keywords:
        if kw.lower() in text_lower:
            # Simple significance: 0.5 base + 0.1 per extra occurrence
            count = text_lower.count(kw.lower())
            sig = min(1.0, 0.5 + (count - 1) * 0.1)
            results.append((kw, sig))
    return results


def match_content(text: str, story_type: str) -> list[tuple[str, str, float]]:
    """
    Match text against default keywords for story_type.
    Returns list of (pattern_type, matched_text, significance_score).
    """
    keywords = (
        PATTERN_KEYWORDS_BY_STORY_TYPE.get(story_type)
        or PATTERN_KEYWORDS_BY_STORY_TYPE.get(DEFAULT_STORY_TYPE)
        or []
    )
    matches = _match_keywords(text, keywords)
    return [("keyword", m[0], m[1]) for m in matches]


def run_pattern_matching(
    domain_key: str,
    storyline_id: int | None = None,
    limit: int = 50,
    significance_threshold: float = SIGNIFICANCE_THRESHOLD_ALERT,
) -> dict[str, Any]:
    """
    Fetch recent content (contexts or versioned_facts) for domain (and optional storyline),
    run keyword matching by story_type, persist pattern_matches, and create watchlist_alerts
    when storyline is on watchlist and significance >= threshold.
    Returns counts: contexts_checked, matches_stored, alerts_created.
    """
    conn = get_db_connection()
    if not conn:
        return {
            "contexts_checked": 0,
            "matches_stored": 0,
            "alerts_created": 0,
            "errors": ["no_db"],
        }

    result: dict[str, Any] = {
        "contexts_checked": 0,
        "matches_stored": 0,
        "alerts_created": 0,
        "errors": [],
    }
    try:
        schema = {"politics": "politics", "finance": "finance", "science-tech": "science_tech"}.get(
            domain_key, domain_key.replace("-", "_")
        )
        since = (datetime.now(timezone.utc) - timedelta(hours=MATCH_LOOKBACK_HOURS)).isoformat()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT c.id, c.title, c.content, c.domain_key
                FROM intelligence.contexts c
                WHERE c.updated_at >= %s::timestamptz
                  AND (c.domain_key = %s OR c.domain_key IS NULL)
                ORDER BY c.updated_at DESC
                LIMIT %s
                """,
                (since, domain_key, limit),
            )
            rows = cur.fetchall()
        result["contexts_checked"] = len(rows)

        story_type = DEFAULT_STORY_TYPE
        for ctx_id, title, content, _domain in rows:
            storyline_ids = _resolve_context_to_storylines(conn, schema, domain_key, ctx_id)
            if not storyline_ids and storyline_id is not None:
                storyline_ids = [storyline_id]
            elif not storyline_ids:
                storyline_ids = [None]

            text = f"{title or ''} {content or ''}"[:10000]
            for _ptype, matched_text, score in match_content(text, story_type):
                if score < 0.3:
                    continue
                for sid in storyline_ids:
                    try:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO intelligence.pattern_matches
                                (domain_key, storyline_id, content_ref_type, content_ref_id, matched_text, significance_score)
                                VALUES (%s, %s, 'context', %s, %s, %s)
                                RETURNING id
                                """,
                                (domain_key, sid, ctx_id, matched_text[:500], score),
                            )
                            mid = cur.fetchone()[0]
                        result["matches_stored"] += 1
                        if score >= significance_threshold and sid is not None:
                            created = _create_watchlist_alert_for_storyline(
                                conn, domain_key, sid, matched_text, score
                            )
                            if created:
                                result["alerts_created"] += 1
                                with conn.cursor() as cur2:
                                    cur2.execute(
                                        "UPDATE intelligence.pattern_matches SET alert_created = TRUE WHERE id = %s",
                                        (mid,),
                                    )
                    except Exception as e:
                        result["errors"].append(str(e))
                        logger.debug("pattern match insert: %s", e)

        conn.commit()
    except Exception as e:
        logger.warning("run_pattern_matching failed: %s", e)
        result["errors"].append(str(e))
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()
    return result


def _resolve_context_to_storylines(
    conn, schema: str, domain_key: str, context_id: int
) -> list[int | None]:
    """Resolve context_id -> article_id -> storyline_ids via article_to_context and schema.storyline_articles."""
    out: list[int | None] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT article_id FROM intelligence.article_to_context WHERE context_id = %s AND domain_key = %s",
                (context_id, domain_key),
            )
            row = cur.fetchone()
        if not row:
            return out
        article_id = row[0]
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT storyline_id FROM {schema}.storyline_articles WHERE article_id = %s",
                (article_id,),
            )
            for r in cur.fetchall():
                out.append(r[0])
    except Exception as e:
        logger.debug("resolve context to storylines: %s", e)
    return out


def _create_watchlist_alert_for_storyline(
    conn, domain_key: str, storyline_id: int, matched_text: str, score: float
) -> bool:
    """If storyline is on watchlist, insert watchlist_alert (pattern_match). Return True if inserted."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM watchlist WHERE storyline_id = %s",
                (storyline_id,),
            )
            row = cur.fetchone()
        if not row:
            return False
        watchlist_id = row[0]
        title = f"Pattern match: {matched_text[:80]}"
        body = f"Matched '{matched_text}' (significance {score:.2f}). Domain: {domain_key}."
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO watchlist_alerts (watchlist_id, storyline_id, alert_type, title, body)
                VALUES (%s, %s, 'pattern_match', %s, %s)
                """,
                (watchlist_id, storyline_id, title, body),
            )
            inserted = cur.rowcount
        return inserted > 0
    except Exception as e:
        logger.debug("create watchlist alert: %s", e)
        return False


def run_pattern_matching_all_domains(limit_per_domain: int = 30) -> dict[str, Any]:
    """Run pattern matching for each domain. Returns combined counts and per-domain results."""
    combined = {"contexts_checked": 0, "matches_stored": 0, "alerts_created": 0, "by_domain": {}}
    for domain in ("politics", "finance", "science-tech"):
        r = run_pattern_matching(domain_key=domain, limit=limit_per_domain)
        combined["contexts_checked"] += r.get("contexts_checked", 0)
        combined["matches_stored"] += r.get("matches_stored", 0)
        combined["alerts_created"] += r.get("alerts_created", 0)
        combined["by_domain"][domain] = r
    return combined
