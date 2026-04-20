"""
Pre-filter for Wikipedia entity resolution.

Determines whether an entity is worth sending to the Wikipedia API
based on its type and name characteristics. Prevents wasting API calls
on generic topics, abstract concepts, dollar amounts, and vague subjects
that will never resolve to a meaningful Wikipedia article — or whose
Wikipedia article wouldn't add useful enrichment to a news intelligence system.

This sits AFTER classify_bad_entity (which catches NER garbage) and BEFORE
the Wikipedia API call. It answers: "This is a real entity name, but is it
worth enriching via Wikipedia?"

Usage:
    from lib.wikipedia_prefilter import is_wikipedia_resolvable

    resolvable, reason = is_wikipedia_resolvable("Federal Reserve", "organization")
    # (True, "type_always_resolve")

    resolvable, reason = is_wikipedia_resolvable("economic uncertainty", "subject")
    # (False, "generic_phrase")
"""

import re
import logging

log = logging.getLogger(__name__)

# ── Type-based rules ─────────────────────────────────────────────

# These entity types almost always map to a real Wikipedia article
ALWAYS_RESOLVE_TYPES = frozenset({"person", "organization", "location", "family"})

# These need heuristic checks on the name before we bother
CONDITIONAL_TYPES = frozenset({"subject", "recurring_event"})

# These should never be sent to Wikipedia
NEVER_RESOLVE_TYPES = frozenset({"topic", "theme", "tag"})


# ── Name-based skip patterns ────────────────────────────────────

_SKIP_PATTERNS = [
    # Dollar amounts / price targets:  "$100 oil", "$847M", "$25B"
    re.compile(r"^\$\d"),
    # Percentage-led phrases: "5% rally"
    re.compile(r"^\d+(\.\d+)?%"),
    # Bare numbers with units: "100bps", "2.5x"
    re.compile(r"^\d+(\.\d+)?(bps|bp|x|pp)\b", re.I),
    # Slash-separated phrases: "Hearing / Summit", "Summit / Hearing"
    re.compile(r"\s*/\s*"),
    # "None found", "None specified", "None identified" — extraction failures
    re.compile(r"^none\s+(found|specified|identified|available|listed|given|provided|applicable)\b", re.I),
    # Phrases ending with abstract nouns that signal thematic descriptions
    re.compile(
        r"\b(concerns?|fears?|risks?|outlook|impact|tensions?|uncertainty"
        r"|challenges?|opportunities?|pressures?|implications?"
        r"|consequences?|dynamics?|fundamentals?|headwinds?"
        r"|tailwinds?|sentiments?|momentum)\s*$",
        re.I,
    ),
    # "The rise/fall/future/cost of …" framing
    re.compile(
        r"^(the|a|an)\s+(rise|fall|decline|growth|impact|future|state"
        r"|role|end|cost|price|value|rate|level|risk|collapse"
        r"|resurgence|return|promise|threat|death)\s+of\s+",
        re.I,
    ),
    # "[action] on/in/with/against/by [proper noun]" — generic topic, not named entity
    # e.g. "attack on Iran", "conflict in Syria", "sanctions against Russia"
    re.compile(
        r"^(attacks?|conflict|conflicts|war|sanctions?|strikes?|assault"
        r"|bombing|bombings|invasion|escalation|crackdown|siege|blockade"
        r"|embargo|intervention|operations?)\s+(on|in|with|against|by)\s+",
        re.I,
    ),
]

# Exact lowercase matches for common generic phrases whose Wikipedia
# articles wouldn't add useful enrichment to a news intelligence system
_GENERIC_PHRASES = frozenset({
    # Economics / macro
    "economic growth", "economic recovery", "economic uncertainty",
    "economic outlook", "economic slowdown", "economic downturn",
    "economic policy", "economic reform", "economic crisis",
    "interest rates", "interest rate", "rate cuts", "rate hikes",
    "rate cut", "rate hike", "rate decision",
    "trade policy", "trade war", "trade tensions", "trade deal",
    "market volatility", "market rally", "market crash", "market correction",
    "fiscal policy", "monetary policy",
    "government spending", "government shutdown", "government debt",
    "consumer spending", "consumer confidence", "consumer prices",
    "corporate earnings", "earnings season", "earnings growth",
    "debt ceiling", "national debt", "deficit spending",
    "inflation", "deflation", "stagflation", "recession",
    "supply chain", "supply chains", "supply chain disruption",
    "job market", "labor market", "housing market",
    "stock market", "bond market", "commodity prices",
    "wage growth", "income inequality", "wealth inequality",
    # Energy
    "energy prices", "oil prices", "gas prices", "energy crisis",
    "energy transition", "renewable energy", "clean energy",
    # Policy / governance
    "immigration policy", "border security", "foreign policy",
    "national security", "cybersecurity", "data privacy",
    "healthcare costs", "drug pricing", "healthcare reform",
    "tax reform", "tax cuts", "tax policy", "tax hikes",
    "climate change", "global warming", "climate policy",
    # Tech
    "artificial intelligence", "machine learning",
    "ai regulation", "tech regulation", "antitrust",
    # Markets
    "ipo market", "bond yields", "treasury yields",
    "credit markets", "emerging markets",
    "risk appetite", "risk sentiment",
    # Generic
    "geopolitical risk", "geopolitical tensions",
    "bipartisan support", "partisan divide",
    "executive order", "executive orders",
    "earnings report", "earnings reports",
    "quarterly results", "annual report",
    "market share", "profit margins",
    "tariffs", "sanctions", "deregulation",
    # Additional generic subjects that appear in the data
    "human rights", "drone strikes", "drone attack",
    "air pollution", "capital punishment", "death penalty",
    "energy infrastructure", "energy markets",
    "immigration enforcement",
})

# Known resolvable names — override all other rules
_KNOWN_RESOLVABLE = frozenset({
    "s&p 500", "nasdaq", "nasdaq composite", "dow jones",
    "dow jones industrial average", "ftse 100", "nikkei 225",
    "russell 2000", "vix",
    "bitcoin", "ethereum", "dogecoin",
    "401(k)", "401(k)s", "roth ira",
    "covid-19", "covid", "coronavirus",
    "el niño", "la niña",
})

# ── Generic single words that are NOT proper nouns ──────────────
# Sentence-cased words that appear as subjects but are just common
# English nouns. These would match Wikipedia disambiguation pages
# or overly broad articles that don't enrich news intelligence.
_GENERIC_SINGLE_WORDS = frozenset({
    "accountability", "affordability", "airfares", "allegations",
    "announcement", "architecture", "arrest", "arrests", "assassination",
    "assault", "attack", "attacks", "austerity",
    "bankruptcy", "budget", "bureaucracy",
    "campaign", "ceasefire", "censorship", "collapse", "competition",
    "compliance", "conflict", "congress", "conscription", "conservation",
    "consolidation", "construction", "controversy", "conviction",
    "cooperation", "corruption", "counterterrorism", "coup", "crisis",
    "debate", "decentralization", "defense", "deficit", "democracy",
    "demographics", "demonstration", "deportation", "deregulation",
    "detention", "development", "diplomacy", "disinformation",
    "displacement", "disruption", "dissent", "diversification",
    "drones", "drought",
    "earthquake", "economy", "education", "election", "elections",
    "embargo", "emergency", "emigration", "employment", "energy",
    "enforcement", "environment", "epidemic", "escalation", "espionage",
    "evacuation", "expansion", "exploitation", "exports", "extremism",
    "famine", "federalism", "flooding", "fraud",
    "gender", "gentrification", "globalization", "governance",
    "hearing", "healthcare", "homelessness", "housing",
    "immigration", "impeachment", "imports", "incarceration",
    "independence", "industrialization", "inequality", "infrastructure",
    "innovation", "insurgency", "integration", "intelligence",
    "intervention", "investigation", "investment",
    "journalism", "judiciary",
    "labor", "leadership", "legislation", "legitimacy",
    "liberalization", "literacy", "litigation", "lobbying",
    "manufacturing", "merger", "migration", "militarization",
    "mobilization", "modernization", "monopoly",
    "nationalism", "nationalization", "negotiation", "negotiations",
    "neutrality", "normalization", "nutrition",
    "occupation", "opposition", "outbreak", "oversight",
    "pandemic", "parliament", "partisanship", "peace", "piracy",
    "polarization", "policing", "pollution", "populism", "poverty",
    "preparedness", "presidency", "privatization", "procurement",
    "propaganda", "prosecution", "prosperity", "protest", "protests",
    "radicalization", "ratification", "rebellion", "recession",
    "reconciliation", "reconstruction", "redistribution", "reform",
    "reforms", "refugees", "regulation", "regulations",
    "rehabilitation", "repatriation", "repression", "resignation",
    "resistance", "restitution", "restructuring", "retaliation",
    "revolution", "rivalry",
    "sabotage", "secession", "security", "segregation", "sovereignty",
    "spending", "stability", "statehood", "stimulus", "strategy",
    "subsidies", "summit", "surveillance", "sustainability",
    "taxation", "technology", "terrorism", "trade", "trafficking",
    "transition", "transparency", "treason", "treaty",
    "unemployment", "unrest", "uprising", "urbanization",
    "vaccination", "violence", "volatility",
    "warfare", "whistleblowing",
    # Common non-political generics
    "faith", "culture", "heritage", "identity", "ideology",
    "legacy", "memory", "narrative", "resilience", "solidarity",
    "tradition", "transformation", "unity", "vision",
})

# ── Generic multi-word patterns for title-cased subjects ────────
# Patterns like "Escalating Conflict", "Drone Attack", "Democratic Primary"
# where words are title-cased but the phrase is still generic.
_GENERIC_TITLE_CASE_PATTERNS = [
    # [Adjective] [GenericNoun] — "Escalating Conflict", "Political Crisis"
    re.compile(
        r"^(Escalating|Ongoing|Potential|Alleged|Growing|Increasing"
        r"|Continuing|Renewed|Recent|Major|New|Rising|Worsening"
        r"|Deepening|Expanding|Intensifying|Looming|Emerging"
        r"|Current|Pending|Proposed|Political|Economic|Military"
        r"|Nuclear|Democratic|Legal|Federal|Global|Regional"
        r"|Domestic|National|International)\s+"
        r"(Conflict|Crisis|War|Attack|Attacks|Strikes?|Threat"
        r"|Tensions?|Dispute|Scandal|Controversy|Debate|Reform"
        r"|Sanctions?|Shutdown|Collapse|Probe|Investigation"
        r"|Hearing|Summit|Rally|Protest|Crackdown|Action"
        r"|Response|Policy|Agenda|Enforcement|Funding|Spending"
        r"|Oversight|Primary|Runoff|Campaign|Race|Contest)s?$",
        re.I,
    ),
    # [Topic] [GenericNoun] — "DHS Funding", "Energy Infrastructure"
    # Only when it's exactly 2 words and the second word is very generic
    re.compile(
        r"^\S+\s+(funding|spending|oversight|enforcement|infrastructure"
        r"|markets?|policy|reform|regulations?|legislation"
        r"|crisis|debate|scandal|hearings?|probe|investigation"
        r"|shutdown|shortages?|supply|demand|costs?|prices?"
        r"|boom|bust|bubble|crash|slump|surge|spike|rally|rout)$",
        re.I,
    ),
]

# ── Generic event words (single capitalized words for recurring_event) ──
_GENERIC_EVENT_WORDS = frozenset({
    "announcement", "arrest", "arrests", "assault", "attack", "attacks",
    "audit", "briefing", "campaign", "ceasefire", "ceremony",
    "conference", "conflict", "conviction", "coup", "crash",
    "crisis", "debate", "demonstration", "deposition", "depositions",
    "disaster", "election", "elections", "emergency", "eruption",
    "evacuation", "execution", "explosion", "flooding", "hearing",
    "hearings", "hurricane", "inauguration", "incident", "inquest",
    "inspection", "invasion", "investigation", "launch", "lockdown",
    "massacre", "meeting", "merger", "missile", "negotiation",
    "outbreak", "parade", "primary", "protest", "protests", "purge",
    "raid", "rally", "recall", "referendum", "resignation",
    "revolution", "riot", "robbery", "roundup", "runoff",
    "sentencing", "shooting", "shutdown", "siege", "speech",
    "strike", "strikes", "summit", "surgery", "testimony",
    "tornado", "trial", "uprising", "verdict", "visit", "vote",
    "walkout", "war",
})


# ── Main API ─────────────────────────────────────────────────────

def is_wikipedia_resolvable(name, entity_type=None):
    """
    Determine whether an entity is worth sending to Wikipedia for resolution.

    Args:
        name:        The entity name string
        entity_type: Optional type from entity_canonical (person, organization,
                     location, subject, recurring_event, family). When None,
                     uses name-only heuristics.

    Returns:
        (should_resolve: bool, reason: str)
        reason is a short tag explaining the decision, useful for logging
        and for storing in the negative cache.
    """
    if not name or not isinstance(name, str) or not name.strip():
        return False, "empty_name"

    cleaned = name.strip()
    lower = cleaned.lower()
    etype = (entity_type or "").lower().strip()

    # ── Known resolvable names (override everything) ──
    if lower in _KNOWN_RESOLVABLE:
        return True, "known_resolvable"

    # ── Pattern-based skips (apply to ALL types including person/org) ──
    # These catch extraction failures and formatting garbage
    for pattern in _SKIP_PATTERNS:
        if pattern.search(cleaned):
            return False, "skip_pattern"

    # ── Generic phrase exact match (before type dispatch) ──
    if lower in _GENERIC_PHRASES:
        return False, "generic_phrase"

    # ── Type-based fast paths ──
    if etype in ALWAYS_RESOLVE_TYPES:
        return True, "type_always_resolve"

    if etype in NEVER_RESOLVE_TYPES:
        return False, "type_never_resolve"

    # ── Type-specific heuristics ──
    if etype == "subject":
        return _check_subject(cleaned, lower)

    if etype == "recurring_event":
        return _check_event(cleaned, lower)

    # ── No type info — use name-only heuristics ──
    if not etype:
        return _check_untyped(cleaned, lower)

    # Unknown type — default to resolving
    return True, "unknown_type_default"


# ── Subject heuristics ───────────────────────────────────────────

def _check_subject(name, lower):
    """
    For entity_type='subject', decide if the name looks like a specific
    named concept (worth Wikipedia enrichment) vs. a generic topic.
    """
    words = name.split()
    wc = len(words)

    # ── All lowercase → generic topic ──
    if name == lower:
        # Exception: alphanumeric codes even in lowercase: "vk2735", "f-35"
        if re.search(r"[a-z]+\d+|\d+[a-z]+", lower):
            return True, "subject_alphanumeric_code"
        return False, "subject_all_lowercase"

    # ── Contains an alphanumeric product/drug/model code ──
    # "VK2735", "OP-1250", "F-35", "COP30", "Galaxy S26"
    if re.search(r"[A-Z]{1,5}[\-]?\d{2,}", name) or re.search(r"\d{2,}[\-]?[A-Z]{1,5}", name):
        return True, "subject_alphanumeric_code"

    # ── Contains parenthetical abbreviation → usually a proper term ──
    # "artificial intelligence (AI)", "post-traumatic stress disorder (PTSD)"
    if re.search(r"\([A-Z]{2,}\)", name):
        return True, "subject_with_abbreviation"

    # ── Single word ──
    if wc == 1:
        # Check against generic single words list
        if lower in _GENERIC_SINGLE_WORDS:
            return False, "subject_generic_single_word"
        # Capitalized single word not in generic list — might be a proper noun
        if name[0].isupper():
            return True, "subject_capitalized_single"
        return False, "subject_all_lowercase"

    # ── Multi-word: check generic title-case patterns ──
    for pattern in _GENERIC_TITLE_CASE_PATTERNS:
        if pattern.match(name):
            return False, "subject_generic_title_case"

    # ── Multi-word capitalization analysis ──
    # Count words with initial capitals (excluding small words)
    _SMALL_WORDS = {"a", "an", "the", "of", "in", "on", "at", "to", "for",
                    "and", "but", "or", "nor", "with", "by", "from", "as", "is"}
    content_words = [w for w in words if w.lower() not in _SMALL_WORDS]
    if not content_words:
        content_words = words

    upper_content = sum(
        1 for w in content_words
        if w and w[0].isalpha() and w[0].isupper()
    )

    # If most content words are capitalized → title case, could be a name
    # But we've already caught the generic title-case patterns above,
    # so what remains might be genuinely named things
    if upper_content >= 2:
        # Check if ALL words are common English words in title case
        # vs. containing actual proper nouns
        # Heuristic: if it has a word with an apostrophe-s (possessive of named entity)
        # that's a strong signal: "Iran's Nuclear Program"
        if re.search(r"[A-Z]\w+'s\b", name):
            return True, "subject_possessive_proper_noun"
        return True, "subject_multiple_proper_nouns"

    # First word capitalized, rest lowercase → sentence-case generic
    # "Democratic primary", "Energy markets", "Air pollution"
    if words[0][0].isupper() and upper_content <= 1:
        return False, "subject_sentence_case_generic"

    return True, "subject_default_allow"


# ── Event heuristics ─────────────────────────────────────────────

def _check_event(name, lower):
    """For recurring_event, check if it's specific enough to resolve."""
    words = name.split()
    wc = len(words)

    # ── Has a year → specific event, resolve ──
    if re.search(r"\b20\d{2}\b", name):
        return True, "event_with_year"

    # ── All lowercase → generic event ──
    if name == lower:
        return False, "event_all_lowercase"

    # ── Single word → check generic events list ──
    if wc == 1:
        if lower in _GENERIC_EVENT_WORDS:
            return False, "event_generic_single_word"
        if name[0].isupper():
            return True, "event_capitalized_single"
        return False, "event_all_lowercase"

    # ── Multi-word: check generic title-case patterns ──
    for pattern in _GENERIC_TITLE_CASE_PATTERNS:
        if pattern.match(name):
            return False, "event_generic_title_case"

    # ── Multi-word with proper nouns → likely a named event ──
    # "House Oversight Committee hearing", "State of the union address"
    # Check if any word looks like a proper noun (capitalized, not first word)
    has_proper = any(
        w[0].isupper()
        for w in words[1:]
        if w and w[0].isalpha()
    )

    if has_proper:
        return True, "event_has_proper_noun"

    # First word capitalized only → likely sentence case generic
    if words[0][0].isupper():
        return False, "event_sentence_case_generic"

    return False, "event_default_skip"


# ── Untyped heuristics (when entity_type is not available) ───────

def _check_untyped(name, lower):
    """
    When no entity_type is available (e.g. resolving from extracted_claims),
    use name structure alone to decide.
    """
    words = name.split()

    # All lowercase, multiple words, no special chars → generic phrase
    if name == lower and len(words) >= 2:
        return False, "untyped_all_lowercase_phrase"

    # All lowercase single common word
    if name == lower and len(words) == 1:
        # Allow alphanumeric codes
        if re.search(r"[a-z]+\d+|\d+[a-z]+", lower):
            return True, "untyped_alphanumeric_code"
        # Skip common dictionary words
        if len(lower) <= 12 and lower.isalpha():
            return False, "untyped_single_lowercase_word"

    # Has proper capitalization → likely a named entity
    if any(w[0].isupper() for w in words if w and w[0].isalpha()):
        return True, "untyped_has_proper_noun"

    return True, "untyped_default_allow"
