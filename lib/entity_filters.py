# ../lib/entity_filters.py
"""
Pattern-based pre-filters that identify entities not worth looking up.
These go straight into the negative cache without hitting Wikipedia at all.
"""

import re

# ── Generic roles, titles, and phrases NER loves to extract ─────────────────
GENERIC_BLOCKLIST = frozenset([
    "president", "prime minister", "the president", "the government",
    "the company", "the state", "the city", "the country",
    "officials", "authorities", "police", "military", "the court",
    "spokesperson", "sources", "analysts", "residents", "witnesses",
    "the ministry", "the department", "the agency", "the committee",
    "the white house", "the pentagon", "the kremlin",
    "mr", "mrs", "dr", "sir", "prof",
    "the united nations",
])

# ── Technical / ML jargon that shows up as "entities" in academic text ──────
# These are individual words; we check if the entity is JUST this word
# or a short phrase dominated by these terms.
_ML_JARGON = frozenset([
    "model", "models", "dataset", "datasets", "benchmark", "benchmarks",
    "parameter", "parameters", "variant", "variants", "baseline", "baselines",
    "epoch", "epochs", "batch", "batches", "gradient", "gradients",
    "optimizer", "checkpoint", "ablation", "embedding", "embeddings",
    "encoder", "decoder", "transformer", "attention", "architecture",
    "framework", "module", "layer", "layers", "hidden", "channel",
    "channels", "training", "inference", "evaluation", "fine-tuning",
    "pretraining", "pretrained", "iteration", "iterations",
    "formulation", "equation", "algorithm", "threshold", "metric",
    "accuracy", "precision", "recall", "loss", "score",
    "array", "arrays", "vector", "vectors", "matrix", "tensor",
    "function", "reward", "objective", "constraint", "optimization",
])

# ── Patterns that indicate NER garbage ──────────────────────────────────────
_GARBAGE_PATTERNS = [
    # --- Original patterns ---
    re.compile(r"^\d+$"),                                      # pure numbers
    re.compile(r"^[^a-zA-Z]*$"),                               # no letters at all
    re.compile(r"^(the|a|an)\s*$", re.I),                      # bare articles
    re.compile(r"[@#]"),                                        # social media handles/hashtags
    re.compile(r"^https?://"),                                  # URLs
    re.compile(r"\b(said|says|told|according)\b", re.I),        # sentence fragments

    # --- Currency / monetary ---
    re.compile(r"^[\$\€\£\₹\¥\₩\₿\¢\₫\₺\₴\₸\₮\₭\₱\₣\₤\₦\₧\₨\₪\₻\₼\₽\₾]"),
    re.compile(r"^[\d,]+(\.\d+)?\s*%"),                         # percentage values
    re.compile(
        r"^\d[\d,.]*\s*(per\b|percent|billion|million|thousand|hundred|"
        r"trillion|bps|basis|crore|lakh|cr\b|bn\b|bln\b|mn\b|"
        r"rupee|euro|dollar|pound|yen|won|cent)",
        re.I,
    ),

    # --- Code / LaTeX / tech garbage ---
    re.compile(r"\\(texttt|text|frac|sqrt|begin|end|mathbb|mathrm|left|right)\{"),
    re.compile(r"\.(com|org|net|io|gov|edu|html|php|asp)\b", re.I),
    re.compile(r"^(curl|bash|sudo|pip|npm|wget|docker|git)\s", re.I),

    # --- Date-like starts ---
    re.compile(r"^\d{4}-\d{2}"),                                # ISO dates

    # ── NEW: Comma-formatted large numbers (100,000 anything) ────────────
    # Real entity names almost never start with comma-grouped numbers
    re.compile(r"^\d{1,3}(,\d{3})+\b"),

    # ── NEW: Decimal numbers at start (0.5, 1.2, etc.) ──────────────────
    # Catches "0.5b model", "0.26m-parameter cmm", "0.12 e / s threshold"
    re.compile(r"^\d*\.\d+\s"),

    # ── NEW: Starts with ( or [ — sentence fragments / list items ────────
    re.compile(r"^[\(\[]"),

    # ── NEW: Academic citation patterns ──────────────────────────────────
    re.compile(r"\([\w\s]+et\s+al\.?,?\s*\d{4}\)", re.I),
    re.compile(r"\(\w+\s+and\s+\w+,?\s*\d{4}\)", re.I),
    re.compile(r"\(\w+,\s*\d{4}\)"),

    # ── NEW: "N out of M" patterns ──────────────────────────────────────
    re.compile(r"\d+\s+out\s+of\s+\d+", re.I),

    # ── NEW: "version of" / "variant of" / "instance of" ────────────────
    re.compile(r"\b(version|instance|implementation|variant)\s+of\b", re.I),

    # ── NEW: Strings that are clearly unit measurements ─────────────────
    re.compile(r"^\d[\d.]*\s*(mev|gev|tev|kev|ghz|mhz|khz|nm|mm|cm|km|kg|mb|gb|tb|ms|ns|μs)\b", re.I),

    # ── NEW: "defined in equation/section/table/figure" ─────────────────
    re.compile(r"\b(defined|described|shown|presented|illustrated|given|listed)\s+in\s+(equation|section|table|figure|appendix|chapter)\b", re.I),

    # ── NEW: Escaped/garbled text with brackets ─────────────────────────
    re.compile(r"\[.*\].*\["),                                  # multiple bracket groups
    re.compile(r"[\[\]]{2,}"),                                  # consecutive brackets
]

# ── NEW: Words that signal "this is a description, not a name" ──────────────
# Used only when the entity has many words (> 4)
_DESCRIPTION_SIGNALS = re.compile(
    r"\b(employees|users|people|workers|students|soldiers|troops|residents|"
    r"citizens|members|victims|patients|refugees|migrants|prisoners|"
    r"civilians|officers|farmers|voters|attendees|customers|subscribers|"
    r"participants|candidates|sentences|images|iterations|containers|"
    r"hotels|jobs|pairs|filings|documents|tokens|samples|examples|"
    r"rounds|steps|updates|queries|requests|responses|records|rows|"
    r"columns|features|dimensions|weights|nodes|edges|classes|labels|"
    r"categories|clusters|segments|regions|patches|pixels|frames|"
    r"episodes|trials|experiments|runs|seeds|folds|splits)\b",
    re.I,
)


def _ascii_alpha_ratio(text):
    """Fraction of characters that are basic Latin letters (a-z, A-Z)."""
    if not text:
        return 0.0
    return sum(1 for c in text if 'a' <= c <= 'z' or 'A' <= c <= 'Z') / len(text)


def _word_count(text):
    return len(text.split())


def _jargon_ratio(text):
    """Fraction of words that are ML/technical jargon."""
    words = text.lower().split()
    if not words:
        return 0.0
    jargon_count = sum(1 for w in words if w in _ML_JARGON)
    return jargon_count / len(words)


def classify_bad_entity(name, entity_type=None):
    """
    Returns a reason string if this entity should be blocklisted,
    or None if it's worth trying to resolve.
    """
    if not name or not name.strip():
        return "empty"

    cleaned = name.strip()

    # Too short to be meaningful
    if len(cleaned) < 3:
        return "too_short"

    # Too long — probably a sentence fragment
    if len(cleaned) > 120:
        return "ner_artifact"

    # Generic terms
    if cleaned.lower() in GENERIC_BLOCKLIST:
        return "generic_term"

    # Single-word "person" names are almost never resolvable
    if " " not in cleaned and entity_type == "person":
        return "generic_term"

    # ── ASCII alpha ratio (catches unicode math, symbol soup) ───────────
    if len(cleaned) >= 3 and _ascii_alpha_ratio(cleaned) < 0.4:
        return "ner_artifact"

    # ── Word count limit: real entity names rarely exceed 7 words ───────
    wc = _word_count(cleaned)
    if wc > 7:
        return "ner_artifact"

    # ── Starts with digit + has 4+ words → almost never an entity ───────
    # Exceptions like "50 Cent" or "21 Pilots" are ≤ 2-3 words
    if cleaned[0].isdigit() and wc >= 4:
        return "ner_artifact"

    # ── Garbage patterns ────────────────────────────────────────────────
    for pat in _GARBAGE_PATTERNS:
        if pat.search(cleaned):
            return "ner_artifact"

    # ── Jargon-dominated phrases (> 50% ML jargon words, 3+ words) ─────
    if wc >= 3 and _jargon_ratio(cleaned) > 0.5:
        return "ml_jargon"

    # ── Description pattern: number + description words (4+ words) ──────
    if wc >= 4 and cleaned[0].isdigit() and _DESCRIPTION_SIGNALS.search(cleaned):
        return "ner_artifact"

    # ── Single technical jargon word ────────────────────────────────────
    if wc == 1 and cleaned.lower() in _ML_JARGON:
        return "ml_jargon"

    return None
