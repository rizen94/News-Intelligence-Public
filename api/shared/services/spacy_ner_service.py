"""
spaCy NER validation service — validates entity names against spaCy's NER model
to filter out garbage entries that should never have been stored.
"""

import logging
import re

logger = logging.getLogger(__name__)

_GARBAGE_PATTERNS = [
    re.compile(r"^\d+$"),                          # Pure numbers
    re.compile(r"^[\W_]+$"),                        # Pure punctuation / symbols
    re.compile(r"^.{1}$"),                           # Single char strings
    re.compile(r"^.{200,}$"),                       # Absurdly long
    re.compile(r"^\s+$"),                            # Whitespace only
    re.compile(r"^(the|a|an|this|that|it|and|or|but|is|was|are|were|be|been|have|has|had|do|does|did|will|would|could|should|may|might|shall|can)$", re.IGNORECASE),
    re.compile(r"^https?://", re.IGNORECASE),       # URLs
    re.compile(r"^@\w+$"),                           # Bare twitter/social handles only
    re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$"),      # Dates
    re.compile(r"^\d{4}-\d{2}-\d{2}"),              # ISO dates
    re.compile(r"[\x00-\x1f]"),                      # Control characters
]

_GARBAGE_EXACT = {
    "", " ", "  ", "null", "none", "undefined", "n/a", "na",
    "unknown", "other", "misc", "test", "example", "placeholder",
    "untitled", "no name", "anonymous", "tbd", "todo",
}


def is_garbage_entity_name(name: str) -> bool:
    """Quick heuristic check — returns True if name is obviously garbage."""
    if not name or not isinstance(name, str):
        return True

    stripped = name.strip()
    if stripped.lower() in _GARBAGE_EXACT:
        return True

    for pattern in _GARBAGE_PATTERNS:
        if pattern.search(stripped):
            return True

    return False


class SpacyNERService:
    """Lazy-loading spaCy NER service for entity validation."""

    def __init__(self):
        self._nlp = None
        self._loaded = False
        self._available = False
        self._model_name = None

    def _ensure_loaded(self):
        if self._loaded:
            return

        self._loaded = True
        try:
            import spacy
        except ImportError:
            logger.warning("spaCy not installed — NER validation disabled")
            return

        for model in ("en_core_web_lg", "en_core_web_sm", "en_core_web_trf"):
            try:
                self._nlp = spacy.load(model, disable=["parser", "lemmatizer", "textcat"])
                self._model_name = model
                self._available = True
                logger.info("Loaded spaCy model: %s", model)
                return
            except OSError:
                continue

        logger.warning("No spaCy NER model found. Install one with: python -m spacy download en_core_web_sm")

    @property
    def is_available(self) -> bool:
        self._ensure_loaded()
        return self._available

    @property
    def model_name(self) -> str | None:
        self._ensure_loaded()
        return self._model_name

    def validate_entity_name(self, name: str, entity_type: str | None = None) -> bool:
        """
        Returns True if the name looks like a valid named entity.
        Uses spaCy NER if available, otherwise falls back to heuristics.
        """
        if is_garbage_entity_name(name):
            return False

        self._ensure_loaded()
        if not self._available:
            return True

        try:
            doc = self._nlp(name.strip())

            if doc.ents:
                return True

            if entity_type in ("person", "organization"):
                tokens = [t for t in doc if not t.is_punct and not t.is_space]
                if tokens and any(t.text[0].isupper() for t in tokens if t.text):
                    return True
                return False

            return True

        except Exception as e:
            logger.debug("spaCy validation error for '%s': %s", name, e)
            return True


_service = None


def get_spacy_ner_service() -> SpacyNERService:
    global _service
    if _service is None:
        _service = SpacyNERService()
    return _service
