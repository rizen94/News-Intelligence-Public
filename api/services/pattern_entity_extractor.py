"""
Pattern-Based Entity Extraction Service
Uses pattern matching techniques for entity extraction including:
- Regex pattern matching
- Context-aware extraction
- Entity type classification
- Entity relationship detection
"""

import logging
import re

logger = logging.getLogger(__name__)


class PatternEntityExtractor:
    """Pattern-based entity extraction using regex patterns"""

    def __init__(self):
        # Common entity patterns
        self.person_patterns = [
            r"\b[A-Z][a-z]+ [A-Z][a-z]+\b",  # First Last
            r"\b[A-Z][a-z]+, [A-Z][a-z]+\b",  # Last, First
            r"\b(?:Mr|Mrs|Ms|Dr|Prof|President|Senator|Governor|Mayor|CEO|CFO|CTO)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b",  # Titles
        ]

        self.organization_patterns = [
            r"\b[A-Z][a-zA-Z]+(?:\s+(?:Inc|Corp|Corporation|LLC|Ltd|Limited|Company|Co|Group|Systems|Technologies|International|Global|Holdings|Enterprises))\.?\b",
            r"\b(?:The|US|U\.S\.|UK|U\.K\.)\s+[A-Z][a-zA-Z]+\s+(?:Department|Agency|Bureau|Commission|Committee|Administration)\b",
            r"\b[A-Z][a-zA-Z]+\s+(?:University|College|Hospital|Medical Center|Bank|Foundation)\b",
        ]

        self.location_patterns = [
            r"\b(?:New|Old|North|South|East|West|Upper|Lower|Greater|Lesser)\s+[A-Z][a-z]+\b",  # New York, North Korea
            r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:City|State|County|Province|Republic|Kingdom|Empire)\b",
            r"\b(?:United States|United Kingdom|Saudi Arabia|South Africa|New Zealand|United Arab Emirates)\b",
            r"\b[A-Z][a-z]+\s+(?:Street|Avenue|Boulevard|Road|Drive|Lane|Parkway)\b",  # Addresses
        ]

        # Stop words to filter out
        self.entity_stop_words = {
            "The",
            "This",
            "That",
            "These",
            "Those",
            "And",
            "Or",
            "But",
            "In",
            "On",
            "At",
            "To",
            "For",
            "Of",
            "With",
            "By",
            "From",
            "Since",
            "Until",
            "During",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        }

        # Common non-entities
        self.common_non_entities = {
            "Today",
            "Yesterday",
            "Tomorrow",
            "Now",
            "Then",
            "Here",
            "There",
            "America",
            "Americans",
            "United",
            "States",
            "Government",
            "Officials",
        }

    def extract_entities(self, text: str, context: str | None = None) -> dict[str, list[str]]:
        """
        Extract entities from text with type classification

        Args:
            text: Text to extract entities from
            context: Optional context to improve extraction

        Returns:
            Dictionary with entity types as keys and lists of entities as values
        """
        try:
            entities = {
                "people": [],
                "organizations": [],
                "locations": [],
                "topics": [],
                "products": [],
                "events": [],
            }

            if not text:
                return entities

            # Extract people
            entities["people"] = self._extract_people(text)

            # Extract organizations
            entities["organizations"] = self._extract_organizations(text)

            # Extract locations
            entities["locations"] = self._extract_locations(text)

            # Extract topics/keywords
            entities["topics"] = self._extract_topics(text)

            # Extract products/technologies
            entities["products"] = self._extract_products(text)

            # Extract events
            entities["events"] = self._extract_events(text)

            # Filter and deduplicate
            for entity_type in entities:
                entities[entity_type] = self._filter_and_deduplicate(entities[entity_type])

            return entities

        except Exception as e:
            logger.error(f"Error extracting entities: {e}")
            return {
                "people": [],
                "organizations": [],
                "locations": [],
                "topics": [],
                "products": [],
                "events": [],
            }

    def _extract_people(self, text: str) -> list[str]:
        """Extract person names"""
        try:
            people = set()

            # Use patterns
            for pattern in self.person_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    # Clean and validate
                    cleaned = match.strip()
                    if self._is_valid_person(cleaned):
                        people.add(cleaned)

            # Also look for "X said", "according to X" patterns
            said_pattern = r"(?:said|according to|told|reported by|quoted|interviewed)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)"
            matches = re.findall(said_pattern, text)
            for match in matches:
                if self._is_valid_person(match):
                    people.add(match)

            return list(people)[:20]  # Limit to 20

        except Exception as e:
            logger.error(f"Error extracting people: {e}")
            return []

    def _extract_organizations(self, text: str) -> list[str]:
        """Extract organization names"""
        try:
            organizations = set()

            # Use patterns
            for pattern in self.organization_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    cleaned = match.strip()
                    if self._is_valid_organization(cleaned):
                        organizations.add(cleaned)

            # Look for common organization indicators
            org_indicators = [
                r"([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:announced|released|launched|reported)",
                r"(?:at|from|by)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+)\s+(?:Inc|Corp|Company|Ltd)",
            ]

            for pattern in org_indicators:
                matches = re.findall(pattern, text)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0] if match else ""
                    if self._is_valid_organization(match):
                        organizations.add(match.strip())

            return list(organizations)[:20]

        except Exception as e:
            logger.error(f"Error extracting organizations: {e}")
            return []

    def _extract_locations(self, text: str) -> list[str]:
        """Extract location names"""
        try:
            locations = set()

            # Use patterns
            for pattern in self.location_patterns:
                matches = re.findall(pattern, text)
                for match in matches:
                    cleaned = match.strip()
                    if self._is_valid_location(cleaned):
                        locations.add(cleaned)

            return list(locations)[:15]

        except Exception as e:
            logger.error(f"Error extracting locations: {e}")
            return []

    def _extract_topics(self, text: str) -> list[str]:
        """Extract topic keywords"""
        try:
            # Common topic indicators
            topic_keywords = [
                "technology",
                "innovation",
                "economy",
                "business",
                "finance",
                "politics",
                "policy",
                "regulation",
                "health",
                "healthcare",
                "education",
                "science",
                "research",
                "development",
                "security",
                "climate",
                "environment",
                "energy",
                "trade",
                "commerce",
                "artificial intelligence",
                "machine learning",
                "blockchain",
                "cryptocurrency",
                "startup",
                "investment",
                "venture capital",
            ]

            text_lower = text.lower()
            topics = []

            for keyword in topic_keywords:
                if keyword.lower() in text_lower:
                    topics.append(keyword.title())

            # Also extract capitalized phrases that might be topics
            capitalized_phrases = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
            for phrase in capitalized_phrases:
                if len(phrase) > 5 and len(phrase.split()) <= 3:
                    if phrase.lower() not in self.entity_stop_words:
                        topics.append(phrase)

            return list(set(topics))[:15]

        except Exception as e:
            logger.error(f"Error extracting topics: {e}")
            return []

    def _extract_products(self, text: str) -> list[str]:
        """Extract product/technology names"""
        try:
            products = set()

            # Look for quoted names (often products)
            quoted = re.findall(r'"([^"]+)"', text)
            for quote in quoted:
                if len(quote) > 3 and len(quote.split()) <= 5:
                    products.add(quote)

            # Look for trademark/copyright indicators
            tm_pattern = r"([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)\s+(?:TM|®|™)"
            matches = re.findall(tm_pattern, text)
            products.update(matches)

            # Technology terms
            tech_patterns = [
                r"\b([A-Z][a-z]+(?:OS|OS|API|SDK|SDK|UI|UX))\b",
                r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+(?:Pro|Max|Mini|Plus|Lite))\b",
            ]

            for pattern in tech_patterns:
                matches = re.findall(pattern, text)
                products.update(matches)

            return list(products)[:10]

        except Exception as e:
            logger.error(f"Error extracting products: {e}")
            return []

    def _extract_events(self, text: str) -> list[str]:
        """Extract event names"""
        try:
            events = set()

            # Event indicators
            event_patterns = [
                r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:Conference|Summit|Meeting|Summit|Forum|Convention)\b",
                r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:Awards|Ceremony|Festival|Celebration)\b",
                r"\b(?:the|The)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)\s+(?:Incident|Crisis|Scandal|Investigation)\b",
            ]

            for pattern in event_patterns:
                matches = re.findall(pattern, text)
                events.update(matches)

            return list(events)[:10]

        except Exception as e:
            logger.error(f"Error extracting events: {e}")
            return []

    def _is_valid_person(self, name: str) -> bool:
        """Validate if string is likely a person name"""
        if not name or len(name) < 4:
            return False

        # Must have at least first and last name (2 words)
        words = name.split()
        if len(words) < 2:
            return False

        # Check against stop words
        if name in self.entity_stop_words or name in self.common_non_entities:
            return False

        # Must start with capital letter
        if not name[0].isupper():
            return False

        # Should not contain numbers or special chars (except hyphens, apostrophes)
        if re.search(r"[0-9@#$%^&*()]", name):
            return False

        # Length check
        if len(name) > 50:
            return False

        return True

    def _is_valid_organization(self, org: str) -> bool:
        """Validate if string is likely an organization"""
        if not org or len(org) < 3:
            return False

        if org in self.entity_stop_words:
            return False

        # Should start with capital
        if not org[0].isupper():
            return False

        # Length check
        if len(org) > 100:
            return False

        return True

    def _is_valid_location(self, location: str) -> bool:
        """Validate if string is likely a location"""
        if not location or len(location) < 3:
            return False

        if location in self.entity_stop_words:
            return False

        # Should start with capital
        if not location[0].isupper():
            return False

        # Length check
        if len(location) > 50:
            return False

        return True

    def _filter_and_deduplicate(self, entities: list[str]) -> list[str]:
        """Filter and deduplicate entity list"""
        try:
            # Remove empty strings
            filtered = [e for e in entities if e and len(e.strip()) > 0]

            # Deduplicate (case-insensitive)
            seen = set()
            unique = []
            for entity in filtered:
                entity_lower = entity.lower()
                if entity_lower not in seen:
                    seen.add(entity_lower)
                    unique.append(entity)

            # Sort by length (longer entities often more specific)
            unique.sort(key=lambda x: len(x), reverse=True)

            return unique

        except Exception as e:
            logger.error(f"Error filtering entities: {e}")
            return entities
