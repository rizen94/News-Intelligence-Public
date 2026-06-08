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
    return os.getenv("STORYLINE_COHERENCE_GUARDRAILS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def min_distinct_specific_entities() -> int:
    try:
        return max(1, int(os.getenv("STORYLINE_MIN_DISTINCT_SPECIFIC_ENTITIES", "2")))
    except ValueError:
        return 2


def _norm_title(title: str | None) -> str:
    return re.sub(r"\s+", " ", (title or "").strip())


def _title_content_words(title: str) -> list[str]:
    return [w.lower() for w in re.findall(r"[A-Za-z0-9]+", title or "") if len(w) >= 2]


def is_overly_generic_storyline_title(title: str | None, domain: str = "") -> bool:
    """True when title is too vague to stand alone as a storyline label."""
    t = _norm_title(title)
    if not t:
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
    if len(words) == 1 and words[0] in _STORYLINE_GENERIC_TITLE_WORDS:
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
    if all(is_overly_generic_storyline_title(t, domain) for t in titles if t):
        return False, "all_generic_child_titles"

    dk = (domain or "").lower().replace("_", "-")
    if dk.startswith("finance"):
        er_hits = sum(1 for t in titles if _EARNINGS_REPORT_CHILD_TITLE_RE.search(t))
        if er_hits >= max(2, (len(children) * 2 + 2) // 3):
            all_entities: Counter[str] = Counter()
            for child in children:
                for ent in getattr(child, "entities", None) or set():
                    key = (ent or "").strip().lower()
                    if key and key not in _FINANCE_ENTITY_STOPWORDS:
                        all_entities[key] += 1
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
    )
    if any(m in lower for m in boilerplate_markers) and len(d) < 120:
        return ""
    return d
