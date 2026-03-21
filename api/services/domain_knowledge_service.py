"""
Domain Knowledge Service
Provides domain-specific context, historical data, and enrichment for RAG analysis.

Each domain (politics, finance, science-tech) has:
- Knowledge base with key entities and concepts
- Historical context templates
- Domain-specific entity recognition patterns
- External source references
- Contextual enrichment rules
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DomainEntity:
    """A domain-specific entity with context"""

    name: str
    entity_type: str  # person, organization, concept, event, etc.
    aliases: list[str] = field(default_factory=list)
    description: str = ""
    importance: float = 0.5  # 0-1
    related_entities: list[str] = field(default_factory=list)
    external_refs: dict[str, str] = field(default_factory=dict)  # source -> url


@dataclass
class DomainContext:
    """Domain-specific context for enriching RAG results"""

    domain: str
    entities_found: list[DomainEntity]
    historical_context: str
    key_concepts: list[str]
    related_topics: list[str]
    external_sources: list[dict[str, str]]
    domain_terminology: dict[str, str]
    timeline_context: str
    geopolitical_context: str = ""
    economic_context: str = ""


# =============================================================================
# POLITICS DOMAIN KNOWLEDGE BASE
# =============================================================================

POLITICS_ENTITIES = {
    # US Government
    "white house": DomainEntity(
        name="White House",
        entity_type="institution",
        aliases=["executive branch", "administration", "oval office"],
        description="Executive branch of the US federal government",
        importance=0.95,
        related_entities=["President", "Vice President", "Cabinet"],
        external_refs={"official": "https://www.whitehouse.gov"},
    ),
    "congress": DomainEntity(
        name="US Congress",
        entity_type="institution",
        aliases=["capitol", "capitol hill", "legislature", "lawmakers"],
        description="Legislative branch consisting of Senate and House of Representatives",
        importance=0.95,
        related_entities=["Senate", "House of Representatives", "Speaker"],
        external_refs={"official": "https://www.congress.gov"},
    ),
    "supreme court": DomainEntity(
        name="Supreme Court",
        entity_type="institution",
        aliases=["scotus", "high court", "justices"],
        description="Highest court in the US judicial system",
        importance=0.9,
        related_entities=["Chief Justice", "Justices"],
        external_refs={"official": "https://www.supremecourt.gov"},
    ),
    "senate": DomainEntity(
        name="US Senate",
        entity_type="institution",
        aliases=["upper chamber", "senators"],
        description="Upper chamber of Congress with 100 members",
        importance=0.85,
        related_entities=["Senate Majority Leader", "Senate committees"],
    ),
    "house": DomainEntity(
        name="House of Representatives",
        entity_type="institution",
        aliases=["house", "lower chamber", "representatives", "congressmen"],
        description="Lower chamber of Congress with 435 members",
        importance=0.85,
        related_entities=["Speaker of the House", "House committees"],
    ),
    # Political Parties
    "republican": DomainEntity(
        name="Republican Party",
        entity_type="party",
        aliases=["gop", "republicans", "conservative"],
        description="Major US conservative political party",
        importance=0.8,
        related_entities=["RNC", "Republican National Committee"],
    ),
    "democrat": DomainEntity(
        name="Democratic Party",
        entity_type="party",
        aliases=["democrats", "dems", "liberal", "progressive"],
        description="Major US liberal/progressive political party",
        importance=0.8,
        related_entities=["DNC", "Democratic National Committee"],
    ),
    # Key Concepts
    "election": DomainEntity(
        name="Election",
        entity_type="concept",
        aliases=["vote", "ballot", "polls", "voting"],
        description="Democratic process of selecting representatives",
        importance=0.85,
    ),
    "legislation": DomainEntity(
        name="Legislation",
        entity_type="concept",
        aliases=["bill", "law", "act", "statute", "policy"],
        description="Laws passed by legislative bodies",
        importance=0.8,
    ),
    "impeachment": DomainEntity(
        name="Impeachment",
        entity_type="concept",
        aliases=["impeach", "removal"],
        description="Process to remove officials from office",
        importance=0.7,
    ),
}

POLITICS_TERMINOLOGY = {
    "filibuster": "Procedural tactic to delay or block legislation in the Senate",
    "executive order": "Directive issued by the President with force of law",
    "veto": "Presidential rejection of legislation passed by Congress",
    "bipartisan": "Supported by both major political parties",
    "gerrymandering": "Manipulation of electoral district boundaries for political advantage",
    "lobbying": "Attempting to influence government decisions",
    "appropriations": "Congressional allocation of government funds",
    "cloture": "Senate procedure to end debate and proceed to vote",
    "reconciliation": "Budget process allowing passage with simple majority",
    "midterms": "Congressional elections held between presidential elections",
}

POLITICS_SOURCES = [
    {"name": "Congress.gov", "url": "https://www.congress.gov", "type": "legislation"},
    {"name": "White House", "url": "https://www.whitehouse.gov", "type": "executive"},
    {"name": "C-SPAN", "url": "https://www.c-span.org", "type": "proceedings"},
    {"name": "FEC", "url": "https://www.fec.gov", "type": "campaign_finance"},
    {"name": "Ballotpedia", "url": "https://ballotpedia.org", "type": "elections"},
    {"name": "GovTrack", "url": "https://www.govtrack.us", "type": "legislation"},
    {"name": "OpenSecrets", "url": "https://www.opensecrets.org", "type": "money_politics"},
]


# =============================================================================
# FINANCE DOMAIN KNOWLEDGE BASE
# =============================================================================

FINANCE_ENTITIES = {
    # Central Banks
    "federal reserve": DomainEntity(
        name="Federal Reserve",
        entity_type="institution",
        aliases=["fed", "the fed", "fomc", "federal reserve board"],
        description="Central bank of the United States",
        importance=0.95,
        related_entities=["Fed Chair", "FOMC", "Interest Rates"],
        external_refs={"official": "https://www.federalreserve.gov"},
    ),
    "ecb": DomainEntity(
        name="European Central Bank",
        entity_type="institution",
        aliases=["european central bank"],
        description="Central bank for the eurozone",
        importance=0.85,
        external_refs={"official": "https://www.ecb.europa.eu"},
    ),
    # Exchanges
    "nyse": DomainEntity(
        name="New York Stock Exchange",
        entity_type="exchange",
        aliases=["new york stock exchange", "wall street"],
        description="Largest stock exchange by market capitalization",
        importance=0.9,
        external_refs={"official": "https://www.nyse.com"},
    ),
    "nasdaq": DomainEntity(
        name="NASDAQ",
        entity_type="exchange",
        aliases=["nasdaq composite"],
        description="Second-largest stock exchange, technology-focused",
        importance=0.9,
        external_refs={"official": "https://www.nasdaq.com"},
    ),
    # Indices
    "s&p 500": DomainEntity(
        name="S&P 500",
        entity_type="index",
        aliases=["s&p", "sp500", "standard and poor"],
        description="Index of 500 largest US public companies",
        importance=0.9,
    ),
    "dow jones": DomainEntity(
        name="Dow Jones Industrial Average",
        entity_type="index",
        aliases=["dow", "djia", "dow jones"],
        description="Price-weighted index of 30 large US companies",
        importance=0.85,
    ),
    # Regulators
    "sec": DomainEntity(
        name="Securities and Exchange Commission",
        entity_type="regulator",
        aliases=["securities and exchange commission"],
        description="Federal agency regulating securities markets",
        importance=0.85,
        external_refs={"official": "https://www.sec.gov"},
    ),
    # Concepts
    "interest rate": DomainEntity(
        name="Interest Rate",
        entity_type="concept",
        aliases=["rate", "fed funds rate", "rates"],
        description="Cost of borrowing money",
        importance=0.9,
    ),
    "inflation": DomainEntity(
        name="Inflation",
        entity_type="concept",
        aliases=["cpi", "price increase", "inflationary"],
        description="Rate at which prices for goods and services rise",
        importance=0.9,
    ),
    "gdp": DomainEntity(
        name="Gross Domestic Product",
        entity_type="indicator",
        aliases=["gross domestic product", "economic growth"],
        description="Total value of goods and services produced",
        importance=0.85,
    ),
    "recession": DomainEntity(
        name="Recession",
        entity_type="concept",
        aliases=["economic downturn", "contraction"],
        description="Period of economic decline",
        importance=0.8,
    ),
    "ipo": DomainEntity(
        name="Initial Public Offering",
        entity_type="concept",
        aliases=["initial public offering", "going public"],
        description="First sale of stock to the public",
        importance=0.75,
    ),
}

FINANCE_TERMINOLOGY = {
    "bull market": "Period of rising stock prices and investor optimism",
    "bear market": "Period of declining stock prices (20%+ from peak)",
    "quantitative easing": "Central bank purchasing assets to increase money supply",
    "yield curve": "Graph showing interest rates across different maturities",
    "market cap": "Total value of a company's outstanding shares",
    "earnings": "Company's net income/profit",
    "dividend": "Portion of earnings distributed to shareholders",
    "volatility": "Measure of price fluctuation in markets",
    "liquidity": "Ease of converting assets to cash",
    "hedge fund": "Investment fund using advanced strategies",
    "etf": "Exchange-traded fund tracking an index or sector",
    "bond": "Debt security with fixed interest payments",
    "equity": "Ownership stake in a company (stocks)",
    "derivatives": "Financial contracts deriving value from underlying assets",
    "short selling": "Betting that a stock price will decline",
}

FINANCE_SOURCES = [
    {"name": "Federal Reserve", "url": "https://www.federalreserve.gov", "type": "monetary_policy"},
    {"name": "SEC EDGAR", "url": "https://www.sec.gov/edgar", "type": "filings"},
    {"name": "Bureau of Labor Statistics", "url": "https://www.bls.gov", "type": "employment"},
    {"name": "Bureau of Economic Analysis", "url": "https://www.bea.gov", "type": "gdp"},
    {"name": "Treasury Department", "url": "https://home.treasury.gov", "type": "fiscal"},
    {"name": "FRED", "url": "https://fred.stlouisfed.org", "type": "economic_data"},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com", "type": "market_data"},
    {"name": "Bloomberg", "url": "https://www.bloomberg.com", "type": "financial_news"},
]


# =============================================================================
# SCIENCE-TECH DOMAIN KNOWLEDGE BASE
# =============================================================================

SCIENCE_TECH_ENTITIES = {
    # Major Tech Companies
    "google": DomainEntity(
        name="Google",
        entity_type="company",
        aliases=["alphabet", "googl"],
        description="Technology company focused on search, cloud, and AI",
        importance=0.9,
        related_entities=["Alphabet", "DeepMind", "YouTube"],
    ),
    "microsoft": DomainEntity(
        name="Microsoft",
        entity_type="company",
        aliases=["msft"],
        description="Technology company focusing on software, cloud, and AI",
        importance=0.9,
        related_entities=["Azure", "OpenAI", "LinkedIn"],
    ),
    "apple": DomainEntity(
        name="Apple",
        entity_type="company",
        aliases=["aapl"],
        description="Technology company known for consumer electronics",
        importance=0.9,
    ),
    "openai": DomainEntity(
        name="OpenAI",
        entity_type="company",
        aliases=["open ai", "chatgpt maker"],
        description="AI research company behind ChatGPT and GPT models",
        importance=0.85,
        related_entities=["ChatGPT", "GPT-4", "DALL-E"],
    ),
    # Key Concepts
    "artificial intelligence": DomainEntity(
        name="Artificial Intelligence",
        entity_type="concept",
        aliases=["ai", "machine learning", "ml", "deep learning"],
        description="Technology enabling machines to perform intelligent tasks",
        importance=0.95,
    ),
    "machine learning": DomainEntity(
        name="Machine Learning",
        entity_type="concept",
        aliases=["ml", "neural networks"],
        description="Subset of AI using statistical methods to learn from data",
        importance=0.9,
    ),
    "large language model": DomainEntity(
        name="Large Language Model",
        entity_type="concept",
        aliases=["llm", "language model", "foundation model"],
        description="AI models trained on vast text data for language tasks",
        importance=0.85,
    ),
    "cybersecurity": DomainEntity(
        name="Cybersecurity",
        entity_type="concept",
        aliases=["cyber security", "infosec", "security"],
        description="Protection of systems from digital attacks",
        importance=0.85,
    ),
    "cloud computing": DomainEntity(
        name="Cloud Computing",
        entity_type="concept",
        aliases=["cloud", "aws", "azure", "gcp"],
        description="On-demand computing resources over the internet",
        importance=0.8,
    ),
    "blockchain": DomainEntity(
        name="Blockchain",
        entity_type="concept",
        aliases=["crypto", "cryptocurrency", "web3"],
        description="Distributed ledger technology",
        importance=0.75,
    ),
    "quantum computing": DomainEntity(
        name="Quantum Computing",
        entity_type="concept",
        aliases=["quantum", "qubit"],
        description="Computing using quantum mechanical phenomena",
        importance=0.7,
    ),
    # Research Institutions
    "mit": DomainEntity(
        name="MIT",
        entity_type="institution",
        aliases=["massachusetts institute of technology"],
        description="Leading research university in science and technology",
        importance=0.8,
    ),
    "stanford": DomainEntity(
        name="Stanford University",
        entity_type="institution",
        aliases=["stanford"],
        description="Research university at the heart of Silicon Valley",
        importance=0.8,
    ),
}

SCIENCE_TECH_TERMINOLOGY = {
    "api": "Application Programming Interface - allows software to communicate",
    "algorithm": "Step-by-step procedure for solving a problem",
    "neural network": "Computing system inspired by biological neural networks",
    "gpu": "Graphics Processing Unit - hardware for parallel processing",
    "open source": "Software with publicly accessible source code",
    "saas": "Software as a Service - cloud-delivered applications",
    "iot": "Internet of Things - network of connected devices",
    "5g": "Fifth generation mobile network technology",
    "edge computing": "Processing data closer to where it's generated",
    "devops": "Practices combining development and IT operations",
    "containerization": "Packaging software in isolated environments",
    "microservices": "Architecture of loosely coupled services",
    "transformer": "Neural network architecture for sequence data (like GPT)",
    "inference": "Using trained AI models to make predictions",
    "fine-tuning": "Adapting pre-trained models to specific tasks",
}

SCIENCE_TECH_SOURCES = [
    {"name": "arXiv", "url": "https://arxiv.org", "type": "research_papers"},
    {"name": "IEEE", "url": "https://www.ieee.org", "type": "standards"},
    {"name": "ACM", "url": "https://www.acm.org", "type": "computing_research"},
    {"name": "Nature", "url": "https://www.nature.com", "type": "scientific_journal"},
    {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com",
        "type": "tech_analysis",
    },
    {"name": "Wired", "url": "https://www.wired.com", "type": "tech_news"},
    {"name": "TechCrunch", "url": "https://techcrunch.com", "type": "startup_news"},
    {"name": "GitHub", "url": "https://github.com", "type": "open_source"},
]


class DomainKnowledgeService:
    """
    Provides domain-specific knowledge for RAG enrichment.
    """

    def __init__(self, db_config: dict[str, Any] = None):
        self.db_config = db_config or {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 5433)),
            "database": os.getenv("DB_NAME", "news_intelligence"),
            "user": os.getenv("DB_USER", "newsapp"),
            "password": os.getenv("DB_PASSWORD", "newsapp_password"),
        }

        # Domain knowledge bases
        self.knowledge_bases = {
            "politics": {
                "entities": POLITICS_ENTITIES,
                "terminology": POLITICS_TERMINOLOGY,
                "sources": POLITICS_SOURCES,
            },
            "finance": {
                "entities": FINANCE_ENTITIES,
                "terminology": FINANCE_TERMINOLOGY,
                "sources": FINANCE_SOURCES,
            },
            "science-tech": {
                "entities": SCIENCE_TECH_ENTITIES,
                "terminology": SCIENCE_TECH_TERMINOLOGY,
                "sources": SCIENCE_TECH_SOURCES,
            },
        }

        logger.info("Domain Knowledge Service initialized")

    def get_db_connection(self):
        from shared.database.connection import get_db_connection as _get_conn

        return _get_conn()

    def extract_domain_entities(self, domain: str, text: str) -> list[DomainEntity]:
        """
        Extract domain-specific entities from text.
        """
        schema = domain.replace("-", "_")
        kb = self.knowledge_bases.get(domain, self.knowledge_bases.get(schema, {}))
        entities_db = kb.get("entities", {})

        text_lower = text.lower()
        found_entities = []

        for key, entity in entities_db.items():
            # Check main name and aliases
            all_names = [entity.name.lower()] + [a.lower() for a in entity.aliases]
            for name in all_names:
                if name in text_lower:
                    found_entities.append(entity)
                    break

        # Sort by importance
        found_entities.sort(key=lambda e: e.importance, reverse=True)
        return found_entities

    def get_terminology_definitions(self, domain: str, text: str) -> dict[str, str]:
        """
        Get definitions for domain terminology found in text.
        """
        schema = domain.replace("-", "_")
        kb = self.knowledge_bases.get(domain, self.knowledge_bases.get(schema, {}))
        terminology = kb.get("terminology", {})

        text_lower = text.lower()
        found_terms = {}

        for term, definition in terminology.items():
            if term.lower() in text_lower:
                found_terms[term] = definition

        return found_terms

    def get_relevant_sources(
        self, domain: str, content_type: str | None = None
    ) -> list[dict[str, str]]:
        """
        Get relevant external sources for a domain.
        """
        schema = domain.replace("-", "_")
        kb = self.knowledge_bases.get(domain, self.knowledge_bases.get(schema, {}))
        sources = kb.get("sources", [])

        if content_type:
            sources = [s for s in sources if s.get("type") == content_type]

        return sources

    def generate_historical_context(
        self, domain: str, entities: list[DomainEntity], timeframe: str = "recent"
    ) -> str:
        """
        Generate historical context for the given entities.
        """
        if not entities:
            return ""

        domain_name = domain.replace("-", " ").title()
        entity_names = [e.name for e in entities[:5]]

        if domain == "politics":
            return self._generate_politics_context(entity_names, timeframe)
        elif domain == "finance":
            return self._generate_finance_context(entity_names, timeframe)
        elif domain in ["science-tech", "science_tech"]:
            return self._generate_science_tech_context(entity_names, timeframe)
        else:
            return f"Context for {', '.join(entity_names)} in {domain_name}."

    def _generate_politics_context(self, entities: list[str], timeframe: str) -> str:
        """Generate politics-specific historical context"""
        context_parts = []

        if any(
            "congress" in e.lower() or "senate" in e.lower() or "house" in e.lower()
            for e in entities
        ):
            context_parts.append(
                "Congressional dynamics are shaped by current party control, "
                "committee leadership, and pending legislation."
            )

        if any("white house" in e.lower() or "president" in e.lower() for e in entities):
            context_parts.append(
                "Executive actions and policy priorities are central to "
                "understanding current political developments."
            )

        if any("supreme court" in e.lower() or "court" in e.lower() for e in entities):
            context_parts.append(
                "Judicial decisions have lasting impacts on policy and law, "
                "with the current court composition affecting rulings."
            )

        if any("election" in e.lower() or "vote" in e.lower() for e in entities):
            context_parts.append(
                "Electoral dynamics, polling, and campaign developments "
                "influence political strategies and outcomes."
            )

        return (
            " ".join(context_parts)
            if context_parts
            else (
                "Political developments are interconnected with legislative, "
                "executive, and judicial branch activities."
            )
        )

    def _generate_finance_context(self, entities: list[str], timeframe: str) -> str:
        """Generate finance-specific historical context"""
        context_parts = []

        if any(
            "federal reserve" in e.lower() or "fed" in e.lower() or "interest" in e.lower()
            for e in entities
        ):
            context_parts.append(
                "Federal Reserve policy on interest rates significantly impacts "
                "borrowing costs, market valuations, and economic growth."
            )

        if any("inflation" in e.lower() or "cpi" in e.lower() for e in entities):
            context_parts.append(
                "Inflation trends affect consumer purchasing power, "
                "corporate earnings, and monetary policy decisions."
            )

        if any("s&p" in e.lower() or "dow" in e.lower() or "nasdaq" in e.lower() for e in entities):
            context_parts.append(
                "Major indices reflect overall market sentiment and are "
                "influenced by earnings, economic data, and global events."
            )

        if any("recession" in e.lower() or "gdp" in e.lower() for e in entities):
            context_parts.append(
                "Economic growth indicators and recession risks are closely "
                "monitored by investors and policymakers."
            )

        return (
            " ".join(context_parts)
            if context_parts
            else (
                "Financial markets are influenced by monetary policy, "
                "economic indicators, and global events."
            )
        )

    def _generate_science_tech_context(self, entities: list[str], timeframe: str) -> str:
        """Generate science-tech-specific historical context"""
        context_parts = []

        if any(
            "ai" in e.lower()
            or "artificial intelligence" in e.lower()
            or "machine learning" in e.lower()
            for e in entities
        ):
            context_parts.append(
                "AI development has accelerated rapidly with large language models, "
                "raising both opportunities and concerns about capabilities and safety."
            )

        if any(
            "openai" in e.lower() or "chatgpt" in e.lower() or "gpt" in e.lower() for e in entities
        ):
            context_parts.append(
                "The emergence of ChatGPT and similar systems has transformed "
                "public awareness and adoption of AI technologies."
            )

        if any("cyber" in e.lower() or "security" in e.lower() for e in entities):
            context_parts.append(
                "Cybersecurity threats continue to evolve with state-sponsored "
                "attacks, ransomware, and data breaches affecting organizations globally."
            )

        if any("quantum" in e.lower() for e in entities):
            context_parts.append(
                "Quantum computing development progresses toward practical applications, "
                "with implications for cryptography and scientific computing."
            )

        return (
            " ".join(context_parts)
            if context_parts
            else (
                "Technology developments are rapidly evolving across AI, cloud computing, "
                "and cybersecurity with significant societal implications."
            )
        )

    def enrich_rag_context(
        self, domain: str, text: str, storyline_title: str | None = None
    ) -> DomainContext:
        """
        Enrich RAG context with domain-specific knowledge.
        """
        combined_text = f"{storyline_title or ''} {text}"

        # Extract domain entities
        entities = self.extract_domain_entities(domain, combined_text)

        # Get terminology definitions
        terminology = self.get_terminology_definitions(domain, combined_text)

        # Get relevant sources
        sources = self.get_relevant_sources(domain)

        # Generate historical context
        historical = self.generate_historical_context(domain, entities)

        # Extract key concepts (entity types and names)
        key_concepts = list(set([e.entity_type for e in entities[:10]]))

        # Get related topics from entity relationships
        related_topics = []
        for entity in entities[:5]:
            related_topics.extend(entity.related_entities)
        related_topics = list(set(related_topics))[:10]

        # Domain-specific geopolitical/economic context
        geo_context = ""
        econ_context = ""

        if domain == "politics":
            geo_context = self._get_geopolitical_context(entities)
        elif domain == "finance":
            econ_context = self._get_economic_context(entities)

        # Generate timeline context
        timeline_context = self._generate_timeline_context(domain, entities)

        return DomainContext(
            domain=domain,
            entities_found=entities,
            historical_context=historical,
            key_concepts=key_concepts,
            related_topics=related_topics,
            external_sources=sources,
            domain_terminology=terminology,
            timeline_context=timeline_context,
            geopolitical_context=geo_context,
            economic_context=econ_context,
        )

    def _get_geopolitical_context(self, entities: list[DomainEntity]) -> str:
        """Get geopolitical context for politics domain"""
        if any(e.entity_type in ["institution", "party"] for e in entities):
            return (
                "Current political dynamics involve inter-party negotiations, "
                "legislative priorities, and executive-legislative relations. "
                "International relations and foreign policy also influence domestic politics."
            )
        return ""

    def _get_economic_context(self, entities: list[DomainEntity]) -> str:
        """Get economic context for finance domain"""
        has_monetary = any(
            "fed" in e.name.lower() or "interest" in e.name.lower() for e in entities
        )
        has_market = any(e.entity_type in ["exchange", "index"] for e in entities)

        parts = []
        if has_monetary:
            parts.append(
                "Monetary policy decisions impact all asset classes and economic activity."
            )
        if has_market:
            parts.append(
                "Market movements reflect collective investor sentiment and economic expectations."
            )

        return " ".join(parts)

    def _generate_timeline_context(self, domain: str, entities: list[DomainEntity]) -> str:
        """Generate timeline-relevant context"""
        if domain == "politics":
            return (
                "Political timelines often align with legislative sessions, "
                "election cycles, and administration terms. Key dates include "
                "budget deadlines, primary elections, and inauguration periods."
            )
        elif domain == "finance":
            return (
                "Financial timelines follow quarterly earnings cycles, FOMC meetings, "
                "and economic data releases. Key dates include employment reports, "
                "CPI releases, and Fed announcements."
            )
        elif domain in ["science-tech", "science_tech"]:
            return (
                "Technology timelines are marked by product launches, research milestones, "
                "and regulatory developments. Conference seasons and earnings reports "
                "drive news cycles."
            )
        return ""

    def get_entity_details(self, domain: str, entity_name: str) -> DomainEntity | None:
        """
        Get detailed information about a specific entity.
        """
        schema = domain.replace("-", "_")
        kb = self.knowledge_bases.get(domain, self.knowledge_bases.get(schema, {}))
        entities_db = kb.get("entities", {})

        entity_lower = entity_name.lower()

        # Direct match
        if entity_lower in entities_db:
            return entities_db[entity_lower]

        # Search by name or alias
        for key, entity in entities_db.items():
            if entity.name.lower() == entity_lower:
                return entity
            if entity_lower in [a.lower() for a in entity.aliases]:
                return entity

        return None

    def search_knowledge_base(
        self, domain: str, query: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Search the domain knowledge base for relevant information.
        """
        schema = domain.replace("-", "_")
        kb = self.knowledge_bases.get(domain, self.knowledge_bases.get(schema, {}))

        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # Search entities
        for key, entity in kb.get("entities", {}).items():
            all_text = f"{entity.name} {entity.description} {' '.join(entity.aliases)}".lower()
            matches = len(query_words & set(all_text.split()))
            if matches > 0:
                results.append(
                    {
                        "type": "entity",
                        "name": entity.name,
                        "description": entity.description,
                        "importance": entity.importance,
                        "relevance": matches / len(query_words),
                    }
                )

        # Search terminology
        for term, definition in kb.get("terminology", {}).items():
            if query_lower in term.lower() or query_lower in definition.lower():
                results.append(
                    {
                        "type": "term",
                        "name": term,
                        "description": definition,
                        "importance": 0.5,
                        "relevance": 0.5,
                    }
                )

        # Sort by relevance and importance
        results.sort(key=lambda x: (x["relevance"], x["importance"]), reverse=True)
        return results[:limit]


# Singleton instance
_domain_knowledge_service = None


def get_domain_knowledge_service() -> DomainKnowledgeService:
    """Get or create the domain knowledge service singleton"""
    global _domain_knowledge_service
    if _domain_knowledge_service is None:
        _domain_knowledge_service = DomainKnowledgeService()
    return _domain_knowledge_service
