"""
Topic filter rules — exclude dates, days, months, and country identifiers from topic clouds.
Used by word_cloud and trending endpoints to present meaningful topics only.
"""

import re

# Days of the week (full and abbreviated)
_DAYS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
    "mon",
    "tue",
    "wed",
    "thu",
    "fri",
    "sat",
    "sun",
}

# Months (full and abbreviated)
_MONTHS = {
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
    "jan",
    "feb",
    "mar",
    "apr",
    "jun",
    "jul",
    "aug",
    "sep",
    "oct",
    "nov",
    "dec",
}

# Date-related terms
_DATE_TERMS = {
    "today",
    "yesterday",
    "tomorrow",
    "week",
    "month",
    "year",
    "quarter",
    "q1",
    "q2",
    "q3",
    "q4",
    "am",
    "pm",
    "bst",
    "est",
    "pst",
    "cet",
    "utc",
    "gmt",
}

# Date/time phrase extensions (slipped through filters: "on friday", "last week", etc.)
_DATE_PHRASES: set[str] = {
    "on friday",
    "on monday",
    "on tuesday",
    "on wednesday",
    "on thursday",
    "on saturday",
    "on sunday",
    "last week",
    "this week",
    "next week",
    "last month",
    "this month",
    "next month",
    "last year",
    "this year",
    "next year",
    "friday morning",
    "saturday night",
    "sunday afternoon",
    "monday evening",
    "yesterday morning",
    "today afternoon",
    "tomorrow evening",
    "on the 15th",
    "on the 16th",
    "in january",
    "in february",
}

# Country names and common identifiers (lowercase)
# Includes sovereign states + common news variants (e.g. "usa", "uk")
_COUNTRIES: set[str] = {
    "afghanistan",
    "albania",
    "algeria",
    "andorra",
    "angola",
    "argentina",
    "armenia",
    "australia",
    "austria",
    "azerbaijan",
    "bahamas",
    "bahrain",
    "bangladesh",
    "barbados",
    "belarus",
    "belgium",
    "belize",
    "benin",
    "bhutan",
    "bolivia",
    "bosnia",
    "botswana",
    "brazil",
    "brunei",
    "bulgaria",
    "burkina",
    "burma",
    "burundi",
    "cambodia",
    "cameroon",
    "canada",
    "chad",
    "chile",
    "china",
    "colombia",
    "comoros",
    "congo",
    "costa rica",
    "croatia",
    "cuba",
    "cyprus",
    "czech",
    "denmark",
    "djibouti",
    "dominica",
    "dominican",
    "ecuador",
    "egypt",
    "el salvador",
    "england",
    "eritrea",
    "estonia",
    "ethiopia",
    "fiji",
    "finland",
    "france",
    "gabon",
    "gambia",
    "georgia",
    "germany",
    "ghana",
    "greece",
    "guatemala",
    "guinea",
    "guyana",
    "haiti",
    "honduras",
    "hungary",
    "iceland",
    "india",
    "indonesia",
    "iran",
    "iraq",
    "ireland",
    "israel",
    "italy",
    "jamaica",
    "japan",
    "jordan",
    "kazakhstan",
    "kenya",
    "kosovo",
    "kuwait",
    "kyrgyzstan",
    "laos",
    "latvia",
    "lebanon",
    "lesotho",
    "liberia",
    "libya",
    "liechtenstein",
    "lithuania",
    "luxembourg",
    "macedonia",
    "madagascar",
    "malawi",
    "malaysia",
    "maldives",
    "mali",
    "malta",
    "mauritania",
    "mauritius",
    "mexico",
    "moldova",
    "monaco",
    "mongolia",
    "montenegro",
    "morocco",
    "mozambique",
    "myanmar",
    "namibia",
    "nepal",
    "netherlands",
    "nicaragua",
    "niger",
    "nigeria",
    "north korea",
    "norway",
    "oman",
    "pakistan",
    "palestine",
    "panama",
    "papua",
    "paraguay",
    "peru",
    "philippines",
    "poland",
    "portugal",
    "qatar",
    "romania",
    "russia",
    "rwanda",
    "saudi",
    "scotland",
    "senegal",
    "serbia",
    "singapore",
    "slovakia",
    "slovenia",
    "somalia",
    "south africa",
    "south korea",
    "spain",
    "sri lanka",
    "sudan",
    "suriname",
    "sweden",
    "switzerland",
    "syria",
    "taiwan",
    "tajikistan",
    "tanzania",
    "thailand",
    "togo",
    "trinidad",
    "tunisia",
    "turkey",
    "turkmenistan",
    "uganda",
    "ukraine",
    "united arab emirates",
    "united kingdom",
    "united states",
    "uruguay",
    "uzbekistan",
    "venezuela",
    "vietnam",
    "wales",
    "yemen",
    "zambia",
    "zimbabwe",
    # Common abbreviations and variants
    "usa",
    "us",
    "u.s.",
    "u.s.a.",
    "uk",
    "u.k.",
    "uae",
    "ussr",
    "dprk",
    "prc",
    "roc",  # North Korea, China, Taiwan
}

# Regex: 4-digit year (e.g. 2024, 2025)
_YEAR_PATTERN = re.compile(r"^\d{4}$")

# Regex: date-like (e.g. "01-01", "jan 15", "15th")
_DATE_LIKE_PATTERN = re.compile(
    r"^(\d{1,2}[-/]\d{1,2}|"
    r"\d{1,2}(st|nd|rd|th)?\s*(of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?|"
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\.?\s*\d{1,2})",
    re.I,
)

# News organization / source names — exclude from topic clusters (these are sources, not topics)
_NEWS_SOURCES: set[str] = {
    # Major US
    "breitbart",
    "cnn",
    "fox news",
    "msnbc",
    "nbc",
    "abc",
    "cbs",
    "npr",
    "pbs",
    "associated press",
    "ap news",
    "reuters",
    "bloomberg",
    "axios",
    "politico",
    "the hill",
    "huffpost",
    "huffington post",
    "usa today",
    "vox",
    "vice",
    "slate",
    "new york times",
    "washington post",
    "wall street journal",
    "los angeles times",
    "daily wire",
    "newsmax",
    "oann",
    "one america news",
    # Major UK & international
    "bbc",
    "bbc news",
    "the guardian",
    "telegraph",
    "daily mail",
    "the sun",
    "sky news",
    "independent",
    "financial times",
    "ft",
    "the times",
    "al jazeera",
    "rt",
    "sputnik",
    "afp",
    "agence france-presse",
    "dpa",
    "ap",
    # Tech & business
    "techcrunch",
    "the verge",
    "ars technica",
    "wired",
    "engadget",
    "mashable",
    # Wire services and agencies
    "upi",
    "dpa",
    "ap",
    "reuters",
    "afp",
}


def should_exclude_from_topic_cloud(text: str, banned_topics: set[str] | None = None) -> bool:
    """
    Return True if the topic/keyword should be excluded from the topic cloud.
    Excludes: days of week, months, date terms, country names, years, date-like strings,
    date/time phrase extensions (e.g. "on friday", "last week"), manually banned topics,
    and news organization/source names (e.g. Breitbart, CNN, Reuters).
    """
    if not text or not isinstance(text, str):
        return True
    t = text.lower().strip()
    if len(t) < 2:
        return True

    # Manually banned topics (domain-specific, passed from API)
    if banned_topics and t in banned_topics:
        return True

    # Date/time phrase extensions
    if t in _DATE_PHRASES:
        return True

    # Days of week
    if t in _DAYS:
        return True
    # Months
    if t in _MONTHS:
        return True
    # Date-related terms
    if t in _DATE_TERMS:
        return True
    # Country names (exact match)
    if t in _COUNTRIES:
        return True
    # 4-digit year
    if _YEAR_PATTERN.match(t):
        return True
    # Date-like patterns
    if _DATE_LIKE_PATTERN.match(t):
        return True
    # News sources / organizations (exact match; strip leading "the " for "The Guardian" etc.)
    t_normalized = re.sub(r"^the\s+", "", t)
    if t in _NEWS_SOURCES or t_normalized in _NEWS_SOURCES:
        return True

    return False


def filter_topic_list(
    topics: list, name_key: str = "name", banned_topics: set[str] | None = None
) -> list:
    """
    Filter a list of topic dicts or objects, removing those whose name matches exclusion rules.
    Supports both dicts (t.get) and objects with attributes (e.g. TopicInsight).
    Use for trending_topics, topic_distribution, topic clusters, etc.
    """
    result = []
    for t in topics:
        name = t.get(name_key, "") if isinstance(t, dict) else getattr(t, name_key, "")
        if not should_exclude_from_topic_cloud(str(name or ""), banned_topics=banned_topics):
            result.append(t)
    return result


def filter_word_cloud_entries(
    entries: list, text_key: str = "text", banned_topics: set[str] | None = None
) -> list:
    """
    Filter a list of word cloud entries, removing those that match exclusion rules.
    Each entry is a dict; text_key is the key containing the display text (default "text").
    """
    return [
        e
        for e in entries
        if not should_exclude_from_topic_cloud(e.get(text_key, ""), banned_topics=banned_topics)
    ]
