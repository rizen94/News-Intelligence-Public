"""
Guardrails for storyline creation: reject overly generic titles/clusters and
require minimum subject coherence before promote, save, or mega-parent merge.

Finance pain point: bare "reports" / "earnings" megathreads from unrelated company
filings. Valid earnings-season arcs need shared theme (sector misses, guidance cuts)
or multiple named actors — not keyword overlap on generic filing vocabulary.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from typing import Any
from config.runtime import env_bool, env_float, env_int, env_pop, env_set, env_setdefault, env_str

# Align with claim_extraction_service._GENERIC_SUBJECTS (avoid importing that module at package load).
_GENERIC_SUBJECTS = frozenset(
    {
        "company",
        "companies",
        "administration",
        "government",
        "public",
        "people",
        "person",
        "official",
        "officials",
        "officer",
        "officers",
        "investigator",
        "investigators",
        "source",
        "sources",
        "analyst",
        "analysts",
        "method",
        "methods",
        "approach",
        "approaches",
        "model",
        "models",
        "system",
        "systems",
        "report",
        "reports",
        "study",
        "studies",
        "paper",
        "papers",
        "price target",
        "target price",
        "consumer",
        "consumers",
        "customer",
        "customers",
        "parent",
        "parents",
        "women",
        "men",
        "i",
        "we",
        "they",
        "it",
        "this",
        "that",
    }
)

def _subject_norm(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _is_overly_generic_subject(subject_text: str | None) -> bool:
    s = _subject_norm(subject_text)
    if not s:
        return True
    if s in _GENERIC_SUBJECTS:
        return True
    if len(s) <= 1:
        return True
    if re.fullmatch(r"[a-z]", s):
        return True
    if re.fullmatch(r"(the\s+)?(company|government|administration|public|people|officials?)", s):
        return True
    return False


# Storyline-specific generics (extends claim-extraction set via helper above).
_STORYLINE_GENERIC_TITLE_WORDS = frozenset(
    {
        "news",
        "update",
        "updates",
        "latest",
        "breaking",
        "related",
        "articles",
        "story",
        "stories",
        "coverage",
        "developments",
        "analysis",
        "markets",
        "market",
        "stocks",
        "stock",
        "shares",
        "earnings",
        "earnings season",
        "reports",
        "report",
        "quarterly",
        "results",
        "financial",
        "finance",
        "business",
        "corporate",
        "company",
        "companies",
        "sector",
        "economy",
        "economic",
        "investors",
        "investor",
        "trading",
        "wall",
        "street",
        "keywords",
        "entities",
        "ongoing",
        "preview",
        "transcript",
        "summary",
        "filings",
    }
)

# Finance entity extraction noise (not sufficient alone for coherence).
_FINANCE_ENTITY_STOPWORDS = frozenset(
    {
        "market",
        "markets",
        "stock",
        "stocks",
        "share",
        "shares",
        "earnings",
        "report",
        "reports",
        "quarter",
        "quarterly",
        "revenue",
        "profit",
        "loss",
        "guidance",
        "forecast",
        "analyst",
        "analysts",
        "investor",
        "investors",
        "company",
        "companies",
        "corp",
        "inc",
        "ltd",
        "llc",
        "ceo",
        "cfo",
        "fed",
        "federal",
        "reserve",
        "year",
        "today",
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    }
    | _STORYLINE_GENERIC_TITLE_WORDS
)

# Bare finance topic titles (whole title or "Ongoing: …" mega prefix).
_FINANCE_BARE_TOPIC_RE = re.compile(
    r"^(?:ongoing:\s*)?"
    r"(?:q[1-4]\s+|first[- ]quarter\s+|second[- ]quarter\s+|third[- ]quarter\s+|fourth[- ]quarter\s+)?"
    r"(?:corporate\s+|company\s+|quarterly\s+)?"
    r"(?:earnings(?:\s+reports?|\s+season|\s+results?|\s+updates?)?|"
    r"reports?(?:\s+season|\s+roundups?|\s+updates?)?|"
    r"financial\s+reports?|market\s+updates?|stock\s+updates?)"
    r"(?:\s+season|\s+coverage|\s+roundups?)?"
    r"\s*$",
    re.IGNORECASE,
)

_EARNINGS_REPORT_CHILD_TITLE_RE = re.compile(
    r"\b(earnings|reports?|quarterly\s+results?|q[1-4]\s+earnings)\b",
    re.IGNORECASE,
)

# Shared theme signals for valid cross-company earnings arcs.
_EARNINGS_COHERENCE_THEME_RE = re.compile(
    r"\b("
    r"miss(?:ed|es|ing)?\s+expectations?|beat\s+expectations?|"
    r"guidance\s+cut|lowered\s+guidance|raised\s+guidance|"
    r"profit\s+warning|revenue\s+decline|same[- ]store\s+sales|"
    r"sector(?:-wide)?\s+(?:selloff|rally|weakness|strength)|"
    r"semiconductor|retail|banking|energy\s+sector|tech\s+sector|"
    r"tariff\s+impact|supply\s+chain"
    r")\b",
    re.IGNORECASE,
)


def guardrails_enabled() -> bool:
    return env_str("STORYLINE_COHERENCE_GUARDRAILS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def min_distinct_specific_entities() -> int:
    try:
        return max(1, int(env_str("STORYLINE_MIN_DISTINCT_SPECIFIC_ENTITIES", "2")))
    except ValueError:
        return 2


def _norm_title(title: str | None) -> str:
    return re.sub(r"\s+", " ", (title or "").strip())


def _title_content_words(title: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z0-9]+", title or "") if len(w) >= 2]


# 5W1H + editorial prompt keys that must never become mega titles / entities.
_FIVE_W_PLACEHOLDER_TOKENS = frozenset(
    {"what", "who", "when", "where", "why", "how", "lede", "headline", "summary"}
)

_PLACEHOLDER_MEGA_TITLE_RE = re.compile(
    r"^Ongoing:\s*(WHAT|WHO|WHEN|WHERE|WHY|HOW|LEDE|HEADLINE|SUMMARY)\s*$",
    re.IGNORECASE,
)

_LEAKED_TITLE_KEY_RE = re.compile(
    r"^[\{\[]|"
    r'["\']?(lede|headline|summary|title|who|what|when|where|why|how)["\']?\s*:',
    re.IGNORECASE,
)


def is_placeholder_mega_title(title: str | None) -> bool:
    """True for titles like 'Ongoing: WHAT' (leaked 5W1H keys)."""
    t = _norm_title(title)
    if not t:
        return False
    if _PLACEHOLDER_MEGA_TITLE_RE.match(t):
        return True
    lower = t.lower()
    if lower.startswith("ongoing:"):
        rest = lower[len("ongoing:") :].strip()
        words = _title_content_words(rest)
        if len(words) == 1 and words[0] in _FIVE_W_PLACEHOLDER_TOKENS:
            return True
    return False


def is_leaked_storyline_title(title: str | None) -> bool:
    """True when title looks like JSON / prompt-key leakage."""
    t = _norm_title(title)
    if not t:
        return False
    if t.startswith("{") or t.startswith("["):
        return True
    if '":' in t or "':" in t:
        return True
    if _LEAKED_TITLE_KEY_RE.search(t):
        return True
    return False


_YEAR_ENTITY_TITLE_PREFIX_RE = re.compile(r"^Year_20\d{2}\s*:\s*", re.IGNORECASE)


def sanitize_storyline_title_for_display(
    title: str | None,
    *,
    fallback: str | None = None,
) -> str:
    """
    Strip leaked JSON braces, prompt keys, and Year_20xx: prefixes for API/UI.

    Does not invent a better headline — only removes known garbage prefixes.
    """
    raw = (title or "").strip()
    if not raw:
        return (fallback or "").strip() or "Untitled Storyline"

    cleaned = _YEAR_ENTITY_TITLE_PREFIX_RE.sub("", raw).strip()
    if cleaned.startswith("{") or cleaned.startswith("["):
        cleaned = re.sub(r"^[\{\[\s\"']+", "", cleaned)
        cleaned = re.sub(r"^:\s*", "", cleaned).strip()
        cleaned = re.sub(
            r"^(lede|headline|summary|title|who|what|when|where|why|how)\s*:\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        ).strip()

    if (
        not cleaned
        or is_placeholder_mega_title(cleaned)
        or is_leaked_storyline_title(cleaned)
        or cleaned in ("{", ":", "[", "]")
    ):
        return (fallback or "").strip() or "Untitled Storyline"
    return _soft_ellipsize_mid_word_truncation(cleaned)


def _soft_ellipsize_mid_word_truncation(title: str) -> str:
    """If title ends mid-token (e.g. '… ove'), trim to last full word + ellipsis."""
    t = (title or "").strip()
    if len(t) < 24:
        return t
    if re.search(r"[.!?…)\"'\]]$", t):
        return t
    m = re.match(r"^(.*\s)([A-Za-z]{1,3})$", t)
    if not m:
        return t
    head = m.group(1).rstrip()
    if len(head) < 20:
        return t
    return f"{head}…"


def is_mega_template_description(description: str | None) -> bool:
    """True for retired boilerplate mega descriptions."""
    d = (description or "").strip().lower()
    return d.startswith("mega-storyline covering") or d.startswith(
        "mega-storyline (initializing"
    )


def mega_quality_score_for_title(title: str | None, *, coherent: bool = True) -> float:
    """Stamp quality_score on mega rows: low for placeholders/leaks."""
    if is_placeholder_mega_title(title) or is_leaked_storyline_title(title):
        return 0.15
    if is_overly_generic_storyline_title(title):
        return 0.25
    if not coherent:
        return 0.25
    return 0.75


def mega_min_shared_entities() -> int:
    try:
        return max(1, int(env_str("STORYLINE_MEGA_MIN_SHARED_ENTITIES", "1")))
    except ValueError:
        return 1


def merge_min_shared_entities() -> int:
    try:
        return max(1, int(env_str("STORYLINE_MERGE_MIN_SHARED_ENTITIES", "1")))
    except ValueError:
        return 1


def _clean_storyline_entity_set(raw: Any) -> set[str]:
    out: set[str] = set()
    for ent in raw or set():
        key = (ent or "").strip().lower()
        if (
            not key
            or len(key) < 3
            or key in _FINANCE_ENTITY_STOPWORDS
            or key in _FIVE_W_PLACEHOLDER_TOKENS
        ):
            continue
        out.add(key)
    return out


def _entities_from_title(title: str | None) -> set[str]:
    """Lightweight title entities for merge gating when StorylineInfo.entities is empty."""
    text = title or ""
    ents: set[str] = set()
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text):
        key = match.group(1).strip().lower()
        if (
            len(key) >= 3
            and key not in _FINANCE_ENTITY_STOPWORDS
            and key not in _FIVE_W_PLACEHOLDER_TOKENS
        ):
            ents.add(key)
    for match in re.finditer(r"\b([A-Z]{2,})\b", text):
        key = match.group(1).lower()
        if (
            len(key) >= 2
            and key not in _FINANCE_ENTITY_STOPWORDS
            and key not in _FIVE_W_PLACEHOLDER_TOKENS
        ):
            ents.add(key)
    return ents


def assess_storyline_pair_merge_coherence(
    domain: str,
    s1: Any,
    s2: Any,
) -> tuple[bool, str]:
    """
    Gate pairwise storyline merge. Requires shared non-stopword entities and
    rejects leaked/placeholder titles.
    """
    if not guardrails_enabled():
        return True, "disabled"

    t1 = (getattr(s1, "title", None) or "").strip()
    t2 = (getattr(s2, "title", None) or "").strip()
    if is_leaked_storyline_title(t1) or is_leaked_storyline_title(t2):
        return False, "leaked_title"
    if is_placeholder_mega_title(t1) or is_placeholder_mega_title(t2):
        return False, "placeholder_title"

    e1 = _clean_storyline_entity_set(getattr(s1, "entities", None))
    e2 = _clean_storyline_entity_set(getattr(s2, "entities", None))
    if not e1:
        e1 = _entities_from_title(t1)
    if not e2:
        e2 = _entities_from_title(t2)

    shared = e1 & e2
    min_shared = merge_min_shared_entities()
    if len(shared) < min_shared:
        return False, "insufficient_shared_entities"

    # Finance: bare earnings pairs without shared actors already fail above;
    # also block when both titles are generic filing vocabulary only.
    dk = (domain or "").lower().replace("_", "-")
    if dk.startswith("finance"):
        if is_overly_generic_storyline_title(t1, domain) and is_overly_generic_storyline_title(
            t2, domain
        ):
            return False, "generic_pair_titles"

    return True, "ok"


def is_overly_generic_storyline_title(title: str | None, domain: str = "") -> bool:
    """True when title is too vague to stand alone as a storyline label."""
    t = _norm_title(title)
    if not t:
        return True
    if is_placeholder_mega_title(t) or is_leaked_storyline_title(t):
        return True
    if _is_overly_generic_subject(t):
        return True

    lower = t.lower()
    if lower.startswith("ongoing:"):
        lower = lower[len("ongoing:") :].strip()

    # Single-token or all-generic multi-word titles
    words = _title_content_words(lower)
    if not words:
        return True
    if len(words) == 1 and words[0] in _FIVE_W_PLACEHOLDER_TOKENS:
        return True
    if len(words) == 1 and words[0] in _STORYLINE_GENERIC_TITLE_WORDS:
        return True
    uniq = list(dict.fromkeys(words))
    if uniq and all(w in _STORYLINE_GENERIC_TITLE_WORDS for w in uniq):
        return True
    if len(words) <= 3 and all(w in _STORYLINE_GENERIC_TITLE_WORDS for w in words):
        return True

    dk = (domain or "").lower().replace("_", "-")
    if dk.startswith("finance") and _FINANCE_BARE_TOPIC_RE.match(t):
        return True

    # "Emerging Story" / keyword fallback titles from proactive detection
    if lower in {"emerging story", "related articles", "related stories"}:
        return True

    return False


def _article_text_blob(article: dict[str, Any]) -> str:
    return " ".join(
        [
            str(article.get("title") or ""),
            str(article.get("summary") or ""),
            str(article.get("content") or "")[:2000],
        ]
    )


def extract_specific_entities_from_text(text: str) -> set[str]:
    """Capitalized phrases + acronyms, minus generic finance/storyline noise."""
    entities: set[str] = set()
    for match in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text or ""):
        phrase = match.group(1).strip()
        key = phrase.lower()
        if len(key) < 3 or key in _FINANCE_ENTITY_STOPWORDS:
            continue
        entities.add(key)
    for match in re.finditer(r"\b([A-Z]{2,})\b", text or ""):
        key = match.group(1).lower()
        if len(key) >= 2 and key not in _FINANCE_ENTITY_STOPWORDS:
            entities.add(key)
    return entities


def extract_cluster_specific_entities(articles: list[dict[str, Any]]) -> Counter[str]:
    """Count specific entities per article (each article contributes at most once per entity)."""
    counts: Counter[str] = Counter()
    for article in articles:
        blob = _article_text_blob(article)
        for ent in extract_specific_entities_from_text(blob):
            counts[ent] += 1
    return counts


def _cluster_has_earnings_report_vocabulary(articles: list[dict[str, Any]]) -> bool:
    hits = 0
    for article in articles:
        blob = _article_text_blob(article).lower()
        if _EARNINGS_REPORT_CHILD_TITLE_RE.search(blob):
            hits += 1
    return hits >= max(2, len(articles) // 2)


def _cluster_has_shared_theme(articles: list[dict[str, Any]]) -> bool:
    theme_hits = 0
    for article in articles:
        if _EARNINGS_COHERENCE_THEME_RE.search(_article_text_blob(article)):
            theme_hits += 1
    return theme_hits >= 2


def assess_cluster_coherence(
    domain: str,
    title: str,
    articles: list[dict[str, Any]],
    *,
    common_entities: list[str] | None = None,
) -> tuple[bool, str]:
    """
    Return (coherent, reason). When guardrails disabled, always (True, "disabled").
    """
    if not guardrails_enabled():
        return True, "disabled"
    if not articles:
        return False, "empty_cluster"

    if is_overly_generic_storyline_title(title, domain):
        return False, "generic_title"

    entity_counts = extract_cluster_specific_entities(articles)
    if common_entities:
        for ent in common_entities:
            key = (ent or "").strip().lower()
            if key and key not in _FINANCE_ENTITY_STOPWORDS:
                entity_counts[key] = max(entity_counts.get(key, 0), 1)

    dk = (domain or "").lower().replace("_", "-")
    if dk.startswith("finance") and _cluster_has_earnings_report_vocabulary(articles):
        if _cluster_has_shared_theme(articles):
            return True, "finance_earnings_theme"
        recurring_entities = sum(1 for _, n in entity_counts.items() if n >= 2)
        if recurring_entities >= 2:
            return True, "finance_recurring_entities"
        if entity_counts:
            top_entity, top_n = entity_counts.most_common(1)[0]
            if top_n >= max(3, int(len(articles) * 0.6)):
                return True, f"finance_dominant_entity:{top_entity}"
        return False, "finance_generic_earnings_reports"

    distinct_specific = sum(1 for _, n in entity_counts.items() if n >= 1)
    min_distinct = min_distinct_specific_entities()
    if distinct_specific >= min_distinct:
        return True, "entity_diversity"

    # Strong single-subject: one entity in most articles
    if entity_counts:
        top_entity, top_n = entity_counts.most_common(1)[0]
        if top_n >= max(3, int(len(articles) * 0.6)):
            return True, f"dominant_entity:{top_entity}"

    if distinct_specific < min_distinct:
        return False, "insufficient_entity_specificity"

    return True, "ok"


def assess_kitchen_sink_risk(
    title: str | None,
    articles: list[dict[str, Any]],
) -> tuple[bool, str]:
    """
    Heuristic for bloated multi-topic storylines that still pass entity_diversity.
    Returns (is_kitchen_sink, reason).
    """
    t = (title or "").strip()
    lower = t.lower()
    if " amid " in lower and (" and " in lower or "," in lower):
        return True, "title_amid_join"
    if not articles:
        return False, "ok"
    entity_counts = extract_cluster_specific_entities(articles)
    n = len(articles)
    if not entity_counts:
        return False, "ok"
    top_entity, top_n = entity_counts.most_common(1)[0]
    # Many distinct actors, none dominant → kitchen sink
    if len(entity_counts) >= 8 and top_n < max(2, int(n * 0.25)):
        return True, f"diffuse_entities:{top_entity}"
    # Two leading entities both weak relative to bag size
    top2 = entity_counts.most_common(2)
    if len(top2) == 2 and n >= 15:
        if all(c < max(2, int(n * 0.2)) for _, c in top2) and len(entity_counts) >= 6:
            return True, "no_dominant_theme"
    return False, "ok"


def assess_mega_group_coherence(domain: str, children: list[Any]) -> tuple[bool, str]:
    """
    Gate mega-storyline parent creation. ``children`` are StorylineInfo-like objects
    with ``title`` and optional ``entities`` set.
    """
    if not guardrails_enabled():
        return True, "disabled"
    if len(children) < 2:
        return False, "too_few_children"

    titles = [(getattr(c, "title", None) or "").strip() for c in children]
    if any(is_leaked_storyline_title(t) for t in titles if t):
        return False, "leaked_child_title"
    if all(is_overly_generic_storyline_title(t, domain) for t in titles if t):
        return False, "all_generic_child_titles"

    # All domains: require at least one entity shared by ≥2 children.
    all_entities: Counter[str] = Counter()
    for child in children:
        for ent in getattr(child, "entities", None) or set():
            key = (ent or "").strip().lower()
            if (
                not key
                or len(key) < 3
                or key in _FINANCE_ENTITY_STOPWORDS
                or key in _FIVE_W_PLACEHOLDER_TOKENS
            ):
                continue
            all_entities[key] += 1
    shared = sum(1 for _, n in all_entities.items() if n >= 2)
    min_shared = mega_min_shared_entities()
    if shared < min_shared:
        return False, "insufficient_shared_entities"

    dk = (domain or "").lower().replace("_", "-")
    if dk.startswith("finance"):
        er_hits = sum(1 for t in titles if _EARNINGS_REPORT_CHILD_TITLE_RE.search(t))
        if er_hits >= max(2, (len(children) * 2 + 2) // 3):
            recurring = sum(1 for _, n in all_entities.items() if n >= 2)
            if recurring < 2:
                return False, "finance_earnings_mega_insufficient_entities"

    return True, "ok"


def storyline_metadata_prompt_suffix(domain: str) -> str:
    """Extra LLM instructions for title/description generation."""
    dk = (domain or "").lower().replace("_", "-")
    base = (
        "\nRequirements:\n"
        "- Headline must name specific actors (companies, officials, sectors, commodities) "
        "when the sources support it — never a bare generic like 'Reports' or 'Earnings'.\n"
        "- Description must state what is being reported AND why it matters "
        "(market/sector/policy implications), not boilerplate about 'related articles'.\n"
        "- If sources only share generic filing vocabulary without a shared story, "
        "prefer the most specific shared theme or return a title that names the sector/event.\n"
    )
    if dk.startswith("finance"):
        base += (
            "- Finance: distinguish unrelated company filings from a coherent arc "
            "(e.g. sector-wide misses, tariff impact on semiconductors). "
            "Q2 earnings is valid only when companies/sectors share a causal thread.\n"
        )
    return base


def post_process_storyline_description(description: str | None, domain: str) -> str:
    """Trim boilerplate from stored descriptions when guardrails are on."""
    d = (description or "").strip()
    if not d or not guardrails_enabled():
        return d
    lower = d.lower()
    boilerplate_markers = (
        "cluster of ",
        " related articles",
        "similarity.",
        "emerging storyline detected from",
        "mega-storyline covering",
        "mega-storyline (initializing",
    )
    if any(m in lower for m in boilerplate_markers) and (
        len(d) < 120 or lower.startswith("mega-storyline")
    ):
        return ""
    return d
