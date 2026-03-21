"""
Entity relational expansion — resolve phrases like "Zohran Mamdani's wife" to real names.

Detects relational person phrases (X's wife, spouse of X, X's spokesperson, etc.),
looks up the related person's name via LLM (or Wikipedia when available), and returns
the expanded name so we store real people/places instead of concepts.

Used at article entity extraction (before resolve_to_canonical) and optionally in
batch jobs to normalize existing entity_canonical rows.
"""

import logging
import re

logger = logging.getLogger(__name__)

# Patterns: (anchor_group, relation_group). Anchor is the known person; relation is wife/husband/etc.
# "X's wife" -> anchor=X, relation=wife
PERSON_RELATIONAL_PATTERNS = [
    re.compile(
        r"^(.+?)'s\s+(wife|husband|spouse|partner|spokesperson|spokesman|spokeswoman)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(wife|husband|spouse|partner|spokesperson|spokesman|spokeswoman)\s+of\s+(.+)$",
        re.IGNORECASE,
    ),
    re.compile(r"^(.+?)'s\s+(daughter|son|mother|father|sister|brother)$", re.IGNORECASE),
    re.compile(r"^(daughter|son|mother|father|sister|brother)\s+of\s+(.+)$", re.IGNORECASE),
]

# For "wife of X" we get (relation, anchor) from group 2 and 1
INVERTED_RELATION_GROUPS = (1, 2)  # group 2 = anchor, group 1 = relation


def is_relational_person_phrase(name: str) -> bool:
    """Return True if name looks like a relational phrase (e.g. "X's wife")."""
    if not name or len(name) < 6:
        return False
    name = name.strip()
    for pat in PERSON_RELATIONAL_PATTERNS:
        if pat.search(name):
            return True
    return False


def _parse_relational_phrase(name: str) -> tuple[str, str] | None:
    """
    If name matches a relational pattern, return (anchor_name, relation).
    E.g. "Zohran Mamdani's wife" -> ("Zohran Mamdani", "wife").
    "wife of Zohran Mamdani" -> ("Zohran Mamdani", "wife").
    """
    name = name.strip()
    for pat in PERSON_RELATIONAL_PATTERNS:
        m = pat.search(name)
        if not m:
            continue
        groups = m.groups()
        if len(groups) >= 2:
            # "X's wife" -> group0=X, group1=wife. "wife of X" -> group0=wife, group1=X
            if re.search(r"\s+of\s+", name, re.IGNORECASE):
                relation, anchor = groups[0].strip(), groups[1].strip()
            else:
                anchor, relation = groups[0].strip(), groups[1].strip()
            if anchor and relation and len(anchor) >= 2:
                return (anchor, relation)
    return None


def _normalize_llm_name(raw: str) -> str | None:
    """Extract a single full name from LLM response; return None if unknown or invalid."""
    if not raw:
        return None
    raw = raw.strip()
    # Use first line only (LLM may add explanation)
    first_line = raw.split("\n")[0].strip()
    raw = first_line.rstrip(".")
    # Single word "unknown" or "n/a" etc.
    if raw.lower() in ("unknown", "n/a", "na", "none", "no", "cannot", "unk", ""):
        return None
    # Strip quotes and "the" prefix
    raw = re.sub(r"^['\"]|['\"]$", "", raw)
    raw = re.sub(r"^(the)\s+", "", raw, flags=re.IGNORECASE)
    # Should look like a name: at least 2 chars, no obvious sentence
    if len(raw) < 2 or "." in raw[:10] or raw.lower().startswith("i "):
        return None
    return raw[:255]


async def expand_relational_entity_async(
    entity_name: str,
    entity_type: str,
    llm_call,
    timeout_seconds: float = 8.0,
) -> tuple[str, str | None]:
    """
    If entity_name is a relational phrase (e.g. "Zohran Mamdani's wife"),
    try to resolve it to the actual person's name via LLM.

    llm_call: async (prompt: str) -> str (e.g. llm._call_ollama(model, prompt)).

    Returns (name_to_use, original_phrase_if_expanded).
    - If not relational or expansion fails: (entity_name, None).
    - If expanded: (resolved_name, entity_name) so caller can use resolved_name for
      canonical resolution and add entity_name as alias.
    """
    name = (entity_name or "").strip()
    if not name or entity_type != "person":
        return (name, None)
    if not is_relational_person_phrase(name):
        return (name, None)

    parsed = _parse_relational_phrase(name)
    if not parsed:
        return (name, None)

    anchor, relation = parsed
    prompt = (
        f'What is the full name of the person described as "{name}"?\n'
        f'Reply with ONLY the person\'s full name (e.g. "Jane Smith"). '
        f"If you do not know or cannot determine, reply with exactly: unknown"
    )
    try:
        import asyncio

        response = await asyncio.wait_for(llm_call(prompt), timeout=timeout_seconds)
        resolved = _normalize_llm_name(response)
        if resolved:
            logger.debug("Entity expansion: %s -> %s", name, resolved)
            return (resolved, name)
    except Exception as e:
        logger.debug("Entity expansion failed for %s: %s", name, e)
    return (name, None)


def try_expand_entity_name_sync(
    entity_name: str,
    entity_type: str,
    expanded_cache: dict | None = None,
) -> tuple[str, str | None]:
    """
    Synchronous helper: if you already have a cache of (phrase -> resolved_name),
    use it. Otherwise returns (entity_name, None) so callers can skip expansion
    when not in an async context or when expansion is disabled.

    expanded_cache: optional dict mapping relational phrase -> resolved name.
    """
    name = (entity_name or "").strip()
    if not name or entity_type != "person" or not is_relational_person_phrase(name):
        return (name, None)
    if expanded_cache is not None and name in expanded_cache:
        resolved = expanded_cache.get(name)
        if resolved:
            return (resolved, name)
    return (name, None)


def get_relational_patterns_help() -> str:
    """Return a short description of detected patterns for docs."""
    return (
        'Relational person phrases: "X\'s wife", "X\'s husband", "X\'s spouse", '
        '"X\'s spokesperson", "wife of X", "daughter/son/mother/father of X", etc. '
        "Expansion uses the LLM to resolve to the actual person's name."
    )
