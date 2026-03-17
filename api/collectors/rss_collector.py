#!/usr/bin/env python3
"""
RSS Feed Collector for News Intelligence System v5.0
Collects articles from RSS feeds with advanced deduplication.
Excludes sports, entertainment, and pop culture content.
"""

import os
import sys
import logging
import threading
import hashlib
import feedparser
import psycopg2
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional


def _utc_aware(dt):
    """Return a timezone-aware datetime in UTC. Feed and DB datetimes may be naive or aware."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

# Add parent directory to path for service imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from services.bias_detection_service import calculate_domain_bias_score

# Import deduplication system
try:
    from modules.deduplication import DeduplicationManager
    DEDUPLICATION_AVAILABLE = True
except ImportError:
    DEDUPLICATION_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Deduplication system not available - falling back to basic collection")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use shared pool (run with api as cwd or PYTHONPATH=api)
from shared.database.connection import get_db_connection as _get_conn

def get_db_connection():
    """Get database connection from shared pool. Raises if DB unreachable."""
    return _get_conn()

def calculate_article_impact_score(title: str, content: str) -> float:
    """
    Calculate a simple impact score (0.0-1.0) for an article.
    
    Higher scores indicate more important/newsworthy content.
    Lower scores indicate fluff, lifestyle, or low-impact content.
    
    Args:
        title: Article title
        content: Article content/summary
        
    Returns:
        Impact score between 0.0 and 1.0
    """
    text_to_check = f"{title} {content}".lower()
    score = 0.5  # Base score
    
    # High-impact indicators (increase score)
    high_impact_keywords = [
        # Breaking news / Urgency
        'breaking', 'urgent', 'crisis', 'emergency', 'alert', 'warning', 'developing',
        'exclusive', 'just in', 'live', 'update', 'latest', 'reports',
        
        # Policy & Government
        'policy', 'policies', 'legislation', 'regulation', 'regulations', 'law', 'laws',
        'bill', 'bills', 'act', 'acts', 'congress', 'parliament', 'senate', 'house',
        'government', 'official', 'officials', 'minister', 'ministers', 'president',
        'prime minister', 'cabinet', 'administration', 'executive', 'legislative',
        'judicial', 'supreme court', 'federal', 'state', 'municipal',
        
        # Elections & Democracy
        'election', 'elections', 'vote', 'voting', 'campaign', 'campaigns', 'poll',
        'polls', 'ballot', 'ballots', 'candidate', 'candidates', 'primary', 'primaries',
        'referendum', 'referendums', 'democracy', 'democratic', 'republican',
        'constituency', 'constituencies', 'electoral', 'voter', 'voters',
        
        # Economy & Finance
        'economy', 'economic', 'economics', 'market', 'markets', 'financial', 'finance',
        'trade', 'trading', 'gdp', 'inflation', 'deflation', 'recession', 'depression',
        'unemployment', 'employment', 'jobs', 'wages', 'salary', 'salaries',
        'interest rate', 'interest rates', 'federal reserve', 'fed', 'central bank',
        'stock market', 'stocks', 'bonds', 'currency', 'currencies', 'exchange rate',
        'budget', 'deficit', 'surplus', 'debt', 'tax', 'taxes', 'taxation',
        'tariff', 'tariffs', 'sanctions', 'embargo', 'embargoes',
        'merger', 'mergers', 'acquisition', 'acquisitions', 'ipo', 'bankruptcy',
        'foreclosure', 'foreclosures', 'default', 'defaults',
        
        # Business & Corporate
        'corporation', 'corporations', 'company', 'companies', 'business', 'businesses',
        'industry', 'industries', 'sector', 'sectors', 'quarterly', 'earnings',
        'revenue', 'profit', 'profits', 'loss', 'losses', 'shareholder', 'shareholders',
        'ceo', 'cfo', 'executive', 'executives', 'board', 'board of directors',
        
        # International Relations
        'international', 'diplomatic', 'diplomacy', 'treaty', 'treaties', 'alliance',
        'alliances', 'summit', 'summits', 'negotiation', 'negotiations', 'agreement',
        'agreements', 'trade deal', 'trade war', 'conflict', 'conflicts', 'war',
        'peace', 'ceasefire', 'truce', 'military', 'defense', 'defence',
        'nato', 'united nations', 'un', 'who', 'wto', 'imf', 'world bank',
        
        # Legal & Justice
        'investigation', 'investigations', 'probe', 'probes', 'inquiry', 'inquiries',
        'scandal', 'scandals', 'corruption', 'fraud', 'lawsuit', 'lawsuits',
        'trial', 'trials', 'court', 'courts', 'judge', 'judges', 'jury',
        'announcement', 'announcements', 'decision', 'decisions', 'ruling', 'rulings',
        'verdict', 'verdicts', 'sentence', 'sentencing', 'appeal', 'appeals',
        'prosecution', 'prosecutor', 'attorney', 'attorneys', 'lawyer', 'lawyers',
        
        # Social & Public Policy
        'healthcare', 'health care', 'medicare', 'medicaid', 'social security',
        'education', 'school', 'schools', 'university', 'universities', 'college',
        'colleges', 'immigration', 'immigrant', 'immigrants', 'refugee', 'refugees',
        'climate', 'environment', 'environmental', 'emissions', 'carbon', 'renewable',
        'energy', 'infrastructure', 'transportation', 'housing', 'homelessness',
        'poverty', 'inequality', 'discrimination', 'civil rights', 'human rights',
        
        # Technology & Innovation
        'technology', 'tech', 'innovation', 'artificial intelligence', 'ai',
        'cybersecurity', 'cyber attack', 'data breach', 'privacy', 'regulation',
        'startup', 'startups', 'venture capital', 'investment', 'investments',
        
        # Impact & Consequences
        'impact', 'impacts', 'consequence', 'consequences', 'effect', 'effects',
        'implication', 'implications', 'significance', 'important', 'major',
        'significant', 'critical', 'crucial', 'historic', 'historical',
        'unprecedented', 'first time', 'milestone', 'landmark', 'watershed'
    ]
    
    # Count high-impact keyword matches (more matches = higher score)
    high_impact_matches = sum(1 for keyword in high_impact_keywords if keyword in text_to_check)
    if high_impact_matches > 0:
        # Boost score based on number of matches (diminishing returns)
        score += min(0.3, high_impact_matches * 0.03)  # Max +0.3 boost
    
    # Low-impact indicators — only clearly non-news content (no ambiguous terms)
    low_impact_keywords = [
        # Recipes / cooking (unambiguous)
        'recipe', 'recipes', 'how to cook', 'cooking tips', 'meal prep',
        'food blog', 'cookbook', 'cooking show',

        # Home / lifestyle tips (unambiguous)
        'home decor', 'diy project', 'organizing tips', 'cleaning tips',
        'gift wrapping', 'skincare routine', 'makeup tutorial',
        'outfit ideas', 'wardrobe tips', 'packing tips',

        # Clickbait patterns (unambiguous)
        'you won\'t believe', 'one weird trick', 'doctors hate',
        'hack that will', 'this one thing', 'number one reason',

        # Advice columns (unambiguous)
        'dear abby', 'ask amy', 'horoscope', 'horoscopes', 'zodiac',

        # Sponsored content (unambiguous)
        'sponsored content', 'paid partnership', 'advertorial',
    ]
    
    # Count low-impact keyword matches (more matches = lower score)
    low_impact_matches = sum(1 for keyword in low_impact_keywords if keyword in text_to_check)
    if low_impact_matches > 0:
        # Reduce score based on number of matches
        score -= min(0.4, low_impact_matches * 0.08)  # Max -0.4 reduction
    
    # Content length factor (longer articles often more substantial)
    content_length = len(content or '')
    if content_length > 2000:
        score += 0.15  # Very long articles often more in-depth
    elif content_length > 1000:
        score += 0.1
    elif content_length > 500:
        score += 0.05
    elif content_length < 200:
        score -= 0.15  # Very short articles often fluff
    
    # Title analysis (news titles vs clickbait)
    title_lower = title.lower()
    if any(phrase in title_lower for phrase in ['breaking', 'urgent', 'exclusive', 'developing']):
        score += 0.1  # Breaking news indicators
    if any(phrase in title_lower for phrase in ['you won\'t believe', 'shocking', 'amazing trick', 'one weird']):
        score -= 0.2  # Clickbait indicators
    
    # Clamp to 0.0-1.0 range
    return max(0.0, min(1.0, score))


def calculate_article_quality_score(title: str, content: str, source: str = "") -> float:
    """
    Calculate a simple quality score (0.0-1.0) for an article.
    
    Based on content length, structure, and source reliability.
    
    Args:
        title: Article title
        content: Article content/summary
        source: Source name/domain
        
    Returns:
        Quality score between 0.0 and 1.0
    """
    score = 0.5  # Base score
    
    # Content length factor
    content_length = len(content or '')
    if content_length > 1000:
        score += 0.2
    elif content_length > 500:
        score += 0.1
    elif content_length < 200:
        score -= 0.2
    
    # Title quality (not too short, not clickbait)
    title_length = len(title or '')
    if 20 <= title_length <= 100:
        score += 0.1
    elif title_length < 10:
        score -= 0.1
    
    # Source reliability (reputable sources get boost)
    reputable_sources = [
        # Wire services & major news
        'reuters', 'ap news', 'associated press', 'bbc', 'bloomberg',
        'financial times', 'wall street journal', 'wsj', 'economist', 'guardian',
        'new york times', 'washington post', 'cnn', 'fox news', 'nbc', 'abc', 'cbs',
        'pbs', 'npr', 'ap', 'afp', 'agence france-presse',
        
        # Financial news
        'bloomberg', 'financial times', 'ft', 'wall street journal', 'wsj',
        'marketwatch', 'cnbc', 'yahoo finance', 'forbes', 'fortune',
        'barrons', 'investors business daily', 'seeking alpha',
        
        # International
        'bbc', 'guardian', 'telegraph', 'times', 'independent',
        'le monde', 'der spiegel', 'frankfurter allgemeine',
        
        # Business
        'harvard business review', 'mckinsey', 'boston consulting',
        'strategy+business', 'sloan review'
    ]
    source_lower = source.lower()
    if any(reputable in source_lower for reputable in reputable_sources):
        score += 0.15
    
    # Content structure indicators (journalistic quality markers)
    text_to_check = (title + ' ' + content).lower()
    quality_indicators = [
        # Attribution & sources
        'according to', 'reported', 'sources', 'source', 'official', 'officials',
        'spokesperson', 'spokesman', 'spokeswoman', 'statement', 'announced',
        
        # Data & evidence
        'data', 'statistics', 'statistical', 'study', 'studies', 'research',
        'analysis', 'analyst', 'analysts', 'report', 'reports', 'survey',
        'poll', 'polls', 'findings', 'evidence', 'figures', 'numbers',
        
        # Professional terms
        'expert', 'experts', 'economist', 'economists', 'analyst', 'analysts',
        'professor', 'researcher', 'scholar', 'academic', 'institution',
        
        # News structure
        'breaking', 'developing', 'update', 'latest', 'exclusive',
        'investigation', 'inquiry', 'probe', 'hearing', 'testimony'
    ]
    indicator_count = sum(1 for indicator in quality_indicators if indicator in text_to_check)
    score += min(0.2, indicator_count * 0.025)  # Max +0.2 boost for quality indicators
    
    # Clamp to 0.0-1.0 range
    return max(0.0, min(1.0, score))


def is_clickbait_title(title: str) -> bool:
    """
    Check if article title is clickbait.
    Excludes news briefs, press releases, and official filings.
    
    Args:
        title: Article title
        
    Returns:
        True if title is clickbait, False otherwise
    """
    if not title:
        return False
    
    title_lower = title.lower()
    
    # Allow official/press release indicators (these are NOT clickbait)
    official_indicators = [
        'press release', 'press release:', 'for immediate release',
        'official statement', 'official announcement', 'filing', 'filed',
        'sec filing', 'sec form', 'regulatory filing', 'news brief',
        'brief:', 'announcement:', 'statement:', 'report:'
    ]
    
    # If it's an official document, it's not clickbait
    if any(indicator in title_lower for indicator in official_indicators):
        return False
    
    # Clickbait patterns
    clickbait_patterns = [
        r'you won\'t believe',
        r'shocking.*will.*blow.*mind',
        r'amazing trick',
        r'one weird trick',
        r'doctors hate',
        r'this one thing',
        r'number one reason',
        r'secret.*will.*blow.*mind',
        r'\d+.*things.*need.*know',
        r'before.*die',
        r'changed.*life.*forever',
        r'everyone.*talking.*about',
        r'going.*viral',
        r'trending.*now',
        r'you.*never.*guess',
        r'what.*happens.*next.*shock'
    ]
    
    for pattern in clickbait_patterns:
        if re.search(pattern, title_lower):
            return True
    
    return False


def is_advertisement(title: str, content: str, url: str = "") -> bool:
    """
    Check if article is an advertisement or sponsored content.
    Excludes press releases and official announcements.
    
    Args:
        title: Article title
        content: Article content
        url: Article URL
        
    Returns:
        True if article is an ad, False otherwise
    """
    text_to_check = f"{title} {content} {url}".lower()
    
    # Allow official/press release indicators (these are NOT ads)
    official_indicators = [
        'press release', 'for immediate release', 'official statement',
        'official announcement', 'filing', 'sec filing', 'regulatory filing',
        'news brief', 'announcement:', 'statement:', 'report:'
    ]
    
    # If it's an official document, it's not an ad
    if any(indicator in text_to_check for indicator in official_indicators):
        return False
    
    # Advertisement indicators
    ad_indicators = [
        'sponsored', 'sponsored content', 'advertisement', 'advertisements',
        'paid partnership', 'affiliate', 'buy now', 'shop now',
        'limited time offer', 'special offer', 'discount', 'sale',
        'promo code', 'coupon', 'deal', 'deals', 'save \d+%',
        'click here to', 'order now', 'get yours', 'shop here',
        'promotional', 'promotion', 'marketing', 'advertorial'
    ]
    
    # Check for ad indicators
    for indicator in ad_indicators:
        if indicator in text_to_check:
            return True
    
    # URL patterns that indicate ads
    ad_url_patterns = [
        '/ad/', '/ads/', '/advertisement/', '/sponsored/',
        '/promo/', '/promotion/', '/shop/', '/store/',
        '/buy/', '/deal/', '/offer/'
    ]
    
    url_lower = url.lower()
    if any(pattern in url_lower for pattern in ad_url_patterns):
        return True
    
    return False


def is_excluded_content(title: str, content: str, feed_name: str = "", feed_url: str = "") -> bool:
    """
    Check if article should be excluded (sports, entertainment, pop culture)
    
    Args:
        title: Article title
        content: Article content/summary
        feed_name: Name of the RSS feed
        feed_url: URL of the RSS feed
        
    Returns:
        True if article should be excluded, False otherwise
    """
    # Combine all text for checking
    text_to_check = f"{title} {content} {feed_name}".lower()
    
    # Sports keywords — only unambiguous sports terms (no common English words)
    sports_keywords = [
        # Specific sports (unambiguous)
        'football', 'soccer', 'basketball', 'baseball', 'hockey', 'tennis',
        'golf', 'cricket', 'rugby', 'volleyball', 'boxing', 'mma', 'ufc',
        'nascar', 'motorsport', 'olympic', 'olympics', 'paralympic',

        # Leagues and events (unambiguous)
        'nba', 'nfl', 'mlb', 'nhl', 'fifa', 'uefa', 'ncaa',
        'world cup', 'super bowl', 'stanley cup', 'world series', 'final four',
        'championship game', 'playoff game', 'playoff series',

        # Sports-specific roles (unambiguous)
        'quarterback', 'pitcher', 'goalkeeper', 'goalie', 'referee', 'umpire',
        'head coach', 'offensive coordinator', 'defensive coordinator',

        # Sports-specific phrases (unambiguous)
        'fantasy football', 'fantasy baseball', 'fantasy basketball',
        'starting lineup', 'depth chart', 'injury report', 'injury update',
        'power rankings', 'all-star game', 'hall of fame induction',
        'draft pick', 'trade deadline', 'free agent signing',
        'sports betting', 'point spread',
    ]
    
    # Entertainment keywords — only unambiguous entertainment terms
    entertainment_keywords = [
        # Celebrity/gossip (unambiguous)
        'celebrity news', 'celebrity gossip', 'red carpet',
        'paparazzi', 'tabloid gossip', 'reality tv', 'reality show',
        'kardashian', 'jenner', 'real housewives', 'love island',

        # Awards shows (unambiguous)
        'oscars ceremony', 'grammy awards', 'emmy awards', 'golden globes ceremony',
        'academy awards', 'tony awards',

        # Box office / movie industry (unambiguous)
        'box office', 'opening weekend', 'film festival', 'movie premiere',
        'nielsen ratings', 'tv ratings',

        # Music industry (unambiguous)
        'billboard hot 100', 'top 40 chart', 'album release', 'concert tour',
        'music video', 'spotify playlist',

        # Showbiz (unambiguous)
        'showbiz', 'show business', 'tinseltown',
    ]
    
    # Pop culture keywords — only unambiguous pop culture terms
    pop_culture_keywords = [
        # Influencer culture (unambiguous)
        'tiktok star', 'instagram model', 'youtube star', 'onlyfans',
        'twitch streamer', 'viral tiktok',

        # Gaming (unambiguous — note: science-tech should cover gaming industry news)
        'esports tournament', 'fortnite', 'call of duty', 'speedrun',

        # Comics/anime (unambiguous)
        'comic con', 'cosplay', 'anime convention', 'manga release',

        # Fandom (unambiguous)
        'fan theory', 'fanfiction', 'kpop', 'jpop', 'boy band',

        # Fashion/beauty (unambiguous — not "style" or "trend" alone)
        'fashion week', 'red carpet fashion', 'beauty guru', 'makeup tutorial',

        # Reality TV (unambiguous)
        'married at first sight', 'the challenge', 'vanderpump rules',
        '90 day fiance', 'love after lockup',
    ]
    
    # Lifestyle/fluff keywords — only unambiguous non-news terms
    lifestyle_fluff_keywords = [
        # Recipes (unambiguous)
        'recipe', 'recipes', 'how to cook', 'cooking tips', 'meal prep',
        'meal planning', 'food blog', 'cookbook',

        # Home/DIY (unambiguous)
        'home decor', 'diy project', 'organizing tips', 'cleaning tips',
        'gift wrapping', 'wrapping presents',

        # Lifestyle tips (unambiguous)
        'skincare routine', 'makeup tutorial', 'outfit ideas',
        'wardrobe tips', 'packing tips',

        # Advice columns (unambiguous)
        'dear abby', 'ask amy', 'horoscope', 'zodiac sign',

        # Holiday fluff (unambiguous)
        'holiday recipes', 'christmas recipes', 'stocking stuffers',
        'gift guide',
    ]
    
    # Check for exclusion keywords
    all_exclusion_keywords = sports_keywords + entertainment_keywords + pop_culture_keywords + lifestyle_fluff_keywords
    
    for keyword in all_exclusion_keywords:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, text_to_check):
            logger.debug(f"Article excluded (matched keyword '{keyword}'): {title[:60]}...")
            return True
    
    # Pattern matching — only multi-word patterns that are unambiguously non-news
    exclusion_patterns = [
        r'\b\d+\s*-\s*\d+\s*(final|score|points?|goals?)\b',  # "3-2 final" (sports score)
        r'\b(football|basketball|baseball|hockey|soccer|tennis|golf|cricket)\s+(game|match|season|league|team)\b',
        r'\b\w+\s+vs\.?\s+\w+\s+(game|match|final|semifinal|championship)\b',
        r'\b(album|single|ep)\s+release\b',
        r'\bcelebrity\s+(gossip|rumor)\b',
        r'\b(pop|rock|hip hop|rap|country)\s+(music|song|album)\b',
        r'\b(you won\'t believe|one weird trick|doctors hate)\b',
    ]
    
    for pattern in exclusion_patterns:
        if re.search(pattern, text_to_check):
            logger.debug(f"Article excluded (matched pattern '{pattern}'): {title[:60]}...")
            return True
    
    return False

def collect_rss_feeds() -> int:
    """
    Collect articles from all active RSS feeds with deduplication
    Returns: Number of articles added
    """
    logger.info("Starting RSS feed collection with deduplication (v5.0 domain-aware)...")
    
    # Initialize deduplication manager if available
    dedup_manager = None
    if DEDUPLICATION_AVAILABLE:
        try:
            dedup_manager = DeduplicationManager(_db_config())
            logger.info("Deduplication system initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize deduplication system: {e}")
            dedup_manager = None
    
    conn = get_db_connection()
    if not conn:
        logger.error("Failed to connect to database")
        return 0
    
    try:
        cur = conn.cursor()
        
        # Get all active RSS feeds from all domain schemas (v5.0)
        # Query each domain schema: politics, finance, science_tech
        feeds = []
        domains = [
            ('politics', 'politics'),
            ('finance', 'finance'),
            ('science-tech', 'science_tech')
        ]
        
        for domain_key, schema_name in domains:
            try:
                cur.execute(f"""
                    SELECT id, feed_name, feed_url, %s as domain_key
                    FROM {schema_name}.rss_feeds 
                    WHERE is_active = true
                """, (domain_key,))
                domain_feeds = cur.fetchall()
                feeds.extend(domain_feeds)
                logger.info(f"Found {len(domain_feeds)} active feeds in {domain_key} domain")
            except Exception as e:
                logger.warning(f"Error querying feeds from {schema_name} schema: {e}")
                continue
        
        total_articles_added = 0
        total_articles_updated = 0
        total_duplicates_rejected = 0
        total_excluded = 0
        total_filtered_clickbait = 0
        total_filtered_ads = 0
        total_filtered_quality = 0
        total_filtered_impact = 0
        
        # OPTIMIZATION: Process feeds in parallel (max 5 concurrent)
        def process_single_feed(feed_data):
            """Process a single RSS feed - designed for parallel execution"""
            import time as _time
            feed_start = _time.time()
            feed_id, feed_name, feed_url, domain_key = feed_data
            schema_name = domain_key.replace('-', '_') if domain_key else 'politics'
            
            def _rss_log(status, fetched=0, saved=0, err=None):
                try:
                    from shared.logging.activity_logger import log_rss_pull
                    log_rss_pull(feed_id=feed_id, feed_name=feed_name, status=status,
                                 articles_fetched=fetched, articles_saved=saved,
                                 duration_ms=(_time.time() - feed_start) * 1000, error=err)
                except Exception:
                    pass
            
            # Each thread gets its own database connection
            feed_conn = get_db_connection()
            if not feed_conn:
                logger.error(f"Failed to get DB connection for feed: {feed_name}")
                _rss_log("error", err="No DB connection")
                return {'articles_added': 0, 'articles_updated': 0, 'duplicates': 0, 'excluded': 0, 'error': 'No DB connection'}
            
            try:
                feed_cur = feed_conn.cursor()
                articles_added = 0
                articles_updated = 0
                duplicates_rejected = 0
                excluded_count = 0
                filtered_clickbait = 0
                filtered_ads = 0
                filtered_quality = 0
                filtered_impact = 0
                
                try:
                    # Parse RSS feed with timeout
                    def parse_feed():
                        return feedparser.parse(feed_url)
                    
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(parse_feed)
                        try:
                            feed = future.result(timeout=30)
                        except FutureTimeoutError:
                            raise TimeoutError("RSS parsing timeout")
                    
                    for entry in feed.entries[:50]:
                        try:
                            feed_cur.execute("SAVEPOINT sp_article")
                            title = entry.get('title', '')[:500]
                            url = entry.get('link', '')[:500]
                            # Prefer full article body (content:encoded) over excerpt
                            content = ''
                            if hasattr(entry, 'content') and entry.content:
                                try:
                                    content = entry.content[0].get('value', '')
                                except (IndexError, AttributeError):
                                    pass
                            if not content:
                                content = entry.get('summary', '') or entry.get('description', '')
                            
                            # Filter excluded content (sports/entertainment/pop culture)
                            if is_excluded_content(title, content, feed_name, feed_url):
                                excluded_count += 1
                                continue
                            
                            # Filter clickbait titles (but allow press releases/official filings)
                            if is_clickbait_title(title):
                                filtered_clickbait += 1
                                excluded_count += 1
                                logger.debug(f"Article excluded (clickbait): {title[:60]}...")
                                continue
                            
                            # Filter advertisements (but allow press releases/official filings)
                            if is_advertisement(title, content, url):
                                filtered_ads += 1
                                excluded_count += 1
                                logger.debug(f"Article excluded (advertisement): {title[:60]}...")
                                continue
                            
                            # Calculate scores BEFORE filtering (need scores for threshold check)
                            impact_score = calculate_article_impact_score(title, content)
                            quality_score = calculate_article_quality_score(title, content, feed_name)
                            
                            # Filter by minimum quality score
                            if quality_score < 0.3:
                                filtered_quality += 1
                                excluded_count += 1
                                logger.debug(f"Article excluded (quality score {quality_score:.2f} < 0.3): {title[:60]}...")
                                continue
                            
                            # Filter by minimum impact score
                            if impact_score < 0.25:
                                filtered_impact += 1
                                excluded_count += 1
                                logger.debug(f"Article excluded (impact score {impact_score:.2f} < 0.25): {title[:60]}...")
                                continue
                            
                            # Parse published date (normalize to UTC-aware for comparison with DB timestamps)
                            published_date = None
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                published_date = _utc_aware(datetime(*entry.published_parsed[:6]))
                            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                                published_date = _utc_aware(datetime(*entry.updated_parsed[:6]))
                            else:
                                published_date = datetime.now(timezone.utc)
                            feed_updated_dt = None
                            if hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                                feed_updated_dt = _utc_aware(datetime(*entry.updated_parsed[:6]))
                            
                            # Check for existing article by URL (update-aware)
                            feed_cur.execute(f"""
                                SELECT id, content, published_at, updated_at
                                FROM {schema_name}.articles WHERE url = %s
                            """, (url,))
                            existing_by_url = feed_cur.fetchone()
                            if existing_by_url:
                                existing_id, existing_content, existing_pub, existing_updated = existing_by_url
                                new_content_hash = hashlib.md5((content or '').encode()).hexdigest()
                                existing_content_hash = hashlib.md5((existing_content or '').encode()).hexdigest() if existing_content else ''
                                existing_ts = _utc_aware(existing_updated or existing_pub)
                                content_changed = new_content_hash != existing_content_hash
                                feed_says_newer = feed_updated_dt and existing_ts and feed_updated_dt > existing_ts
                                should_update = content_changed or feed_says_newer or not (existing_content or '').strip()
                                if should_update:
                                    raw_bias = calculate_domain_bias_score(domain_key, title, content, feed_name)
                                    bias_score = (raw_bias + 1) / 2 if raw_bias is not None else 0.5
                                    bias_score = max(0.0, min(1.0, bias_score))
                                    quality_score = max(0.0, min(1.0, quality_score))
                                    feed_cur.execute(f"""
                                        UPDATE {schema_name}.articles SET
                                        title = %s, content = %s, summary = %s, published_at = %s,
                                        source_domain = %s, quality_score = %s, bias_score = %s, updated_at = NOW()
                                        WHERE id = %s
                                    """, (title, content, None, published_date, feed_name, quality_score, bias_score, existing_id))
                                    articles_updated += 1
                                    try:
                                        feed_cur.execute(f"""
                                            INSERT INTO {schema_name}.topic_extraction_queue
                                            (article_id, status, priority, created_at)
                                            VALUES (%s, 'pending', 2, NOW())
                                            ON CONFLICT (article_id) DO UPDATE SET status = 'pending', priority = 2, created_at = NOW()
                                        """, (existing_id,))
                                    except Exception:
                                        pass
                                    try:
                                        from services.context_processor_service import ensure_context_for_article
                                        ensure_context_for_article(domain_key, existing_id)
                                    except Exception:
                                        pass
                                else:
                                    duplicates_rejected += 1
                                continue
                            # Check for duplicate by title + source (different URL = different article, skip)
                            feed_cur.execute(f"""
                                SELECT id FROM {schema_name}.articles
                                WHERE title = %s AND source_domain = %s
                            """, (title, feed_name))
                            if feed_cur.fetchone():
                                duplicates_rejected += 1
                                continue
                            
                            # Calculate domain-specific bias score
                            raw_bias = calculate_domain_bias_score(domain_key, title, content, feed_name)
                            # chk_quality_scores requires bias_score in [0, 1]; raw bias is [-1, 1]
                            bias_score = (raw_bias + 1) / 2 if raw_bias is not None else 0.5
                            bias_score = max(0.0, min(1.0, bias_score))
                            quality_score = max(0.0, min(1.0, quality_score))

                            # Inline enrichment: if RSS content >= 500 chars treat as enriched; else try trafilatura once
                            insert_content = content or ""
                            enrichment_status = "enriched"
                            enrichment_attempts = 0
                            if len(insert_content) < 500 and url and url.strip():
                                try:
                                    from services.article_content_enrichment_service import enrich_article_content
                                    full_text, ok = enrich_article_content(url)
                                    if ok and full_text:
                                        insert_content = full_text
                                    else:
                                        enrichment_status = "failed"
                                        enrichment_attempts = 1
                                except Exception:
                                    enrichment_status = "failed"
                                    enrichment_attempts = 1

                            # Insert article (scores already calculated above)
                            feed_cur.execute("SAVEPOINT sp_article")
                            feed_cur.execute(f"""
                                INSERT INTO {schema_name}.articles
                                (title, url, content, summary, published_at, created_at, source_domain, quality_score, bias_score, enrichment_status, enrichment_attempts)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                            """, (title, url, insert_content, None, published_date, datetime.now(timezone.utc), feed_name, quality_score, bias_score, enrichment_status, enrichment_attempts))
                            
                            result = feed_cur.fetchone()
                            if result and feed_cur.rowcount > 0:
                                article_id = result[0]
                                articles_added += 1
                                
                                # Auto-queue article for LLM topic extraction
                                try:
                                    feed_cur.execute(f"""
                                        INSERT INTO {schema_name}.topic_extraction_queue
                                        (article_id, status, priority, created_at)
                                        VALUES (%s, 'pending', 2, NOW())
                                        ON CONFLICT (article_id) DO NOTHING
                                    """, (article_id,))
                                    feed_conn.commit()
                                except Exception as queue_error:
                                    logger.debug(f"Could not queue article {article_id} for topic extraction: {queue_error}")
                                    # Non-critical, continue processing
                                
                                # Context-centric: ensure intelligence.contexts + article_to_context (Phase 1.2)
                                try:
                                    from services.context_processor_service import ensure_context_for_article
                                    ensure_context_for_article(domain_key, article_id)
                                except Exception as ctx_err:
                                    logger.debug(f"Context processor skip: {ctx_err}")
                                
                        except Exception as e:
                            logger.warning(f"Error processing article from {feed_name}: {e}")
                            try:
                                feed_cur.execute("ROLLBACK TO SAVEPOINT sp_article")
                            except Exception:
                                try:
                                    feed_conn.rollback()
                                except Exception:
                                    pass
                                break
                            continue
                    
                    # Update feed timestamp
                    feed_cur.execute(f"""
                        UPDATE {schema_name}.rss_feeds 
                        SET last_fetched_at = NOW() 
                        WHERE id = %s
                    """, (feed_id,))
                    
                    feed_conn.commit()
                    
                    # Log detailed stats for this feed
                    filter_summary = []
                    if excluded_count > 0:
                        filter_summary.append(f"excluded: {excluded_count}")
                    if filtered_clickbait > 0:
                        filter_summary.append(f"clickbait: {filtered_clickbait}")
                    if filtered_ads > 0:
                        filter_summary.append(f"ads: {filtered_ads}")
                    if filtered_quality > 0:
                        filter_summary.append(f"low-quality: {filtered_quality}")
                    if filtered_impact > 0:
                        filter_summary.append(f"low-impact: {filtered_impact}")
                    if duplicates_rejected > 0:
                        filter_summary.append(f"duplicates: {duplicates_rejected}")
                    
                    filter_str = f" ({', '.join(filter_summary)})" if filter_summary else ""
                    logger.info(f"✅ {feed_name}: Added {articles_added} articles{filter_str}")
                    entries_count = min(50, len(feed.entries)) if feed.entries else 0
                    _rss_log("success", fetched=entries_count, saved=articles_added)
                    
                    # Note: Topic clustering will be handled by periodic background tasks
                    # Articles are now in database and will be picked up by scheduled clustering
                    if articles_added > 0:
                        logger.debug(f"📊 {articles_added} new articles added - will be processed by topic clustering scheduler")
                    
                    return {
                        'articles_added': articles_added,
                        'articles_updated': articles_updated,
                        'duplicates': duplicates_rejected,
                        'excluded': excluded_count,
                        'filtered_clickbait': filtered_clickbait,
                        'filtered_ads': filtered_ads,
                        'filtered_quality': filtered_quality,
                        'filtered_impact': filtered_impact,
                        'error': None
                    }
                    
                except TimeoutError:
                    logger.error(f"⏱️ Timeout processing feed: {feed_name}")
                    feed_conn.rollback()
                    _rss_log("error", err="Timeout")
                    return {'articles_added': 0, 'articles_updated': 0, 'duplicates': 0, 'excluded': 0, 'error': 'Timeout'}
                except Exception as e:
                    logger.error(f"❌ Error processing feed {feed_name}: {e}")
                    feed_conn.rollback()
                    _rss_log("error", err=str(e))
                    return {'articles_added': 0, 'articles_updated': 0, 'duplicates': 0, 'excluded': 0, 'error': str(e)}
                finally:
                    feed_cur.close()
                    
            finally:
                if feed_conn:
                    feed_conn.close()
        
        # Process feeds in parallel (max 5 concurrent to avoid overwhelming DB)
        logger.info(f"🚀 Processing {len(feeds)} feeds in parallel (max 5 concurrent)...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(process_single_feed, feeds))
        
        # Aggregate results from parallel processing
        for result in results:
            total_articles_added += result.get('articles_added', 0)
            total_articles_updated += result.get('articles_updated', 0)
            total_duplicates_rejected += result.get('duplicates', 0)
            total_excluded += result.get('excluded', 0)
            total_filtered_clickbait += result.get('filtered_clickbait', 0)
            total_filtered_ads += result.get('filtered_ads', 0)
            total_filtered_quality += result.get('filtered_quality', 0)
            total_filtered_impact += result.get('filtered_impact', 0)
        
        # Note: No need to commit here - each feed connection commits its own transaction
        
        # Log final results with detailed breakdown
        logger.info(f"📊 RSS collection completed:")
        logger.info(f"  ✅ Articles added: {total_articles_added}")
        if total_articles_updated > 0:
            logger.info(f"  🔄 Articles updated (same URL, new content): {total_articles_updated}")
        if total_duplicates_rejected > 0:
            logger.info(f"  🔄 Duplicates rejected: {total_duplicates_rejected}")
        if total_excluded > 0:
            logger.info(f"  🚫 Total articles filtered: {total_excluded}")
            if total_filtered_clickbait > 0:
                logger.info(f"     - Clickbait: {total_filtered_clickbait}")
            if total_filtered_ads > 0:
                logger.info(f"     - Advertisements: {total_filtered_ads}")
            if total_filtered_quality > 0:
                logger.info(f"     - Low quality score (<0.3): {total_filtered_quality}")
            if total_filtered_impact > 0:
                logger.info(f"     - Low impact score (<0.25): {total_filtered_impact}")
            # Content exclusion (sports/entertainment) is the remainder
            content_excluded = total_excluded - total_filtered_clickbait - total_filtered_ads - total_filtered_quality - total_filtered_impact
            if content_excluded > 0:
                logger.info(f"     - Content exclusion (sports/entertainment): {content_excluded}")
        
        return total_articles_added
        
    except Exception as e:
        logger.error(f"Error during RSS collection: {e}")
        conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()

def collect_rss_feed(feed_url: str, feed_name: str = "Unknown") -> int:
    """
    Collect articles from a specific RSS feed
    Args:
        feed_url: URL of the RSS feed
        feed_name: Name of the feed for logging
    Returns:
        Number of articles added
    """
    logger.info(f"Collecting from single feed: {feed_name}")
    
    conn = get_db_connection()
    if not conn:
        return 0
    
    try:
        cur = conn.cursor()
        
        # Parse RSS feed with thread-based timeout (works in background threads)
        def parse_feed():
            return feedparser.parse(feed_url)
        
        # Use ThreadPoolExecutor for timeout (works in any thread)
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(parse_feed)
            try:
                feed = future.result(timeout=30)  # 30 second timeout
            except FutureTimeoutError:
                raise TimeoutError("RSS parsing timeout")
        
        articles_added = 0
        
        for entry in feed.entries:
            try:
                cur.execute("SAVEPOINT sp_article")
                title = entry.get('title', '')[:500]
                url = entry.get('link', '')[:500]
                content = entry.get('summary', '') or entry.get('description', '')
                
                # Filter out sports, entertainment, and pop culture content
                if is_excluded_content(title, content, feed_name, feed_url):
                    logger.debug(f"Skipping excluded article: {title[:60]}...")
                    continue
                
                # Filter clickbait titles (but allow press releases/official filings)
                if is_clickbait_title(title):
                    logger.debug(f"Skipping clickbait article: {title[:60]}...")
                    continue
                
                # Filter advertisements (but allow press releases/official filings)
                if is_advertisement(title, content, url):
                    logger.debug(f"Skipping advertisement: {title[:60]}...")
                    continue
                
                impact_score = calculate_article_impact_score(title, content)
                quality_score = calculate_article_quality_score(title, content, feed_name)
                
                if quality_score < 0.3:
                    logger.debug(f"Skipping article (quality score {quality_score:.2f} < 0.3): {title[:60]}...")
                    continue
                
                if impact_score < 0.25:
                    logger.debug(f"Skipping article (impact score {impact_score:.2f} < 0.25): {title[:60]}...")
                    continue
                
                published_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_date = _utc_aware(datetime(*entry.published_parsed[:6]))
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published_date = _utc_aware(datetime(*entry.updated_parsed[:6]))
                else:
                    published_date = datetime.now(timezone.utc)
                
                # Determine domain for single feed collection (default to politics)
                # Note: For single feed, we need to determine domain from feed_name or query all schemas
                # For now, default to politics schema
                schema_name = 'politics'
                
                # Try to find feed in any domain schema to determine correct schema
                cur.execute("""
                    SELECT 'politics' as schema FROM politics.rss_feeds WHERE feed_url = %s
                    UNION ALL
                    SELECT 'finance' as schema FROM finance.rss_feeds WHERE feed_url = %s
                    UNION ALL
                    SELECT 'science_tech' as schema FROM science_tech.rss_feeds WHERE feed_url = %s
                    LIMIT 1
                """, (feed_url, feed_url, feed_url))
                result = cur.fetchone()
                if result:
                    schema_name = result[0]
                
                # Check for duplicates before inserting (in domain schema)
                cur.execute(f"""
                    SELECT id FROM {schema_name}.articles 
                    WHERE url = %s OR (title = %s AND source_domain = %s)
                """, (url, title, feed_name))
                
                if cur.fetchone():
                    # Article already exists, skip it
                    logger.debug(f"Skipping duplicate article: {title[:60]}...")
                    continue
                
                # Calculate domain-specific bias score
                # Determine domain from schema_name
                domain_key = schema_name.replace('_', '-') if schema_name in ['science_tech'] else schema_name
                raw_bias = calculate_domain_bias_score(domain_key, title, content, feed_name)
                # chk_quality_scores requires bias_score in [0, 1]; raw bias is [-1, 1] -> normalize
                bias_score = (raw_bias + 1) / 2 if raw_bias is not None else 0.5
                bias_score = max(0.0, min(1.0, bias_score))
                # Ensure quality_score stays in [0, 1] (impact_score already clamped)
                quality_score = max(0.0, min(1.0, quality_score))

                # Inline enrichment: if RSS content >= 500 chars treat as enriched; else try trafilatura once
                insert_content = content or ""
                enrichment_status = "enriched"
                enrichment_attempts = 0
                if len(insert_content) < 500 and url and url.strip():
                    try:
                        from services.article_content_enrichment_service import enrich_article_content
                        full_text, ok = enrich_article_content(url)
                        if ok and full_text:
                            insert_content = full_text
                        else:
                            enrichment_status = "failed"
                            enrichment_attempts = 1
                    except Exception:
                        enrichment_status = "failed"
                        enrichment_attempts = 1

                # Insert article into domain schema (v5.0) with quality score and bias score
                cur.execute(f"""
                    INSERT INTO {schema_name}.articles
                    (title, url, content, summary, published_at, created_at, source_domain, quality_score, bias_score, enrichment_status, enrichment_attempts)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    title, url, insert_content, None, published_date, datetime.now(timezone.utc), feed_name, quality_score, bias_score, enrichment_status, enrichment_attempts
                ))
                
                result = cur.fetchone()
                if result and cur.rowcount > 0:
                    article_id = result[0]
                    articles_added += 1
                    
                    # Auto-queue article for LLM topic extraction
                    try:
                        cur.execute(f"""
                            INSERT INTO {schema_name}.topic_extraction_queue
                            (article_id, status, priority, created_at)
                            VALUES (%s, 'pending', 2, NOW())
                            ON CONFLICT (article_id) DO NOTHING
                        """, (article_id,))
                        conn.commit()
                    except Exception as queue_error:
                        logger.debug(f"Could not queue article {article_id} for topic extraction: {queue_error}")
                        # Non-critical, continue processing
                    
                    # Context-centric: ensure intelligence.contexts + article_to_context (Phase 1.2)
                    try:
                        from services.context_processor_service import ensure_context_for_article
                        ensure_context_for_article(domain_key, article_id)
                    except Exception as ctx_err:
                        logger.debug(f"Context processor skip: {ctx_err}")
                    
            except Exception as e:
                logger.warning(f"Error processing article: {e}")
                try:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_article")
                except Exception:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    break
                continue
        
        conn.commit()
        logger.info(f"Added {articles_added} articles from {feed_name}")
        return articles_added
        
    except TimeoutError:
        logger.error(f"Timeout processing feed: {feed_name}")
        return 0
    except Exception as e:
        logger.error(f"Error processing feed {feed_name}: {e}")
        conn.rollback()
        return 0
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Test RSS collection
    print("Testing RSS collection...")
    result = collect_rss_feeds()
    print(f"Collection completed. Articles added: {result}")
