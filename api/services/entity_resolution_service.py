"""
Entity resolution service — enhanced disambiguation, alias population, and cross-domain linking.

Maps (domain, entity_name, entity_type) to canonical_entity_id in that domain's entity_canonical.
Used by article entity extraction, batch alias population, merge-candidate detection, and
cross-domain entity linking.

See docs/RAG_ENHANCEMENT_ROADMAP.md, docs/V6_QUALITY_FIRST_TODO.md T1.2.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from shared.database.connection import get_db_connection

logger = logging.getLogger(__name__)

DOMAIN_SCHEMA = {
    "politics": "politics",
    "finance": "finance",
    "science-tech": "science_tech",
}

ALL_DOMAINS = ["politics", "finance", "science-tech"]

TITLE_PREFIXES = re.compile(
    r"^(president|vice president|senator|rep\.|representative|"
    r"gov\.|governor|sec\.|secretary|dr\.|prof\.|judge|justice|"
    r"gen\.|general|adm\.|admiral|maj\.|major|ceo|cfo|coo|cto|"
    r"chairman|chairwoman|chair|speaker|mayor|minister|"
    r"prime minister|chancellor|king|queen|prince|princess)\s+",
    re.IGNORECASE,
)

ORG_SUFFIXES = re.compile(
    r"\s+(inc\.?|corp\.?|ltd\.?|llc|plc|co\.?|group|holdings|"
    r"corporation|company|enterprises|international|partners|"
    r"association|foundation|institute|committee)$",
    re.IGNORECASE,
)


def _schema_for_domain(domain_key: str) -> str:
    return DOMAIN_SCHEMA.get(domain_key, domain_key.replace("-", "_"))


def _normalize_name(name: str, entity_type: str) -> str:
    """Strip titles/suffixes and normalize whitespace for matching."""
    n = name.strip()
    if entity_type == "person":
        n = TITLE_PREFIXES.sub("", n).strip()
    elif entity_type == "organization":
        n = ORG_SUFFIXES.sub("", n).strip()
    return re.sub(r"\s+", " ", n)


# Last-word "surname" matching only applies when the last word is not a role/title.
# Otherwise "DXS International executives" and "Meta's executives" get merged incorrectly.
LAST_WORD_ROLE_BLOCKLIST = frozenset({
    "executives", "executive", "chair", "chairs", "board", "team", "teams",
    "spokesperson", "spokesman", "spokeswoman", "office", "leadership",
    "management", "staff", "officials", "representatives", "members",
    "committee", "commission", "division", "department", "unit", "group",
})


def _extract_last_name(name: str) -> Optional[str]:
    """For person entities, extract the last word as surname (if not a role word)."""
    parts = name.strip().split()
    if len(parts) >= 2:
        last = parts[-1].lower().rstrip("'s")
        if last not in LAST_WORD_ROLE_BLOCKLIST:
            return parts[-1]
    return None


def _name_ends_with_role_word(name: str) -> bool:
    """True if name's last word is in the role blocklist (e.g. 'X executives', 'Y chair')."""
    parts = name.strip().split()
    if not parts:
        return False
    last = parts[-1].lower().rstrip("'s")
    return last in LAST_WORD_ROLE_BLOCKLIST


# ---------------------------------------------------------------------------
# Core resolution (enhanced with title stripping + last-name fallback)
# ---------------------------------------------------------------------------

def resolve_to_canonical(
    domain_key: str,
    entity_name: str,
    entity_type: str,
    create_if_missing: bool = True,
) -> Optional[int]:
    """
    Resolve a mention to entity_canonical.id.

    Matching cascade:
      1. Exact canonical_name or alias (case-insensitive)
      2. Title-stripped name match (e.g., "President Biden" → "Joe Biden")
      3. If person and multi-word, last-name match against single-match canonicals

    On match at step 2/3, the mention name is added to aliases.
    If create_if_missing and no match, inserts a new canonical.
    """
    name = (entity_name or "").strip()
    if not name or len(name) < 2:
        return None
    etype = (entity_type or "person").strip().lower()
    if etype not in ("person", "organization", "subject", "recurring_event"):
        etype = "person"
    schema = _schema_for_domain(domain_key)

    conn = get_db_connection()
    if not conn:
        logger.warning("entity resolution: no DB connection")
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(f"SET search_path TO {schema}, public")

            # --- Step 1: exact match on canonical_name or alias ---
            cur.execute(
                f"""
                SELECT id FROM {schema}.entity_canonical
                WHERE entity_type = %s
                  AND (
                    LOWER(canonical_name) = LOWER(%s)
                    OR EXISTS (
                        SELECT 1 FROM unnest(COALESCE(aliases, '{{}}')) a
                        WHERE LOWER(a) = LOWER(%s)
                    )
                  )
                LIMIT 1
                """,
                (etype, name, name),
            )
            row = cur.fetchone()
            if row:
                conn.close()
                return row[0]

            # --- Step 2: title-stripped match ---
            stripped = _normalize_name(name, etype)
            if stripped.lower() != name.lower():
                cur.execute(
                    f"""
                    SELECT id FROM {schema}.entity_canonical
                    WHERE entity_type = %s
                      AND (
                        LOWER(canonical_name) = LOWER(%s)
                        OR EXISTS (
                            SELECT 1 FROM unnest(COALESCE(aliases, '{{}}')) a
                            WHERE LOWER(a) = LOWER(%s)
                        )
                      )
                    LIMIT 1
                    """,
                    (etype, stripped, stripped),
                )
                row = cur.fetchone()
                if row:
                    _add_alias(cur, schema, row[0], name)
                    conn.commit()
                    conn.close()
                    return row[0]

            # --- Step 3: last-name fallback for persons ---
            if etype == "person":
                last_name = _extract_last_name(stripped)
                if last_name and len(last_name) >= 3:
                    cur.execute(
                        f"""
                        SELECT id, canonical_name FROM {schema}.entity_canonical
                        WHERE entity_type = 'person'
                          AND (
                            LOWER(canonical_name) LIKE '%%' || LOWER(%s)
                            OR EXISTS (
                                SELECT 1 FROM unnest(COALESCE(aliases, '{{}}')) a
                                WHERE LOWER(a) LIKE '%%' || LOWER(%s)
                            )
                          )
                        """,
                        (f" {last_name}", f" {last_name}"),
                    )
                    candidates = cur.fetchall()
                    if len(candidates) == 1:
                        _add_alias(cur, schema, candidates[0][0], name)
                        conn.commit()
                        conn.close()
                        return candidates[0][0]

            if not create_if_missing:
                conn.close()
                return None

            cur.execute(
                f"""
                INSERT INTO {schema}.entity_canonical (canonical_name, entity_type, aliases)
                VALUES (%s, %s, ARRAY[%s]::TEXT[])
                ON CONFLICT (canonical_name, entity_type) DO UPDATE SET
                    updated_at = NOW()
                RETURNING id
                """,
                (name[:255], etype, name[:255]),
            )
            new_row = cur.fetchone()
            conn.commit()
            conn.close()
            return new_row[0] if new_row else None
    except Exception as e:
        logger.debug("entity resolution failed for %s/%s: %s", domain_key, name, e)
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return None


def _add_alias(cur, schema: str, canonical_id: int, alias: str) -> None:
    """Add an alias to entity_canonical if not already present."""
    cur.execute(
        f"""
        UPDATE {schema}.entity_canonical
        SET aliases = array_append(aliases, %s),
            updated_at = NOW()
        WHERE id = %s
          AND NOT (LOWER(%s) = ANY(
              SELECT LOWER(a) FROM unnest(COALESCE(aliases, '{{}}')) a
          ))
        """,
        (alias[:255], canonical_id, alias[:255]),
    )


# ---------------------------------------------------------------------------
# Resolve with candidates (API use — returns ranked matches, not just first)
# ---------------------------------------------------------------------------

def resolve_with_candidates(
    domain_key: str,
    entity_name: str,
    entity_type: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """
    Find canonical entities matching the mention, ranked by confidence.
    Returns {match: {id, canonical_name, confidence} | None, candidates: [...]}.
    """
    name = (entity_name or "").strip()
    if not name or len(name) < 2:
        return {"match": None, "candidates": []}
    etype = (entity_type or "person").strip().lower()
    if etype not in ("person", "organization", "subject", "recurring_event"):
        etype = "person"
    schema = _schema_for_domain(domain_key)
    stripped = _normalize_name(name, etype)
    last_name = _extract_last_name(stripped) if etype == "person" else None

    conn = get_db_connection()
    if not conn:
        return {"match": None, "candidates": [], "error": "Database connection failed"}

    try:
        candidates: List[Dict[str, Any]] = []
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, canonical_name, aliases
                FROM {schema}.entity_canonical
                WHERE entity_type = %s
                ORDER BY canonical_name
                """,
                (etype,),
            )
            rows = cur.fetchall()

        name_lower = name.lower()
        stripped_lower = stripped.lower()

        for cid, cname, aliases in rows:
            cname_lower = cname.lower()
            alias_lowers = [a.lower() for a in (aliases or [])]
            all_names = [cname_lower] + alias_lowers
            confidence = 0.0
            match_reason = ""

            if name_lower in all_names:
                confidence = 1.0
                match_reason = "exact_match"
            elif stripped_lower in all_names:
                confidence = 0.95
                match_reason = "title_stripped"
            elif any(name_lower in a or a in name_lower for a in all_names if len(a) >= 4):
                confidence = 0.7
                match_reason = "substring"
            elif last_name and any(a.endswith(f" {last_name.lower()}") for a in all_names):
                confidence = 0.6
                match_reason = "last_name"
            elif stripped_lower and any(
                _similarity(stripped_lower, a) > 0.7 for a in all_names
            ):
                confidence = 0.5
                match_reason = "fuzzy"

            if confidence > 0:
                candidates.append({
                    "canonical_entity_id": cid,
                    "canonical_name": cname,
                    "aliases": aliases or [],
                    "confidence": round(confidence, 2),
                    "match_reason": match_reason,
                })

        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        candidates = candidates[:limit]

        conn.close()
        best = candidates[0] if candidates and candidates[0]["confidence"] >= 0.9 else None
        return {"match": best, "candidates": candidates}
    except Exception as e:
        logger.warning("resolve_with_candidates: %s", e)
        try:
            conn.close()
        except Exception:
            pass
        return {"match": None, "candidates": [], "error": str(e)}


def _similarity(a: str, b: str) -> float:
    """Bigram similarity (Dice coefficient) — lightweight fuzzy matching."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    bigrams_a = set(a[i:i+2] for i in range(len(a) - 1))
    bigrams_b = set(b[i:i+2] for i in range(len(b) - 1))
    if not bigrams_a or not bigrams_b:
        return 0.0
    intersection = bigrams_a & bigrams_b
    return 2 * len(intersection) / (len(bigrams_a) + len(bigrams_b))


# ---------------------------------------------------------------------------
# Batch alias population — collect name variants from article_entities
# ---------------------------------------------------------------------------

def populate_aliases_from_mentions(
    domain_key: str,
    min_mentions: int = 2,
) -> Dict[str, Any]:
    """
    For each canonical entity in a domain, collect all distinct entity_name values
    from article_entities that point to it and add missing variants to aliases.
    Only adds variants seen in at least min_mentions articles.

    Returns {updated: N, new_aliases: N}.
    """
    schema = _schema_for_domain(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "updated": 0, "new_aliases": 0, "error": "Database connection failed"}

    try:
        updated = 0
        new_aliases = 0
        with conn.cursor() as cur:
            # Collect all name variants per canonical entity (above mention threshold)
            cur.execute(
                f"""
                SELECT ae.canonical_entity_id,
                       array_agg(DISTINCT ae.entity_name) AS mention_names
                FROM {schema}.article_entities ae
                WHERE ae.canonical_entity_id IS NOT NULL
                GROUP BY ae.canonical_entity_id
                HAVING COUNT(DISTINCT ae.entity_name) >= 1
                """,
            )
            rows = cur.fetchall()

            for canonical_id, mention_names in rows:
                if not mention_names:
                    continue

                # Get current aliases
                cur.execute(
                    f"SELECT aliases FROM {schema}.entity_canonical WHERE id = %s",
                    (canonical_id,),
                )
                arow = cur.fetchone()
                if not arow:
                    continue
                current_aliases = arow[0] or []
                current_lower = {a.lower() for a in current_aliases}

                # Find new aliases: mention names not yet in aliases (case-insensitive)
                to_add = []
                for mname in mention_names:
                    if mname and mname.lower() not in current_lower:
                        # Only add if this variant appears in enough articles
                        cur.execute(
                            f"""
                            SELECT COUNT(*) FROM {schema}.article_entities
                            WHERE canonical_entity_id = %s
                              AND LOWER(entity_name) = LOWER(%s)
                            """,
                            (canonical_id, mname),
                        )
                        cnt = cur.fetchone()[0]
                        if cnt >= min_mentions:
                            to_add.append(mname[:255])
                            current_lower.add(mname.lower())

                if to_add:
                    cur.execute(
                        f"""
                        UPDATE {schema}.entity_canonical
                        SET aliases = aliases || %s::TEXT[],
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (to_add, canonical_id),
                    )
                    updated += 1
                    new_aliases += len(to_add)

        conn.commit()
        conn.close()
        logger.info(
            "populate_aliases %s: %d entities updated, %d new aliases added",
            domain_key, updated, new_aliases,
        )
        return {"success": True, "updated": updated, "new_aliases": new_aliases}
    except Exception as e:
        logger.warning("populate_aliases %s: %s", domain_key, e)
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "updated": 0, "new_aliases": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Disambiguation — find merge candidates (likely-duplicate canonical entities)
# ---------------------------------------------------------------------------

def find_merge_candidates(
    domain_key: str,
    min_confidence: float = 0.5,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Find pairs of canonical entities within a domain that likely refer to the same
    real-world entity (different names, same person/org).

    Heuristics:
      - Shared name or alias (0.95)
      - Title-stripped names match (e.g. "King Trump" ↔ "Trump", "President Biden" ↔ "Joe Biden") (0.9)
      - Last-name match for persons: "Trump" ↔ "Donald Trump" (0.8), other same last name (0.75)
      - Substring overlap (0.7), bigram similarity ≥ 0.7

    For consolidating variants like Donald Trump / Donald J Trump / Trump / King Trump,
    use min_confidence=0.6 or 0.75; auto_merge then keeps the primary (full) name and
    merges others into it (variants become aliases).

    Returns {candidates: [{source_id, source_name, target_id, target_name, confidence, reason}]}.
    """
    schema = _schema_for_domain(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "candidates": [], "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, canonical_name, entity_type, aliases
                FROM {schema}.entity_canonical
                ORDER BY id
                """,
            )
            entities = cur.fetchall()
        conn.close()

        candidates: List[Dict[str, Any]] = []
        seen_pairs = set()

        for i, (id_a, name_a, type_a, aliases_a) in enumerate(entities):
            stripped_a = _normalize_name(name_a, type_a).lower()
            last_a = _extract_last_name(name_a)
            all_a = {name_a.lower(), stripped_a} | {
                a.lower() for a in (aliases_a or [])
            }

            for j in range(i + 1, len(entities)):
                id_b, name_b, type_b, aliases_b = entities[j]
                if type_a != type_b:
                    continue
                pair = (min(id_a, id_b), max(id_a, id_b))
                if pair in seen_pairs:
                    continue

                stripped_b = _normalize_name(name_b, type_b).lower()
                all_b = {name_b.lower(), stripped_b} | {
                    a.lower() for a in (aliases_b or [])
                }

                confidence = 0.0
                reason = ""

                # Check cross-set overlap (one entity's alias matches another's name)
                if all_a & all_b:
                    confidence = 0.95
                    reason = "shared_name_or_alias"
                elif stripped_a == stripped_b:
                    confidence = 0.9
                    reason = "title_stripped_match"
                elif type_a == "person" and last_a:
                    last_b = _extract_last_name(name_b)
                    if last_a and last_b and last_a.lower() == last_b.lower():
                        # Single word equals other's last name (e.g. "Trump" vs "Donald Trump") -> higher
                        words_a, words_b = len(name_a.split()), len(name_b.split())
                        if words_a == 1 or words_b == 1:
                            confidence = 0.8
                            reason = "last_name_match"
                        else:
                            confidence = 0.75
                            reason = "same_last_name"
                if confidence < min_confidence:
                    # Substring check
                    for na in all_a:
                        for nb in all_b:
                            if len(na) >= 4 and len(nb) >= 4:
                                if na in nb or nb in na:
                                    confidence = max(confidence, 0.7)
                                    reason = reason or "substring"
                    # Bigram similarity
                    if confidence < min_confidence:
                        sim = _similarity(stripped_a, stripped_b)
                        if sim >= 0.7:
                            confidence = max(confidence, sim * 0.8)
                            reason = reason or "fuzzy_similarity"

                if confidence >= min_confidence:
                    seen_pairs.add(pair)
                    candidates.append({
                        "source_id": id_a,
                        "source_name": name_a,
                        "target_id": id_b,
                        "target_name": name_b,
                        "entity_type": type_a,
                        "confidence": round(confidence, 2),
                        "reason": reason,
                    })

        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        return {"success": True, "candidates": candidates[:limit]}
    except Exception as e:
        logger.warning("find_merge_candidates %s: %s", domain_key, e)
        return {"success": False, "candidates": [], "error": str(e)}


def _choose_primary_entity(
    domain_key: str,
    id_a: int,
    name_a: str,
    id_b: int,
    name_b: str,
    entity_type: str,
) -> Tuple[int, int]:
    """
    Choose which of two same-entity canonicals to keep (primary) vs merge into it.
    Prefer: (1) longer/full name for persons (e.g. "Donald Trump" over "Trump"),
    (2) name not starting with a title ("Donald Trump" over "King Trump"),
    (3) higher article mention count. Returns (keep_id, merge_id).
    """
    schema = _schema_for_domain(domain_key)
    conn = get_db_connection()
    if not conn:
        return (id_a, id_b)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT canonical_entity_id, COUNT(*) FROM {schema}.article_entities
                WHERE canonical_entity_id IN (%s, %s)
                GROUP BY canonical_entity_id
                """,
                (id_a, id_b),
            )
            counts = {row[0]: row[1] for row in cur.fetchall()}
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return (id_a, id_b)
    count_a = counts.get(id_a, 0)
    count_b = counts.get(id_b, 0)
    words_a = len((name_a or "").split())
    words_b = len((name_b or "").split())
    stripped_a = _normalize_name(name_a or "", entity_type)
    stripped_b = _normalize_name(name_b or "", entity_type)
    # Prefer name that stayed longer after title strip (more "content")
    len_after_strip_a = len(stripped_a)
    len_after_strip_b = len(stripped_b)
    # Prefer the one that looks like a full name (more words) for person
    if entity_type == "person":
        if words_a > words_b:
            return (id_a, id_b)
        if words_b > words_a:
            return (id_b, id_a)
        if len_after_strip_a > len_after_strip_b:
            return (id_a, id_b)
        if len_after_strip_b > len_after_strip_a:
            return (id_b, id_a)
    if count_a >= count_b:
        return (id_a, id_b)
    return (id_b, id_a)


def merge_canonical_entities(
    domain_key: str,
    keep_id: int,
    merge_id: int,
) -> Dict[str, Any]:
    """
    Merge merge_id into keep_id within a domain:
      1. Add merge_id's canonical_name and aliases to keep_id's aliases
      2. Reassign article_entities.canonical_entity_id from merge_id → keep_id
      3. Delete merge_id from entity_canonical

    Returns {success, articles_reassigned, aliases_added}.
    """
    if keep_id == merge_id:
        return {"success": False, "error": "Cannot merge entity into itself"}

    schema = _schema_for_domain(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "Database connection failed"}

    try:
        with conn.cursor() as cur:
            # Get merge_id's name and aliases
            cur.execute(
                f"SELECT canonical_name, aliases FROM {schema}.entity_canonical WHERE id = %s",
                (merge_id,),
            )
            merge_row = cur.fetchone()
            if not merge_row:
                conn.close()
                return {"success": False, "error": f"Entity {merge_id} not found"}

            merge_name, merge_aliases = merge_row
            new_aliases = [merge_name]
            for a in (merge_aliases or []):
                if a not in new_aliases:
                    new_aliases.append(a)

            # Get keep_id's current aliases to avoid duplicates
            cur.execute(
                f"SELECT aliases FROM {schema}.entity_canonical WHERE id = %s",
                (keep_id,),
            )
            keep_row = cur.fetchone()
            if not keep_row:
                conn.close()
                return {"success": False, "error": f"Entity {keep_id} not found"}

            keep_aliases_lower = {a.lower() for a in (keep_row[0] or [])}
            aliases_to_add = [a for a in new_aliases if a.lower() not in keep_aliases_lower]

            if aliases_to_add:
                cur.execute(
                    f"""
                    UPDATE {schema}.entity_canonical
                    SET aliases = aliases || %s::TEXT[],
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (aliases_to_add, keep_id),
                )

            # Reassign article_entities
            cur.execute(
                f"""
                UPDATE {schema}.article_entities
                SET canonical_entity_id = %s
                WHERE canonical_entity_id = %s
                """,
                (keep_id, merge_id),
            )
            articles_reassigned = cur.rowcount

            # Update entity_profiles mapping if present (optional; use savepoint so failure doesn't abort transaction)
            try:
                cur.execute("SAVEPOINT sp_merge_old_entity")
                cur.execute(
                    """
                    UPDATE intelligence.old_entity_to_new
                    SET old_entity_id = %s
                    WHERE domain_key = %s AND old_entity_id = %s
                    """,
                    (keep_id, domain_key, merge_id),
                )
            except Exception:
                try:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_merge_old_entity")
                except Exception:
                    conn.rollback()
                    raise
            else:
                try:
                    cur.execute("RELEASE SAVEPOINT sp_merge_old_entity")
                except Exception:
                    pass

            # Delete the merged entity
            cur.execute(
                f"DELETE FROM {schema}.entity_canonical WHERE id = %s",
                (merge_id,),
            )

        conn.commit()
        conn.close()
        logger.info(
            "merge_canonical_entities %s: %d → %d, %d articles reassigned, %d aliases added",
            domain_key, merge_id, keep_id, articles_reassigned, len(aliases_to_add),
        )
        return {
            "success": True,
            "keep_id": keep_id,
            "merged_id": merge_id,
            "articles_reassigned": articles_reassigned,
            "aliases_added": len(aliases_to_add),
        }
    except Exception as e:
        logger.warning("merge_canonical_entities %s: %s", domain_key, e)
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "error": str(e)}


def auto_merge_high_confidence(
    domain_key: str,
    min_confidence: float = 0.9,
) -> Dict[str, Any]:
    """
    Find merge candidates above min_confidence and automatically merge them.
    Always keeps the "primary" entity (full name, e.g. "Donald Trump") and merges
    variants (e.g. "Trump", "King Trump") into it; sub-entities are tracked as aliases.
    Returns {merges_performed, details: [...]}.
    """
    result = find_merge_candidates(domain_key, min_confidence=min_confidence, limit=100)
    if not result.get("success"):
        return {"success": False, "merges_performed": 0, "error": result.get("error")}

    details: List[Dict[str, Any]] = []
    for candidate in result.get("candidates", []):
        if candidate["confidence"] >= min_confidence:
            keep_id, merge_id = _choose_primary_entity(
                domain_key,
                candidate["source_id"],
                candidate["source_name"],
                candidate["target_id"],
                candidate["target_name"],
                candidate.get("entity_type", "person"),
            )
            merge_result = merge_canonical_entities(domain_key, keep_id=keep_id, merge_id=merge_id)
            kept_name = candidate["source_name"] if keep_id == candidate["source_id"] else candidate["target_name"]
            merged_name = candidate["target_name"] if keep_id == candidate["source_id"] else candidate["source_name"]
            details.append({
                "kept": kept_name,
                "merged": merged_name,
                "confidence": candidate["confidence"],
                "reason": candidate["reason"],
                "result": merge_result,
            })

    return {
        "success": True,
        "merges_performed": len(details),
        "details": details,
    }


# ---------------------------------------------------------------------------
# Decouple role-word merges (split canonicals incorrectly merged by "same last name")
# ---------------------------------------------------------------------------

def split_role_merged_canonicals(
    domain_key: str,
    dry_run: bool = False,
    max_splits: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Find entity_canonical rows that have multiple role-word names (e.g. "X executives",
    "Y executives") and split them: create a new canonical per distinct role name and
    reassign article_entities by entity_name so each gets its own canonical. Removes
    the split names from the original canonical's aliases.

    Use after fixing LAST_WORD_ROLE_BLOCKLIST to undo incorrect merges.
    When dry_run=True, only compute and return what would be done; no DB writes.
    max_splits: cap splits per domain (None = no cap).
    Returns {success, split_count, canonicals_processed, details: [...], dry_run: bool}.
    """
    schema = _schema_for_domain(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "split_count": 0, "error": "Database connection failed", "dry_run": dry_run}

    details: List[Dict[str, Any]] = []
    split_count = 0
    canonicals_processed = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, canonical_name, entity_type, aliases FROM {schema}.entity_canonical",
            )
            rows = cur.fetchall()

        for (canonical_id, canonical_name, entity_type, aliases) in rows:
            if max_splits is not None and split_count >= max_splits:
                break
            all_names = [canonical_name] + list(aliases or [])
            role_names = [n for n in all_names if n and _name_ends_with_role_word(n)]
            if len(role_names) < 2:
                continue
            canonicals_processed += 1
            with conn.cursor() as cur:
                for alias_name in (aliases or []):
                    if max_splits is not None and split_count >= max_splits:
                        break
                    if not alias_name or not _name_ends_with_role_word(alias_name):
                        continue
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.article_entities
                        WHERE canonical_entity_id = %s AND LOWER(TRIM(entity_name)) = LOWER(TRIM(%s))
                        """,
                        (canonical_id, alias_name),
                    )
                    (cnt,) = cur.fetchone()
                    if cnt == 0:
                        continue
                    if dry_run:
                        details.append({
                            "canonical_id": canonical_id,
                            "canonical_name": canonical_name,
                            "split_off": alias_name,
                            "new_canonical_id": None,
                            "articles_reassigned": cnt,
                        })
                        split_count += 1
                        continue
                    cur.execute(
                        f"""
                        INSERT INTO {schema}.entity_canonical (canonical_name, entity_type, aliases)
                        VALUES (%s, %s, '{{}}')
                        ON CONFLICT (canonical_name, entity_type) DO UPDATE SET updated_at = NOW()
                        RETURNING id
                        """,
                        (alias_name[:255], entity_type),
                    )
                    new_row = cur.fetchone()
                    if not new_row:
                        continue
                    new_id = new_row[0]
                    cur.execute(
                        f"""
                        UPDATE {schema}.article_entities
                        SET canonical_entity_id = %s
                        WHERE canonical_entity_id = %s AND LOWER(TRIM(entity_name)) = LOWER(TRIM(%s))
                        """,
                        (new_id, canonical_id, alias_name),
                    )
                    reassigned = cur.rowcount
                    cur.execute(
                        f"""
                        UPDATE {schema}.entity_canonical
                        SET aliases = array_remove(aliases, %s), updated_at = NOW()
                        WHERE id = %s AND %s = ANY(COALESCE(aliases, '{{}}'))
                        """,
                        (alias_name, canonical_id, alias_name),
                    )
                    conn.commit()
                    split_count += 1
                    details.append({
                        "canonical_id": canonical_id,
                        "canonical_name": canonical_name,
                        "split_off": alias_name,
                        "new_canonical_id": new_id,
                        "articles_reassigned": reassigned,
                    })
    except Exception as e:
        logger.warning("split_role_merged_canonicals %s: %s", domain_key, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "split_count": split_count, "canonicals_processed": canonicals_processed, "error": str(e), "details": details, "dry_run": dry_run}
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return {
        "success": True,
        "split_count": split_count,
        "canonicals_processed": canonicals_processed,
        "details": details,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Entity decouple pipeline — routine bad-merge detection and split
# ---------------------------------------------------------------------------

DECOUPLE_STEP_ROLE_WORD = "role_word"

DEFAULT_DECOUPLE_STEPS = (DECOUPLE_STEP_ROLE_WORD,)


def run_entity_decouple_pipeline(
    domain_keys: Optional[List[str]] = None,
    dry_run: bool = False,
    steps: Optional[List[str]] = None,
    max_splits_per_domain: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Routine entity decouple: find bad merges and split them so each canonical
    represents a single real-world entity. Safe to run as part of data_cleanup.

    Steps (all run when steps is None):
      - role_word: split canonicals that merged distinct entities by shared
        role-word last name (e.g. "X executives" + "Y executives" → separate).

    Use from automation (data_cleanup), cron, or manual scripts.
    Returns {success, total_splits, by_domain: {domain: {split_count, canonicals_processed, ...}}, steps_run: [...]}.
    """
    domains = list(domain_keys) if domain_keys else list(ALL_DOMAINS)
    steps_to_run = list(steps) if steps else list(DEFAULT_DECOUPLE_STEPS)
    by_domain: Dict[str, Dict[str, Any]] = {}
    total_splits = 0

    for domain_key in domains:
        if domain_key not in ALL_DOMAINS:
            continue
        domain_result: Dict[str, Any] = {"split_count": 0, "canonicals_processed": 0}
        for step in steps_to_run:
            if step == DECOUPLE_STEP_ROLE_WORD:
                out = split_role_merged_canonicals(
                    domain_key,
                    dry_run=dry_run,
                    max_splits=max_splits_per_domain,
                )
                if out.get("success"):
                    domain_result["split_count"] = out.get("split_count", 0)
                    domain_result["canonicals_processed"] = out.get("canonicals_processed", 0)
                    total_splits += domain_result["split_count"]
                else:
                    domain_result["error"] = out.get("error", "unknown")
                    logger.warning("Decouple role_word %s: %s", domain_key, domain_result["error"])
                domain_result["role_word"] = out
            else:
                logger.debug("Decouple step %s not implemented, skipping", step)
        by_domain[domain_key] = domain_result

    return {
        "success": True,
        "total_splits": total_splits,
        "by_domain": by_domain,
        "steps_run": steps_to_run,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Cross-domain entity linking
# ---------------------------------------------------------------------------

def link_cross_domain_entities(
    min_confidence: float = 0.8,
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Find entities with the same canonical_name (or alias overlap) across different
    domain schemas and create cross_domain_same_entity relationships in
    intelligence.entity_relationships.

    Returns {linked: N, relationships_created: N}.
    """
    conn = get_db_connection()
    if not conn:
        return {"success": False, "linked": 0, "error": "Database connection failed"}

    try:
        domain_entities: Dict[str, List[Tuple[int, str, str, List[str]]]] = {}
        for domain_key in ALL_DOMAINS:
            schema = _schema_for_domain(domain_key)
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        f"""
                        SELECT id, canonical_name, entity_type, aliases
                        FROM {schema}.entity_canonical
                        ORDER BY id
                        """,
                    )
                    domain_entities[domain_key] = cur.fetchall()
                except Exception:
                    domain_entities[domain_key] = []

        # Find cross-domain matches
        relationships: List[Tuple[str, int, str, int, float, str]] = []
        domains = list(domain_entities.keys())

        for i in range(len(domains)):
            for j in range(i + 1, len(domains)):
                d1, d2 = domains[i], domains[j]
                for id1, name1, type1, aliases1 in domain_entities[d1]:
                    all_names_1 = {name1.lower()} | {a.lower() for a in (aliases1 or [])}
                    stripped_1 = _normalize_name(name1, type1).lower()

                    for id2, name2, type2, aliases2 in domain_entities[d2]:
                        if type1 != type2:
                            continue

                        all_names_2 = {name2.lower()} | {a.lower() for a in (aliases2 or [])}
                        stripped_2 = _normalize_name(name2, type2).lower()

                        confidence = 0.0
                        if all_names_1 & all_names_2:
                            confidence = 0.95
                        elif stripped_1 == stripped_2:
                            confidence = 0.9
                        elif _similarity(stripped_1, stripped_2) > 0.85:
                            confidence = 0.75

                        if confidence >= min_confidence:
                            relationships.append((d1, id1, d2, id2, confidence, "cross_domain_same_entity"))

        created = 0
        with conn.cursor() as cur:
            for src_d, src_id, tgt_d, tgt_id, conf, rel_type in relationships[:limit]:
                try:
                    # Check if this relationship already exists (either direction)
                    cur.execute(
                        """
                        SELECT id FROM intelligence.entity_relationships
                        WHERE (
                            (source_domain = %s AND source_entity_id = %s
                             AND target_domain = %s AND target_entity_id = %s)
                            OR
                            (source_domain = %s AND source_entity_id = %s
                             AND target_domain = %s AND target_entity_id = %s)
                        )
                        AND relationship_type = %s
                        LIMIT 1
                        """,
                        (src_d, src_id, tgt_d, tgt_id,
                         tgt_d, tgt_id, src_d, src_id,
                         rel_type),
                    )
                    if cur.fetchone():
                        continue
                    cur.execute(
                        """
                        INSERT INTO intelligence.entity_relationships
                        (source_domain, source_entity_id, target_domain, target_entity_id,
                         relationship_type, confidence)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        RETURNING id
                        """,
                        (src_d, src_id, tgt_d, tgt_id, rel_type, conf),
                    )
                    if cur.fetchone():
                        created += 1
                except Exception as e:
                    logger.debug("cross-domain link skip: %s", e)

        conn.commit()
        conn.close()
        logger.info("link_cross_domain_entities: %d relationships created", created)
        return {
            "success": True,
            "linked": len(relationships),
            "relationships_created": created,
        }
    except Exception as e:
        logger.warning("link_cross_domain_entities: %s", e)
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass
        return {"success": False, "linked": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# Batch run — combine alias population + auto-merge + cross-domain linking
# ---------------------------------------------------------------------------

def run_resolution_batch(
    auto_merge_confidence: float = 0.9,
    cross_domain_confidence: float = 0.8,
) -> Dict[str, Any]:
    """
    Run a full resolution cycle across all domains:
      1. Populate aliases from article mentions
      2. Auto-merge high-confidence duplicates
      3. Link cross-domain entities

    Suitable for orchestrator or cron scheduling.
    """
    results: Dict[str, Any] = {"domains": {}, "cross_domain": {}}

    for domain_key in ALL_DOMAINS:
        domain_result: Dict[str, Any] = {}

        alias_result = populate_aliases_from_mentions(domain_key)
        domain_result["aliases"] = alias_result

        merge_result = auto_merge_high_confidence(domain_key, min_confidence=auto_merge_confidence)
        domain_result["merges"] = merge_result

        results["domains"][domain_key] = domain_result

    cross_result = link_cross_domain_entities(min_confidence=cross_domain_confidence)
    results["cross_domain"] = cross_result

    return results
