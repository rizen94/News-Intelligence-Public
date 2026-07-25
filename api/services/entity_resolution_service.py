"""
Entity resolution service — enhanced disambiguation, alias population, and cross-domain linking.

Maps (domain, entity_name, entity_type) to canonical_entity_id in that domain's entity_canonical.
Used by article entity extraction, batch alias population, merge-candidate detection, and
cross-domain entity linking.

See docs/RAG_ENHANCEMENT_ROADMAP.md, docs/V6_QUALITY_FIRST_TODO.md T1.2.
"""

import logging
import os
import re
import unicodedata
from typing import Any

from shared.database.connection import get_db_connection
from shared.domain_registry import domain_key_to_schema, get_active_domain_keys, is_valid_domain_key
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

logger = logging.getLogger(__name__)

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
    return domain_key_to_schema(domain_key)


def _normalize_name(name: str, entity_type: str) -> str:
    """Strip titles/suffixes and normalize whitespace for matching."""
    n = name.strip()
    if entity_type == "person":
        n = TITLE_PREFIXES.sub("", n).strip()
    elif entity_type == "organization":
        n = ORG_SUFFIXES.sub("", n).strip()
    return re.sub(r"\s+", " ", n)


def _normalize_for_fuzzy(text: str) -> str:
    """
    Aggressive normalization for fuzzy compare / dedupe keys (not for display).

    - Unicode NFKC + lowercase
    - Common abbreviation punctuation (U.S.A. → usa)
    - Non-alphanumeric → spaces; collapse whitespace
    - Light typo repair: leading ``iu`` before a vowel (``iunited`` → ``united``)
    """
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", text).lower().strip()
    t = t.replace("’", "'").replace("`", "'").replace("“", '"').replace("”", '"')
    # Abbreviations (order matters: longest first)
    t = re.sub(r"\bu\.s\.a\.?\b", "usa", t)
    t = re.sub(r"\bu\.s\.?\b", "us", t)
    t = re.sub(r"\bu\.k\.?\b", "uk", t)
    t = re.sub(r"\bu\.n\.?\b", "un", t)
    t = re.sub(r"\be\.u\.?\b", "eu", t)
    t = re.sub(r"\bn\.y\.c\.?\b", "nyc", t)
    t = re.sub(r"\bd\.c\.?\b", "dc", t)
    t = re.sub(r"\bu\s*s\s*a\b", "usa", t)
    t = re.sub(r"\bu\s*s\b(?!\w)", "us", t)
    t = re.sub(r"\bu\s*k\b(?!\w)", "uk", t)
    t = re.sub(r"\bu\s*n\b(?!\w)", "un", t)
    t = re.sub(r"\be\s*u\b(?!\w)", "eu", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    words: list[str] = []
    for w in t.split():
        if len(w) >= 5 and w.startswith("iu") and w[2] in "aeiou":
            w = w[1:]
        if len(w) >= 4 and w[0] == w[1] and w[0].isalpha():
            w = w[1:]
        words.append(w)
    # Drop generational suffixes so "Robert F Kennedy Jr" ≉ "Martin Luther King Jr"
    words = [w for w in words if w not in {"jr", "sr", "ii", "iii", "iv", "v"}]
    return " ".join(words)


def _normalize_for_entity_match(name: str, entity_type: str) -> str:
    """Chain title/org stripping + fuzzy normalization for matching keys."""
    return _normalize_for_fuzzy(_normalize_name(name or "", entity_type))


# Known equivalent surface forms (human-readable); frozen to normalized tokens at import.
_ENTITY_EQUIVALENCE_GROUPS_RAW: tuple[tuple[str, ...], ...] = (
    (
        "United States",
        "United States of America",
        "USA",
        "US",
        "U.S.",
        "U.S.A.",
        "the United States",
        "the United States of America",
    ),
    (
        "United Kingdom",
        "Great Britain",
        "UK",
        "U.K.",
        "Britain",
    ),
    (
        "European Union",
        "EU",
        "E.U.",
    ),
    (
        "United Nations",
        "UN",
        "U.N.",
    ),
    (
        "New York City",
        "NYC",
        "N.Y.C.",
    ),
    (
        "Washington DC",
        "Washington D.C.",
        "Washington, D.C.",
    ),
    # Foodborne / parasitic disease — surface forms from outbreak coverage
    (
        "cyclospora",
        "cyclosporiasis",
        "cyclospora outbreak",
        "cyclosporiasis outbreak",
        "Cyclospora outbreak",
        "Cyclosporiasis outbreak",
    ),
)

_ENTITY_EQUIV_NORM: tuple[frozenset[str], ...] = tuple(
    frozenset(_normalize_for_fuzzy(x) for x in grp) for grp in _ENTITY_EQUIVALENCE_GROUPS_RAW
)
_TERM_TO_BUCKET: dict[str, str] = {}
_BUCKET_TO_TERMS: dict[str, frozenset[str]] = {}
for _i, _fs in enumerate(_ENTITY_EQUIV_NORM):
    _bid = f"eq:{_i}"
    _BUCKET_TO_TERMS[_bid] = _fs
    for _t in _fs:
        _TERM_TO_BUCKET[_t] = _bid


def _equivalence_bucket_id(normalized: str) -> str | None:
    """Stable bucket id if ``normalized`` is a known alias form, else None."""
    if not normalized:
        return None
    return _TERM_TO_BUCKET.get(normalized)


def normalize_entity_match_key(name: str, entity_type: str) -> str:
    """
    Stable key for dedupe grouping: fuzzy-normalized string, or shared bucket id
    for known abbreviations (e.g. US / USA / United States).
    """
    n = _normalize_for_entity_match(name, entity_type)
    bid = _equivalence_bucket_id(n)
    if bid:
        return bid
    return n


def _equivalence_sql_terms(name: str, entity_type: str) -> list[str]:
    """All normalized bucket strings for SQL ``= ANY(...)`` when ``name`` hits a bucket."""
    n = _normalize_for_entity_match(name, entity_type)
    bid = _equivalence_bucket_id(n)
    if not bid:
        return []
    return sorted(_BUCKET_TO_TERMS[bid])


def _match_variant_strings(name: str, entity_type: str) -> set[str]:
    """Lowered surface + normalized + full bucket expansion for overlap checks."""
    raw = (name or "").strip()
    out: set[str] = set()
    if not raw:
        return out
    out.add(raw.lower())
    out.add(_normalize_name(raw, entity_type).lower())
    mx = _normalize_for_entity_match(raw, entity_type)
    out.add(mx)
    bid = _equivalence_bucket_id(mx)
    if bid:
        out.update(_BUCKET_TO_TERMS[bid])
    return out


# Last-word "surname" matching only applies when the last word is not a role/title.
# Otherwise "DXS International executives" and "Meta's executives" get merged incorrectly.
LAST_WORD_ROLE_BLOCKLIST = frozenset(
    {
        "executives",
        "executive",
        "chair",
        "chairs",
        "board",
        "team",
        "teams",
        "spokesperson",
        "spokesman",
        "spokeswoman",
        "office",
        "leadership",
        "management",
        "staff",
        "officials",
        "representatives",
        "members",
        "committee",
        "commission",
        "division",
        "department",
        "unit",
        "group",
        # Generational suffixes are NOT surnames — matching on "Jr" merged
        # RFK Jr / Biden Jr / Trump Jr into Martin Luther King Jr.
        "jr",
        "sr",
        "ii",
        "iii",
        "iv",
        "v",
    }
)

# Strip before surname extraction (with or without trailing period).
_GENERATIONAL_SUFFIXES = frozenset({"jr", "sr", "ii", "iii", "iv", "v"})


def _strip_generational_suffixes(parts: list[str]) -> list[str]:
    out = list(parts)
    while len(out) >= 2 and out[-1].lower().rstrip(".").rstrip("'s") in _GENERATIONAL_SUFFIXES:
        out.pop()
    return out


def _extract_last_name(name: str) -> str | None:
    """For person entities, extract surname (skip role words and Jr/Sr/II…)."""
    parts = _strip_generational_suffixes(name.strip().split())
    if len(parts) >= 2:
        last = parts[-1].lower().rstrip("'s")
        if last not in LAST_WORD_ROLE_BLOCKLIST and last not in _GENERATIONAL_SUFFIXES:
            return parts[-1]
    return None


def _name_ends_with_role_word(name: str) -> bool:
    """True if name's last word is in the role blocklist (e.g. 'X executives', 'Y chair')."""
    parts = name.strip().split()
    if not parts:
        return False
    last = parts[-1].lower().rstrip("'s")
    return last in LAST_WORD_ROLE_BLOCKLIST


ENTITY_TYPES = ("person", "organization", "subject", "recurring_event", "family")
REL_MEMBER_OF_FAMILY = "member_of_family"


def _person_matches_first_name(canonical_name: str, aliases: list[str] | None, first_tok: str) -> bool:
    """True if canonical (or alias) is clearly this given-first-name + rest."""
    if not first_tok or len(first_tok) < 2:
        return False
    ft = first_tok.lower()
    for raw in [canonical_name, *(aliases or [])]:
        s = (raw or "").strip().lower()
        if not s:
            continue
        if s == ft or s.startswith(ft + " "):
            return True
    return False


def _get_or_create_family_canonical(cur, schema: str, surname_token: str) -> int | None:
    """Surname umbrella row, e.g. 'Trump' -> canonical 'Trump family', entity_type family."""
    sur = surname_token.strip()
    if len(sur) < 2:
        return None
    family_label = f"{sur.title()} family"
    cur.execute(
        f"""
        INSERT INTO {schema}.entity_canonical (canonical_name, entity_type, aliases)
        VALUES (%s, 'family', ARRAY[%s, %s]::TEXT[])
        ON CONFLICT (canonical_name, entity_type) DO UPDATE SET updated_at = NOW()
        RETURNING id
        """,
        (family_label, sur.title(), family_label),
    )
    row = cur.fetchone()
    if row and row[0] is not None:
        return int(row[0])
    cur.execute(
        f"""
        SELECT id FROM {schema}.entity_canonical
        WHERE entity_type = 'family' AND LOWER(canonical_name) = LOWER(%s)
        LIMIT 1
        """,
        (family_label,),
    )
    row2 = cur.fetchone()
    return int(row2[0]) if row2 and row2[0] is not None else None


def _ensure_member_of_family_edge(cur, domain_key: str, person_canonical_id: int, family_canonical_id: int) -> None:
    from shared.entity_relationships_store import UPSERT_ENTITY_RELATIONSHIP_SQL

    cur.execute(
        UPSERT_ENTITY_RELATIONSHIP_SQL,
        (
            domain_key,
            person_canonical_id,
            domain_key,
            family_canonical_id,
            REL_MEMBER_OF_FAMILY,
            0.99,
        ),
    )


def _link_surname_cluster_to_family(
    cur, schema: str, domain_key: str, surname_display: str, candidate_rows: list[tuple[int, str, list[str]]]
) -> int | None:
    """Create/get family canonical and member_of_family edges for all persons in cluster."""
    fam_id = _get_or_create_family_canonical(cur, schema, surname_display)
    if not fam_id:
        return None
    for pid, _cname, _aliases in candidate_rows:
        if pid != fam_id:
            _ensure_member_of_family_edge(cur, domain_key, pid, fam_id)
    return fam_id


# ---------------------------------------------------------------------------
# Core resolution (enhanced with title stripping + last-name fallback)
# ---------------------------------------------------------------------------


def resolve_to_canonical_on_cursor(
    cur,
    schema: str,
    domain_key: str,
    entity_name: str,
    entity_type: str,
    create_if_missing: bool = True,
) -> int | None:
    """Resolve using an existing cursor (caller owns connection + transaction)."""
    name = (entity_name or "").strip()
    if not name or len(name) < 2:
        return None
    etype = (entity_type or "person").strip().lower()
    if etype not in ENTITY_TYPES:
        etype = "person"

    cur.execute(f"SET search_path TO {schema}, public")

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
        return row[0]

    eq_terms = _equivalence_sql_terms(name, etype)
    if eq_terms:
        cur.execute(
            f"""
            SELECT id FROM {schema}.entity_canonical
            WHERE entity_type = %s
              AND (
                lower(trim(canonical_name)) = ANY(%s)
                OR EXISTS (
                    SELECT 1 FROM unnest(COALESCE(aliases, '{{}}')) a
                    WHERE lower(trim(a)) = ANY(%s)
                )
              )
            LIMIT 1
            """,
            (etype, eq_terms, eq_terms),
        )
        row = cur.fetchone()
        if row:
            _add_alias(cur, schema, row[0], name)
            return row[0]

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
            return row[0]

    if etype == "person":
        last_name = _extract_last_name(stripped)
        if (
            not last_name
            and len(stripped.split()) == 1
            and len(stripped.strip()) >= 3
            and not _name_ends_with_role_word(stripped)
        ):
            last_name = stripped.strip()
        if last_name and len(last_name) >= 3:
            ln_pat = f" {last_name.lower()}"
            cur.execute(
                f"""
                SELECT id, canonical_name, COALESCE(aliases, '{{}}')
                FROM {schema}.entity_canonical
                WHERE entity_type = 'person'
                  AND (
                    LOWER(canonical_name) LIKE '%%' || LOWER(%s)
                    OR EXISTS (
                        SELECT 1 FROM unnest(COALESCE(aliases, '{{}}')) a
                        WHERE LOWER(a) LIKE '%%' || LOWER(%s)
                    )
                  )
                """,
                (ln_pat, ln_pat),
            )
            candidates = cur.fetchall()
            if len(candidates) == 1:
                _add_alias(cur, schema, candidates[0][0], name)
                return candidates[0][0]
            if len(candidates) > 1:
                parts_s = stripped.split()
                first_tok = parts_s[0] if parts_s else ""
                matched = [
                    row
                    for row in candidates
                    if _person_matches_first_name(row[1], row[2], first_tok)
                ]
                if len(matched) == 1:
                    cid = matched[0][0]
                    _add_alias(cur, schema, cid, name)
                    return cid
                fam_id = _link_surname_cluster_to_family(
                    cur, schema, domain_key, last_name, list(candidates)
                )
                single_token_surname = len(parts_s) == 1 and parts_s[0].lower().rstrip(
                    "'s"
                ) == last_name.lower()
                ambiguous_multi = len(matched) != 1
                if fam_id and (single_token_surname or ambiguous_multi):
                    return fam_id

    if not create_if_missing:
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
    return new_row[0] if new_row else None


def resolve_to_canonical(
    domain_key: str,
    entity_name: str,
    entity_type: str,
    create_if_missing: bool = True,
) -> int | None:
    """
    Resolve a mention to entity_canonical.id.

    Matching cascade:
      1. Exact canonical_name or alias (case-insensitive)
      2. Title-stripped name match (e.g., "President Biden" → "Joe Biden")
      3. Person surname cluster: unique last-name hit → that person; multiple hits →
         first-name disambiguation; still ambiguous or surname-only mention →
         ``{Surname} family`` umbrella (``entity_type=family``) with ``member_of_family``
         edges to each distinct person (see ``reconcile_surname_family_clusters``).

    On match at step 2/3, the mention name is added to aliases.
    If create_if_missing and no match, inserts a new canonical.
    """
    name = (entity_name or "").strip()
    if not name or len(name) < 2:
        return None
    etype = (entity_type or "person").strip().lower()
    if etype not in ENTITY_TYPES:
        etype = "person"
    schema = _schema_for_domain(domain_key)

    conn = get_db_connection()
    if not conn:
        logger.warning("entity resolution: no DB connection")
        return None

    def _release(result: int | None) -> int | None:
        try:
            conn.close()
        except Exception:
            pass
        return result

    try:
        with conn.cursor() as cur:
            result = resolve_to_canonical_on_cursor(
                cur,
                schema,
                domain_key,
                name,
                etype,
                create_if_missing=create_if_missing,
            )
        conn.commit()
        return _release(result)
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
) -> dict[str, Any]:
    """
    Find canonical entities matching the mention, ranked by confidence.
    Returns {match: {id, canonical_name, confidence} | None, candidates: [...]}.
    """
    name = (entity_name or "").strip()
    if not name or len(name) < 2:
        return {"match": None, "candidates": []}
    etype = (entity_type or "person").strip().lower()
    if etype not in ENTITY_TYPES:
        etype = "person"
    schema = _schema_for_domain(domain_key)
    stripped = _normalize_name(name, etype)
    last_name = _extract_last_name(stripped) if etype == "person" else None

    conn = get_db_connection()
    if not conn:
        return {"match": None, "candidates": [], "error": "Database connection failed"}

    try:
        candidates: list[dict[str, Any]] = []
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
        mention_variants = _match_variant_strings(name, etype)

        for cid, cname, aliases in rows:
            cname_lower = cname.lower()
            alias_lowers = [a.lower() for a in (aliases or [])]
            all_names = [cname_lower] + alias_lowers
            row_variants: set[str] = set()
            row_variants.update(_match_variant_strings(cname, etype))
            for al in aliases or []:
                row_variants.update(_match_variant_strings(al, etype))
            confidence = 0.0
            match_reason = ""

            if name_lower in all_names:
                confidence = 1.0
                match_reason = "exact_match"
            elif mention_variants & row_variants:
                confidence = 0.98
                match_reason = "equivalent_variant"
            elif stripped_lower in all_names:
                confidence = 0.95
                match_reason = "title_stripped"
            elif any(name_lower in a or a in name_lower for a in all_names if len(a) >= 4):
                confidence = 0.7
                match_reason = "substring"
            elif last_name and any(a.endswith(f" {last_name.lower()}") for a in all_names):
                confidence = 0.6
                match_reason = "last_name"
            elif stripped_lower and any(_similarity(name, a) > 0.7 for a in all_names):
                confidence = 0.5
                match_reason = "fuzzy"

            if confidence > 0:
                candidates.append(
                    {
                        "canonical_entity_id": cid,
                        "canonical_name": cname,
                        "aliases": aliases or [],
                        "confidence": round(confidence, 2),
                        "match_reason": match_reason,
                    }
                )

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
    """Fuzzy similarity on normalized strings; RapidFuzz when installed."""
    na = _normalize_for_fuzzy(a)
    nb = _normalize_for_fuzzy(b)
    if not na or not nb:
        return 0.0
    ba, bb = _equivalence_bucket_id(na), _equivalence_bucket_id(nb)
    if ba and bb and ba == bb:
        return 1.0
    if na == nb:
        return 1.0
    try:
        from rapidfuzz import fuzz

        return float(fuzz.token_set_ratio(na, nb)) / 100.0
    except ImportError:
        pass
    bigrams_a = set(na[i : i + 2] for i in range(len(na) - 1))
    bigrams_b = set(nb[i : i + 2] for i in range(len(nb) - 1))
    if not bigrams_a or not bigrams_b:
        return 0.0
    intersection = bigrams_a & bigrams_b
    return 2 * len(intersection) / (len(bigrams_a) + len(bigrams_b))


# ---------------------------------------------------------------------------
# Batch alias population — collect name variants from article_entities
# ---------------------------------------------------------------------------

_RESOLUTION_CURSOR_KEY = "entity_resolution_incremental_cursor"


def _get_resolution_cursor() -> dict[str, int]:
    from shared.database.connection import get_db_connection_context

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT value FROM public.automation_state WHERE key = %s",
                    (_RESOLUTION_CURSOR_KEY,),
                )
                row = cur.fetchone()
        if row and row[0]:
            raw = row[0]
            if isinstance(raw, str):
                import json

                return {str(k): int(v) for k, v in json.loads(raw).items()}
            if isinstance(raw, dict):
                return {str(k): int(v) for k, v in raw.items()}
    except Exception as e:
        logger.debug("resolution cursor read: %s", e)
    return {}


def _set_resolution_cursor(cursor: dict[str, int]) -> None:
    import json

    from shared.database.connection import get_db_connection_context

    try:
        with get_db_connection_context() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.automation_state (key, value, updated_at)
                    VALUES (%s, %s::jsonb, NOW())
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                    """,
                    (_RESOLUTION_CURSOR_KEY, json.dumps(cursor)),
                )
            conn.commit()
    except Exception as e:
        logger.debug("resolution cursor write: %s", e)


def populate_aliases_from_mentions(
    domain_key: str,
    min_mentions: int = 2,
) -> dict[str, Any]:
    """
    For each canonical entity in a domain, collect all distinct entity_name values
    from article_entities that point to it and add missing variants to aliases.
    Only adds variants seen in at least min_mentions articles.

    Returns {updated: N, new_aliases: N}.
    """
    schema = _schema_for_domain(domain_key)
    conn = get_db_connection()
    if not conn:
        return {
            "success": False,
            "updated": 0,
            "new_aliases": 0,
            "error": "Database connection failed",
        }

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
            domain_key,
            updated,
            new_aliases,
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


def populate_aliases_from_mentions_incremental(
    domain_key: str,
    *,
    min_mentions: int = 2,
    batch_limit: int = 200,
) -> dict[str, Any]:
    """Incremental alias population — only article_entities since per-domain cursor."""
    schema = _schema_for_domain(domain_key)
    cursor = _get_resolution_cursor()
    since_article_id = int(cursor.get(domain_key, 0) or 0)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "updated": 0, "new_aliases": 0, "error": "no_db"}

    updated = 0
    new_aliases = 0
    max_article_id = since_article_id
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT ae.canonical_entity_id,
                       array_agg(DISTINCT ae.entity_name) AS mention_names,
                       MAX(ae.article_id) AS max_aid
                FROM {schema}.article_entities ae
                WHERE ae.canonical_entity_id IS NOT NULL
                  AND ae.article_id > %s
                GROUP BY ae.canonical_entity_id
                HAVING COUNT(DISTINCT ae.entity_name) >= 1
                ORDER BY MAX(ae.article_id)
                LIMIT %s
                """,
                (since_article_id, batch_limit),
            )
            rows = cur.fetchall()
            for canonical_id, mention_names, max_aid in rows:
                max_article_id = max(max_article_id, int(max_aid or 0))
                if not mention_names:
                    continue
                cur.execute(
                    f"SELECT aliases FROM {schema}.entity_canonical WHERE id = %s",
                    (canonical_id,),
                )
                arow = cur.fetchone()
                if not arow:
                    continue
                current_aliases = arow[0] or []
                current_lower = {a.lower() for a in current_aliases}
                to_add = []
                for mname in mention_names:
                    if mname and mname.lower() not in current_lower:
                        cur.execute(
                            f"""
                            SELECT COUNT(*) FROM {schema}.article_entities
                            WHERE canonical_entity_id = %s
                              AND LOWER(entity_name) = LOWER(%s)
                              AND article_id > %s
                            """,
                            (canonical_id, mname, since_article_id),
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
        cursor[domain_key] = max_article_id
        _set_resolution_cursor(cursor)
        return {
            "success": True,
            "updated": updated,
            "new_aliases": new_aliases,
            "cursor_article_id": max_article_id,
            "incremental": True,
        }
    except Exception as e:
        logger.warning("populate_aliases_incremental %s: %s", domain_key, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "updated": 0, "new_aliases": 0, "error": str(e)}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Disambiguation — find merge candidates (likely-duplicate canonical entities)
# ---------------------------------------------------------------------------


def find_merge_candidates(
    domain_key: str,
    min_confidence: float = 0.5,
    limit: int = 50,
) -> dict[str, Any]:
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

    # Cap pair scan — blocking key by normalized last/stripped name before nested loops.
    max_entities = env_int("ENTITY_MERGE_CANDIDATE_MAX_ENTITIES", 2500)
    max_pairs = env_int("ENTITY_MERGE_CANDIDATE_MAX_PAIRS", 50_000)

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, canonical_name, entity_type, aliases
                FROM {schema}.entity_canonical
                ORDER BY id
                LIMIT %s
                """,
                (max_entities,),
            )
            entities = cur.fetchall()
        conn.close()

        candidates: list[dict[str, Any]] = []
        seen_pairs = set()
        pairs_checked = 0

        # Blocking: group by entity_type + first letter of stripped name
        blocks: dict[tuple[str, str], list] = {}
        for row in entities:
            id_a, name_a, type_a, aliases_a = row
            stripped = _normalize_name(name_a, type_a).lower()
            key = (str(type_a or ""), (stripped[:1] if stripped else ""))
            blocks.setdefault(key, []).append(row)

        for block_rows in blocks.values():
            for i, (id_a, name_a, type_a, aliases_a) in enumerate(block_rows):
                stripped_a = _normalize_name(name_a, type_a).lower()
                last_a = _extract_last_name(name_a)
                all_a: set[str] = set(_match_variant_strings(name_a, type_a))
                for ax in aliases_a or []:
                    all_a.update(_match_variant_strings(ax, type_a))

                for j in range(i + 1, len(block_rows)):
                    if pairs_checked >= max_pairs:
                        break
                    pairs_checked += 1
                    id_b, name_b, type_b, aliases_b = block_rows[j]
                    if type_a != type_b:
                        continue
                    pair = (min(id_a, id_b), max(id_a, id_b))
                    if pair in seen_pairs:
                        continue

                    stripped_b = _normalize_name(name_b, type_b).lower()
                    all_b: set[str] = set(_match_variant_strings(name_b, type_b))
                    for bx in aliases_b or []:
                        all_b.update(_match_variant_strings(bx, type_b))

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
                        # Bigram similarity (normalization + bucket equivalence inside _similarity)
                        if confidence < min_confidence:
                            sim = _similarity(name_a, name_b)
                            if sim >= 0.7:
                                confidence = max(confidence, sim * 0.8)
                                reason = reason or "fuzzy_similarity"

                    if confidence >= min_confidence:
                        seen_pairs.add(pair)
                        candidates.append(
                            {
                                "source_id": id_a,
                                "source_name": name_a,
                                "target_id": id_b,
                                "target_name": name_b,
                                "entity_type": type_a,
                                "confidence": round(confidence, 2),
                                "reason": reason,
                            }
                        )
                        if len(candidates) >= limit * 3:
                            break
                if pairs_checked >= max_pairs or len(candidates) >= limit * 3:
                    break
            if pairs_checked >= max_pairs or len(candidates) >= limit * 3:
                break

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
) -> tuple[int, int]:
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
) -> dict[str, Any]:
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
            for a in merge_aliases or []:
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
            domain_key,
            merge_id,
            keep_id,
            articles_reassigned,
            len(aliases_to_add),
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
) -> dict[str, Any]:
    """
    Find merge candidates above min_confidence and automatically merge them.
    Always keeps the "primary" entity (full name, e.g. "Donald Trump") and merges
    variants (e.g. "Trump", "King Trump") into it; sub-entities are tracked as aliases.
    Returns {merges_performed, details: [...]}.
    """
    result = find_merge_candidates(domain_key, min_confidence=min_confidence, limit=100)
    if not result.get("success"):
        return {"success": False, "merges_performed": 0, "error": result.get("error")}

    details: list[dict[str, Any]] = []
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
            kept_name = (
                candidate["source_name"]
                if keep_id == candidate["source_id"]
                else candidate["target_name"]
            )
            merged_name = (
                candidate["target_name"]
                if keep_id == candidate["source_id"]
                else candidate["source_name"]
            )
            details.append(
                {
                    "kept": kept_name,
                    "merged": merged_name,
                    "confidence": candidate["confidence"],
                    "reason": candidate["reason"],
                    "result": merge_result,
                }
            )

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
    max_splits: int | None = None,
) -> dict[str, Any]:
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
        return {
            "success": False,
            "split_count": 0,
            "error": "Database connection failed",
            "dry_run": dry_run,
        }

    details: list[dict[str, Any]] = []
    split_count = 0
    canonicals_processed = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT id, canonical_name, entity_type, aliases FROM {schema}.entity_canonical",
            )
            rows = cur.fetchall()

        try:
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        for canonical_id, canonical_name, entity_type, aliases in rows:
            if max_splits is not None and split_count >= max_splits:
                break
            all_names = [canonical_name] + list(aliases or [])
            role_names = [n for n in all_names if n and _name_ends_with_role_word(n)]
            if len(role_names) < 2:
                continue
            canonicals_processed += 1
            with conn.cursor() as cur:
                for alias_name in aliases or []:
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
                        details.append(
                            {
                                "canonical_id": canonical_id,
                                "canonical_name": canonical_name,
                                "split_off": alias_name,
                                "new_canonical_id": None,
                                "articles_reassigned": cnt,
                            }
                        )
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
                    details.append(
                        {
                            "canonical_id": canonical_id,
                            "canonical_name": canonical_name,
                            "split_off": alias_name,
                            "new_canonical_id": new_id,
                            "articles_reassigned": reassigned,
                        }
                    )
    except Exception as e:
        logger.warning("split_role_merged_canonicals %s: %s", domain_key, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {
            "success": False,
            "split_count": split_count,
            "canonicals_processed": canonicals_processed,
            "error": str(e),
            "details": details,
            "dry_run": dry_run,
        }
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
DECOUPLE_STEP_CROSS_TYPE = "cross_type"

# cross_type is opt-in: heuristic is noisy at scale and can flood the refuse ledger.
# Enable with ENTITY_DECOUPLE_CROSS_TYPE_ENABLED=true once reviewed.
def _default_decouple_steps() -> tuple[str, ...]:
    from config.runtime import env_bool

    if env_bool("ENTITY_DECOUPLE_CROSS_TYPE_ENABLED", False):
        return (DECOUPLE_STEP_ROLE_WORD, DECOUPLE_STEP_CROSS_TYPE)
    return (DECOUPLE_STEP_ROLE_WORD,)


DEFAULT_DECOUPLE_STEPS = (DECOUPLE_STEP_ROLE_WORD,)  # runtime via _default_decouple_steps()


def split_cross_type_merged_canonicals(
    domain_key: str,
    dry_run: bool = False,
    max_splits: int | None = None,
) -> dict[str, Any]:
    """
    Split canonicals that incorrectly merged person + organization (or mixed types)
    under one id via alias collision. Creates a new canonical for minority-type aliases
    that have article_entities rows and reassigns those mentions.
    """
    schema = _schema_for_domain(domain_key)
    conn = get_db_connection()
    if not conn:
        return {"success": False, "split_count": 0, "error": "Database connection failed", "dry_run": dry_run}

    person_like = {"person", "people", "individual", "politician"}
    org_like = {"organization", "org", "company", "corporation", "government", "agency"}
    details: list[dict[str, Any]] = []
    split_count = 0
    canonicals_processed = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, canonical_name, entity_type, aliases
                FROM {schema}.entity_canonical
                WHERE aliases IS NOT NULL AND cardinality(aliases) > 0
                """
            )
            rows = cur.fetchall()
        try:
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        for canonical_id, canonical_name, entity_type, aliases in rows:
            if max_splits is not None and split_count >= max_splits:
                break
            base_type = (entity_type or "").strip().lower()
            if not base_type:
                continue
            base_bucket = (
                "person"
                if base_type in person_like
                else ("org" if base_type in org_like else None)
            )
            if base_bucket is None:
                continue
            # Heuristic: aliases that look like the opposite bucket (Inc/Corp/LLC vs person names)
            conflict_aliases: list[str] = []
            for alias in aliases or []:
                if not alias:
                    continue
                al = alias.lower()
                looks_org = any(
                    tok in al for tok in (" inc", " corp", " llc", " ltd", " company", " agency")
                )
                looks_person = (" " in alias.strip()) and not looks_org
                if base_bucket == "person" and looks_org:
                    conflict_aliases.append(alias)
                elif base_bucket == "org" and looks_person and len(alias.split()) >= 2:
                    conflict_aliases.append(alias)
            if not conflict_aliases:
                continue
            canonicals_processed += 1
            with conn.cursor() as cur:
                for alias_name in conflict_aliases:
                    if max_splits is not None and split_count >= max_splits:
                        break
                    cur.execute(
                        f"""
                        SELECT COUNT(*) FROM {schema}.article_entities
                        WHERE canonical_entity_id = %s AND LOWER(TRIM(entity_name)) = LOWER(TRIM(%s))
                        """,
                        (canonical_id, alias_name),
                    )
                    (cnt,) = cur.fetchone()
                    if not cnt:
                        continue
                    new_type = "organization" if base_bucket == "person" else "person"
                    if dry_run:
                        details.append(
                            {
                                "canonical_id": canonical_id,
                                "canonical_name": canonical_name,
                                "split_off": alias_name,
                                "new_type": new_type,
                                "articles_reassigned": cnt,
                            }
                        )
                        split_count += 1
                        continue
                    cur.execute(
                        f"""
                        INSERT INTO {schema}.entity_canonical (canonical_name, entity_type, aliases)
                        VALUES (%s, %s, '{{}}')
                        ON CONFLICT (canonical_name, entity_type) DO UPDATE SET updated_at = NOW()
                        RETURNING id
                        """,
                        (alias_name[:255], new_type),
                    )
                    new_row = cur.fetchone()
                    if not new_row:
                        continue
                    new_id = int(new_row[0])
                    cur.execute(
                        f"""
                        UPDATE {schema}.article_entities
                        SET canonical_entity_id = %s
                        WHERE canonical_entity_id = %s AND LOWER(TRIM(entity_name)) = LOWER(TRIM(%s))
                        """,
                        (new_id, canonical_id, alias_name),
                    )
                    cur.execute(
                        f"""
                        UPDATE {schema}.entity_canonical
                        SET aliases = array_remove(aliases, %s), updated_at = NOW()
                        WHERE id = %s
                        """,
                        (alias_name, canonical_id),
                    )
                    details.append(
                        {
                            "canonical_id": canonical_id,
                            "split_off": alias_name,
                            "new_canonical_id": new_id,
                            "articles_reassigned": cnt,
                        }
                    )
                    split_count += 1
                    # Refuse re-merge of this pair
                    try:
                        from services.graph_connection_queue_service import (
                            entity_pair_dedupe_key,
                            record_pattern_refusal,
                        )

                        record_pattern_refusal(
                            endpoint_key=f"entity|{domain_key}|{min(canonical_id, new_id)}|{max(canonical_id, new_id)}",
                            status="refuse",
                            reason="cross_type_decouple",
                            domain_key=domain_key,
                            endpoints={
                                "domain_key": domain_key,
                                "entity_ids": [canonical_id, new_id],
                            },
                            dedupe_key=entity_pair_dedupe_key(domain_key, canonical_id, new_id),
                            source="entity_decouple_cross_type",
                        )
                    except Exception:
                        pass
            if not dry_run:
                conn.commit()
        return {
            "success": True,
            "split_count": split_count,
            "canonicals_processed": canonicals_processed,
            "details": details,
            "dry_run": dry_run,
        }
    except Exception as e:
        logger.warning("split_cross_type_merged_canonicals %s: %s", domain_key, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {
            "success": False,
            "split_count": split_count,
            "error": str(e),
            "dry_run": dry_run,
        }
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_entity_decouple_pipeline(
    domain_keys: list[str] | None = None,
    dry_run: bool = False,
    steps: list[str] | None = None,
    max_splits_per_domain: int | None = None,
) -> dict[str, Any]:
    """
    Routine entity decouple: find bad merges and split them so each canonical
    represents a single real-world entity. Safe to run as part of data_cleanup.

    Steps (all run when steps is None):
      - role_word: split role-word last-name umbrellas
      - cross_type: split person/org mixed aliases on one canonical
    """
    domains = list(domain_keys) if domain_keys else list(get_active_domain_keys())
    steps_to_run = list(steps) if steps else list(_default_decouple_steps())
    by_domain: dict[str, dict[str, Any]] = {}
    total_splits = 0

    for domain_key in domains:
        if not is_valid_domain_key(domain_key):
            continue
        domain_result: dict[str, Any] = {"split_count": 0, "canonicals_processed": 0}
        for step in steps_to_run:
            if step == DECOUPLE_STEP_ROLE_WORD:
                out = split_role_merged_canonicals(
                    domain_key,
                    dry_run=dry_run,
                    max_splits=max_splits_per_domain,
                )
                if out.get("success"):
                    domain_result["split_count"] = int(domain_result.get("split_count") or 0) + int(
                        out.get("split_count") or 0
                    )
                    domain_result["canonicals_processed"] = int(
                        domain_result.get("canonicals_processed") or 0
                    ) + int(out.get("canonicals_processed") or 0)
                    total_splits += int(out.get("split_count") or 0)
                else:
                    domain_result["error"] = out.get("error", "unknown")
                    logger.warning("Decouple role_word %s: %s", domain_key, domain_result["error"])
                domain_result["role_word"] = out
            elif step == DECOUPLE_STEP_CROSS_TYPE:
                out = split_cross_type_merged_canonicals(
                    domain_key,
                    dry_run=dry_run,
                    max_splits=max_splits_per_domain,
                )
                if out.get("success"):
                    domain_result["split_count"] = int(domain_result.get("split_count") or 0) + int(
                        out.get("split_count") or 0
                    )
                    domain_result["canonicals_processed"] = int(
                        domain_result.get("canonicals_processed") or 0
                    ) + int(out.get("canonicals_processed") or 0)
                    total_splits += int(out.get("split_count") or 0)
                else:
                    domain_result.setdefault("errors", []).append(out.get("error", "unknown"))
                    logger.warning("Decouple cross_type %s: %s", domain_key, out.get("error"))
                domain_result["cross_type"] = out
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
) -> dict[str, Any]:
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
        domain_entities: dict[str, list[tuple[int, str, str, list[str]]]] = {}
        for domain_key in get_active_domain_keys():
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

        # Read-only rows are fully in memory; end the transaction before O(n²) Python work.
        # Otherwise the session stays "idle in transaction" for a long time (blocks vacuum, burns slots).
        try:
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass

        # Find cross-domain matches (blocked by type + first letter; pair cap).
        relationships: list[tuple[str, int, str, int, float, str]] = []
        domains = list(domain_entities.keys())
        max_pairs = env_int("ENTITY_CROSS_DOMAIN_MAX_PAIRS", 100_000)
        pairs_checked = 0

        for i in range(len(domains)):
            for j in range(i + 1, len(domains)):
                d1, d2 = domains[i], domains[j]
                # Index d2 by type + first letter for blocking
                index2: dict[tuple[str, str], list] = {}
                for row in domain_entities[d2]:
                    id2, name2, type2, aliases2 = row
                    stripped = _normalize_name(name2, type2).lower()
                    index2.setdefault((str(type2 or ""), stripped[:1] if stripped else ""), []).append(
                        row
                    )
                for id1, name1, type1, aliases1 in domain_entities[d1]:
                    if pairs_checked >= max_pairs:
                        break
                    all_names_1: set[str] = set(_match_variant_strings(name1, type1))
                    for a1 in aliases1 or []:
                        all_names_1.update(_match_variant_strings(a1, type1))
                    stripped_1 = _normalize_name(name1, type1).lower()
                    block = index2.get((str(type1 or ""), stripped_1[:1] if stripped_1 else "")) or []
                    for id2, name2, type2, aliases2 in block:
                        if pairs_checked >= max_pairs:
                            break
                        pairs_checked += 1
                        if type1 != type2:
                            continue

                        all_names_2: set[str] = set(_match_variant_strings(name2, type2))
                        for a2 in aliases2 or []:
                            all_names_2.update(_match_variant_strings(a2, type2))
                        stripped_2 = _normalize_name(name2, type2).lower()

                        confidence = 0.0
                        if all_names_1 & all_names_2:
                            confidence = 0.95
                        elif stripped_1 == stripped_2:
                            confidence = 0.9
                        elif _similarity(name1, name2) > 0.85:
                            confidence = 0.75

                        if confidence >= min_confidence:
                            relationships.append(
                                (d1, id1, d2, id2, confidence, "cross_domain_same_entity")
                            )
                if pairs_checked >= max_pairs:
                    break
            if pairs_checked >= max_pairs:
                break

        created = 0
        from shared.entity_relationships_store import UPSERT_ENTITY_RELATIONSHIP_SQL, normalize_edge

        with conn.cursor() as cur:
            for src_d, src_id, tgt_d, tgt_id, conf, rel_type in relationships[:limit]:
                try:
                    if rel_type == "cross_domain_same_entity":
                        src_d, src_id, tgt_d, tgt_id = normalize_edge(
                            src_d, src_id, tgt_d, tgt_id
                        )
                    cur.execute(
                        UPSERT_ENTITY_RELATIONSHIP_SQL,
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
# Surname → family umbrella (batch + inline in resolve_to_canonical step 3)
# ---------------------------------------------------------------------------


def reconcile_surname_family_clusters(domain_key: str) -> dict[str, Any]:
    """
    Find person canonicals that share the same trailing surname token (e.g. Donald Trump,
    Melania Trump → surname ``trump``). Ensure a ``{Surname} family`` canonical and
    ``member_of_family`` edges in ``intelligence.entity_relationships`` for each person.

    Bounded by ``SURNAME_FAMILY_MIN_MEMBERS`` (default 2), ``SURNAME_FAMILY_MAX_MEMBERS`` (24),
    ``SURNAME_FAMILY_MIN_SURNAME_LEN`` (4).
    """
    if not is_valid_domain_key(domain_key):
        return {"success": False, "error": "invalid_domain", "clusters": 0}
    schema = _schema_for_domain(domain_key)
    try:
        min_m = max(2, int(env_str("SURNAME_FAMILY_MIN_MEMBERS", "2")))
        max_m = max(min_m, int(env_str("SURNAME_FAMILY_MAX_MEMBERS", "24")))
        min_sur = max(2, int(env_str("SURNAME_FAMILY_MIN_SURNAME_LEN", "4")))
    except ValueError:
        min_m, max_m, min_sur = 2, 24, 4

    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "no_db", "clusters": 0}
    clusters = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                WITH persons AS (
                    SELECT id, canonical_name,
                      lower((string_to_array(trim(canonical_name), ' '))[
                        cardinality(string_to_array(trim(canonical_name), ' '))
                      ]) AS surname
                    FROM {schema}.entity_canonical
                    WHERE entity_type = 'person'
                      AND trim(canonical_name) <> ''
                      AND cardinality(string_to_array(trim(canonical_name), ' ')) >= 1
                )
                SELECT surname, array_agg(id ORDER BY id) AS ids
                FROM persons
                WHERE char_length(surname) >= %s
                GROUP BY surname
                HAVING count(*) >= %s AND count(*) <= %s
                """,
                (min_sur, min_m, max_m),
            )
            groups = cur.fetchall()
            for _surname, idlist in groups:
                if not idlist or len(idlist) < min_m:
                    continue
                cur.execute(
                    f"""
                    SELECT id, canonical_name, COALESCE(aliases, '{{}}')
                    FROM {schema}.entity_canonical
                    WHERE id = ANY(%s) AND entity_type = 'person'
                    ORDER BY id
                    """,
                    (list(idlist),),
                )
                rows = cur.fetchall()
                if len(rows) < min_m:
                    continue
                fam_id = _get_or_create_family_canonical(cur, schema, _surname)
                if not fam_id:
                    continue
                clusters += 1
                for pid, _cn, _al in rows:
                    if int(pid) != fam_id:
                        _ensure_member_of_family_edge(cur, domain_key, int(pid), fam_id)
        conn.commit()
        return {
            "success": True,
            "clusters": clusters,
            "domain_key": domain_key,
        }
    except Exception as e:
        logger.warning("reconcile_surname_family_clusters %s: %s", domain_key, e)
        try:
            conn.rollback()
        except Exception:
            pass
        return {"success": False, "error": str(e)[:500], "clusters": 0}
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Batch run — combine alias population + auto-merge + cross-domain linking
# ---------------------------------------------------------------------------


def _ambiguous_band() -> tuple[float, float]:
    from config.runtime import env_str

    try:
        low = float(env_str("GRAPH_CONNECTION_AMBIGUOUS_BAND_LOW", "0.55"))
        high = float(env_str("GRAPH_CONNECTION_AMBIGUOUS_BAND_HIGH", "0.72"))
    except ValueError:
        low, high = 0.55, 0.72
    return low, high


def run_resolution_ambiguous_batch(
    *,
    auto_merge_confidence: float = 0.9,
    cross_domain_confidence: float = 0.8,
) -> dict[str, Any]:
    """
    T0/T1 programmatic resolution for assembly conductor — incremental aliases,
    high-confidence auto-merge, T1 ambiguous band enqueued as proposals (T2 → editorial room).
    """
    band_low, band_high = _ambiguous_band()
    results: dict[str, Any] = {
        "incremental": True,
        "domains": {},
        "ambiguous_proposals": 0,
        "cross_domain": {},
    }

    for domain_key in get_active_domain_keys():
        domain_result: dict[str, Any] = {}
        domain_result["aliases"] = populate_aliases_from_mentions_incremental(domain_key)
        domain_result["merges"] = auto_merge_high_confidence(
            domain_key, min_confidence=auto_merge_confidence
        )
        ambiguous_n = _enqueue_ambiguous_merge_proposals(
            domain_key, band_low=band_low, band_high=band_high
        )
        results["ambiguous_proposals"] += ambiguous_n
        domain_result["ambiguous_enqueued"] = ambiguous_n
        results["domains"][domain_key] = domain_result

    if cross_domain_confidence >= 0.75:
        results["cross_domain"] = link_cross_domain_entities(min_confidence=cross_domain_confidence)
    return results


def _enqueue_ambiguous_merge_proposals(
    domain_key: str,
    *,
    band_low: float,
    band_high: float,
    limit: int = 25,
) -> int:
    from services.graph_connection_queue_service import upsert_graph_connection_proposal

    result = find_merge_candidates(domain_key, min_confidence=band_low, limit=limit)
    n = 0
    for candidate in result.get("candidates") or []:
        conf = float(candidate.get("confidence") or 0)
        if conf >= band_high:
            continue
        if conf < band_low:
            continue
        keep_id = int(candidate["source_id"])
        merge_id = int(candidate["target_id"])
        pid = upsert_graph_connection_proposal(
            dedupe_key=(
                f"entity_ambiguous|{domain_key}|{keep_id}|{merge_id}"
            ),
            proposal_kind="merge",
            domain_key=domain_key,
            confidence=conf,
            source="entity_resolution_t1",
            endpoints={
                "domain_key": domain_key,
                "entity_ids": [keep_id, merge_id],
            },
            evidence={
                "reason": candidate.get("reason"),
                "source_name": candidate.get("source_name"),
                "target_name": candidate.get("target_name"),
                "tier": "T1_ambiguous",
                "keep_canonical_id": keep_id,
                "merge_canonical_id": merge_id,
            },
            subject_summary=(
                f"{candidate.get('source_name')} ↔ {candidate.get('target_name')}"
            )[:255],
            min_confidence_for_auto=band_high,
        )
        if pid:
            n += 1
    return n


def run_resolution_batch(
    auto_merge_confidence: float = 0.9,
    cross_domain_confidence: float = 0.8,
    *,
    incremental: bool | None = None,
) -> dict[str, Any]:
    """
    Run a resolution cycle across all domains.
    When incremental=True (default under assembly ordered mode), use cursor-based alias
    population and ambiguous-band T1 merges only; skip full-domain scans.
    """
    if incremental is None:
        try:
            from shared.assembly_phase_order import assembly_pipeline_ordered_active

            incremental = assembly_pipeline_ordered_active()
        except Exception:
            incremental = False

    if incremental:
        return run_resolution_ambiguous_batch(
            auto_merge_confidence=auto_merge_confidence,
            cross_domain_confidence=cross_domain_confidence,
        )

    results: dict[str, Any] = {"domains": {}, "cross_domain": {}}

    for domain_key in get_active_domain_keys():
        domain_result: dict[str, Any] = {}

        alias_result = populate_aliases_from_mentions(domain_key)
        domain_result["aliases"] = alias_result

        merge_result = auto_merge_high_confidence(domain_key, min_confidence=auto_merge_confidence)
        domain_result["merges"] = merge_result

        domain_result["surname_families"] = reconcile_surname_family_clusters(domain_key)

        results["domains"][domain_key] = domain_result

    cross_result = link_cross_domain_entities(min_confidence=cross_domain_confidence)
    results["cross_domain"] = cross_result

    return results
