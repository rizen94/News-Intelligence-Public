"""
Narrative-first storyline linking — attach new article clusters to existing conflict
narratives before creating headline-scale storylines.

Signals (in priority order):
1. Open ``intelligence.tracked_events`` with entity + geography + event-type overlap
2. Existing domain storylines (incl. mega parents) with entity/event/geo overlap
3. Consolidation remains the periodic backup for missed pairs
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from config.runtime import env_bool, env_float, env_str
from shared.domain_registry import resolve_domain_schema

logger = logging.getLogger(__name__)

_GEO_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "from",
        "war",
        "crisis",
        "conflict",
        "news",
        "update",
        "latest",
    }
)

_CONFLICT_FAMILY = frozenset(
    {
        "conflict",
        "military_action",
        "diplomatic",
        "protest",
        "investigation",
        "policy_decision",
        "legislation",
        "public_statement",
        "economic_event",
        "election",
        "agreement",
        "death",
    }
)


@dataclass
class NarrativeMatchResult:
    storyline_id: int
    score: float
    match_source: str
    reason: str
    tracked_event_id: int | None = None


def narrative_linking_enabled() -> bool:
    return env_bool("NARRATIVE_FIRST_LINKING_ENABLED", True)


def _min_match_score() -> float:
    try:
        return max(0.2, min(0.9, float(env_str("NARRATIVE_FIRST_LINK_MIN_SCORE", "0.38"))))
    except (TypeError, ValueError):
        return 0.42


def _oversized_storyline_article_count() -> int:
    try:
        return max(50, int(env_str("NARRATIVE_OVERSIZED_STORYLINE_ARTICLES", "250")))
    except (TypeError, ValueError):
        return 250


def _tokenize(text: str) -> set[str]:
    if not text:
        return set()
    return {
        t
        for t in re.findall(r"[a-z0-9]{3,}", text.lower())
        if t not in _GEO_STOP and not t.isdigit()
    }


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _event_types_compatible(a: str | None, b: str | None) -> bool:
    if not a or not b:
        return True
    a = a.strip().lower()
    b = b.strip().lower()
    if a == b:
        return True
    try:
        from services.story_continuation_service import EVENT_TYPE_COMPATIBILITY

        compat = EVENT_TYPE_COMPATIBILITY.get(a, {a})
        return b in compat or b == "other"
    except Exception:
        return a == b or a in _CONFLICT_FAMILY and b in _CONFLICT_FAMILY


def _canonical_ids_for_articles(schema: str, article_ids: list[int]) -> set[int]:
    if not article_ids:
        return set()
    from shared.database.connection import get_db_connection_context

    ids: set[int] = set()
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT DISTINCT ae.canonical_entity_id
                    FROM {schema}.article_entities ae
                    WHERE ae.article_id = ANY(%s)
                      AND ae.canonical_entity_id IS NOT NULL
                    """,
                    (article_ids,),
                )
                ids = {int(r[0]) for r in cur.fetchall() if r[0] is not None}
    except Exception as e:
        logger.debug("narrative_link canonical_ids: %s", e)
    return ids


def _canonical_ids_from_profile_ids(profile_ids: set[int]) -> set[int]:
    if not profile_ids:
        return set()
    from shared.database.connection import get_db_connection_context

    out: set[int] = set()
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT canonical_entity_id
                    FROM intelligence.entity_profiles
                    WHERE id = ANY(%s) AND canonical_entity_id IS NOT NULL
                    """,
                    (list(profile_ids),),
                )
                out = {int(r[0]) for r in cur.fetchall() if r[0] is not None}
    except Exception as e:
        logger.debug("narrative_link profile_to_canonical: %s", e)
    return out


def _canonical_ids_for_entity_names(schema: str, names: list[str]) -> set[int]:
    if not names:
        return set()
    from shared.database.connection import get_db_connection_context

    out: set[int] = set()
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for name in names[:25]:
                    token = (name or "").strip().lower()
                    if len(token) < 2:
                        continue
                    cur.execute(
                        f"""
                        SELECT id FROM {schema}.entity_canonical
                        WHERE lower(canonical_name) = %s
                           OR lower(canonical_name) LIKE %s
                        LIMIT 3
                        """,
                        (token, f"%{token}%"),
                    )
                    for (eid,) in cur.fetchall():
                        out.add(int(eid))
    except Exception as e:
        logger.debug("narrative_link entity_names: %s", e)
    return out


def _event_types_for_articles(article_ids: list[int]) -> set[str]:
    if not article_ids:
        return set()
    from shared.database.connection import get_db_connection_context

    types: set[str] = set()
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT lower(event_type)
                    FROM public.chronological_events
                    WHERE source_article_id = ANY(%s)
                      AND event_type IS NOT NULL
                    """,
                    (article_ids,),
                )
                types = {str(r[0]) for r in cur.fetchall() if r[0]}
    except Exception as e:
        logger.debug("narrative_link event_types: %s", e)
    return types


def _parse_storyline_ref(storyline_id_val: str | None) -> tuple[str, int] | None:
    if not storyline_id_val:
        return None
    raw = str(storyline_id_val).strip()
    if ":" in raw:
        schema_part, id_part = raw.split(":", 1)
        try:
            return schema_part, int(id_part)
        except ValueError:
            return None
    try:
        return "", int(raw)
    except ValueError:
        return None


def _score_tracked_events(
    domain_key: str,
    schema: str,
    canonical_ids: set[int],
    geo_tokens: set[str],
    event_types: set[str],
) -> list[tuple[float, int, int | None, str]]:
    """Returns (score, tracked_event_id, storyline_id_or_none, reason)."""
    from shared.database.connection import get_db_connection_context

    results: list[tuple[float, int, int | None, str]] = []
    if not canonical_ids and not geo_tokens:
        return results

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, event_type, event_name, geographic_scope,
                           COALESCE(key_participant_entity_ids, '[]'::jsonb),
                           storyline_id, domain_keys
                    FROM intelligence.tracked_events
                    WHERE (
                        %s = ANY(COALESCE(domain_keys, ARRAY[]::text[]))
                        OR COALESCE(domain_keys, ARRAY[]::text[]) = '{}'::text[]
                    )
                    ORDER BY id DESC
                    LIMIT 80
                    """,
                    (domain_key,),
                )
                rows = cur.fetchall()
    except Exception as e:
        logger.debug("narrative_link tracked_events: %s", e)
        return results

    for row in rows:
        te_id = int(row[0])
        te_type = (row[1] or "").lower()
        te_name = row[2] or ""
        te_geo = _tokenize(row[3] or "")
        te_geo |= _tokenize(te_name)
        profile_raw = row[4]
        storyline_ref = row[5]

        try:
            profile_ids = (
                json.loads(profile_raw)
                if isinstance(profile_raw, str)
                else (profile_raw or [])
            )
            te_profile_ids = {int(x) for x in profile_ids if x is not None}
            te_profiles = _canonical_ids_from_profile_ids(te_profile_ids)
        except Exception:
            te_profiles = set()

        entity_score = 0.0
        if canonical_ids and te_profiles:
            union = canonical_ids | te_profiles
            entity_score = len(canonical_ids & te_profiles) / len(union)

        geo_score = _jaccard(geo_tokens, te_geo) if geo_tokens and te_geo else 0.0

        type_score = 0.0
        if event_types:
            if any(_event_types_compatible(te_type, et) for et in event_types):
                type_score = 1.0
        elif te_type in _CONFLICT_FAMILY:
            type_score = 0.5

        score = 0.45 * entity_score + 0.30 * geo_score + 0.25 * type_score
        if entity_score >= 0.15 and geo_score >= 0.1:
            score += 0.08
        if te_type in _CONFLICT_FAMILY and ("iran" in te_geo or "iran" in geo_tokens):
            score += 0.05

        if score < 0.25 and entity_score < 0.1:
            continue

        parsed_sl: int | None = None
        ref = _parse_storyline_ref(storyline_ref)
        if ref and (not ref[0] or ref[0] == schema):
            parsed_sl = ref[1]

        reason = (
            f"tracked_event:{te_id} entity={entity_score:.2f} geo={geo_score:.2f} "
            f"type={te_type}"
        )
        results.append((score, te_id, parsed_sl, reason))

    results.sort(key=lambda x: x[0], reverse=True)
    return results


def _score_storylines(
    schema: str,
    canonical_ids: set[int],
    geo_tokens: set[str],
    event_types: set[str],
    title_hint: str | None,
) -> list[tuple[float, int, str]]:
    """Returns (score, storyline_id, reason)."""
    from shared.database.connection import get_db_connection_context

    results: list[tuple[float, int, str]] = []
    title_tokens = _tokenize(title_hint or "")

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT s.id, s.title, s.description,
                           COALESCE(s.is_mega_storyline, FALSE),
                           COALESCE(s.search_keywords, ARRAY[]::text[]),
                           COALESCE(s.key_entities::text, '{{}}'),
                           COALESCE(s.article_count, 0)
                    FROM {schema}.storylines s
                    WHERE s.merged_into_id IS NULL
                      AND COALESCE(s.status, 'active') NOT IN ('archived', 'merged')
                      AND s.created_at > NOW() - INTERVAL '120 days'
                    ORDER BY COALESCE(s.is_mega_storyline, FALSE) DESC,
                             s.updated_at DESC NULLS LAST
                    LIMIT 200
                    """,
                )
                storyline_rows = cur.fetchall()

                entity_overlap: dict[int, int] = {}
                if canonical_ids:
                    cur.execute(
                        f"""
                        SELECT sa.storyline_id, COUNT(DISTINCT ae.canonical_entity_id)
                        FROM {schema}.storyline_articles sa
                        JOIN {schema}.article_entities ae ON ae.article_id = sa.article_id
                        WHERE ae.canonical_entity_id = ANY(%s)
                        GROUP BY sa.storyline_id
                        """,
                        (list(canonical_ids),),
                    )
                    entity_overlap = {int(r[0]): int(r[1]) for r in cur.fetchall()}

                sl_event_types: dict[int, set[str]] = {}
                cur.execute(
                    f"""
                    SELECT sa.storyline_id, lower(ce.event_type)
                    FROM {schema}.storyline_articles sa
                    JOIN public.chronological_events ce ON ce.source_article_id = sa.article_id
                    WHERE ce.event_type IS NOT NULL
                      AND sa.storyline_id IN (
                          SELECT id FROM {schema}.storylines
                          WHERE merged_into_id IS NULL
                            AND created_at > NOW() - INTERVAL '120 days'
                      )
                    """,
                )
                for sl_id, et in cur.fetchall():
                    sl_event_types.setdefault(int(sl_id), set()).add(str(et))
    except Exception as e:
        logger.debug("narrative_link storylines: %s", e)
        return results

    oversized_threshold = _oversized_storyline_article_count()
    for row in storyline_rows:
        sl_id = int(row[0])
        title = row[1] or ""
        desc = row[2] or ""
        is_mega = bool(row[3])
        keywords = row[4] or []
        key_ent_raw = row[5] or "{}"
        article_count = int(row[6] or 0)
        is_oversized = article_count > oversized_threshold
        if is_oversized:
            is_mega = True

        sl_tokens = _tokenize(title) | _tokenize(desc)
        for kw in keywords:
            sl_tokens |= _tokenize(str(kw))
        try:
            key_ent = json.loads(key_ent_raw) if isinstance(key_ent_raw, str) else key_ent_raw
            if isinstance(key_ent, dict):
                for k in ("entities", "keywords"):
                    for item in key_ent.get(k) or []:
                        sl_tokens |= _tokenize(str(item))
        except Exception:
            pass

        overlap_n = entity_overlap.get(sl_id, 0)
        entity_score = 0.0
        if canonical_ids and overlap_n:
            entity_score = min(1.0, overlap_n / max(1, len(canonical_ids)))

        geo_score = _jaccard(geo_tokens | title_tokens, sl_tokens)
        title_score = _jaccard(title_tokens, _tokenize(title))

        type_score = 0.0
        sl_types = sl_event_types.get(sl_id, set())
        if event_types and sl_types:
            if any(
                _event_types_compatible(a, b) for a in event_types for b in sl_types
            ):
                type_score = 1.0
        elif sl_types & _CONFLICT_FAMILY and (
            event_types & _CONFLICT_FAMILY or geo_tokens
        ):
            type_score = 0.4

        score = (
            0.40 * entity_score
            + 0.28 * geo_score
            + 0.17 * title_score
            + 0.15 * type_score
        )
        if is_mega and entity_score >= 0.12:
            score += 0.10
        if is_oversized and entity_score < 0.35:
            continue
        if is_oversized:
            score -= 0.15
        if entity_score >= 0.25 and geo_score >= 0.15:
            score += 0.06

        if score < 0.22 and entity_score < 0.08:
            continue

        reason = (
            f"storyline:{sl_id} entity={entity_score:.2f} geo={geo_score:.2f} "
            f"mega={is_mega} oversized={is_oversized} articles={article_count}"
        )
        results.append((score, sl_id, reason))

    results.sort(key=lambda x: x[0], reverse=True)
    return results


def find_narrative_storyline_match(
    domain_key: str,
    *,
    article_ids: list[int],
    entity_names: list[str] | None = None,
    event_types: list[str] | None = None,
    geographic_terms: list[str] | None = None,
    title_hint: str | None = None,
) -> NarrativeMatchResult | None:
    """
    Find an existing narrative shell for a new cluster before creating a storyline.
  Returns None when no confident match (consolidation / discovery create path).
    """
    if not narrative_linking_enabled():
        return None

    schema = resolve_domain_schema(domain_key)
    aids = [int(x) for x in article_ids if int(x) > 0]
    if not aids and not entity_names:
        return None

    canonical_ids = _canonical_ids_for_articles(schema, aids)
    canonical_ids |= _canonical_ids_for_entity_names(schema, entity_names or [])

    inferred_types = set(event_types or []) | _event_types_for_articles(aids)
    inferred_types = {t.lower() for t in inferred_types if t}

    geo_tokens: set[str] = set()
    for term in geographic_terms or []:
        geo_tokens |= _tokenize(term)
    geo_tokens |= _tokenize(title_hint or "")
    for name in entity_names or []:
        if name and name[0].isupper() and len(name) > 3:
            geo_tokens |= _tokenize(name)

    min_score = _min_match_score()
    best: NarrativeMatchResult | None = None

    for score, te_id, sl_id, reason in _score_tracked_events(
        domain_key, schema, canonical_ids, geo_tokens, inferred_types
    ):
        if sl_id is not None and score >= min_score:
            best = NarrativeMatchResult(
                storyline_id=sl_id,
                score=score,
                match_source="tracked_event",
                reason=reason,
                tracked_event_id=te_id,
            )
            break

    if best is None:
        for score, sl_id, reason in _score_storylines(
            schema, canonical_ids, geo_tokens, inferred_types, title_hint
        ):
            if score >= min_score:
                best = NarrativeMatchResult(
                    storyline_id=sl_id,
                    score=score,
                    match_source="storyline_narrative",
                    reason=reason,
                )
                break

    if best:
        logger.info(
            "[%s] narrative-first match -> storyline %s (%.2f, %s)",
            domain_key,
            best.storyline_id,
            best.score,
            best.match_source,
        )
    return best


def attach_articles_to_storyline(
    domain_key: str,
    storyline_id: int,
    article_ids: list[int],
    *,
    relevance_score: float = 0.72,
) -> int:
    """Link articles to an existing storyline; returns count newly linked."""
    schema = resolve_domain_schema(domain_key)
    aids = [int(x) for x in article_ids if int(x) > 0]
    if not aids:
        return 0

    from shared.database.connection import get_db_connection_context
    from shared.storyline_article_counts import sync_counts_update_sql

    added = 0
    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                for aid in aids:
                    cur.execute(
                        f"""
                        INSERT INTO {schema}.storyline_articles
                        (storyline_id, article_id, relevance_score, created_at)
                        VALUES (%s, %s, %s, NOW())
                        ON CONFLICT DO NOTHING
                        """,
                        (storyline_id, aid, relevance_score),
                    )
                    if cur.rowcount:
                        added += 1
                if added:
                    cur.execute(
                        f"""
                        UPDATE {schema}.storylines
                        SET {sync_counts_update_sql(schema)},
                            updated_at = NOW(),
                            last_automation_run = NOW()
                        WHERE id = %s
                        """,
                        (storyline_id,),
                    )
            conn.commit()
    except Exception as e:
        logger.warning("narrative_link attach %s/%s: %s", domain_key, storyline_id, e)
    return added
