#!/usr/bin/env python3
"""
RSS Feed Collector for News Intelligence System v3.0.0
Collects articles from RSS feeds with advanced deduplication.
Excludes sports, entertainment, and pop culture content.
"""

import os
import sys
import logging
import threading
import feedparser
import psycopg2
import re
from datetime import datetime
from typing import Dict, List, Optional
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

# Import configuration from unified API config
try:
    from config.database import get_db_config  # use API's DB config
    DB_CONFIG = get_db_config()
    # Add timeouts/options
    DB_CONFIG.update({
        'connect_timeout': 10,
        'options': '-c statement_timeout=30000'
    })
except Exception as e:
    logger.error(f"Failed to load database config: {e}")
    # Fallback config - default to NAS, never localhost
    db_host = os.getenv('DB_HOST', '192.168.93.100')  # Default to NAS
    if db_host in ['localhost', '127.0.0.1'] and os.getenv('ALLOW_LOCAL_DB', 'false').lower() != 'true':
        logger.error("Local database is BLOCKED. System requires NAS database (192.168.93.100)")
        raise ValueError("Local database connection blocked - use NAS database")
    DB_CONFIG = {
        'host': db_host,
        'database': os.getenv('DB_NAME', 'news_intelligence'),
        'user': os.getenv('DB_USER', 'newsapp'),
        'password': os.getenv('DB_PASSWORD', 'newsapp_password'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'connect_timeout': 10,
        'options': '-c statement_timeout=30000'
    }

def get_db_connection():
    """Get database connection with timeout protection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

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
    
    # Low-impact indicators (decrease score)
    low_impact_keywords = [
        # Cooking & Recipes
        'recipe', 'recipes', 'cooking', 'cook', 'cooks', 'baking', 'bake', 'baked',
        'dish', 'dishes', 'ingredient', 'ingredients', 'cuisine', 'chef', 'chefs',
        'kitchen', 'meal', 'meals', 'dinner', 'lunch', 'breakfast', 'dessert',
        'appetizer', 'appetizers', 'entree', 'entrees', 'turkey recipe',
        'chicken recipe', 'beef recipe', 'pasta recipe', 'how to cook',
        'cooking tips', 'kitchen tips', 'meal prep', 'meal planning',
        'food blog', 'food blogger', 'cookbook', 'cooking show',
        
        # Home & Lifestyle
        'wrapping presents', 'gift wrapping', 'how to wrap', 'present wrapping',
        'home decor', 'home decoration', 'interior design', 'home improvement',
        'diy project', 'diy projects', 'craft', 'crafts', 'crafting',
        'organizing tips', 'cleaning tips', 'home organization', 'decluttering',
        'gardening tips', 'plant care', 'houseplants', 'indoor plants',
        'decorating', 'renovation', 'renovations', 'remodel', 'remodeling',
        
        # Lifestyle & Self-Help
        'lifestyle tips', 'life hacks', 'productivity tips', 'wellness tips',
        'self care', 'self-care', 'mindfulness tips', 'meditation guide',
        'fashion tips', 'style tips', 'wardrobe tips', 'outfit ideas',
        'beauty tips', 'skincare routine', 'makeup tutorial', 'hair tips',
        'travel tips', 'packing tips', 'vacation planning', 'holiday tips',
        'relationship advice', 'dating advice', 'parenting tips', 'mom tips',
        'dad tips', 'family tips', 'work-life balance',
        
        # Low-Value Content Patterns
        'top 10', 'top 5', 'top 20', 'best of', 'worst of', 'ranking', 'rankings',
        'listicle', 'listicles', 'buzzfeed', 'clickbait', 'viral', 'trending now',
        'you won\'t believe', 'shocking', 'amazing trick', 'secret tip',
        'hack that will', 'one weird trick', 'doctors hate', 'this one thing',
        'number one reason', 'simple trick', 'easy way', 'quick fix',
        
        # Holiday/Seasonal Fluff
        'holiday recipes', 'christmas recipes', 'thanksgiving recipes',
        'holiday decorating', 'christmas decorating', 'holiday shopping',
        'gift guide', 'gift ideas', 'holiday gift', 'stocking stuffers',
        'holiday party', 'christmas party', 'new year\'s resolution',
        'valentine\'s day', 'mother\'s day', 'father\'s day',
        
        # Personal Advice & Columns
        'dear abby', 'advice column', 'ask amy', 'relationship advice',
        'dating advice', 'parenting tips', 'mom tips', 'dad tips',
        'horoscope', 'horoscopes', 'astrology', 'zodiac',
        
        # Entertainment & Celebrity (non-news)
        'entertainment', 'celebrity', 'celebrities', 'gossip', 'rumor', 'rumors',
        'red carpet', 'awards show', 'movie premiere', 'tv premiere',
        'celebrity news', 'hollywood', 'paparazzi', 'tabloid', 'tabloids',
        
        # Opinion/Editorial (lower impact than news)
        'opinion piece', 'opinion', 'editorial', 'editorials', 'commentary',
        'op-ed', 'opinion column', 'my take', 'i think', 'in my opinion',
        
        # Sponsored/Advertising
        'sponsored', 'advertisement', 'advertisements', 'ad', 'ads', 'promotion',
        'promotional', 'sponsored content', 'paid partnership', 'affiliate',
        'buy now', 'shop now', 'limited time', 'special offer',
        
        # How-To Guides (non-news)
        'how to', 'how-to', 'tutorial', 'tutorials', 'guide', 'guides',
        'step by step', 'instructions', 'walkthrough', 'tips and tricks',
        
        # Personal Stories (non-news)
        'my story', 'personal story', 'what happened to me', 'my experience',
        'testimonial', 'testimonials', 'review', 'reviews', 'product review',
        
        # Low-Value Patterns
        'you should know', 'things you need', 'must have', 'essential',
        'game changer', 'life changing', 'revolutionary', 'miracle',
        'secret', 'secrets', 'hidden', 'unknown', 'nobody tells you'
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
    
    # Sports keywords (comprehensive list)
    sports_keywords = [
        # General sports terms
        'sport', 'sports', 'athlete', 'athletes', 'athletic', 'athletics',
        'game', 'games', 'match', 'matches', 'team', 'teams', 'player', 'players',
        'coach', 'coaches', 'league', 'leagues', 'championship', 'championships',
        'tournament', 'tournaments', 'playoff', 'playoffs', 'season', 'seasons',
        'score', 'scores', 'scoring', 'win', 'wins', 'won', 'lose', 'lost', 'loss',
        'victory', 'defeat', 'beat', 'beating', 'defeated',
        
        # Specific sports
        'football', 'soccer', 'basketball', 'baseball', 'hockey', 'tennis',
        'golf', 'cricket', 'rugby', 'volleyball', 'swimming', 'track', 'field',
        'boxing', 'mma', 'ufc', 'wrestling', 'cycling', 'racing', 'nascar',
        'formula', 'f1', 'motorsport', 'olympic', 'olympics', 'paralympic',
        'world cup', 'super bowl', 'stanley cup', 'world series', 'final four',
        'nba', 'nfl', 'mlb', 'nhl', 'fifa', 'uefa', 'ncaa',
        
        # Sports-related terms
        'stadium', 'arena', 'field', 'court', 'pitch', 'referee', 'umpire',
        'quarterback', 'pitcher', 'goalkeeper', 'goalie', 'draft', 'trades',
        'recruiting', 'signing', 'contract', 'extension', 'free agency',
        'fantasy football', 'fantasy baseball', 'fantasy basketball',
        'betting', 'odds', 'spread', 'over/under', 'pick em',
        
        # Common sports phrases
        'game-winning', 'game-winning', 'comeback', 'upset', 'blowout',
        'injury report', 'injury update', 'starting lineup', 'depth chart',
        'power rankings', 'mvp', 'all-star', 'hall of fame', 'rookie', 'veteran',
        'trade deadline', 'free agency', 'draft pick', 'prospect', 'recruit'
    ]
    
    # Entertainment keywords
    entertainment_keywords = [
        # General entertainment
        'entertainment', 'celebrity', 'celebrities', 'celebrity news',
        'hollywood', 'tinseltown', 'star', 'stars', 'superstar', 'superstars',
        'red carpet', 'awards show', 'award ceremony', 'oscars', 'grammys',
        'emmys', 'golden globe', 'golden globes', 'tony awards',
        
        # TV/Streaming
        'tv show', 'television show', 'reality tv', 'reality show', 'series finale',
        'season premiere', 'new episode', 'streaming', 'netflix', 'hulu', 'disney+',
        'hbo max', 'prime video', 'peacock', 'paramount+', 'apple tv+',
        'tv ratings', 'viewership', 'nielsen ratings',
        
        # Movies
        'movie', 'movies', 'film', 'films', 'cinema', 'box office', 'opening weekend',
        'sequel', 'prequel', 'remake', 'reboot', 'franchise', 'franchises',
        'oscar', 'oscars', 'academy award', 'best picture', 'best actor', 'best actress',
        'director', 'screenplay', 'cinematography', 'film festival', 'premiere',
        'trailer', 'teaser', 'behind the scenes', 'making of',
        
        # Music (pop culture)
        'music', 'song', 'songs', 'album', 'albums', 'single', 'singles',
        'artist', 'artists', 'singer', 'singers', 'rapper', 'rappers',
        'concert', 'concerts', 'tour', 'tours', 'tour dates', 'live show',
        'grammy', 'grammys', 'billboard', 'hot 100', 'top 40', 'chart',
        'music video', 'mv', 'viral song', 'trending song', 'spotify', 'apple music',
        'itunes', 'soundcloud', 'youtube music',
        
        # Celebrity gossip/personalities
        'gossip', 'rumor', 'rumors', 'scandal', 'scandals', 'affair', 'affairs',
        'dating', 'engaged', 'married', 'divorce', 'breakup', 'break up',
        'paparazzi', 'tabloid', 'tabloids', 'paparazzi photo', 'exclusive',
        'kardashian', 'jenner', 'real housewives', 'bachelor', 'bachelorette',
        'love island', 'too hot to handle', 'dating show',
        
        # Showbiz news
        'showbiz', 'show business', 'tinseltown', 'la la land',
        'casting news', 'audition', 'role', 'part', 'character', 'cast',
        'director', 'producer', 'screenwriter', 'showrunner',
    ]
    
    # Pop culture keywords
    pop_culture_keywords = [
        # Social media influencers
        'influencer', 'influencers', 'tiktok', 'tik tok', 'instagram model',
        'youtube star', 'youtuber', 'youtubers', 'streamer', 'streamers',
        'twitch', 'onlyfans', 'snapchat', 'tiktok star', 'viral video',
        'viral moment', 'trending', 'trending topic', 'meme', 'memes',
        
        # Video games (pop culture)
        'video game', 'video games', 'gaming', 'gamer', 'gamers', 'esports',
        'playstation', 'xbox', 'nintendo', 'switch', 'ps5', 'xbox series',
        'call of duty', 'fortnite', 'minecraft', 'among us', 'fall guys',
        'streaming', 'twitch stream', 'speedrun', 'achievement', 'trophy',
        
        # Comics/Anime/Manga (pop culture)
        'comic', 'comics', 'comic book', 'superhero', 'superheroes', 'supervillain',
        'mcu', 'marvel', 'dc comics', 'batman', 'superman', 'spider-man',
        'anime', 'manga', 'cosplay', 'convention', 'comic con',
        
        # Fandom/Geek culture
        'fandom', 'fan theory', 'fan theories', 'ship', 'shipping', 'fanfiction',
        'convention', 'con', 'expo', 'fandom drama', 'stan', 'stanning',
        'kpop', 'jpop', 'boy band', 'girl group', 'idol', 'idols',
        
        # Fashion/Beauty (pop culture)
        'fashion week', 'red carpet fashion', 'street style', 'trend',
        'vogue', 'cosmopolitan', 'elle', 'harper\'s bazaar', 'style',
        'makeup', 'beauty', 'skincare', 'beauty guru', 'mua',
        
        # Reality TV/Dating Shows
        'bachelor', 'bachelorette', 'love island', 'too hot to handle',
        'married at first sight', 'the challenge', 'survivor', 'amazing race',
        'real housewives', 'keeping up with', 'vanderpump rules',
        '90 day fiance', 'love after lockup', 'real world', 'road rules'
    ]
    
    # Lifestyle/Fluff keywords (recipes, home tips, low-value content)
    lifestyle_fluff_keywords = [
        # Cooking/Recipes
        'recipe', 'recipes', 'cooking', 'cook', 'chef', 'cuisine', 'dish', 'dishes',
        'ingredient', 'ingredients', 'baking', 'bake', 'baked', 'oven', 'stovetop',
        'turkey recipe', 'chicken recipe', 'beef recipe', 'pasta recipe', 'dessert recipe',
        'how to cook', 'cooking tips', 'kitchen tips', 'meal prep', 'meal planning',
        'food blog', 'food blogger', 'cookbook', 'cooking show',
        
        # Home/Lifestyle tips
        'wrapping presents', 'gift wrapping', 'how to wrap', 'present wrapping',
        'home decor', 'home decoration', 'interior design', 'home improvement',
        'diy project', 'diy projects', 'craft', 'crafts', 'crafting',
        'organizing tips', 'cleaning tips', 'home organization', 'decluttering',
        'gardening tips', 'plant care', 'houseplants', 'indoor plants',
        
        # Lifestyle fluff
        'lifestyle tips', 'life hacks', 'productivity tips', 'wellness tips',
        'self care', 'self-care', 'mindfulness tips', 'meditation guide',
        'fashion tips', 'style tips', 'wardrobe tips', 'outfit ideas',
        'beauty tips', 'skincare routine', 'makeup tutorial', 'hair tips',
        'travel tips', 'packing tips', 'vacation planning', 'holiday tips',
        
        # Low-value content patterns
        'top 10', 'top 5', 'best of', 'worst of', 'ranking', 'listicle',
        'buzzfeed', 'clickbait', 'viral', 'trending now', 'you won\'t believe',
        'shocking', 'amazing trick', 'secret tip', 'hack that will',
        
        # Holiday/Seasonal fluff (non-news)
        'holiday recipes', 'christmas recipes', 'thanksgiving recipes',
        'holiday decorating', 'christmas decorating', 'holiday shopping',
        'gift guide', 'gift ideas', 'holiday gift', 'stocking stuffers',
        
        # Personal advice columns
        'dear abby', 'advice column', 'ask amy', 'relationship advice',
        'dating advice', 'parenting tips', 'mom tips', 'dad tips'
    ]
    
    # Check for exclusion keywords
    all_exclusion_keywords = sports_keywords + entertainment_keywords + pop_culture_keywords + lifestyle_fluff_keywords
    
    for keyword in all_exclusion_keywords:
        # Use word boundaries to avoid partial matches
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, text_to_check):
            logger.debug(f"Article excluded (matched keyword '{keyword}'): {title[:60]}...")
            return True
    
    # Additional pattern matching for common phrases
    # Note: We avoid matching "vs" alone as it appears in political/news contexts too
    exclusion_patterns = [
        r'\b\d+\s*-\s*\d+\s*(final|score|points?|goals?)\b',  # "3-2 final" (sports score)
        r'\b(football|basketball|baseball|hockey|soccer|tennis|golf|cricket)\s+(game|match|season|league|team)\b',
        r'\b\w+\s+vs\.?\s+\w+\s+(game|match|final|semifinal|championship)\b',  # "Team vs Team game" (sports-specific)
        r'\b(oscar|grammy|emmy|tony|golden globe)\s+(nomination|winner|nominee|awards?)\b',
        r'\b(album|single|ep)\s+release\b',
        r'\b(tv|television)\s+(show|series|premiere|episode)\b',
        r'\bcelebrity\s+(news|gossip|rumor|scandal)\b',
        r'\b(pop|rock|hip hop|rap|country)\s+(music|song|album|single)\b',
        r'\b(video game|gaming|esports)\s+(news|update|release)\b',
        r'\b(box office|opening weekend|film festival)\b',
        # Lifestyle/Fluff patterns
        r'\b(recipe|recipes|cooking|how to cook|baking|dish|ingredient)\b',
        r'\b(wrapping presents|gift wrapping|how to wrap|present wrapping)\b',
        r'\b(home decor|home decoration|diy project|organizing tips|cleaning tips)\b',
        r'\b(lifestyle tips|life hacks|self care|wellness tips|mindfulness)\b',
        r'\b(top \d+|best of|worst of|listicle|ranking)\b',  # Listicles
        r'\b(holiday recipes|christmas recipes|thanksgiving recipes)\b',
        r'\b(gift guide|gift ideas|holiday gift|stocking stuffers)\b',
        r'\b(how to|how-to|tutorial|step by step|instructions)\b',  # How-to guides
        r'\b(you won\'t believe|shocking|amazing trick|secret tip|one weird trick)\b',  # Clickbait
        r'\b(sponsored|advertisement|ad|promotion|paid partnership)\b',  # Advertising
        r'\b(opinion piece|editorial|commentary|op-ed|my take)\b',  # Opinion (lower impact)
        r'\b(dear abby|advice column|relationship advice|dating advice)\b',  # Advice columns
        r'\b(product review|my story|personal story|testimonial)\b'  # Personal/reviews
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
    logger.info("Starting RSS feed collection with deduplication (v4.0 domain-aware)...")
    
    # Initialize deduplication manager if available
    dedup_manager = None
    if DEDUPLICATION_AVAILABLE:
        try:
            dedup_manager = DeduplicationManager(DB_CONFIG)
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
        
        # Get all active RSS feeds from all domain schemas (v4.0)
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
                return {'articles_added': 0, 'duplicates': 0, 'excluded': 0, 'error': 'No DB connection'}
            
            try:
                feed_cur = feed_conn.cursor()
                articles_added = 0
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
                            title = entry.get('title', '')[:500]
                            url = entry.get('link', '')[:500]
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
                            
                            # Filter by minimum quality score (>= 0.4)
                            if quality_score < 0.4:
                                filtered_quality += 1
                                excluded_count += 1
                                logger.debug(f"Article excluded (quality score {quality_score:.2f} < 0.4): {title[:60]}...")
                                continue
                            
                            # Filter by minimum impact score (>= 0.4)
                            if impact_score < 0.4:
                                filtered_impact += 1
                                excluded_count += 1
                                logger.debug(f"Article excluded (impact score {impact_score:.2f} < 0.4): {title[:60]}...")
                                continue
                            
                            # Parse published date
                            published_date = None
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                published_date = datetime(*entry.published_parsed[:6])
                            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                                published_date = datetime(*entry.updated_parsed[:6])
                            else:
                                published_date = datetime.now()
                            
                            # Check for duplicates
                            feed_cur.execute(f"""
                                SELECT id FROM {schema_name}.articles 
                                WHERE url = %s OR (title = %s AND source_domain = %s)
                            """, (url, title, feed_name))
                            
                            if feed_cur.fetchone():
                                duplicates_rejected += 1
                                continue
                            
                            # Calculate domain-specific bias score
                            raw_bias = calculate_domain_bias_score(domain_key, title, content, feed_name)
                            # chk_quality_scores requires bias_score in [0, 1]; raw bias is [-1, 1]
                            bias_score = (raw_bias + 1) / 2 if raw_bias is not None else 0.5
                            bias_score = max(0.0, min(1.0, bias_score))
                            quality_score = max(0.0, min(1.0, quality_score))

                            # Insert article (scores already calculated above)
                            feed_cur.execute("SAVEPOINT sp_article")
                            feed_cur.execute(f"""
                                INSERT INTO {schema_name}.articles
                                (title, url, content, summary, published_at, created_at, source_domain, quality_score, bias_score)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                                RETURNING id
                            """, (title, url, content, None, published_date, datetime.now(), feed_name, quality_score, bias_score))
                            
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
                                
                        except Exception as e:
                            logger.warning(f"Error processing article from {feed_name}: {e}")
                            try:
                                feed_cur.execute("ROLLBACK TO SAVEPOINT sp_article")
                            except:
                                pass
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
                    return {'articles_added': 0, 'duplicates': 0, 'excluded': 0, 'error': 'Timeout'}
                except Exception as e:
                    logger.error(f"❌ Error processing feed {feed_name}: {e}")
                    feed_conn.rollback()
                    _rss_log("error", err=str(e))
                    return {'articles_added': 0, 'duplicates': 0, 'excluded': 0, 'error': str(e)}
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
        if total_duplicates_rejected > 0:
            logger.info(f"  🔄 Duplicates rejected: {total_duplicates_rejected}")
        if total_excluded > 0:
            logger.info(f"  🚫 Total articles filtered: {total_excluded}")
            if total_filtered_clickbait > 0:
                logger.info(f"     - Clickbait: {total_filtered_clickbait}")
            if total_filtered_ads > 0:
                logger.info(f"     - Advertisements: {total_filtered_ads}")
            if total_filtered_quality > 0:
                logger.info(f"     - Low quality score (<0.4): {total_filtered_quality}")
            if total_filtered_impact > 0:
                logger.info(f"     - Low impact score (<0.4): {total_filtered_impact}")
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
                
                # Calculate scores for threshold filtering
                impact_score = calculate_article_impact_score(title, content)
                quality_score = calculate_article_quality_score(title, content, feed_name)
                
                # Filter by minimum quality score (>= 0.4)
                if quality_score < 0.4:
                    logger.debug(f"Skipping article (quality score {quality_score:.2f} < 0.4): {title[:60]}...")
                    continue
                
                # Filter by minimum impact score (>= 0.4)
                if impact_score < 0.4:
                    logger.debug(f"Skipping article (impact score {impact_score:.2f} < 0.4): {title[:60]}...")
                    continue
                
                published_date = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published_date = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published_date = datetime(*entry.updated_parsed[:6])
                else:
                    published_date = datetime.now()
                
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

                # Insert article into domain schema (v4.0) with quality score and bias score
                cur.execute(f"""
                    INSERT INTO {schema_name}.articles
                    (title, url, content, summary, published_at, created_at, source_domain, quality_score, bias_score)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    title, url, content, None, published_date, datetime.now(), feed_name, quality_score, bias_score
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
                    
            except Exception as e:
                logger.warning(f"Error processing article: {e}")
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
