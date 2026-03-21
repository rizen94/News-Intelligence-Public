"""
Deep Content Synthesis Service
Creates comprehensive, Wikipedia-style articles from multiple news sources.

Features:
- Full article text analysis (not just headlines)
- Multi-source synthesis with fact extraction
- RAG-enhanced explanations of complex topics
- Structured encyclopedic output
- Citation and source attribution
- Knowledge gap identification and filling
"""

import logging
import os
import re
import json
import requests
import numpy as np
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import psycopg2
from psycopg2.extras import RealDictCursor

from services.domain_knowledge_service import (
    get_domain_knowledge_service,
    DomainContext,
    DomainEntity,
)
from services.domain_synthesis_config import get_domain_synthesis_config

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_BASE_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
LLM_MODEL = os.getenv('SYNTHESIS_LLM_MODEL', 'llama3.1:8b')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')

# Synthesis parameters
MAX_ARTICLE_LENGTH = 100000  # Max characters per article (100KB)
MIN_CONTENT_LENGTH = 100   # Minimum content length to process
MAX_SYNTHESIS_ARTICLES = 80  # v8: higher cap
LLM_TIMEOUT = 180  # Longer timeout for detailed generation


@dataclass
class ExtractedFact:
    """A fact extracted from an article"""
    content: str
    fact_type: str  # claim, quote, statistic, event, opinion
    confidence: float
    source_article_id: int
    source_title: str
    source_url: str
    published_at: datetime
    entities_mentioned: List[str] = field(default_factory=list)
    requires_context: bool = False
    context_topic: str = ""


@dataclass
class ContentSection:
    """A section of synthesized content"""
    title: str
    content: str
    subsections: List['ContentSection'] = field(default_factory=list)
    sources: List[Dict[str, str]] = field(default_factory=list)
    facts_used: List[ExtractedFact] = field(default_factory=list)


@dataclass
class SynthesizedArticle:
    """Complete synthesized Wikipedia-style article"""
    title: str
    summary: str  # Lead paragraph
    sections: List[ContentSection]
    domain: str
    topic: str
    total_sources: int
    source_articles: List[Dict[str, Any]]
    domain_context: Optional[DomainContext]
    key_entities: List[str]
    key_terms_explained: Dict[str, str]
    timeline: List[Dict[str, Any]]
    created_at: datetime
    word_count: int
    quality_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "summary": self.summary,
            "sections": [self._section_to_dict(s) for s in self.sections],
            "domain": self.domain,
            "topic": self.topic,
            "total_sources": self.total_sources,
            "source_articles": self.source_articles,
            "key_entities": self.key_entities,
            "key_terms_explained": self.key_terms_explained,
            "timeline": self.timeline,
            "created_at": self.created_at.isoformat(),
            "word_count": self.word_count,
            "quality_score": self.quality_score,
        }
    
    def _section_to_dict(self, section: ContentSection) -> Dict[str, Any]:
        return {
            "title": section.title,
            "content": section.content,
            "subsections": [self._section_to_dict(s) for s in section.subsections],
            "sources": section.sources,
        }
    
    def to_markdown(self) -> str:
        """Generate full markdown representation"""
        lines = []
        lines.append(f"# {self.title}")
        lines.append("")
        lines.append(self.summary)
        lines.append("")
        
        # Table of contents
        lines.append("## Contents")
        for i, section in enumerate(self.sections, 1):
            lines.append(f"{i}. [{section.title}](#{section.title.lower().replace(' ', '-')})")
        lines.append("")
        
        # Main sections
        for section in self.sections:
            lines.append(f"## {section.title}")
            lines.append("")
            lines.append(section.content)
            lines.append("")
            
            for subsection in section.subsections:
                lines.append(f"### {subsection.title}")
                lines.append("")
                lines.append(subsection.content)
                lines.append("")
        
        # Key terms
        if self.key_terms_explained:
            lines.append("## Glossary")
            lines.append("")
            for term, definition in self.key_terms_explained.items():
                lines.append(f"**{term}**: {definition}")
                lines.append("")
        
        # Timeline
        if self.timeline:
            lines.append("## Timeline")
            lines.append("")
            for event in self.timeline:
                lines.append(f"- **{event.get('date', 'Unknown')}**: {event.get('event', '')}")
            lines.append("")
        
        # Sources
        lines.append("## Sources")
        lines.append("")
        for i, article in enumerate(self.source_articles[:20], 1):
            lines.append(f"{i}. [{article.get('title', 'Unknown')}]({article.get('url', '#')}) - {article.get('source_name', 'Unknown')}")
        lines.append("")
        
        return "\n".join(lines)


class DeepContentSynthesisService:
    """
    Creates comprehensive, Wikipedia-style content from news articles.
    """
    
    def __init__(self, db_config: Dict[str, Any] = None):
        self.db_config = db_config or {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5433)),
            'database': os.getenv('DB_NAME', 'news_intelligence'),
            'user': os.getenv('DB_USER', 'newsapp'),
            'password': os.getenv('DB_PASSWORD', 'newsapp_password'),
        }
        self.knowledge_service = get_domain_knowledge_service()
        logger.info("Deep Content Synthesis Service initialized")
    
    def get_db_connection(self):
        from shared.database.connection import get_db_connection as _get_conn
        return _get_conn()
    
    # =========================================================================
    # FACT EXTRACTION
    # =========================================================================
    
    def extract_facts_from_article(
        self,
        article_id: int,
        title: str,
        content: str,
        url: str,
        published_at: datetime
    ) -> List[ExtractedFact]:
        """
        Extract key facts, quotes, statistics, and claims from article content.
        """
        if not content or len(content) < MIN_CONTENT_LENGTH:
            return []
        
        # Truncate very long content
        content = content[:MAX_ARTICLE_LENGTH]
        
        prompt = f"""Analyze this news article and extract the key facts.

ARTICLE TITLE: {title}

ARTICLE CONTENT:
{content}

Extract and categorize the following types of information:
1. KEY CLAIMS - Main assertions or statements of fact
2. QUOTES - Direct quotes from people (include who said it)
3. STATISTICS - Numbers, percentages, or quantitative data
4. EVENTS - Specific things that happened (include dates if mentioned)
5. OPINIONS - Expressed viewpoints or analysis

For each fact, indicate if it needs additional context to understand (e.g., technical terms, historical background).

Output as JSON array:
[
  {{
    "content": "The exact fact or quote",
    "type": "claim|quote|statistic|event|opinion",
    "entities": ["person/org/place names mentioned"],
    "needs_context": true/false,
    "context_topic": "topic needing explanation if needs_context is true"
  }}
]

Focus on the most important and newsworthy facts. Extract 5-15 key facts."""

        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 2000, "temperature": 0.3}
                },
                timeout=LLM_TIMEOUT
            )
            
            if response.status_code == 200:
                result = response.json().get('response', '').strip()
                
                # Parse JSON from response
                json_match = re.search(r'\[[\s\S]*\]', result)
                if json_match:
                    facts_data = json.loads(json_match.group())
                    
                    facts = []
                    for fd in facts_data:
                        fact = ExtractedFact(
                            content=fd.get('content', ''),
                            fact_type=fd.get('type', 'claim'),
                            confidence=0.8,  # Base confidence
                            source_article_id=article_id,
                            source_title=title,
                            source_url=url,
                            published_at=published_at,
                            entities_mentioned=fd.get('entities', []),
                            requires_context=fd.get('needs_context', False),
                            context_topic=fd.get('context_topic', '')
                        )
                        facts.append(fact)
                    
                    return facts
        except Exception as e:
            logger.warning(f"Fact extraction failed for article {article_id}: {e}")
        
        # Fallback: extract basic facts using patterns
        return self._extract_facts_fallback(article_id, title, content, url, published_at)
    
    def _extract_facts_fallback(
        self,
        article_id: int,
        title: str,
        content: str,
        url: str,
        published_at: datetime
    ) -> List[ExtractedFact]:
        """Fallback fact extraction using pattern matching"""
        facts = []
        sentences = re.split(r'[.!?]+', content)
        
        for sentence in sentences[:30]:  # Check first 30 sentences
            sentence = sentence.strip()
            if len(sentence) < 30:
                continue
            
            # Detect quotes
            quote_match = re.search(r'"([^"]{20,})"', sentence)
            if quote_match:
                facts.append(ExtractedFact(
                    content=quote_match.group(1),
                    fact_type='quote',
                    confidence=0.9,
                    source_article_id=article_id,
                    source_title=title,
                    source_url=url,
                    published_at=published_at,
                ))
                continue
            
            # Detect statistics
            if re.search(r'\d+(?:\.\d+)?%|\$\d+|\d+ (?:million|billion|thousand)', sentence, re.I):
                facts.append(ExtractedFact(
                    content=sentence,
                    fact_type='statistic',
                    confidence=0.7,
                    source_article_id=article_id,
                    source_title=title,
                    source_url=url,
                    published_at=published_at,
                ))
                continue
            
            # Key sentences (contain important verbs)
            if re.search(r'\b(announced|said|reported|revealed|confirmed|stated|declared)\b', sentence, re.I):
                facts.append(ExtractedFact(
                    content=sentence,
                    fact_type='claim',
                    confidence=0.6,
                    source_article_id=article_id,
                    source_title=title,
                    source_url=url,
                    published_at=published_at,
                ))
        
        return facts[:15]
    
    # =========================================================================
    # CONTENT SYNTHESIS
    # =========================================================================
    
    def synthesize_storyline_content(
        self,
        domain: str,
        storyline_id: int,
        depth: str = "comprehensive",  # brief, standard, comprehensive
        save_to_db: bool = True
    ) -> SynthesizedArticle:
        """
        Create comprehensive synthesized content for a storyline.
        Pulls full intelligence context (entities, claims, events, positions)
        from content_synthesis_service when available.
        """
        schema = domain.replace('-', '_')
        
        # Fetch storyline and articles
        storyline, articles = self._fetch_storyline_with_articles(schema, storyline_id)
        
        if not storyline:
            raise ValueError(f"Storyline {storyline_id} not found")
        
        if not articles:
            raise ValueError(f"No articles found for storyline {storyline_id}")
        
        # Gather full intelligence context for richer synthesis
        intel_ctx = None
        try:
            from services.content_synthesis_service import synthesize_storyline_context
            ctx = synthesize_storyline_context(domain, storyline_id)
            if ctx.get("success"):
                intel_ctx = ctx
        except Exception as e:
            logger.debug("Could not load intelligence context for storyline %s: %s", storyline_id, e)
        
        synthesized = self._synthesize_from_articles(
            domain=domain,
            topic=storyline.get('title', 'Unknown Topic'),
            articles=articles,
            depth=depth,
            existing_description=storyline.get('description', ''),
            intelligence_context=intel_ctx,
        )
        
        # Save synthesized content to database
        if save_to_db:
            self._save_synthesis_to_db(schema, storyline_id, synthesized)
        
        return synthesized
    
    def _save_synthesis_to_db(
        self,
        schema: str,
        storyline_id: int,
        synthesized: SynthesizedArticle
    ) -> None:
        """Save synthesized content to the storyline record"""
        try:
            conn = self.get_db_connection()
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                
                # Generate full text content from sections
                full_content = self._generate_full_text(synthesized)
                markdown = synthesized.to_markdown()
                
                cur.execute("""
                    UPDATE storylines SET
                        synthesized_content = %s,
                        synthesized_markdown = %s,
                        synthesized_at = NOW(),
                        synthesis_word_count = %s,
                        synthesis_quality_score = %s,
                        updated_at = NOW()
                    WHERE id = %s
                """, (
                    full_content,
                    markdown,
                    synthesized.word_count,
                    synthesized.quality_score,
                    storyline_id
                ))
                
                conn.commit()
                logger.info(f"Saved synthesis for storyline {storyline_id} ({synthesized.word_count} words)")
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save synthesis: {e}")
    
    def _generate_full_text(self, synthesized: SynthesizedArticle) -> str:
        """Generate full plain text from synthesized article"""
        parts = []
        
        # Title
        parts.append(synthesized.title)
        parts.append("")
        
        # Summary
        parts.append(synthesized.summary)
        parts.append("")
        
        # Sections
        for section in synthesized.sections:
            parts.append(f"## {section.title}")
            parts.append("")
            parts.append(section.content)
            parts.append("")
            
            for subsection in section.subsections:
                parts.append(f"### {subsection.title}")
                parts.append("")
                parts.append(subsection.content)
                parts.append("")
        
        # Key terms
        if synthesized.key_terms_explained:
            parts.append("## Key Terms")
            parts.append("")
            for term, definition in synthesized.key_terms_explained.items():
                parts.append(f"**{term}**: {definition}")
            parts.append("")
        
        # Timeline
        if synthesized.timeline:
            parts.append("## Timeline")
            parts.append("")
            for event in synthesized.timeline:
                parts.append(f"- {event.get('date', '')}: {event.get('event', '')}")
            parts.append("")
        
        return "\n".join(parts)
    
    def get_saved_synthesis(
        self,
        domain: str,
        storyline_id: int
    ) -> Optional[Dict[str, Any]]:
        """Retrieve saved synthesis from database"""
        schema = domain.replace('-', '_')
        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                
                cur.execute("""
                    SELECT synthesized_content, synthesized_markdown, 
                           synthesized_at, synthesis_word_count, 
                           synthesis_quality_score, title
                    FROM storylines 
                    WHERE id = %s
                """, (storyline_id,))
                
                result = cur.fetchone()
                conn.close()
                
                if result and result.get('synthesized_content'):
                    return dict(result)
                return None
        except Exception as e:
            logger.error(f"Failed to get saved synthesis: {e}")
            return None
    
    def synthesize_topic_content(
        self,
        domain: str,
        topic_name: str,
        hours: int = 720,  # v8: 30 days
        depth: str = "comprehensive"
    ) -> SynthesizedArticle:
        """
        Create comprehensive synthesized content for a topic.
        """
        schema = domain.replace('-', '_')
        
        # Fetch relevant articles for topic
        articles = self._fetch_articles_for_topic(schema, topic_name, hours)
        
        if not articles:
            raise ValueError(f"No articles found for topic: {topic_name}")
        
        return self._synthesize_from_articles(
            domain=domain,
            topic=topic_name,
            articles=articles,
            depth=depth
        )
    
    def synthesize_breaking_news(
        self,
        domain: str,
        hours: int = 72,  # v8
        min_articles: int = 3
    ) -> List[SynthesizedArticle]:
        """
        Create synthesized content for breaking/trending stories.
        """
        schema = domain.replace('-', '_')
        
        # Find clustered articles (breaking news)
        clusters = self._find_article_clusters(schema, hours, min_articles)
        
        synthesized = []
        for cluster in clusters[:5]:  # Top 5 breaking stories
            try:
                article = self._synthesize_from_articles(
                    domain=domain,
                    topic=cluster['topic'],
                    articles=cluster['articles'],
                    depth="standard"
                )
                synthesized.append(article)
            except Exception as e:
                logger.warning(f"Failed to synthesize cluster: {e}")
        
        return synthesized
    
    def _synthesize_from_articles(
        self,
        domain: str,
        topic: str,
        articles: List[Dict],
        depth: str = "comprehensive",
        existing_description: str = "",
        intelligence_context: Optional[Dict[str, Any]] = None,
    ) -> SynthesizedArticle:
        """
        Core synthesis logic - creates Wikipedia-style article from multiple sources.

        When intelligence_context is provided (from content_synthesis_service),
        claims, entity positions, dossier summaries, and chronological events
        are injected into the section generation prompts for richer output.
        """
        start_time = datetime.now()
        domain_cfg = get_domain_synthesis_config(domain)
        
        # Limit articles
        articles = articles[:MAX_SYNTHESIS_ARTICLES]
        
        # Step 1: Extract facts from all articles
        logger.info(f"Extracting facts from {len(articles)} articles...")
        all_facts = []
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    self.extract_facts_from_article,
                    a.get('id', 0),
                    a.get('title', ''),
                    a.get('content', ''),
                    a.get('url', ''),
                    a.get('published_at', datetime.now())
                ): a for a in articles
            }
            
            for future in as_completed(futures):
                try:
                    facts = future.result()
                    all_facts.extend(facts)
                except Exception as e:
                    logger.warning(f"Fact extraction failed: {e}")
        
        logger.info(f"Extracted {len(all_facts)} facts")
        
        # Step 2: Get domain context
        domain_context = self.knowledge_service.enrich_rag_context(domain, topic)
        
        # Step 3: Identify knowledge gaps and get explanations
        terms_to_explain = self._identify_terms_needing_explanation(all_facts, domain)
        key_terms_explained = {}
        for term in terms_to_explain[:10]:
            explanation = self._get_term_explanation(domain, term)
            if explanation:
                key_terms_explained[term] = explanation
        
        # Step 4: Build timeline (include chronological events from intelligence)
        timeline = self._build_timeline(all_facts)
        if intelligence_context:
            for ce in intelligence_context.get("chronological_events", []):
                timeline.append({
                    "date": ce.get("event_date", ""),
                    "event": ce.get("title", ""),
                    "detail": ce.get("description", ""),
                    "source": "event_extraction",
                })
        
        # Step 5: Generate structured content
        intelligence_supplement = ""
        if intelligence_context:
            parts = []
            if domain_cfg.llm_context:
                parts.append(f"Domain guidance: {domain_cfg.llm_context}")
            claims = intelligence_context.get("claims", [])
            if claims:
                claim_lines = [f"- {c['subject']} {c['predicate']} {c['object']}" for c in claims[:8]]
                parts.append("Key claims:\n" + "\n".join(claim_lines))
            positions = intelligence_context.get("entity_positions", [])
            if positions:
                pos_lines = [f"- {p['entity_name']} on {p['topic']}: {p['position']}" for p in positions[:6]]
                parts.append("Entity positions:\n" + "\n".join(pos_lines))
            dossiers = intelligence_context.get("entity_dossiers", [])
            if dossiers:
                for d in dossiers[:3]:
                    chronicle = d.get("chronicle_data", [])
                    if chronicle and isinstance(chronicle, list):
                        snippet = str(chronicle[0])[:200] if chronicle else ""
                        parts.append(f"Dossier excerpt: {snippet}")
            intelligence_supplement = "\n\n".join(parts)
        sections = self._generate_sections(
            topic=topic,
            facts=all_facts,
            domain_context=domain_context,
            key_terms=key_terms_explained,
            timeline=timeline,
            depth=depth,
            existing_description=existing_description + ("\n\n" + intelligence_supplement if intelligence_supplement else ""),
        )
        
        # Step 6: Generate lead paragraph (summary)
        summary = self._generate_lead_paragraph(topic, sections, all_facts, domain_context)
        
        # Step 7: Generate title
        title = self._generate_title(topic, all_facts)
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(
            sections, all_facts, len(articles), key_terms_explained
        )
        
        # Calculate word count
        word_count = len(summary.split())
        for section in sections:
            word_count += len(section.content.split())
            for subsection in section.subsections:
                word_count += len(subsection.content.split())
        
        # Extract key entities
        key_entities = list(set([
            e for f in all_facts for e in f.entities_mentioned
        ]))[:20]
        
        return SynthesizedArticle(
            title=title,
            summary=summary,
            sections=sections,
            domain=domain,
            topic=topic,
            total_sources=len(articles),
            source_articles=[{
                'id': a.get('id'),
                'title': a.get('title'),
                'url': a.get('url'),
                'source_name': a.get('source_name', a.get('source_domain', '')),
                'published_at': str(a.get('published_at', ''))
            } for a in articles],
            domain_context=domain_context,
            key_entities=key_entities,
            key_terms_explained=key_terms_explained,
            timeline=timeline,
            created_at=datetime.now(),
            word_count=word_count,
            quality_score=quality_score
        )
    
    def _generate_sections(
        self,
        topic: str,
        facts: List[ExtractedFact],
        domain_context: DomainContext,
        key_terms: Dict[str, str],
        timeline: List[Dict],
        depth: str,
        existing_description: str = ""
    ) -> List[ContentSection]:
        """
        Generate structured sections for the synthesized article.
        """
        # Organize facts by type
        claims = [f for f in facts if f.fact_type == 'claim']
        quotes = [f for f in facts if f.fact_type == 'quote']
        statistics = [f for f in facts if f.fact_type == 'statistic']
        events = [f for f in facts if f.fact_type == 'event']
        opinions = [f for f in facts if f.fact_type == 'opinion']
        
        sections = []
        
        # Section 1: Background
        if domain_context:
            background = self._generate_background_section(
                topic, domain_context, key_terms
            )
            sections.append(background)
        
        # Section 2: Current Developments (main news)
        if claims or events:
            developments = self._generate_developments_section(
                topic, claims, events, depth
            )
            sections.append(developments)
        
        # Section 3: Key Data and Statistics
        if statistics:
            data_section = self._generate_data_section(topic, statistics)
            sections.append(data_section)
        
        # Section 4: Reactions and Perspectives
        if quotes or opinions:
            reactions = self._generate_reactions_section(topic, quotes, opinions)
            sections.append(reactions)
        
        # Section 5: Analysis and Implications
        analysis = self._generate_analysis_section(
            topic, facts, domain_context, depth
        )
        sections.append(analysis)
        
        return sections
    
    def _generate_background_section(
        self,
        topic: str,
        domain_context: DomainContext,
        key_terms: Dict[str, str]
    ) -> ContentSection:
        """Generate background/context section"""
        prompt = f"""Write a comprehensive background section for an article about "{topic}".

Use this domain context:
- Historical context: {domain_context.historical_context}
- Key entities involved: {', '.join([e.name for e in domain_context.entities_found[:5]])}
- Relevant terminology: {', '.join(list(key_terms.keys())[:5])}
- Timeline context: {domain_context.timeline_context}

Write 2-3 detailed paragraphs that:
1. Explain what this topic is about and why it matters
2. Provide necessary historical or contextual background
3. Introduce key players/entities involved
4. Help readers understand the significance

Write in an encyclopedic, neutral tone like Wikipedia. Be informative and educational."""

        content = self._generate_llm_content(prompt, max_tokens=800)
        
        # Add term definitions as subsection if available
        subsections = []
        if key_terms:
            term_content = "\n\n".join([
                f"**{term}**: {definition}" for term, definition in key_terms.items()
            ])
            subsections.append(ContentSection(
                title="Key Terms",
                content=term_content,
                subsections=[],
                sources=[]
            ))
        
        return ContentSection(
            title="Background",
            content=content,
            subsections=subsections,
            sources=[]
        )
    
    def _generate_developments_section(
        self,
        topic: str,
        claims: List[ExtractedFact],
        events: List[ExtractedFact],
        depth: str
    ) -> ContentSection:
        """Generate section about current developments"""
        # Compile facts into context
        facts_text = "\n".join([
            f"- {f.content} (Source: {f.source_title})"
            for f in (claims + events)[:15]
        ])
        
        prompt = f"""Write a comprehensive section about the current developments regarding "{topic}".

Based on these reported facts and events:
{facts_text}

Write {"3-4 detailed" if depth == "comprehensive" else "2-3"} paragraphs that:
1. Explain what has happened in clear, chronological order
2. Connect related events and show how they relate
3. Present multiple perspectives if there are conflicting reports
4. Attribute information to sources where appropriate

Write in encyclopedic style. Be factual and balanced. Synthesize the information cohesively, don't just list facts."""

        content = self._generate_llm_content(
            prompt, 
            max_tokens=1200 if depth == "comprehensive" else 600
        )
        
        sources = [{"title": f.source_title, "url": f.source_url} for f in (claims + events)[:10]]
        
        return ContentSection(
            title="Current Developments",
            content=content,
            subsections=[],
            sources=sources,
            facts_used=claims + events
        )
    
    def _generate_data_section(
        self,
        topic: str,
        statistics: List[ExtractedFact]
    ) -> ContentSection:
        """Generate section about key data and statistics"""
        stats_text = "\n".join([
            f"- {f.content} (Source: {f.source_title})"
            for f in statistics[:10]
        ])
        
        prompt = f"""Write a section presenting key data and statistics about "{topic}".

Reported statistics:
{stats_text}

Write 1-2 paragraphs that:
1. Present the most significant numbers and data points
2. Provide context for what these numbers mean
3. Compare to historical data or benchmarks if relevant
4. Note any limitations or caveats about the data

Be precise with numbers. Explain what they mean for non-expert readers."""

        content = self._generate_llm_content(prompt, max_tokens=500)
        
        return ContentSection(
            title="Key Data and Statistics",
            content=content,
            subsections=[],
            sources=[{"title": f.source_title, "url": f.source_url} for f in statistics[:5]],
            facts_used=statistics
        )
    
    def _generate_reactions_section(
        self,
        topic: str,
        quotes: List[ExtractedFact],
        opinions: List[ExtractedFact]
    ) -> ContentSection:
        """Generate section about reactions and perspectives"""
        quotes_text = "\n".join([
            f'- "{f.content}" (Source: {f.source_title})'
            for f in quotes[:8]
        ])
        
        opinions_text = "\n".join([
            f"- {f.content} (Source: {f.source_title})"
            for f in opinions[:5]
        ])
        
        prompt = f"""Write a section about reactions and different perspectives on "{topic}".

Quotes from relevant parties:
{quotes_text}

Opinions and analysis:
{opinions_text}

Write 2-3 paragraphs that:
1. Present different viewpoints fairly
2. Include direct quotes where impactful
3. Show the range of reactions (support, criticism, concerns)
4. Identify patterns in the responses

Be balanced and present multiple sides. Attribute statements clearly."""

        content = self._generate_llm_content(prompt, max_tokens=700)
        
        return ContentSection(
            title="Reactions and Perspectives",
            content=content,
            subsections=[],
            sources=[{"title": f.source_title, "url": f.source_url} for f in (quotes + opinions)[:8]],
            facts_used=quotes + opinions
        )
    
    def _generate_analysis_section(
        self,
        topic: str,
        all_facts: List[ExtractedFact],
        domain_context: DomainContext,
        depth: str
    ) -> ContentSection:
        """Generate analysis and implications section"""
        # Summarize key facts for context
        key_facts = sorted(all_facts, key=lambda f: f.confidence, reverse=True)[:10]
        facts_summary = "; ".join([f.content[:100] for f in key_facts[:5]])
        
        prompt = f"""Write an analysis section about the implications of developments regarding "{topic}".

Key facts: {facts_summary}

Domain context: {domain_context.historical_context if domain_context else 'General news topic'}

Write {"2-3 detailed" if depth == "comprehensive" else "1-2"} paragraphs that:
1. Analyze what these developments mean for the future
2. Discuss potential implications and consequences
3. Identify remaining uncertainties or open questions
4. Connect to broader trends or patterns

Be analytical but balanced. Avoid speculation; base analysis on the facts. Note areas of uncertainty."""

        content = self._generate_llm_content(
            prompt,
            max_tokens=800 if depth == "comprehensive" else 400
        )
        
        return ContentSection(
            title="Analysis and Implications",
            content=content,
            subsections=[],
            sources=[]
        )
    
    def _generate_lead_paragraph(
        self,
        topic: str,
        sections: List[ContentSection],
        facts: List[ExtractedFact],
        domain_context: Optional[DomainContext]
    ) -> str:
        """Generate the lead paragraph (summary) for the article"""
        # Gather key content
        key_facts = sorted(facts, key=lambda f: f.confidence, reverse=True)[:5]
        facts_text = "; ".join([f.content[:80] for f in key_facts])
        
        prompt = f"""Write a comprehensive lead paragraph (like Wikipedia's opening) for an article about "{topic}".

Key facts: {facts_text}

The article covers: {', '.join([s.title for s in sections])}

Write a single, information-dense paragraph (150-250 words) that:
1. Immediately explains what this topic/story is about
2. Summarizes the most important facts
3. Places the topic in broader context
4. Answers: Who, What, When, Where, Why
5. Can stand alone as a complete summary

Write in neutral, encyclopedic tone. Be informative and comprehensive."""

        return self._generate_llm_content(prompt, max_tokens=400)
    
    def _generate_title(self, topic: str, facts: List[ExtractedFact]) -> str:
        """Generate an informative, encyclopedic title"""
        # Use the topic as base, but make it more descriptive if possible
        if len(facts) > 0:
            # Find most common entities
            entities = [e for f in facts for e in f.entities_mentioned]
            if entities:
                return f"{topic}: {facts[0].content[:50]}..."
        
        return topic
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _generate_llm_content(self, prompt: str, max_tokens: int = 500) -> str:
        """Generate content using LLM"""
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": LLM_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.7
                    }
                },
                timeout=LLM_TIMEOUT
            )
            
            if response.status_code == 200:
                return response.json().get('response', '').strip()
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
        
        return f"[Content generation failed for this section. Topic: {prompt[:100]}...]"
    
    def _identify_terms_needing_explanation(
        self,
        facts: List[ExtractedFact],
        domain: str
    ) -> List[str]:
        """Identify technical terms that need explanation"""
        terms = []
        
        # Get terms from facts that need context
        for fact in facts:
            if fact.requires_context and fact.context_topic:
                terms.append(fact.context_topic)
        
        # Get domain-specific terms mentioned
        all_text = " ".join([f.content for f in facts])
        domain_terms = self.knowledge_service.get_terminology_definitions(domain, all_text)
        terms.extend(domain_terms.keys())
        
        return list(set(terms))
    
    def _get_term_explanation(self, domain: str, term: str) -> Optional[str]:
        """Get explanation for a technical term"""
        # First check domain knowledge base
        schema = domain.replace('-', '_')
        kb = self.knowledge_service.knowledge_bases.get(
            domain, 
            self.knowledge_service.knowledge_bases.get(schema, {})
        )
        
        terminology = kb.get('terminology', {})
        if term.lower() in terminology:
            return terminology[term.lower()]
        
        # Check entities
        for key, entity in kb.get('entities', {}).items():
            if term.lower() in key.lower() or term.lower() in entity.name.lower():
                return entity.description
        
        # Fall back to LLM
        prompt = f"Explain '{term}' in 1-2 sentences for a general audience. Be concise and clear."
        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": LLM_MODEL, "prompt": prompt, "stream": False},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get('response', '').strip()[:200]
        except:
            pass
        
        return None
    
    def _build_timeline(self, facts: List[ExtractedFact]) -> List[Dict[str, Any]]:
        """Build a timeline of events from facts"""
        timeline = []
        
        events = [f for f in facts if f.fact_type == 'event']
        events.sort(key=lambda f: f.published_at)
        
        for event in events[:10]:
            timeline.append({
                "date": event.published_at.strftime("%Y-%m-%d"),
                "event": event.content[:200],
                "source": event.source_title
            })
        
        return timeline
    
    def _calculate_quality_score(
        self,
        sections: List[ContentSection],
        facts: List[ExtractedFact],
        source_count: int,
        key_terms: Dict[str, str]
    ) -> float:
        """Calculate quality score for synthesized article"""
        score = 0.0
        
        # Source diversity (up to 0.3)
        score += min(source_count / 10, 0.3)
        
        # Fact density (up to 0.2)
        score += min(len(facts) / 30, 0.2)
        
        # Section completeness (up to 0.2)
        score += min(len(sections) / 5, 0.2)
        
        # Term explanations (up to 0.15)
        score += min(len(key_terms) / 5, 0.15)
        
        # Content length (up to 0.15)
        total_content = sum([len(s.content) for s in sections])
        score += min(total_content / 5000, 0.15)
        
        return round(score, 2)
    
    # =========================================================================
    # DATABASE QUERIES
    # =========================================================================
    
    def _fetch_storyline_with_articles(
        self,
        schema: str,
        storyline_id: int
    ) -> Tuple[Optional[Dict], List[Dict]]:
        """Fetch storyline and its full article content"""
        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                
                # Get storyline
                cur.execute("""
                    SELECT * FROM storylines WHERE id = %s
                """, (storyline_id,))
                storyline = cur.fetchone()
                
                if not storyline:
                    conn.close()
                    return None, []
                
                # Get full articles
                cur.execute("""
                    SELECT a.id, a.title, a.content, a.url, a.source_name, 
                           a.source_domain, a.published_at, a.sentiment_score,
                           a.extracted_entities
                    FROM articles a
                    JOIN storyline_articles sa ON a.id = sa.article_id
                    WHERE sa.storyline_id = %s
                    ORDER BY a.published_at DESC
                """, (storyline_id,))
                articles = cur.fetchall()
                
                conn.close()
                return dict(storyline), [dict(a) for a in articles]
                
        except Exception as e:
            logger.error(f"Error fetching storyline {storyline_id}: {e}")
            return None, []
    
    def _fetch_articles_for_topic(
        self,
        schema: str,
        topic_name: str,
        hours: int
    ) -> List[Dict]:
        """Fetch articles related to a topic"""
        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                
                # Search in title and content
                search_pattern = f"%{topic_name}%"
                
                cur.execute("""
                    SELECT id, title, content, url, source_name, source_domain,
                           published_at, sentiment_score, extracted_entities
                    FROM articles
                    WHERE (title ILIKE %s OR content ILIKE %s)
                      AND published_at >= NOW() - INTERVAL '%s hours'
                      AND content IS NOT NULL
                      AND LENGTH(content) > 200
                    ORDER BY published_at DESC
                    LIMIT %s
                """, (search_pattern, search_pattern, hours, MAX_SYNTHESIS_ARTICLES))
                
                articles = cur.fetchall()
                conn.close()
                
                return [dict(a) for a in articles]
                
        except Exception as e:
            logger.error(f"Error fetching articles for topic: {e}")
            return []
    
    def _find_article_clusters(
        self,
        schema: str,
        hours: int,
        min_articles: int
    ) -> List[Dict[str, Any]]:
        """Find clusters of related articles (breaking news)"""
        try:
            conn = self.get_db_connection()
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"SET search_path TO {schema}, public")
                
                # Get recent articles
                cur.execute("""
                    SELECT id, title, content, url, source_name, published_at
                    FROM articles
                    WHERE published_at >= NOW() - INTERVAL '%s hours'
                      AND content IS NOT NULL
                      AND LENGTH(content) > 200
                    ORDER BY published_at DESC
                    LIMIT 100
                """, (hours,))
                
                articles = [dict(a) for a in cur.fetchall()]
                conn.close()
                
                # Simple clustering by title similarity
                clusters = []
                used = set()
                
                for i, article in enumerate(articles):
                    if i in used:
                        continue
                    
                    cluster = [article]
                    title_words = set(article['title'].lower().split())
                    
                    for j, other in enumerate(articles[i+1:], i+1):
                        if j in used:
                            continue
                        
                        other_words = set(other['title'].lower().split())
                        overlap = len(title_words & other_words) / max(len(title_words), 1)
                        
                        if overlap > 0.3:  # 30% word overlap
                            cluster.append(other)
                            used.add(j)
                    
                    if len(cluster) >= min_articles:
                        clusters.append({
                            'topic': article['title'],
                            'articles': cluster,
                            'count': len(cluster)
                        })
                    
                    used.add(i)
                
                # Sort by cluster size
                clusters.sort(key=lambda c: c['count'], reverse=True)
                return clusters
                
        except Exception as e:
            logger.error(f"Error finding article clusters: {e}")
            return []


# Singleton
_synthesis_service = None


def get_synthesis_service() -> DeepContentSynthesisService:
    global _synthesis_service
    if _synthesis_service is None:
        _synthesis_service = DeepContentSynthesisService()
    return _synthesis_service

