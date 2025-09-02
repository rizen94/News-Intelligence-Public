#!/usr/bin/env python3
"""
News Intelligence System Web Application v2.7.0
Professional website with both static pages and API endpoints
Enhanced with comprehensive security features
"""

from flask import Flask, jsonify, request, send_from_directory, render_template_string, redirect, url_for
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

def get_rate_limit_key():
    """Custom rate limit key function that treats localhost more leniently"""
    client_ip = get_remote_address()
    # If it's localhost or internal Docker network, use a more lenient key
    if client_ip in ['127.0.0.1', '::1', '172.20.0.1']:
        return 'localhost'
    return client_ip
import os
import sys
import json
import hashlib
import time
from datetime import datetime, timedelta
import logging
import re
from urllib.parse import urlparse
import psycopg2
import psutil
import threading

# Add the modules directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import monitoring module
try:
    from modules.monitoring import resource_logger
    MONITORING_AVAILABLE = True
except ImportError:
    MONITORING_AVAILABLE = False
    logger.warning("Monitoring module not available - resource logging disabled")

try:
    from modules.ml import MLSummarizationService, ContentAnalyzer, QualityScorer
    from modules.ml.ml_pipeline import MLPipeline
    from modules.ml.storyline_tracker import StorylineTracker
    from modules.ml.deduplication_service import ContentDeduplicationService
    from modules.ml.daily_briefing_service import DailyBriefingService
    from modules.ml.background_processor import BackgroundMLProcessor
    from modules.ml.rag_enhanced_service import RAGEnhancedService
    from modules.ml.iterative_rag_service import IterativeRAGService
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML module not available - ML features disabled")

try:
    from modules.data_collection import RSSFeedService, FeedScheduler
    from modules.data_collection.progress_tracker import progress_tracker
    DATA_COLLECTION_AVAILABLE = True
except ImportError:
    DATA_COLLECTION_AVAILABLE = False
    logger.warning("Data collection module not available - RSS features disabled")

# Define the React build directory path - adjust for Docker container
REACT_BUILD_DIR = os.path.join(os.path.dirname(__file__), '..', 'web', 'build')
if not os.path.exists(REACT_BUILD_DIR):
    # Fallback for Docker container path
    REACT_BUILD_DIR = os.path.join(os.path.dirname(__file__), 'web', 'build')
if not os.path.exists(REACT_BUILD_DIR):
    # Second fallback for Docker container path
    REACT_BUILD_DIR = os.path.join(os.path.dirname(__file__), '..', 'build')
if not os.path.exists(REACT_BUILD_DIR):
    # Third fallback for Docker container path
    REACT_BUILD_DIR = '/app/build'

# Import database configuration
try:
    from config.database import get_db_config, test_database_connection
except ImportError:
    # Fallback for minimal setup
    def get_db_config():
        return {
            'host': os.environ.get('DB_HOST', 'postgres'),
            'database': os.environ.get('DB_NAME', 'news_system'),
            'user': os.environ.get('DB_USER', 'newsapp'),
            'password': os.environ.get('DB_PASSWORD', ''),
            'port': os.environ.get('DB_PORT', '5432')
        }
    
    def test_database_connection():
        return True

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Log the React build directory path for debugging
logger.info(f"React build directory: {REACT_BUILD_DIR}")
logger.info(f"Build directory exists: {os.path.exists(REACT_BUILD_DIR)}")
if os.path.exists(REACT_BUILD_DIR):
    logger.info(f"Build directory contents: {os.listdir(REACT_BUILD_DIR)}")
else:
    logger.warning(f"React build directory not found at: {REACT_BUILD_DIR}")

# Add missing database connection function
def get_db_connection():
    """Get database connection using environment variables"""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get('DB_HOST', 'postgres'),
            database=os.environ.get('DB_NAME', 'news_system'),
            user=os.environ.get('DB_USER', 'newsapp'),
            password=os.environ.get('DB_PASSWORD', ''),
            port=os.environ.get('DB_PORT', '5432')
        )
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

# Define DB_CONFIG for the prioritization API endpoints
# Import configuration
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
try:
    from database import get_database_config
    DB_CONFIG = get_database_config()
except ImportError:
    # Fallback configuration if config module not available
    DB_CONFIG = {
        'host': os.getenv('DB_HOST', 'postgres'),
        'database': os.getenv('DB_NAME', 'news_system'),
        'user': os.getenv('DB_USER', 'newsapp'),
        'password': os.getenv('DB_PASSWORD', ''),
        'connect_timeout': 10,
        'options': '-c statement_timeout=30000'
    }

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0  # Disable default caching

# Web API endpoints are already implemented in this file
# No additional blueprint registration needed

# Initialize background ML processor, RAG service, and RSS feed scheduler
background_ml_processor = None
rag_enhanced_service = None
feed_scheduler = None

# Define database configuration (needed for all services)
db_config = {
    'host': os.environ.get('POSTGRES_HOST', 'news-system-postgres-local'),
    'port': os.environ.get('POSTGRES_PORT', '5432'),
    'database': os.environ.get('POSTGRES_DB', 'news_system'),
    'user': os.environ.get('POSTGRES_USER', 'NewsInt_DB'),
    'password': os.environ.get('POSTGRES_PASSWORD', 'Database@NEWSINT2025')
}

if ML_AVAILABLE:
    try:
        
        # Initialize background ML processor
        background_ml_processor = BackgroundMLProcessor(db_config)
        background_ml_processor.start_workers()
        logger.info("Background ML processor started")
        
        # Initialize RAG Enhanced Service
        ml_service = MLSummarizationService()
        rag_enhanced_service = RAGEnhancedService(db_config, ml_service)
        logger.info("RAG Enhanced Service initialized")
        
    except Exception as e:
        logger.error(f"Failed to start ML services: {e}")
        background_ml_processor = None
        rag_enhanced_service = None

# Initialize RSS feed scheduler
if DATA_COLLECTION_AVAILABLE:
    try:
        
        # Initialize RSS feed scheduler
        feed_scheduler = FeedScheduler(db_config)
        feed_scheduler.start(collection_interval_minutes=30)  # Collect every 30 minutes
        logger.info("RSS feed scheduler started")
        
    except Exception as e:
        logger.error(f"Failed to start RSS feed scheduler: {e}")
        feed_scheduler = None

# Initialize metrics
app_metrics = {
    'requests_total': 0,
    'requests_duration_seconds': 0,
    'articles_processed': 0,
    'ml_inferences': 0,
    'database_queries': 0,
    'errors_total': 0,
    'start_time': time.time()
}

# Metrics collection thread
def collect_system_metrics():
    """Collect system metrics every 30 seconds"""
    while True:
        try:
            # System metrics
            app_metrics['cpu_percent'] = psutil.cpu_percent(interval=1)
            app_metrics['memory_percent'] = psutil.virtual_memory().percent
            app_metrics['disk_percent'] = psutil.disk_usage('/').percent
            
            # GPU metrics (if available)
            try:
                import subprocess
                result = subprocess.run(['nvidia-smi', '--query-gpu=memory.used,memory.total,utilization.gpu', '--format=csv,noheader,nounits'], 
                                     capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    gpu_info = result.stdout.strip().split(',')
                    if len(gpu_info) >= 3:
                        app_metrics['gpu_memory_used_mb'] = int(gpu_info[0])
                        app_metrics['gpu_memory_total_mb'] = int(gpu_info[1])
                        app_metrics['gpu_utilization_percent'] = int(gpu_info[2])
            except:
                pass
                
            time.sleep(30)
        except Exception as e:
            logger.error(f"Error collecting metrics: {e}")
            time.sleep(30)

# Start metrics collection in background
metrics_thread = threading.Thread(target=collect_system_metrics, daemon=True)
metrics_thread.start()

# Start resource logging if available
if MONITORING_AVAILABLE:
    try:
        resource_logger.start_logging()
        logger.info("Resource logging started successfully")
    except Exception as e:
        logger.error(f"Failed to start resource logging: {e}")
else:
    logger.info("Resource logging not available - skipping")

# Configure static file serving with explicit route - using a different path to avoid conflicts
@app.route('/assets/<path:filename>')
def serve_static(filename):
    """Serve static files from React build directory"""
    logger.info(f"Static route hit for: {filename}")
    
    # Dynamically determine the build directory at runtime
    build_dirs = [
        os.path.join(os.path.dirname(__file__), '..', 'web', 'build'),
        os.path.join(os.path.dirname(__file__), 'web', 'build'),
        os.path.join(os.path.dirname(__file__), '..', 'build'),
        '/app/web/build',  # Direct Docker path
        '/app/build'        # Alternative Docker path
    ]
    
    for build_dir in build_dirs:
        if os.path.exists(build_dir):
            try:
                # Handle nested paths like 'static/js/main.js' or 'static/css/main.css'
                if filename.startswith('static/'):
                    # Remove the 'static/' prefix since we're already in the build directory
                    relative_path = filename[7:]  # Remove 'static/' prefix
                    file_path = os.path.join(build_dir, 'static', relative_path)
                    logger.info(f"Serving from build dir: {build_dir}, relative path: {relative_path}, file_path: {file_path}")
                    if os.path.exists(file_path):
                        logger.info(f"File exists, serving from: {os.path.join(build_dir, 'static')}")
                        response = send_from_directory(os.path.join(build_dir, 'static'), relative_path)
                        # Add cache control headers for static assets
                        if relative_path.endswith('.js') or relative_path.endswith('.css'):
                            response.headers['Cache-Control'] = 'public, max-age=3600'  # 1 hour
                        else:
                            response.headers['Cache-Control'] = 'public, max-age=86400'  # 1 day
                        return response
                elif '/' in filename:
                    # Handle other nested paths
                    subdir, subfilename = filename.split('/', 1)
                    static_dir = os.path.join(build_dir, 'static', subdir)
                    logger.info(f"Serving from subdir: {static_dir}, file: {subfilename}")
                    if os.path.exists(os.path.join(static_dir, subfilename)):
                        response = send_from_directory(static_dir, subfilename)
                        # Add cache control headers for static assets
                        if subfilename.endswith('.js') or subfilename.endswith('.css'):
                            response.headers['Cache-Control'] = 'public, max-age=3600'  # 1 hour
                        else:
                            response.headers['Cache-Control'] = 'public, max-age=86400'  # 1 day
                        return response
                else:
                    # Direct file in static directory
                    static_dir = os.path.join(build_dir, 'static')
                    logger.info(f"Serving from static dir: {static_dir}, file: {filename}")
                    if os.path.exists(os.path.join(static_dir, filename)):
                        response = send_from_directory(static_dir, filename)
                        # Add cache control headers for static assets
                        if filename.endswith('.js') or filename.endswith('.css'):
                            response.headers['Cache-Control'] = 'public, max-age=3600'  # 1 hour
                        else:
                            response.headers['Cache-Control'] = 'public, max-age=86400'  # 1 day
                        return response
            except Exception as e:
                logger.error(f"Error serving static file {filename} from {build_dir}: {e}")
                continue
    
    logger.error(f"Static file {filename} not found in any build directory")
    return jsonify({'error': 'Static file not found'}), 404

# Security Configuration
app.config['SECURE_HEADERS'] = {
    'X-Frame-Options': 'DENY',
    'X-Content-Type-Options': 'nosniff',
    'X-XSS-Protection': '1; mode=block',
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=()',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
}

# Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_rate_limit_key,
    default_limits=["1000 per day", "500 per hour"],
    storage_uri="memory://"
)

# CORS with security restrictions - now allowing localhost:8000 since we're serving both frontend and backend
CORS(app, 
     origins=os.environ.get('ALLOWED_ORIGINS', 'http://localhost:8000').split(','),
     methods=['GET', 'POST', 'PUT', 'DELETE'],
     allow_headers=['Content-Type', 'Authorization'],
     expose_headers=['X-Total-Count', 'X-Rate-Limit-Reset'])

# Security monitoring
SECURITY_EVENTS = []
MAX_SECURITY_EVENTS = 1000

def log_security_event(event_type, details, ip_address=None, user_agent=None):
    """Log security events for monitoring and alerting"""
    event = {
        'timestamp': datetime.now().isoformat(),
        'type': event_type,
        'details': details,
        'ip_address': ip_address or get_remote_address(),
        'user_agent': user_agent or request.headers.get('User-Agent', 'Unknown'),
        'endpoint': request.endpoint,
        'method': request.method
    }
    
    SECURITY_EVENTS.append(event)
    
    # Keep only the last MAX_SECURITY_EVENTS
    if len(SECURITY_EVENTS) > MAX_SECURITY_EVENTS:
        SECURITY_EVENTS.pop(0)
    
    # Log to console for development
    logger.warning(f"SECURITY EVENT: {event_type} - {details}")
    
    return event

def validate_input(data, max_length=10000):
    """Validate and sanitize input data"""
    if isinstance(data, str):
        # Check for potential XSS patterns
        xss_patterns = [
            r'<script[^>]*>.*?</script>',
            r'javascript:',
            r'on\w+\s*=',
            r'<iframe[^>]*>',
            r'<object[^>]*>',
            r'<embed[^>]*>'
        ]
        
        for pattern in xss_patterns:
            if re.search(pattern, data, re.IGNORECASE):
                log_security_event('XSS_ATTEMPT', f'Pattern detected: {pattern}', 
                                 get_remote_address(), request.headers.get('User-Agent'))
                return False
        
        # Check length
        if len(data) > max_length:
            log_security_event('INPUT_TOO_LONG', f'Length: {len(data)}, Max: {max_length}',
                             get_remote_address(), request.headers.get('User-Agent'))
            return False
    
    return True

def validate_url(url):
    """Validate URL format and security"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            return False
        
        # Block potentially dangerous domains
        dangerous_domains = ['localhost', '127.0.0.1', '0.0.0.0', '::1']
        if parsed.hostname in dangerous_domains:
            return False
            
        return True
    except:
        return False

# Security middleware
@app.before_request
def security_middleware():
    """Apply security checks before each request"""
    # Log suspicious requests
    user_agent = request.headers.get('User-Agent', '')
    if not user_agent or user_agent.lower() in ['', 'python', 'curl', 'wget']:
        log_security_event('SUSPICIOUS_USER_AGENT', f'User-Agent: {user_agent}')
    
    # Check for suspicious headers
    suspicious_headers = ['X-Forwarded-For', 'X-Real-IP', 'X-Client-IP']
    for header in suspicious_headers:
        if header in request.headers:
            log_security_event('SUSPICIOUS_HEADER', f'Header: {header}')
    
    # Validate request size
    if request.content_length and request.content_length > 10 * 1024 * 1024:  # 10MB
        log_security_event('REQUEST_TOO_LARGE', f'Size: {request.content_length}')
        return jsonify({'error': 'Request too large'}), 413

@app.after_request
def security_headers(response):
    """Add security headers to all responses"""
    # Content Security Policy
    csp_policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self' http://localhost:8000; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )
    
    response.headers['Content-Security-Policy'] = csp_policy
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    
    # Set cache control headers based on request path
    if request.path.startswith('/assets/static/'):
        # Static assets - cache for 1 hour
        if request.path.endswith(('.js', '.css')):
            response.headers['Cache-Control'] = 'public, max-age=3600'
        else:
            response.headers['Cache-Control'] = 'public, max-age=86400'
    elif request.path == '/' or not request.path.startswith('/api/'):
        # Main HTML file and React routes - no cache
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    # HSTS header for HTTPS
    if request.is_secure:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    return response

# Error handlers with security logging
@app.errorhandler(400)
def bad_request(error):
    log_security_event('BAD_REQUEST', f'400 error: {error.description}')
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(404)
def not_found(error):
    log_security_event('NOT_FOUND', f'404 error for: {request.url}')
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(413)
def too_large(error):
    log_security_event('REQUEST_TOO_LARGE', f'413 error: {error.description}')
    return jsonify({'error': 'Request too large'}), 413

@app.errorhandler(429)
def too_many_requests(error):
    log_security_event('RATE_LIMIT_EXCEEDED', f'429 error from IP: {get_remote_address()}')
    return jsonify({'error': 'Too many requests'}), 429

@app.errorhandler(500)
def internal_error(error):
    log_security_event('INTERNAL_ERROR', f'500 error: {error.description}')
    return jsonify({'error': 'Internal server error'}), 500

# Mock data for development
MOCK_DATA = {
    'system_status': {
        'isOnline': True,
        'lastUpdate': datetime.now().isoformat(),
        'version': 'v2.8.0',
        'status': 'healthy',
        'uptime': '0h 5m',  # Will be calculated dynamically
        'memoryUsage': '45%',
        'cpuUsage': '12%',
        'diskUsage': '23%',
        'securityStatus': 'secure',
        'lastSecurityScan': datetime.now().isoformat(),
        'threatsBlocked': 0,
        'vulnerabilities': 0,
    },
    'dashboard': {
        'articleCount': 1247,
        'clusterCount': 89,
        'entityCount': 2341,
        'sourceCount': 12,
        'recentArticles': [
            {
                'id': 1,
                'title': 'Breaking: Major Tech Merger Announced',
                'source': 'Tech News Daily',
                'publishedDate': (datetime.now() - timedelta(hours=2)).isoformat(),
                'category': 'Technology',
                'summary': 'Two major technology companies have announced a historic merger...',
            },
            {
                'id': 2,
                'title': 'Global Climate Summit Reaches Historic Agreement',
                'source': 'World News',
                'publishedDate': (datetime.now() - timedelta(hours=4)).isoformat(),
                'category': 'Environment',
                'summary': 'World leaders have reached a landmark agreement on climate change...',
            },
        ],
        'topSources': [
            {'name': 'BBC News', 'articleCount': 156, 'health': 'excellent'},
            {'name': 'Reuters', 'articleCount': 134, 'health': 'excellent'},
            {'name': 'Associated Press', 'articleCount': 98, 'health': 'good'},
        ],
        'topEntities': [
            {'name': 'United States', 'type': 'GPE', 'frequency': 234, 'category': 'Politics'},
            {'name': 'China', 'type': 'GPE', 'frequency': 189, 'category': 'Economy'},
            {'name': 'Elon Musk', 'type': 'PERSON', 'frequency': 156, 'category': 'Technology'},
        ],
        'feedHealth': [
            {
                'source': 'BBC News',
                'status': 'healthy',
                'lastFetch': (datetime.now() - timedelta(minutes=30)).isoformat(),
                'successRate': 99.8
            },
            {
                'source': 'Reuters',
                'status': 'healthy',
                'lastFetch': (datetime.now() - timedelta(minutes=45)).isoformat(),
                'successRate': 99.5
            },
        ],
    },
    'articles': [
        {
            'id': 1,
            'title': 'Breaking: Major Tech Merger Announced',
            'content': 'Two major technology companies have announced a historic merger that will reshape the industry landscape...',
            'url': 'https://example.com/tech-merger',
            'source': 'Tech News Daily',
            'publishedDate': (datetime.now() - timedelta(hours=2)).isoformat(),
            'category': 'Technology',
            'language': 'en',
            'qualityScore': 0.89,
            'entities': [
                {'text': 'TechCorp', 'type': 'ORG', 'confidence': 0.95},
                {'text': 'InnovateTech', 'type': 'ORG', 'confidence': 0.93},
                {'text': 'John Smith', 'type': 'PERSON', 'confidence': 0.87},
            ],
            'clusterId': 1,
            'processingStatus': 'processed',
        },
        {
            'id': 2,
            'title': 'Global Climate Summit Reaches Historic Agreement',
            'content': 'World leaders have reached a landmark agreement on climate change during the recent summit...',
            'url': 'https://example.com/climate-summit',
            'source': 'World News',
            'publishedDate': (datetime.now() - timedelta(hours=4)).isoformat(),
            'category': 'Environment',
            'language': 'en',
            'qualityScore': 0.92,
            'entities': [
                {'text': 'United Nations', 'type': 'ORG', 'confidence': 0.98},
                {'text': 'Paris', 'type': 'GPE', 'confidence': 0.96},
                {'text': 'Climate Action', 'type': 'ORG', 'confidence': 0.89},
            ],
            'clusterId': 2,
            'processingStatus': 'processed',
        },
    ],
    'clusters': [
        {
            'id': 1,
            'name': 'Tech Industry Mergers',
            'topic': 'Technology',
            'articleCount': 23,
            'dateRange': {
                'start': (datetime.now() - timedelta(days=7)).isoformat(),
                'end': datetime.now().isoformat(),
            },
            'entities': [
                {'text': 'TechCorp', 'type': 'ORG', 'frequency': 15},
                {'text': 'InnovateTech', 'type': 'ORG', 'frequency': 12},
                {'text': 'Merger', 'type': 'CONCEPT', 'frequency': 23},
            ],
            'keywords': ['merger', 'acquisition', 'technology', 'industry', 'consolidation'],
            'cohesionScore': 0.87,
            'status': 'active',
        },
        {
            'id': 2,
            'name': 'Climate Change Summit',
            'topic': 'Environment',
            'articleCount': 18,
            'dateRange': {
                'start': (datetime.now() - timedelta(days=14)).isoformat(),
                'end': datetime.now().isoformat(),
            },
            'entities': [
                {'text': 'United Nations', 'type': 'ORG', 'frequency': 18},
                {'text': 'Paris', 'type': 'GPE', 'frequency': 12},
                {'text': 'Climate Action', 'type': 'ORG', 'frequency': 8},
            ],
            'keywords': ['climate', 'summit', 'agreement', 'global', 'environment'],
            'cohesionScore': 0.92,
            'status': 'active',
        },
    ],
    'sources': [
        {
            'id': 1,
            'name': 'BBC News',
            'url': 'https://feeds.bbci.co.uk/news/rss.xml',
            'category': 'General News',
            'isActive': True,
            'lastFetched': (datetime.now() - timedelta(minutes=30)).isoformat(),
            'status': 'active',
            'health': 'excellent',
            'articleCount': 156,
            'successRate': 99.8,
            'avgResponseTime': 1200,
            'errorCount': 2,
        },
        {
            'id': 2,
            'name': 'Reuters',
            'url': 'https://feeds.reuters.com/reuters/topNews',
            'category': 'General News',
            'isActive': True,
            'lastFetched': (datetime.now() - timedelta(minutes=45)).isoformat(),
            'status': 'active',
            'health': 'excellent',
            'articleCount': 134,
            'successRate': 99.5,
            'avgResponseTime': 980,
            'errorCount': 3,
        },
    ],
}

# HTML Templates for the professional website
LANDING_PAGE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>News Intelligence System v2.7.0 - Professional News Analysis Platform</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            line-height: 1.6;
            color: #333;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }
        
        /* Header */
        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 1rem 0;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: 0 2px 20px rgba(0,0,0,0.1);
        }
        
        .nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 1.8rem;
            font-weight: 700;
            color: #667eea;
            text-decoration: none;
        }
        
        .nav-links {
            display: flex;
            gap: 2rem;
            list-style: none;
        }
        
        .nav-links a {
            text-decoration: none;
            color: #333;
            font-weight: 500;
            transition: color 0.3s ease;
        }
        
        .nav-links a:hover {
            color: #667eea;
        }
        
        /* Hero Section */
        .hero {
            text-align: center;
            padding: 4rem 0;
            color: white;
        }
        
        .hero h1 {
            font-size: 3.5rem;
            font-weight: 700;
            margin-bottom: 1rem;
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        
        .hero p {
            font-size: 1.3rem;
            margin-bottom: 2rem;
            opacity: 0.9;
        }
        
        .cta-button {
            display: inline-block;
            background: #fff;
            color: #667eea;
            padding: 1rem 2rem;
            border-radius: 50px;
            text-decoration: none;
            font-weight: 600;
            font-size: 1.1rem;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .cta-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        /* Features Section */
        .features {
            background: white;
            padding: 4rem 0;
        }
        
        .features h2 {
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 3rem;
            color: #333;
        }
        
        .features-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 2rem;
        }
        
        .feature-card {
            background: #f8f9fa;
            padding: 2rem;
            border-radius: 15px;
            text-align: center;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        
        .feature-icon {
            font-size: 3rem;
            color: #667eea;
            margin-bottom: 1rem;
        }
        
        .feature-card h3 {
            font-size: 1.5rem;
            margin-bottom: 1rem;
            color: #333;
        }
        
        .feature-card p {
            color: #666;
            line-height: 1.6;
        }
        
        /* Stats Section */
        .stats {
            background: #667eea;
            color: white;
            padding: 4rem 0;
        }
        
        .stats h2 {
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 3rem;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 2rem;
            text-align: center;
        }
        
        .stat-item h3 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }
        
        .stat-item p {
            opacity: 0.9;
        }
        
        /* Dashboard Section */
        .dashboard {
            background: white;
            padding: 4rem 0;
        }
        
        .dashboard h2 {
            text-align: center;
            font-size: 2.5rem;
            margin-bottom: 3rem;
            color: #333;
        }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 2rem;
        }
        
        .dashboard-card {
            background: #f8f9fa;
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .dashboard-card h3 {
            font-size: 1.5rem;
            margin-bottom: 1rem;
            color: #333;
        }
        
        .article-list {
            list-style: none;
        }
        
        .article-item {
            padding: 1rem 0;
            border-bottom: 1px solid #eee;
        }
        
        .article-item:last-child {
            border-bottom: none;
        }
        
        .article-title {
            font-weight: 600;
            color: #333;
            margin-bottom: 0.5rem;
        }
        
        .article-meta {
            font-size: 0.9rem;
            color: #666;
        }
        
        /* Footer */
        .footer {
            background: #333;
            color: white;
            text-align: center;
            padding: 2rem 0;
        }
        
        .footer p {
            opacity: 0.8;
        }
        
        /* Responsive */
        @media (max-width: 768px) {
            .hero h1 {
                font-size: 2.5rem;
            }
            
            .nav-links {
                display: none;
            }
            
            .features-grid {
                grid-template-columns: 1fr;
            }
            
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <nav class="nav container">
            <a href="/" class="logo">
                <i class="fas fa-newspaper"></i> News Intelligence
            </a>
            <ul class="nav-links">
                <li><a href="/dashboard">Dashboard</a></li>
                <li><a href="/articles">Articles</a></li>
                <li><a href="/clusters">Clusters</a></li>
                <li><a href="/entities">Entities</a></li>
                <li><a href="/sources">Sources</a></li>
                <li><a href="/monitoring">Monitoring</a></li>
            </ul>
        </nav>
    </header>

    <!-- Hero Section -->
    <section class="hero">
        <div class="container">
            <h1>News Intelligence System</h1>
            <p>Advanced AI-powered news analysis, clustering, and intelligence platform</p>
            <a href="/dashboard" class="cta-button">Explore Dashboard</a>
        </div>
    </section>

    <!-- Features Section -->
    <section class="features">
        <div class="container">
            <h2>Powerful Features</h2>
            <div class="features-grid">
                <div class="feature-card">
                    <div class="feature-icon">
                        <i class="fas fa-robot"></i>
                    </div>
                    <h3>AI-Powered Analysis</h3>
                    <p>Advanced natural language processing for entity extraction, event detection, and content clustering.</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">
                        <i class="fas fa-chart-line"></i>
                    </div>
                    <h3>Real-time Intelligence</h3>
                    <p>Live monitoring of news sources with intelligent deduplication and quality assessment.</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">
                        <i class="fas fa-brain"></i>
                    </div>
                    <h3>Machine Learning Ready</h3>
                    <p>Prepared datasets and pipelines for advanced ML models and summarization.</p>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">
                        <i class="fas fa-shield-alt"></i>
                    </div>
                    <h3>Enterprise Security</h3>
                    <p>Production-ready with automated cleanup, monitoring, and security features.</p>
                </div>
            </div>
        </div>
    </section>

    <!-- Stats Section -->
    <section class="stats">
        <div class="container">
            <h2>System Statistics</h2>
            <div class="stats-grid">
                <div class="stat-item">
                    <h3 id="article-count">1,247</h3>
                    <p>Articles Processed</p>
                </div>
                <div class="stat-item">
                    <h3 id="cluster-count">89</h3>
                    <p>Event Clusters</p>
                </div>
                <div class="stat-item">
                    <h3 id="entity-count">2,341</h3>
                    <p>Entities Extracted</p>
                </div>
                <div class="stat-item">
                    <h3 id="source-count">12</h3>
                    <p>Active Sources</p>
                </div>
            </div>
        </div>
    </section>

    <!-- Dashboard Preview -->
    <section class="dashboard">
        <div class="container">
            <h2>Live Dashboard Preview</h2>
            <div class="dashboard-grid">
                <div class="dashboard-card">
                    <h3>Recent Articles</h3>
                    <ul class="article-list" id="recent-articles">
                        <!-- Articles will be populated by JavaScript -->
                    </ul>
                </div>
                <div class="dashboard-card">
                    <h3>System Health</h3>
                    <div id="system-health">
                        <!-- System health will be populated by JavaScript -->
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
        <div class="container">
            <p>&copy; 2025 News Intelligence System v2.7.0. Professional news analysis platform.</p>
        </div>
    </footer>

    <script>
        // Fetch and display live data
        async function fetchDashboardData() {
            try {
                const response = await fetch('/api/dashboard');
                const data = await response.json();
                
                // Update stats
                document.getElementById('article-count').textContent = data.articleCount.toLocaleString();
                document.getElementById('cluster-count').textContent = data.clusterCount.toLocaleString();
                document.getElementById('entity-count').textContent = data.entityCount.toLocaleString();
                document.getElementById('source-count').textContent = data.sourceCount.toLocaleString();
                
                // Update recent articles
                const recentArticlesList = document.getElementById('recent-articles');
                recentArticlesList.innerHTML = data.recentArticles.map(article => `
                    <li class="article-item">
                        <div class="article-title">${article.title}</div>
                        <div class="article-meta">
                            ${article.source} • ${new Date(article.publishedDate).toLocaleDateString()}
                        </div>
                    </li>
                `).join('');
                
                // Update system health
                const systemHealth = document.getElementById('system-health');
                systemHealth.innerHTML = `
                    <p><strong>Status:</strong> <span style="color: green;">${data.feedHealth[0].status}</span></p>
                    <p><strong>Last Update:</strong> ${new Date(data.feedHealth[0].lastFetch).toLocaleString()}</p>
                    <p><strong>Success Rate:</strong> ${data.feedHealth[0].successRate}%</p>
                `;
                
            } catch (error) {
                console.error('Error fetching dashboard data:', error);
            }
        }
        
        // Fetch data on page load
        fetchDashboardData();
        
        // Refresh data every 30 seconds
        setInterval(fetchDashboardData, 30000);
    </script>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - News Intelligence System</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #f5f7fa;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 20px;
        }
        
        .header {
            background: white;
            padding: 1rem 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        
        .nav {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 1.5rem;
            font-weight: 700;
            color: #667eea;
            text-decoration: none;
        }
        
        .nav-links {
            display: flex;
            gap: 2rem;
            list-style: none;
        }
        
        .nav-links a {
            text-decoration: none;
            color: #333;
            font-weight: 500;
        }
        
        .main-content {
            padding: 2rem 0;
        }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 2rem;
            margin-bottom: 2rem;
        }
        
        .card {
            background: white;
            padding: 2rem;
            border-radius: 15px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        
        .card h3 {
            font-size: 1.5rem;
            margin-bottom: 1rem;
            color: #333;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 1rem;
        }
        
        .stat-item {
            text-align: center;
            padding: 1rem;
            background: #f8f9fa;
            border-radius: 10px;
        }
        
        .stat-number {
            font-size: 2rem;
            font-weight: 700;
            color: #667eea;
        }
        
        .stat-label {
            color: #666;
            font-size: 0.9rem;
        }
        
        .chart-container {
            position: relative;
            height: 300px;
        }
        
        .article-list {
            list-style: none;
        }
        
        .article-item {
            padding: 1rem 0;
            border-bottom: 1px solid #eee;
        }
        
        .article-item:last-child {
            border-bottom: none;
        }
        
        .article-title {
            font-weight: 600;
            color: #333;
            margin-bottom: 0.5rem;
        }
        
        .article-meta {
            font-size: 0.9rem;
            color: #666;
        }
    </style>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <nav class="nav container">
            <a href="/" class="logo">
                <i class="fas fa-newspaper"></i> News Intelligence
            </a>
            <ul class="nav-links">
                <li><a href="/dashboard">Dashboard</a></li>
                <li><a href="/articles">Articles</a></li>
                <li><a href="/clusters">Clusters</a></li>
                <li><a href="/entities">Entities</a></li>
                <li><a href="/sources">Sources</a></li>
                <li><a href="/monitoring">Monitoring</a></li>
            </ul>
        </nav>
    </header>

    <!-- Main Content -->
    <main class="main-content">
        <div class="container">
            <h1 style="margin-bottom: 2rem; color: #333;">Dashboard</h1>
            
            <!-- Stats Cards -->
            <div class="dashboard-grid">
                <div class="card">
                    <h3>System Overview</h3>
                    <div class="stats-grid">
                        <div class="stat-item">
                            <div class="stat-number" id="article-count">-</div>
                            <div class="stat-label">Articles</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-number" id="cluster-count">-</div>
                            <div class="stat-label">Clusters</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-number" id="entity-count">-</div>
                            <div class="stat-label">Entities</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-number" id="source-count">-</div>
                            <div class="stat-label">Sources</div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>System Health</h3>
                    <div id="system-health">
                        <p>Loading...</p>
                    </div>
                </div>
            </div>
            
            <!-- Charts and Data -->
            <div class="dashboard-grid">
                <div class="card">
                    <h3>Articles Over Time</h3>
                    <div class="chart-container">
                        <canvas id="articlesChart"></canvas>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Recent Articles</h3>
                    <ul class="article-list" id="recent-articles">
                        <li>Loading...</li>
                    </ul>
                </div>
            </div>
        </div>
    </main>

    <script>
        // Fetch dashboard data
        async function fetchDashboardData() {
            try {
                const response = await fetch('/api/dashboard');
                const data = await response.json();
                
                // Update stats
                document.getElementById('article-count').textContent = data.articleCount.toLocaleString();
                document.getElementById('cluster-count').textContent = data.clusterCount.toLocaleString();
                document.getElementById('entity-count').textContent = data.entityCount.toLocaleString();
                document.getElementById('source-count').textContent = data.sourceCount.toLocaleString();
                
                // Update system health
                const systemHealth = document.getElementById('system-health');
                systemHealth.innerHTML = `
                    <p><strong>Status:</strong> <span style="color: green;">${data.feedHealth[0].status}</span></p>
                    <p><strong>Last Update:</strong> ${new Date(data.feedHealth[0].lastFetch).toLocaleString()}</p>
                    <p><strong>Success Rate:</strong> ${data.feedHealth[0].successRate}%</p>
                `;
                
                // Update recent articles
                const recentArticlesList = document.getElementById('recent-articles');
                recentArticlesList.innerHTML = data.recentArticles.map(article => `
                    <li class="article-item">
                        <div class="article-title">${article.title}</div>
                        <div class="article-meta">
                            ${article.source} • ${new Date(article.publishedDate).toLocaleDateString()}
                        </div>
                    </li>
                `).join('');
                
                // Create chart
                createArticlesChart(data);
                
            } catch (error) {
                console.error('Error fetching dashboard data:', error);
            }
        }
        
        // Create articles chart
        function createArticlesChart(data) {
            const ctx = document.getElementById('articlesChart').getContext('2d');
            
            // Mock time series data
            const labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
            const values = [120, 150, 180, 200, 180, 150, 130];
            
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Articles Collected',
                        data: values,
                        borderColor: '#667eea',
                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                        tension: 0.4,
                        fill: true
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        }
        
        // Fetch data on page load
        fetchDashboardData();
        
        // Refresh data every 30 seconds
        setInterval(fetchDashboardData, 30000);
    </script>
</body>
</html>
"""

# Route handlers
# Note: Root route is handled by React serving route below

@app.route('/dashboard')
def dashboard():
    """Serve the dashboard page"""
    return DASHBOARD_HTML

@app.route('/health')
def health():
    """Health check endpoint"""
    # Test database connectivity
    db_healthy = test_database_connection()
    
    return jsonify({
        'status': 'healthy' if db_healthy else 'degraded',
        'timestamp': datetime.now().isoformat(),
        'version': 'v2.8.0',
        'database': 'connected' if db_healthy else 'disconnected'
    })

@app.route('/api/system/status')
@limiter.limit("500 per hour")
def system_status():
    """Get system status"""
    # Calculate actual uptime
    uptime_seconds = time.time() - app_metrics['start_time']
    hours = int(uptime_seconds // 3600)
    minutes = int((uptime_seconds % 3600) // 60)
    uptime_str = f"{hours}h {minutes}m"
    
    # Update the mock data with real uptime
    status_data = MOCK_DATA['system_status'].copy()
    status_data['uptime'] = uptime_str
    status_data['lastUpdate'] = datetime.now().isoformat()
    
    return jsonify(status_data)

@app.route('/api/security/events')
# @limiter.limit("50 per hour")
def security_events():
    """Get security events (admin only)"""
    # In production, add authentication here
    return jsonify({
        'events': SECURITY_EVENTS[-100:],  # Last 100 events
        'total': len(SECURITY_EVENTS),
        'threats_blocked': len([e for e in SECURITY_EVENTS if 'XSS_ATTEMPT' in e['type'] or 'SUSPICIOUS' in e['type']])
    })

@app.route('/api/dashboard')
# @limiter.limit("200 per hour")
def dashboard_api():
    """Get dashboard data from database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get article count
        cursor.execute("SELECT COUNT(*) FROM articles")
        article_count = cursor.fetchone()[0]
        
        # Get cluster count
        cursor.execute("SELECT COUNT(*) FROM article_clusters")
        cluster_count = cursor.fetchone()[0]
        
        # Get entity count
        cursor.execute("SELECT COUNT(*) FROM entities")
        entity_count = cursor.fetchone()[0]
        
        # Get source count
        cursor.execute("SELECT COUNT(DISTINCT source) FROM articles")
        source_count = cursor.fetchone()[0]
        
        # Get recent articles
        cursor.execute("""
            SELECT id, title, content, source, published_date, category
            FROM articles 
            ORDER BY published_date DESC 
            LIMIT 5
        """)
        recent_articles = []
        for row in cursor.fetchall():
            recent_articles.append({
                'id': row[0],
                'title': row[1],
                'summary': row[2][:100] + '...' if row[2] and len(row[2]) > 100 else row[2],
                'source': row[3],
                'publishedDate': row[4].isoformat() if row[4] else None,
                'category': row[5]
            })
        
        # Get top sources
        cursor.execute("""
            SELECT source, COUNT(*) as article_count
            FROM articles 
            GROUP BY source 
            ORDER BY article_count DESC 
            LIMIT 5
        """)
        top_sources = []
        for row in cursor.fetchall():
            top_sources.append({
                'name': row[0],
                'articleCount': row[1],
                'health': 'excellent'  # Placeholder
            })
        
        # Get top entities (placeholder - would need entity extraction)
        top_entities = [
            {'name': 'United States', 'type': 'GPE', 'frequency': 234, 'category': 'Politics'},
            {'name': 'China', 'type': 'GPE', 'frequency': 189, 'category': 'Economy'},
            {'name': 'Technology', 'type': 'TOPIC', 'frequency': 156, 'category': 'Technology'}
        ]
        
        # Feed health (placeholder - would need RSS feed monitoring)
        feed_health = [
            {
                'source': 'BBC News',
                'status': 'healthy',
                'lastFetch': datetime.now().isoformat(),
                'successRate': 99.8
            },
            {
                'source': 'Reuters',
                'status': 'healthy',
                'lastFetch': datetime.now().isoformat(),
                'successRate': 99.5
            }
        ]
        
        conn.close()
        
        return jsonify({
            'articleCount': article_count,
            'clusterCount': cluster_count,
            'entityCount': entity_count,
            'sourceCount': source_count,
            'recentArticles': recent_articles,
            'topSources': top_sources,
            'topEntities': top_entities,
            'feedHealth': feed_health,
            'status': 'real_data'
        })
        
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        return jsonify({'error': f'Failed to get dashboard data: {str(e)}'}), 500

@app.route('/api/articles', methods=['GET'])
def get_articles():
    """Get articles with optional filtering and pagination"""
    try:
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        search = request.args.get('search', '')
        category = request.args.get('category', '')
        source = request.args.get('source', '')
        priority = request.args.get('priority', '')
        sort_by = request.args.get('sort_by', 'published_date')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Validate parameters
        if page < 1:
            page = 1
        if per_page < 1 or per_page > 100:
            per_page = 10
        
        # Build query
        query = """
            SELECT a.id, a.title, a.url, a.content, a.summary, a.published_date, 
                   a.source, a.category, a.language, a.quality_score, a.processing_status,
                   a.created_at, a.updated_at, a.content_hash, a.deduplication_status,
                   a.normalized_content, a.content_similarity_score,
                   cpa.priority_level_id,
                   st.id as thread_id,
                   cpl.name as priority_level
            FROM articles a
            LEFT JOIN content_priority_assignments cpa ON a.id = cpa.article_id
            LEFT JOIN story_threads st ON cpa.thread_id = st.id
            LEFT JOIN content_priority_levels cpl ON cpa.priority_level_id = cpl.id
            WHERE 1=1
        """
        params = []
        
        if search:
            query += " AND (a.title ILIKE %s OR a.content ILIKE %s)"
            params.extend([f'%{search}%', f'%{search}%'])
        
        if category:
            query += " AND a.category = %s"
            params.append(category)
        
        if source:
            query += " AND a.source = %s"
            params.append(source)
        
        if priority:
            query += " AND cpl.name = %s"
            params.append(priority)
        
        # Add sorting
        valid_sort_fields = ['title', 'published_date', 'source', 'category', 'created_at', 'priority']
        if sort_by not in valid_sort_fields:
            sort_by = 'published_date'
        
        if sort_by == 'priority':
            query += " ORDER BY cpa.priority_level_id DESC NULLS LAST"
        else:
            query += f" ORDER BY a.{sort_by} {sort_order.upper()}"
        
        # Add pagination
        offset = (page - 1) * per_page
        query += " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        # Execute query
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(query, params)
        articles = cursor.fetchall()
        
        # Get total count for pagination
        count_query = """
            SELECT COUNT(*) 
            FROM articles a
            LEFT JOIN content_priority_assignments cpa ON a.id = cpa.article_id
            LEFT JOIN content_priority_levels cpl ON cpa.priority_level_id = cpl.id
            WHERE 1=1
        """
        count_params = []
        
        if search:
            count_query += " AND (a.title ILIKE %s OR a.content ILIKE %s)"
            count_params.extend([f'%{search}%', f'%{search}%'])
        
        if category:
            count_query += " AND a.category = %s"
            count_params.append(category)
        
        if priority:
            count_query += " AND cpl.name = %s"
            count_params.append(priority)
        
        cursor.execute(count_query, count_params)
        total = cursor.fetchone()[0]
        
        conn.close()
        
        # Format articles
        formatted_articles = []
        for article in articles:
            # Handle date formatting safely
            published_date = None
            if article[5] and hasattr(article[5], 'isoformat'):
                published_date = article[5].isoformat()
            elif article[5]:
                published_date = str(article[5])
            
            created_at = None
            if article[11] and hasattr(article[11], 'isoformat'):
                created_at = article[11].isoformat()
            elif article[11]:
                created_at = str(article[11])
            
            formatted_articles.append({
                'id': article[0],
                'title': article[1],
                'url': article[2],
                'content': article[3],
                'summary': article[4],
                'published_date': published_date,
                'source': article[6],
                'category': article[7],
                'language': article[8],
                'quality_score': float(article[9]) if article[9] else None,
                'processing_status': article[10],
                'created_at': created_at,
                'updated_at': article[12].isoformat() if article[12] and hasattr(article[12], 'isoformat') else None,
                'content_hash': article[13],
                'deduplication_status': article[14],
                'normalized_content': article[15],
                'content_similarity_score': float(article[16]) if article[16] else None,
                'priority_level_id': article[17] if len(article) > 17 else None,
                'thread_id': article[18] if len(article) > 18 else None,
                'priority_level': article[19] if len(article) > 19 else None
            })
        
        return jsonify({
            'success': True,
            'articles': formatted_articles,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })
        
    except Exception as e:
        logger.error(f"Error getting articles: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/articles/categories', methods=['GET'])
def get_article_categories():
    """Get unique article categories"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT DISTINCT category 
            FROM articles 
            WHERE category IS NOT NULL AND category != ''
            ORDER BY category
        """)
        
        categories = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'categories': categories
        })
        
    except Exception as e:
        logger.error(f"Error getting article categories: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/clusters')
def clusters():
    """Get clusters from database"""
    logger.info("Clusters endpoint called - attempting database query")
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT id, topic, article_count, cohesion_score, cluster_type, created_date, updated_at
            FROM article_clusters 
            ORDER BY created_date DESC
        """
        
        logger.info(f"Executing query: {query}")
        cursor.execute(query)
        clusters = []
        for row in cursor.fetchall():
            clusters.append({
                'id': row[0],
                'name': row[1],  # Use topic as name
                'topic': row[1],
                'articleCount': row[2],
                'cohesionScore': float(row[3]) if row[3] else 0.0,
                'status': row[4] if row[4] else 'active',
                'createdAt': row[5].isoformat() if row[5] else None,
                'updatedAt': row[6].isoformat() if row[6] else None
            })
        
        logger.info(f"Found {len(clusters)} clusters in database")
        conn.close()
        
        return jsonify({
            'clusters': clusters,
            'total': len(clusters),
            'status': 'real_data'
        })
        
    except Exception as e:
        logger.error(f"Error fetching clusters: {e}")
        return jsonify({'error': f'Failed to get clusters: {str(e)}'}), 500

@app.route('/api/entities')
def entities():
    """Get entities by type"""
    entity_type = request.args.get('type', 'PERSON')
    
    # Mock entity data by type
    entity_data = {
        'PERSON': [
            {'text': 'Elon Musk', 'frequency': 156, 'articles': [1, 5, 12, 23], 'category': 'Technology'},
            {'text': 'Dr. Sarah Johnson', 'frequency': 89, 'articles': [3, 7, 15], 'category': 'Health'},
        ],
        'ORG': [
            {'text': 'Apple Inc.', 'frequency': 134, 'articles': [5, 9, 16, 22], 'category': 'Technology'},
            {'text': 'United Nations', 'frequency': 98, 'articles': [2, 6, 13], 'category': 'Politics'},
        ],
        'GPE': [
            {'text': 'United States', 'frequency': 234, 'articles': [1, 3, 5, 7, 9, 11], 'category': 'Politics'},
            {'text': 'China', 'frequency': 189, 'articles': [2, 4, 6, 8, 10, 12], 'category': 'Economy'},
        ],
    }
    
    entities = entity_data.get(entity_type, [])
    
    return jsonify({
        'entities': entities,
        'total': len(entities),
        'type': entity_type
    })

@app.route('/api/sources')
def sources():
    """Get sources"""
    return jsonify({
        'sources': MOCK_DATA['sources'],
        'total': len(MOCK_DATA['sources']),
        'healthMetrics': [
            {
                'sourceId': s['id'],
                'sourceName': s['name'],
                'health': s['health'],
                'successRate': s['successRate'],
                'avgResponseTime': s['avgResponseTime'],
                'errorCount': s['errorCount'],
                'lastFetched': s['lastFetched'],
            }
            for s in MOCK_DATA['sources']
        ]
    })

@app.route('/api/search')
def search():
    """Search across articles, clusters, and entities"""
    query = request.args.get('q', '')
    
    if not query:
        return jsonify({'results': [], 'total': 0})
    
    # Mock search results
    results = []
    
    # Search in articles
    for article in MOCK_DATA['articles']:
        if query.lower() in article['title'].lower() or query.lower() in article['content'].lower():
            results.append({
                'type': 'article',
                'title': article['title'],
                'content': article['content'],
                'source': article['source'],
                'publishedDate': article['publishedDate'],
                'relevanceScore': 0.95,
                'matchType': 'title' if query.lower() in article['title'].lower() else 'content'
            })
    
    # Search in clusters
    for cluster in MOCK_DATA['clusters']:
        if query.lower() in cluster['name'].lower() or query.lower() in cluster['topic'].lower():
            results.append({
                'type': 'cluster',
                'name': cluster['name'],
                'articleCount': cluster['articleCount'],
                'relevanceScore': 0.87,
                'matchType': 'topic'
            })
    
    return jsonify({
        'results': results,
        'total': len(results),
        'query': query
    })

@app.route('/api/pipeline/run', methods=['POST'])
def run_pipeline():
    """Run the intelligence pipeline"""
    # Mock pipeline execution
    return jsonify({
        'status': 'completed',
        'statistics': {
            'articlesProcessed': 1247,
            'duplicatesRemoved': 89,
            'entitiesExtracted': 2341,
            'clustersCreated': 89,
            'processingTime': '2m 34s',
            'successRate': 98.7,
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/populate-db', methods=['POST'])
# @limiter.limit("1 per hour")  # Only allow once per hour
def populate_database():
    """Populate database with sample data for testing"""
    try:
        # Import here to avoid circular imports
        import psycopg2
        import json
        from datetime import datetime, timedelta
        
        # Get database connection
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM articles")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            return jsonify({'message': f'Database already has {existing_count} articles', 'status': 'skipped'}), 200
        
        # Sample articles data
        articles_data = [
            ('Breaking: Major Tech Merger Announced', 
             'Two major technology companies have announced a historic merger that will reshape the industry landscape.',
             'https://example.com/tech-merger', 'Tech News Daily', 'Technology', 'en', 0.89),
            ('Global Climate Summit Reaches Historic Agreement',
             'World leaders have reached a landmark agreement on climate change during the recent summit.',
             'https://example.com/climate-summit', 'World News', 'Environment', 'en', 0.92),
            ('AI Breakthrough in Medical Diagnosis',
             'Researchers have developed a new AI system that can diagnose rare diseases with 95% accuracy.',
             'https://example.com/ai-medical', 'Science Daily', 'Health', 'en', 0.94),
            ('Economic Recovery Shows Strong Momentum',
             'New economic data indicates a robust recovery across multiple sectors.',
             'https://example.com/economic-recovery', 'Business Times', 'Economy', 'en', 0.87),
            ('Space Tourism Company Announces First Commercial Flight',
             'A private space company has announced its first commercial passenger flight to orbit.',
             'https://example.com/space-tourism', 'Space News', 'Science', 'en', 0.91)
        ]
        
        # Insert articles
        for i, (title, content, url, source, category, language, quality_score) in enumerate(articles_data):
            published_date = datetime.now() - timedelta(hours=2 + i*2)
            cursor.execute("""
                INSERT INTO articles (title, content, url, source, published_date, category, language, quality_score, processing_status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (title, content, url, source, published_date, category, language, quality_score, 'processed', datetime.now()))
        
        # Sample entities
        entities_data = [
            ('TechCorp', 'ORG', 15, 0.95, 'Technology'),
            ('Elon Musk', 'PERSON', 25, 0.92, 'Technology'),
            ('United Nations', 'ORG', 18, 0.98, 'Politics'),
            ('Climate Change', 'CONCEPT', 28, 0.93, 'Environment')
        ]
        
        # Insert entities
        for text, type_, frequency, confidence, category in entities_data:
            cursor.execute("""
                INSERT INTO entities (text, type, frequency, confidence, metadata, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (text, type_, frequency, confidence, json.dumps({"category": category}), datetime.now()))
        
        # Sample clusters
        clusters_data = [
            ('Tech Industry Mergers', 'Technology', 3, 0.87, 'active'),
            ('Climate Change Summit', 'Environment', 2, 0.92, 'active'),
            ('AI and Medical Breakthroughs', 'Health', 1, 0.89, 'active')
        ]
        
        # Insert clusters
        for name, topic, article_count, cohesion_score, status in clusters_data:
            cursor.execute("""
                INSERT INTO article_clusters (topic, article_count, cohesion_score, created_date)
                VALUES (%s, %s, %s, %s)
            """, (topic, article_count, cohesion_score, datetime.now()))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'message': 'Database populated successfully',
            'articles_added': len(articles_data),
            'entities_added': len(entities_data),
            'clusters_added': len(clusters_data),
            'status': 'success'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to populate database: {str(e)}'}), 500

# Add this route to get real database counts
@app.route('/api/dashboard/real')
# @limiter.limit("100 per hour")
def dashboard_real():
    """Get dashboard data from actual database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        
        # Get real counts
        cursor.execute("SELECT COUNT(*) FROM articles")
        article_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM article_clusters")
        cluster_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM entities")
        entity_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM rss_feeds")
        source_count = cursor.fetchone()[0]
        
        # Get recent articles
        cursor.execute("""
            SELECT id, title, source, published_date, category, 
                   LEFT(content, 100) as summary
            FROM articles 
            ORDER BY published_date DESC 
            LIMIT 5
        """)
        recent_articles = []
        for row in cursor.fetchall():
            recent_articles.append({
                'id': row[0],
                'title': row[1],
                'source': row[2],
                'publishedDate': row[3].isoformat() if row[3] else None,
                'category': row[4],
                'summary': row[5] + '...' if row[5] else ''
            })
        
        # Get top sources
        cursor.execute("""
            SELECT source, COUNT(*) as article_count
            FROM articles 
            GROUP BY source 
            ORDER BY article_count DESC 
            LIMIT 5
        """)
        top_sources = []
        for row in cursor.fetchall():
            top_sources.append({
                'name': row[0],
                'articleCount': row[1],
                'health': 'excellent' if row[1] > 10 else 'good'
            })
        
        conn.close()
        
        return jsonify({
            'articleCount': article_count,
            'clusterCount': cluster_count,
            'entityCount': entity_count,
            'sourceCount': source_count,
            'recentArticles': recent_articles,
            'topSources': top_sources,
            'status': 'real_data'
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to get dashboard data: {str(e)}'}), 500

# Content Prioritization API Endpoints
@app.route('/api/prioritization/story-threads', methods=['GET'])
def get_story_threads():
    """Get story threads with optional filtering"""
    try:
        status = request.args.get('status', 'active')
        priority_level = request.args.get('priority_level')
        
        from modules.prioritization import ContentPrioritizationManager
        manager = ContentPrioritizationManager(DB_CONFIG)
        
        threads = manager.get_story_threads(status=status, priority_level_name=priority_level)
        
        return jsonify({
            'success': True,
            'data': threads,
            'count': len(threads)
        })
        
    except Exception as e:
        logger.error(f"Error getting story threads: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/story-threads', methods=['POST'])
def create_story_thread():
    """Create a new story thread"""
    try:
        data = request.get_json()
        
        title = data.get('title')
        description = data.get('description')
        category = data.get('category')
        priority_level = data.get('priority_level', 'medium')
        keywords = data.get('keywords', [])
        
        if not all([title, description, category]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: title, description, category'
            }), 400
        
        from modules.prioritization import ContentPrioritizationManager
        manager = ContentPrioritizationManager(DB_CONFIG)
        
        result = manager.create_story_thread(
            title=title,
            description=description,
            category=category,
            priority_level_name=priority_level,
            keywords=keywords,
            user_created=True
        )
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
        return jsonify({
            'success': True,
            'data': result,
            'message': 'Story thread created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating story thread: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/story-threads/<int:thread_id>', methods=['PUT'])
def update_story_thread(thread_id):
    """Update a story thread"""
    try:
        data = request.get_json()
        
        # Get current thread info
        from modules.prioritization import ContentPrioritizationManager
        manager = ContentPrioritizationManager(DB_CONFIG)
        
        # Update thread in database
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        update_fields = []
        params = []
        
        if 'title' in data:
            update_fields.append("title = %s")
            params.append(data['title'])
        
        if 'description' in data:
            update_fields.append("description = %s")
            params.append(data['description'])
        
        if 'category' in data:
            update_fields.append("category = %s")
            params.append(data['category'])
        
        if 'status' in data:
            update_fields.append("status = %s")
            params.append(data['status'])
        
        if update_fields:
            params.append(thread_id)
            query = f"""
                UPDATE story_threads 
                SET {', '.join(update_fields)}, updated_at = NOW()
                WHERE id = %s
            """
            cursor.execute(query, params)
            
            # Update keywords if provided
            if 'keywords' in data:
                # Remove existing keywords
                cursor.execute("DELETE FROM story_thread_keywords WHERE thread_id = %s", (thread_id,))
                
                # Add new keywords
                for keyword in data['keywords']:
                    cursor.execute("""
                        INSERT INTO story_thread_keywords (thread_id, keyword, weight)
                        VALUES (%s, %s, %s)
                    """, (thread_id, keyword, 1.0))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': 'Story thread updated successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No fields to update'
            }), 400
        
    except Exception as e:
        logger.error(f"Error updating story thread: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/story-threads/<int:thread_id>', methods=['DELETE'])
def delete_story_thread(thread_id):
    """Delete a story thread and all associated data"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check if thread exists
        cursor.execute("SELECT id, title FROM story_threads WHERE id = %s", (thread_id,))
        thread = cursor.fetchone()
        
        if not thread:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Story thread not found'
            }), 404
        
        # Delete associated data in correct order (foreign key constraints)
        # 1. Delete storyline alerts
        cursor.execute("DELETE FROM storyline_alerts WHERE thread_id = %s", (thread_id,))
        
        # 2. Delete content priority assignments
        cursor.execute("DELETE FROM content_priority_assignments WHERE thread_id = %s", (thread_id,))
        
        # 3. Delete story thread keywords
        cursor.execute("DELETE FROM story_thread_keywords WHERE thread_id = %s", (thread_id,))
        
        # 4. Delete the story thread itself
        cursor.execute("DELETE FROM story_threads WHERE id = %s", (thread_id,))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Deleted story thread {thread_id}: {thread[1]}")
        
        return jsonify({
            'success': True,
            'message': f'Story thread "{thread[1]}" deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting story thread: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/user-rules', methods=['GET'])
def get_user_rules():
    """Get user interest rules"""
    try:
        profile_name = request.args.get('profile', 'default')
        
        from modules.prioritization import ContentPrioritizationManager
        manager = ContentPrioritizationManager(DB_CONFIG)
        
        # Get rules from the engine
        user_rules = manager.engine.user_rules.get(profile_name, [])
        
        return jsonify({
            'success': True,
            'data': user_rules,
            'count': len(user_rules)
        })
        
    except Exception as e:
        logger.error(f"Error getting user rules: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/user-rules', methods=['POST'])
def create_user_rule():
    """Create a new user interest rule"""
    try:
        data = request.get_json()
        
        profile_name = data.get('profile_name', 'default')
        rule_type = data.get('rule_type')
        rule_value = data.get('rule_value')
        priority_level = data.get('priority_level', 'medium')
        action = data.get('action', 'track')
        weight = data.get('weight', 1.0)
        
        if not all([rule_type, rule_value]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: rule_type, rule_value'
            }), 400
        
        from modules.prioritization import ContentPrioritizationManager
        manager = ContentPrioritizationManager(DB_CONFIG)
        
        result = manager.add_user_interest_rule(
            profile_name=profile_name,
            rule_type=rule_type,
            rule_value=rule_value,
            priority_level_name=priority_level,
            action=action,
            weight=weight
        )
        
        if 'error' in result:
            return jsonify({
                'success': False,
                'error': result['error']
            }), 400
        
        return jsonify({
            'success': True,
            'data': result,
            'message': 'User interest rule created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating user rule: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/user-rules/<int:rule_id>', methods=['DELETE'])
def delete_user_rule(rule_id):
    """Delete a user interest rule"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM user_interest_rules WHERE id = %s", (rule_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({
                'success': False,
                'error': 'Rule not found'
            }), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'User interest rule deleted successfully'
        })
        
    except Exception as e:
        logger.error(f"Error deleting user rule: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/priority-levels', methods=['GET'])
def get_priority_levels():
    """Get available priority levels"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, description, sort_order, color
            FROM content_priority_levels
            ORDER BY sort_order DESC
        """)
        
        levels = []
        for row in cursor.fetchall():
            levels.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'sort_order': row[3],
                'color': row[4]
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': levels,
            'count': len(levels)
        })
        
    except Exception as e:
        logger.error(f"Error getting priority levels: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/statistics', methods=['GET'])
def get_prioritization_statistics():
    """Get prioritization system statistics"""
    try:
        from modules.prioritization import ContentPrioritizationManager
        manager = ContentPrioritizationManager(DB_CONFIG)
        
        stats = manager.get_manager_statistics()
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting prioritization statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/rag-context/<int:thread_id>', methods=['POST'])
def build_rag_context(thread_id):
    """Build RAG context for a story thread"""
    try:
        data = request.get_json() or {}
        context_type = data.get('context_type', 'historical')
        max_articles = data.get('max_articles', 20)
        
        from modules.prioritization import ContentPrioritizationManager
        manager = ContentPrioritizationManager(DB_CONFIG)
        
        context = manager.build_rag_context(
            thread_id=thread_id,
            context_type=context_type,
            max_articles=max_articles
        )
        
        if 'error' in context:
            return jsonify({
                'success': False,
                'error': context['error']
            }), 400
        
        return jsonify({
            'success': True,
            'data': context
        })
        
    except Exception as e:
        logger.error(f"Error building RAG context: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/articles/<int:article_id>/priority', methods=['PUT'])
def update_article_priority(article_id):
    """Update article priority assignment"""
    try:
        data = request.get_json()
        
        priority_level_id = data.get('priority_level_id')
        thread_id = data.get('thread_id')
        reasoning = data.get('reasoning', '')
        
        if not priority_level_id:
            return jsonify({
                'success': False,
                'error': 'Missing priority_level_id'
            }), 400
        
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check if assignment already exists
        cursor.execute("""
            SELECT id FROM content_priority_assignments WHERE article_id = %s
        """, (article_id,))
        
        existing = cursor.fetchone()
        
        if existing:
            # Update existing assignment
            cursor.execute("""
                UPDATE content_priority_assignments 
                SET priority_level_id = %s, thread_id = %s, assigned_by = %s, 
                    confidence_score = %s, reasoning = %s, assigned_at = NOW()
                WHERE article_id = %s
            """, (
                priority_level_id,
                thread_id,
                'user',
                1.0,
                reasoning,
                article_id
            ))
        else:
            # Create new assignment
            cursor.execute("""
                INSERT INTO content_priority_assignments 
                (article_id, priority_level_id, thread_id, assigned_by, confidence_score, reasoning)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                article_id,
                priority_level_id,
                thread_id,
                'user',
                1.0,
                reasoning
            ))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Article priority updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating article priority: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/collection-rules', methods=['GET'])
def get_collection_rules():
    """Get content collection rules"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, rule_name, rule_type, rule_conditions, priority_level_id,
                   action, is_active, created_at, updated_at
            FROM content_collection_rules
            WHERE is_active = TRUE
            ORDER BY created_at DESC
        """)
        
        rules = []
        for row in cursor.fetchall():
            rules.append({
                'id': row[0],
                'rule_name': row[1],
                'rule_type': row[2],
                'rule_conditions': row[3],
                'priority_level_id': row[4],
                'action': row[5],
                'is_active': row[6],
                'created_at': row[7].isoformat() if row[7] else None,
                'updated_at': row[8].isoformat() if row[8] else None
            })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': rules,
            'count': len(rules)
        })
        
    except Exception as e:
        logger.error(f"Error getting collection rules: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/prioritization/collection-rules', methods=['POST'])
def create_collection_rule():
    """Create a new content collection rule"""
    try:
        data = request.get_json()
        
        rule_name = data.get('rule_name')
        rule_type = data.get('rule_type')
        rule_conditions = data.get('rule_conditions', {})
        priority_level_id = data.get('priority_level_id')
        action = data.get('action')
        
        if not all([rule_name, rule_type, action]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: rule_name, rule_type, action'
            }), 400
        
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO content_collection_rules
            (rule_name, rule_type, rule_conditions, priority_level_id, action)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (
            rule_name,
            rule_type,
            json.dumps(rule_conditions),
            priority_level_id,
            action
        ))
        
        rule_id = cursor.fetchone()[0]
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'data': {'id': rule_id},
            'message': 'Collection rule created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating collection rule: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



# Prometheus metrics endpoint
@app.route('/metrics')
def metrics():
    """Prometheus metrics endpoint"""
    try:
        # Format metrics in Prometheus format
        metrics_output = []
        
        # Application metrics
        metrics_output.append(f"# HELP news_system_requests_total Total number of requests")
        metrics_output.append(f"# TYPE news_system_requests_total counter")
        metrics_output.append(f"news_system_requests_total {app_metrics['requests_total']}")
        
        metrics_output.append(f"# HELP news_system_articles_processed Total articles processed")
        metrics_output.append(f"# TYPE news_system_articles_processed counter")
        metrics_output.append(f"news_system_articles_processed {app_metrics['articles_processed']}")
        
        metrics_output.append(f"# HELP news_system_ml_inferences Total ML inferences")
        metrics_output.append(f"# TYPE news_system_ml_inferences counter")
        metrics_output.append(f"news_system_ml_inferences {app_metrics['ml_inferences']}")
        
        metrics_output.append(f"# HELP news_system_database_queries Total database queries")
        metrics_output.append(f"# TYPE news_system_database_queries counter")
        metrics_output.append(f"news_system_database_queries {app_metrics['database_queries']}")
        
        metrics_output.append(f"# HELP news_system_errors_total Total errors")
        metrics_output.append(f"# TYPE news_system_errors_total counter")
        metrics_output.append(f"news_system_errors_total {app_metrics['errors_total']}")
        
        # System metrics
        if 'cpu_percent' in app_metrics:
            metrics_output.append(f"# HELP news_system_cpu_percent CPU usage percentage")
            metrics_output.append(f"# TYPE news_system_cpu_percent gauge")
            metrics_output.append(f"news_system_cpu_percent {app_metrics['cpu_percent']}")
        
        if 'memory_percent' in app_metrics:
            metrics_output.append(f"# HELP news_system_memory_percent Memory usage percentage")
            metrics_output.append(f"# TYPE news_system_memory_percent gauge")
            metrics_output.append(f"news_system_memory_percent {app_metrics['memory_percent']}")
        
        if 'disk_percent' in app_metrics:
            metrics_output.append(f"# HELP news_system_disk_percent Disk usage percentage")
            metrics_output.append(f"# TYPE news_system_disk_percent gauge")
            metrics_output.append(f"news_system_disk_percent {app_metrics['disk_percent']}")
        
        # GPU metrics
        if 'gpu_memory_used_mb' in app_metrics:
            metrics_output.append(f"# HELP news_system_gpu_memory_used_mb GPU memory used in MB")
            metrics_output.append(f"# TYPE news_system_gpu_memory_used_mb gauge")
            metrics_output.append(f"news_system_gpu_memory_used_mb {app_metrics['gpu_memory_used_mb']}")
        
        if 'gpu_memory_total_mb' in app_metrics:
            metrics_output.append(f"# HELP news_system_gpu_memory_total_mb GPU memory total in MB")
            metrics_output.append(f"# TYPE news_system_gpu_memory_total_mb gauge")
            metrics_output.append(f"news_system_gpu_memory_total_mb {app_metrics['gpu_memory_total_mb']}")
        
        if 'gpu_utilization_percent' in app_metrics:
            metrics_output.append(f"# HELP news_system_gpu_utilization_percent GPU utilization percentage")
            metrics_output.append(f"# TYPE news_system_gpu_utilization_percent gauge")
            metrics_output.append(f"news_system_gpu_utilization_percent {app_metrics['gpu_utilization_percent']}")
        
        # Uptime
        uptime = time.time() - app_metrics['start_time']
        metrics_output.append(f"# HELP news_system_uptime_seconds Uptime in seconds")
        metrics_output.append(f"# TYPE news_system_uptime_seconds counter")
        metrics_output.append(f"news_system_uptime_seconds {uptime}")
        
        return '\n'.join(metrics_output), 200, {'Content-Type': 'text/plain'}
        
    except Exception as e:
        logger.error(f"Error generating metrics: {e}")
        return f"# Error generating metrics: {e}", 500, {'Content-Type': 'text/plain'}

# Resource logging API endpoints
@app.route('/api/metrics/history')
def get_metrics_history():
    """Get historical metrics data"""
    try:
        if not MONITORING_AVAILABLE:
            return jsonify({'error': 'Resource logging not available'}), 503
        
        hours = request.args.get('hours', 24, type=int)
        if hours > 168:  # Max 1 week
            hours = 168
            
        summary = resource_logger.get_metrics_summary(hours)
        return jsonify({
            'success': True,
            'data': summary,
            'period_hours': hours
        })
        
    except Exception as e:
        logger.error(f"Error getting metrics history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/metrics/cleanup', methods=['POST'])
def cleanup_old_metrics():
    """Clean up old metrics data"""
    try:
        if not MONITORING_AVAILABLE:
            return jsonify({'error': 'Resource logging not available'}), 503
        
        days_to_keep = request.json.get('days_to_keep', 30)
        if days_to_keep < 1 or days_to_keep > 365:
            return jsonify({'error': 'Invalid days_to_keep value'}), 400
            
        resource_logger.cleanup_old_metrics(days_to_keep)
        return jsonify({
            'success': True,
            'message': f'Cleaned up metrics older than {days_to_keep} days'
        })
        
    except Exception as e:
        logger.error(f"Error cleaning up metrics: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ML API ENDPOINTS
# ============================================================================

@app.route('/api/ml/status')
def ml_status():
    """Get ML service status"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        ml_service = MLSummarizationService()
        status = ml_service.get_service_status()
        
        return jsonify({
            'success': True,
            'ml_available': ML_AVAILABLE,
            'service_status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting ML status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/process-article/<int:article_id>', methods=['POST'])
def process_article_ml(article_id):
    """Process a single article through ML pipeline"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        ml_pipeline = MLPipeline(DB_CONFIG)
        result = ml_pipeline.process_article(article_id)
        
        return jsonify({
            'success': result['status'] == 'success',
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error processing article {article_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/process-all', methods=['POST'])
def process_all_articles():
    """Process all unprocessed articles through ML pipeline"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        # Get all articles that haven't been ML processed
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM articles 
            WHERE processing_status != 'ml_processed' 
            AND content IS NOT NULL 
            AND LENGTH(content) > 100
            ORDER BY created_at DESC
        """)
        
        article_ids = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        if not article_ids:
            return jsonify({
                'success': True,
                'message': 'No articles need ML processing',
                'result': {
                    'total_articles': 0,
                    'processed': 0,
                    'failed': 0,
                    'skipped': 0
                }
            })
        
        ml_pipeline = MLPipeline(DB_CONFIG)
        result = ml_pipeline.process_articles_batch(article_ids)
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error processing all articles: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/summarize', methods=['POST'])
def summarize_content():
    """Generate summary for provided content"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        data = request.get_json()
        content = data.get('content', '')
        title = data.get('title', '')
        
        if not content:
            return jsonify({'error': 'No content provided'}), 400
        
        ml_service = MLSummarizationService()
        result = ml_service.generate_summary(content, title)
        
        return jsonify({
            'success': result['status'] == 'success',
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/analyze-arguments', methods=['POST'])
def analyze_arguments():
    """Analyze arguments and perspectives in content"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        data = request.get_json()
        content = data.get('content', '')
        title = data.get('title', '')
        
        if not content:
            return jsonify({'error': 'No content provided'}), 400
        
        ml_service = MLSummarizationService()
        result = ml_service.analyze_arguments(content, title)
        
        return jsonify({
            'success': result['status'] == 'success',
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error analyzing arguments: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/processing-status')
def ml_processing_status():
    """Get ML processing status and statistics"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        ml_pipeline = MLPipeline(DB_CONFIG)
        status = ml_pipeline.get_processing_status()
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting ML processing status: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ML TIMING AND BACKGROUND PROCESSING API ENDPOINTS
# ============================================================================

@app.route('/api/ml/queue-article/<int:article_id>', methods=['POST'])
def queue_article_for_ml_processing(article_id):
    """Queue an article for background ML processing"""
    try:
        if not ML_AVAILABLE or not background_ml_processor:
            return jsonify({'error': 'ML background processing not available'}), 503
        
        data = request.get_json() or {}
        operation_type = data.get('operation_type', 'full_analysis')
        priority = data.get('priority', 0)
        model_name = data.get('model_name')
        
        queue_id = background_ml_processor.queue_article_for_processing(
            article_id, operation_type, priority, model_name
        )
        
        return jsonify({
            'success': True,
            'queue_id': queue_id,
            'message': f'Article {article_id} queued for {operation_type} processing'
        })
        
    except Exception as e:
        logger.error(f"Error queueing article for ML processing: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/processing-status/<int:article_id>')
def get_article_ml_processing_status(article_id):
    """Get ML processing status for a specific article"""
    try:
        if not ML_AVAILABLE or not background_ml_processor:
            return jsonify({'error': 'ML background processing not available'}), 503
        
        status = background_ml_processor.get_processing_status(article_id)
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting article ML processing status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/processing-status')
def get_all_ml_processing_status():
    """Get ML processing status for all articles"""
    try:
        if not ML_AVAILABLE or not background_ml_processor:
            return jsonify({'error': 'ML background processing not available'}), 503
        
        status = background_ml_processor.get_processing_status()
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting ML processing status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/queue-status')
def get_ml_queue_status():
    """Get current ML processing queue status"""
    try:
        if not ML_AVAILABLE or not background_ml_processor:
            return jsonify({'error': 'ML background processing not available'}), 503
        
        queue_status = background_ml_processor.get_queue_status()
        
        return jsonify({
            'success': True,
            'queue_status': queue_status
        })
        
    except Exception as e:
        logger.error(f"Error getting ML queue status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/ml/timing-stats')
def get_ml_timing_stats():
    """Get ML processing timing statistics"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        with psycopg2.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cursor:
                # Get timing statistics from articles table
                cursor.execute("""
                    SELECT 
                        DATE(ml_processing_started_at) as processing_date,
                        ml_model_used,
                        COUNT(*) as total_processed,
                        AVG(ml_processing_duration_seconds) as avg_duration_seconds,
                        MIN(ml_processing_duration_seconds) as min_duration_seconds,
                        MAX(ml_processing_duration_seconds) as max_duration_seconds,
                        COUNT(CASE WHEN ml_processing_status = 'completed' THEN 1 END) as successful_count,
                        COUNT(CASE WHEN ml_processing_status = 'failed' THEN 1 END) as failed_count
                    FROM articles 
                    WHERE ml_processing_started_at IS NOT NULL
                    GROUP BY DATE(ml_processing_started_at), ml_model_used
                    ORDER BY processing_date DESC, ml_model_used
                    LIMIT 30
                """)
                
                timing_stats = []
                for row in cursor.fetchall():
                    timing_stats.append({
                        'processing_date': row[0].isoformat() if row[0] else None,
                        'model_used': row[1],
                        'total_processed': row[2],
                        'avg_duration_seconds': float(row[3]) if row[3] else 0,
                        'min_duration_seconds': float(row[4]) if row[4] else 0,
                        'max_duration_seconds': float(row[5]) if row[5] else 0,
                        'successful_count': row[6],
                        'failed_count': row[7]
                    })
                
                # Get recent processing logs
                cursor.execute("""
                    SELECT 
                        l.operation_type,
                        l.model_name,
                        l.duration_seconds,
                        l.status,
                        l.started_at,
                        a.title
                    FROM ml_processing_logs l
                    JOIN articles a ON l.article_id = a.id
                    ORDER BY l.started_at DESC
                    LIMIT 50
                """)
                
                recent_logs = []
                for row in cursor.fetchall():
                    recent_logs.append({
                        'operation_type': row[0],
                        'model_name': row[1],
                        'duration_seconds': float(row[2]) if row[2] else 0,
                        'status': row[3],
                        'started_at': row[4].isoformat() if row[4] else None,
                        'article_title': row[5]
                    })
                
                return jsonify({
                    'success': True,
                    'timing_stats': timing_stats,
                    'recent_logs': recent_logs
                })
        
    except Exception as e:
        logger.error(f"Error getting ML timing stats: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# STORYLINE ALERT API ENDPOINTS
# ============================================================================

@app.route('/api/alerts/storyline/unread', methods=['GET'])
def get_unread_storyline_alerts():
    """Get unread storyline alerts"""
    try:
        from modules.prioritization import StorylineAlertService
        alert_service = StorylineAlertService(DB_CONFIG)
        
        limit = request.args.get('limit', 10, type=int)
        alerts = alert_service.get_unread_alerts(limit=limit)
        
        return jsonify({
            'success': True,
            'alerts': alerts,
            'count': len(alerts)
        })
        
    except Exception as e:
        logger.error(f"Error getting unread storyline alerts: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/alerts/storyline/<int:alert_id>/read', methods=['POST'])
def mark_storyline_alert_read(alert_id):
    """Mark a storyline alert as read"""
    try:
        from modules.prioritization import StorylineAlertService
        alert_service = StorylineAlertService(DB_CONFIG)
        
        success = alert_service.mark_alert_as_read(alert_id)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Alert marked as read'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to mark alert as read'
            }), 400
        
    except Exception as e:
        logger.error(f"Error marking alert as read: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/alerts/storyline/statistics', methods=['GET'])
def get_storyline_alert_statistics():
    """Get storyline alert statistics"""
    try:
        from modules.prioritization import StorylineAlertService
        alert_service = StorylineAlertService(DB_CONFIG)
        
        stats = alert_service.get_alert_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting alert statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/alerts/storyline/check-updates', methods=['POST'])
def check_storyline_updates():
    """Manually check for storyline updates and create alerts"""
    try:
        from modules.prioritization import StorylineAlertService
        alert_service = StorylineAlertService(DB_CONFIG)
        
        data = request.get_json() or {}
        thread_id = data.get('thread_id')
        
        if thread_id:
            # Check specific thread
            alert_data = alert_service.check_for_significant_updates(thread_id)
            if alert_data:
                alert_id = alert_service.create_alert(alert_data)
                return jsonify({
                    'success': True,
                    'alert_created': True,
                    'alert_id': alert_id,
                    'message': 'Significant update detected and alert created'
                })
            else:
                return jsonify({
                    'success': True,
                    'alert_created': False,
                    'message': 'No significant updates detected'
                })
        else:
            # Check all active threads
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM story_threads WHERE status = 'active'")
            thread_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            alerts_created = 0
            for tid in thread_ids:
                alert_data = alert_service.check_for_significant_updates(tid)
                if alert_data:
                    alert_service.create_alert(alert_data)
                    alerts_created += 1
            
            return jsonify({
                'success': True,
                'alerts_created': alerts_created,
                'threads_checked': len(thread_ids),
                'message': f'Checked {len(thread_ids)} threads, created {alerts_created} alerts'
            })
        
    except Exception as e:
        logger.error(f"Error checking storyline updates: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# INTELLIGENT TAGGING API ENDPOINTS
# ============================================================================

@app.route('/api/tags/analyze-thread/<int:thread_id>', methods=['POST'])
def analyze_thread_tags(thread_id):
    """Analyze and suggest tags for a story thread"""
    try:
        from modules.prioritization import IntelligentTaggingService
        tagging_service = IntelligentTaggingService(DB_CONFIG)
        
        analysis_result = tagging_service.analyze_story_thread_tags(thread_id)
        
        if 'error' in analysis_result:
            return jsonify({
                'success': False,
                'error': analysis_result['error']
            }), 400
        
        return jsonify({
            'success': True,
            'analysis': analysis_result
        })
        
    except Exception as e:
        logger.error(f"Error analyzing thread tags: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/tags/update-thread/<int:thread_id>', methods=['POST'])
def update_thread_tags(thread_id):
    """Update thread tags based on analysis"""
    try:
        from modules.prioritization import IntelligentTaggingService
        tagging_service = IntelligentTaggingService(DB_CONFIG)
        
        # First analyze the thread
        analysis_result = tagging_service.analyze_story_thread_tags(thread_id)
        
        if 'error' in analysis_result:
            return jsonify({
                'success': False,
                'error': analysis_result['error']
            }), 400
        
        # Then update the tags
        update_result = tagging_service.update_thread_tags(thread_id, analysis_result)
        
        if 'error' in update_result:
            return jsonify({
                'success': False,
                'error': update_result['error']
            }), 400
        
        return jsonify({
            'success': True,
            'update_result': update_result,
            'analysis': analysis_result
        })
        
    except Exception as e:
        logger.error(f"Error updating thread tags: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/tags/thread/<int:thread_id>/analytics', methods=['GET'])
def get_thread_tag_analytics(thread_id):
    """Get tag analytics for a story thread"""
    try:
        from modules.prioritization import IntelligentTaggingService
        tagging_service = IntelligentTaggingService(DB_CONFIG)
        
        analytics = tagging_service.get_thread_tag_analytics(thread_id)
        
        if 'error' in analytics:
            return jsonify({
                'success': False,
                'error': analytics['error']
            }), 400
        
        return jsonify({
            'success': True,
            'analytics': analytics
        })
        
    except Exception as e:
        logger.error(f"Error getting thread tag analytics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/tags/extract-from-content', methods=['POST'])
def extract_tags_from_content():
    """Extract tags from provided content"""
    try:
        from modules.prioritization import IntelligentTaggingService
        tagging_service = IntelligentTaggingService(DB_CONFIG)
        
        data = request.get_json() or {}
        content = data.get('content', '')
        title = data.get('title', '')
        max_tags = data.get('max_tags', 20)
        
        if not content:
            return jsonify({
                'success': False,
                'error': 'Content is required'
            }), 400
        
        extracted_tags = tagging_service.extract_tags_from_content(content, title, max_tags)
        
        return jsonify({
            'success': True,
            'tags': extracted_tags,
            'count': len(extracted_tags)
        })
        
    except Exception as e:
        logger.error(f"Error extracting tags from content: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ============================================================================
# RAG ENHANCED API ENDPOINTS
# ============================================================================

@app.route('/api/rag/enhanced-context', methods=['POST'])
def build_enhanced_rag_context():
    """Build enhanced RAG context with ML analysis"""
    try:
        if not ML_AVAILABLE or not rag_enhanced_service:
            return jsonify({'error': 'RAG Enhanced Service not available'}), 503
        
        data = request.get_json() or {}
        query = data.get('query', '')
        context_type = data.get('context_type', 'comprehensive')
        max_articles = data.get('max_articles', 25)
        include_ml_analysis = data.get('include_ml_analysis', True)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        context = rag_enhanced_service.build_enhanced_context(
            query=query,
            context_type=context_type,
            max_articles=max_articles,
            include_ml_analysis=include_ml_analysis
        )
        
        return jsonify({
            'success': True,
            'context': context
        })
        
    except Exception as e:
        logger.error(f"Error building enhanced RAG context: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/story-dossier/<story_id>', methods=['POST'])
def build_story_dossier_with_rag(story_id):
    """Build comprehensive story dossier with RAG enhancement"""
    try:
        if not ML_AVAILABLE or not rag_enhanced_service:
            return jsonify({'error': 'RAG Enhanced Service not available'}), 503
        
        data = request.get_json() or {}
        story_title = data.get('story_title')
        include_historical = data.get('include_historical', True)
        include_related = data.get('include_related', True)
        include_analysis = data.get('include_analysis', True)
        
        dossier = rag_enhanced_service.build_story_dossier_with_rag(
            story_id=story_id,
            story_title=story_title,
            include_historical=include_historical,
            include_related=include_related,
            include_analysis=include_analysis
        )
        
        return jsonify({
            'success': True,
            'dossier': dossier
        })
        
    except Exception as e:
        logger.error(f"Error building story dossier with RAG: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/statistics')
def get_rag_statistics():
    """Get RAG service statistics"""
    try:
        if not ML_AVAILABLE or not rag_enhanced_service:
            return jsonify({'error': 'RAG Enhanced Service not available'}), 503
        
        stats = rag_enhanced_service.get_rag_statistics()
        
        return jsonify({
            'success': True,
            'statistics': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting RAG statistics: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/search', methods=['POST'])
def rag_search():
    """Perform RAG-powered search with ML enhancement"""
    try:
        if not ML_AVAILABLE or not rag_enhanced_service:
            return jsonify({'error': 'RAG Enhanced Service not available'}), 503
        
        data = request.get_json() or {}
        query = data.get('query', '')
        search_type = data.get('search_type', 'comprehensive')  # comprehensive, historical, related, expert
        max_results = data.get('max_results', 20)
        
        if not query:
            return jsonify({'error': 'Search query is required'}), 400
        
        # Map search types to context types
        context_type_map = {
            'comprehensive': 'comprehensive',
            'historical': 'historical',
            'related': 'related',
            'expert': 'expert_analysis'
        }
        
        context_type = context_type_map.get(search_type, 'comprehensive')
        
        context = rag_enhanced_service.build_enhanced_context(
            query=query,
            context_type=context_type,
            max_articles=max_results,
            include_ml_analysis=True
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'search_type': search_type,
            'results': context
        })
        
    except Exception as e:
        logger.error(f"Error performing RAG search: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/comprehensive-research', methods=['POST'])
def comprehensive_research():
    """Perform comprehensive research using internal and external sources"""
    try:
        if not ML_AVAILABLE or not rag_enhanced_service:
            return jsonify({'error': 'RAG Enhanced Service not available'}), 503
        
        data = request.get_json() or {}
        query = data.get('query', '')
        story_keywords = data.get('story_keywords', [])
        include_external = data.get('include_external', True)
        include_internal = data.get('include_internal', True)
        
        if not query:
            return jsonify({'error': 'Research query is required'}), 400
        
        context = rag_enhanced_service.build_comprehensive_research_context(
            query=query,
            story_keywords=story_keywords,
            include_external=include_external,
            include_internal=include_internal
        )
        
        return jsonify({
            'success': True,
            'query': query,
            'context': context
        })
        
    except Exception as e:
        logger.error(f"Error performing comprehensive research: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/external-services-status')
def get_external_services_status():
    """Get status of external services integration"""
    try:
        if not ML_AVAILABLE or not rag_enhanced_service:
            return jsonify({'error': 'RAG Enhanced Service not available'}), 503
        
        # Check external services configuration
        external_config = rag_enhanced_service.external_services.config
        services_status = {
            'wikipedia': {
                'available': True,
                'rate_limited': True,
                'description': 'Wikipedia API for historical context and background information'
            },
            'newsapi': {
                'available': bool(external_config.get('newsapi_key') and external_config.get('newsapi_key') != 'your_newsapi_key_here'),
                'rate_limited': True,
                'description': 'NewsAPI for recent articles and trending topics'
            },
            'knowledge_graph': {
                'available': bool(external_config.get('kg_api_key') and external_config.get('kg_api_key') != 'your_kg_api_key_here'),
                'rate_limited': True,
                'description': 'Google Knowledge Graph for entity relationships'
            },
            'semantic_search': {
                'available': True,
                'rate_limited': False,
                'description': 'Semantic search using sentence transformers'
            },
            'timeline_analysis': {
                'available': True,
                'rate_limited': False,
                'description': 'Timeline analysis for story evolution tracking'
            },
            'entity_relationships': {
                'available': True,
                'rate_limited': False,
                'description': 'Entity relationship mapping for connected stories'
            }
        }
        
        return jsonify({
            'success': True,
            'services': services_status,
            'config': {
                'enable_external_services': rag_enhanced_service.config.get('enable_external_services', True),
                'rate_limits': rag_enhanced_service.external_services.rate_limits
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting external services status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/gdelt-enhancement/<int:article_id>', methods=['POST'])
def enhance_article_with_gdelt(article_id):
    """Enhance an article with GDELT timeline and context data"""
    try:
        if not ML_AVAILABLE or not rag_enhanced_service:
            return jsonify({'error': 'RAG Enhanced Service not available'}), 503
        
        # Get optional keywords from request
        data = request.get_json() or {}
        keywords = data.get('keywords', [])
        
        # Enhance article with GDELT data
        enhancement_result = rag_enhanced_service.enhance_article_with_gdelt_timeline(
            article_id=article_id,
            keywords=keywords
        )
        
        if 'error' in enhancement_result:
            return jsonify({
                'success': False,
                'error': enhancement_result['error']
            }), 400
        
        return jsonify({
            'success': True,
            'enhancement': enhancement_result,
            'message': f'Article {article_id} enhanced with GDELT timeline data',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error enhancing article {article_id} with GDELT: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/gdelt-timeline', methods=['POST'])
def get_gdelt_timeline():
    """Get GDELT timeline data for a query"""
    try:
        if not ML_AVAILABLE or not rag_enhanced_service:
            return jsonify({'error': 'RAG Enhanced Service not available'}), 503
        
        data = request.get_json()
        if not data or 'query' not in data:
            return jsonify({'error': 'Query parameter is required'}), 400
        
        query = data['query']
        days_back = data.get('days_back', 7)
        
        # Get GDELT timeline data
        timeline_data = rag_enhanced_service.gdelt_service.get_event_timeline(
            query=query,
            days_back=days_back
        )
        
        if 'error' in timeline_data:
            return jsonify({
                'success': False,
                'error': timeline_data['error']
            }), 400
        
        return jsonify({
            'success': True,
            'timeline': timeline_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting GDELT timeline: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/simple-enhancement/<int:article_id>', methods=['POST'])
def enhance_article_with_simple_rag(article_id):
    """Enhance an article with simple RAG context (no external APIs)"""
    try:
        # Import the simple RAG service
        from modules.ml.simple_rag_service import SimpleRAGService
        
        # Get optional keywords from request
        data = request.get_json() or {}
        keywords = data.get('keywords', [])
        
        # Initialize simple RAG service
        simple_rag = SimpleRAGService(db_config)
        
        # Enhance article with simple RAG
        enhancement_result = simple_rag.enhance_article_with_context(
            article_id=article_id,
            keywords=keywords
        )
        
        if 'error' in enhancement_result:
            return jsonify({
                'success': False,
                'error': enhancement_result['error']
            }), 400
        
        return jsonify({
            'success': True,
            'enhancement': enhancement_result,
            'message': f'Article {article_id} enhanced with RAG context',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error enhancing article {article_id} with simple RAG: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# ITERATIVE RAG SYSTEM API ENDPOINTS (V2.9)
# ============================================================================

@app.route('/api/rag/iterative/test', methods=['GET'])
def test_iterative_rag_registration():
    """Test route to verify iterative RAG route registration"""
    return jsonify({'message': 'Iterative RAG routes are working!', 'timestamp': datetime.now().isoformat()})

@app.route('/api/rag/iterative/create-dossier/<int:article_id>', methods=['POST'])
def create_iterative_rag_dossier(article_id):
    """Create a new iterative RAG dossier for an article"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML services not available'}), 503
        
        # Get optional initial keywords from request
        data = request.get_json() or {}
        initial_keywords = data.get('keywords', [])
        
        # Initialize iterative RAG service with database connection
        import psycopg2
        from psycopg2.extras import RealDictCursor
        db_connection = psycopg2.connect(**db_config, cursor_factory=RealDictCursor)
        iterative_rag = IterativeRAGService(db_connection)
        
        # Create dossier
        dossier = iterative_rag.create_dossier(article_id, initial_keywords)
        
        return jsonify({
            'success': True,
            'dossier_id': dossier.dossier_id,
            'article_id': dossier.article_id,
            'created_at': dossier.created_at,
            'current_phase': dossier.current_phase,
            'message': f'Iterative RAG dossier created for article {article_id}',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error creating iterative RAG dossier for article {article_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/iterative/process-iteration/<dossier_id>', methods=['POST'])
def process_iterative_rag_iteration(dossier_id):
    """Process the next iteration in an iterative RAG dossier"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML services not available'}), 503
        
        # Get optional force continue flag
        data = request.get_json() or {}
        force_continue = data.get('force_continue', False)
        
        # Initialize iterative RAG service with database connection
        import psycopg2
        from psycopg2.extras import RealDictCursor
        db_connection = psycopg2.connect(**db_config, cursor_factory=RealDictCursor)
        iterative_rag = IterativeRAGService(db_connection)
        
        # Process iteration
        iteration = iterative_rag.process_iteration(dossier_id, force_continue)
        
        return jsonify({
            'success': True,
            'dossier_id': dossier_id,
            'iteration': {
                'iteration_number': iteration.iteration_number,
                'phase': iteration.phase,
                'timestamp': iteration.timestamp,
                'processing_time': iteration.processing_time,
                'plateau_score': iteration.plateau_score,
                'new_articles_found': iteration.new_articles_found,
                'new_entities_found': iteration.new_entities_found,
                'success': iteration.success,
                'error_message': iteration.error_message
            },
            'message': f'Iteration {iteration.iteration_number} completed for dossier {dossier_id}',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error processing iteration for dossier {dossier_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/iterative/dossier-status/<dossier_id>')
def get_iterative_rag_dossier_status(dossier_id):
    """Get the current status of an iterative RAG dossier"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML services not available'}), 503
        
        # Initialize iterative RAG service with database connection
        import psycopg2
        from psycopg2.extras import RealDictCursor
        db_connection = psycopg2.connect(**db_config, cursor_factory=RealDictCursor)
        iterative_rag = IterativeRAGService(db_connection)
        
        # Get dossier status
        status = iterative_rag.get_dossier_status(dossier_id)
        
        if 'error' in status:
            return jsonify(status), 404
        
        return jsonify({
            'success': True,
            'status': status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting dossier status for {dossier_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/iterative/complete-dossier/<dossier_id>')
def get_complete_iterative_rag_dossier(dossier_id):
    """Get the complete iterative RAG dossier with all data"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML services not available'}), 503
        
        # Initialize iterative RAG service with database connection
        import psycopg2
        from psycopg2.extras import RealDictCursor
        db_connection = psycopg2.connect(**db_config, cursor_factory=RealDictCursor)
        iterative_rag = IterativeRAGService(db_connection)
        
        # Get complete dossier
        dossier = iterative_rag.get_complete_dossier(dossier_id)
        
        if 'error' in dossier:
            return jsonify(dossier), 404
        
        return jsonify({
            'success': True,
            'dossier': dossier,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error getting complete dossier {dossier_id}: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/iterative/list-dossiers')
def list_iterative_rag_dossiers():
    """List all iterative RAG dossiers"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML services not available'}), 503
        
        # Get query parameters
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        status = request.args.get('status', 'all')  # 'all', 'complete', 'processing'
        
        # Build query
        query = """
            SELECT d.*, a.title as article_title
            FROM rag_dossiers d
            LEFT JOIN articles a ON d.article_id = a.id
        """
        
        conditions = []
        params = []
        
        if status == 'complete':
            conditions.append("d.is_complete = TRUE")
        elif status == 'processing':
            conditions.append("d.is_complete = FALSE")
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY d.last_updated DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        # Execute query
        cursor = db_config.cursor()
        cursor.execute(query, params)
        dossiers = cursor.fetchall()
        cursor.close()
        
        # Format results
        dossier_list = []
        for dossier in dossiers:
            dossier_list.append({
                'dossier_id': dossier['dossier_id'],
                'article_id': dossier['article_id'],
                'article_title': dossier['article_title'],
                'created_at': dossier['created_at'].isoformat() if dossier['created_at'] else None,
                'last_updated': dossier['last_updated'].isoformat() if dossier['last_updated'] else None,
                'total_iterations': dossier['total_iterations'],
                'current_phase': dossier['current_phase'],
                'is_complete': dossier['is_complete'],
                'plateau_reached': dossier['plateau_reached'],
                'total_articles_analyzed': dossier['total_articles_analyzed'],
                'total_entities_found': dossier['total_entities_found'],
                'historical_depth_years': dossier['historical_depth_years']
            })
        
        return jsonify({
            'success': True,
            'dossiers': dossier_list,
            'count': len(dossier_list),
            'limit': limit,
            'offset': offset,
            'status_filter': status,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error listing iterative RAG dossiers: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rag/iterative/auto-process/<dossier_id>', methods=['POST'])
def auto_process_iterative_rag_dossier(dossier_id):
    """Automatically process iterations until plateau is reached"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML services not available'}), 503
        
        # Get optional parameters
        data = request.get_json() or {}
        max_iterations = data.get('max_iterations', 10)
        min_iteration_gap = data.get('min_iteration_gap_seconds', 30)
        
        # Initialize iterative RAG service with database connection
        import psycopg2
        from psycopg2.extras import RealDictCursor
        db_connection = psycopg2.connect(**db_config, cursor_factory=RealDictCursor)
        iterative_rag = IterativeRAGService(db_connection)
        
        # Process iterations until plateau or max iterations
        iterations_processed = 0
        results = []
        
        while iterations_processed < max_iterations:
            try:
                # Process next iteration
                iteration = iterative_rag.process_iteration(dossier_id)
                iterations_processed += 1
                
                results.append({
                    'iteration_number': iteration.iteration_number,
                    'phase': iteration.phase,
                    'plateau_score': iteration.plateau_score,
                    'new_articles_found': iteration.new_articles_found,
                    'new_entities_found': iteration.new_entities_found,
                    'success': iteration.success
                })
                
                # Check if plateau reached
                if iteration.plateau_score < iterative_rag.plateau_threshold:
                    break
                
                # Wait between iterations
                if min_iteration_gap > 0:
                    time.sleep(min_iteration_gap)
                    
            except Exception as e:
                logger.error(f"Error in auto-processing iteration {iterations_processed + 1}: {e}")
                break
        
        return jsonify({
            'success': True,
            'dossier_id': dossier_id,
            'iterations_processed': iterations_processed,
            'results': results,
            'message': f'Auto-processed {iterations_processed} iterations for dossier {dossier_id}',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error auto-processing dossier {dossier_id}: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# RSS FEED COLLECTION API ENDPOINTS
# ============================================================================

@app.route('/api/rss/collect-now', methods=['POST'])
def collect_rss_feeds_now():
    """Trigger immediate RSS feed collection"""
    try:
        if not DATA_COLLECTION_AVAILABLE or not feed_scheduler:
            return jsonify({'error': 'RSS feed scheduler not available'}), 503
        
        results = feed_scheduler.collect_now()
        
        return jsonify({
            'success': True,
            'results': results
        })
        
    except Exception as e:
        logger.error(f"Error collecting RSS feeds: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/status')
def get_rss_feed_status():
    """Get RSS feed scheduler status"""
    try:
        if not DATA_COLLECTION_AVAILABLE or not feed_scheduler:
            return jsonify({'error': 'RSS feed scheduler not available'}), 503
        
        status = feed_scheduler.get_status()
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting RSS feed status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/feeds')
def get_rss_feeds():
    """Get list of RSS feeds"""
    try:
        if not DATA_COLLECTION_AVAILABLE or not feed_scheduler:
            return jsonify({'error': 'RSS feed scheduler not available'}), 503
        
        feed_status = feed_scheduler.rss_service.get_feed_status()
        
        return jsonify({
            'success': True,
            'feeds': feed_status
        })
        
    except Exception as e:
        logger.error(f"Error getting RSS feeds: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/feeds/<feed_name>/enable', methods=['POST'])
def enable_rss_feed(feed_name):
    """Enable a disabled RSS feed"""
    try:
        if not DATA_COLLECTION_AVAILABLE or not feed_scheduler:
            return jsonify({'error': 'RSS feed scheduler not available'}), 503
        
        success = feed_scheduler.rss_service.enable_feed(feed_name)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Feed {feed_name} enabled'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Feed {feed_name} not found'
            }), 404
        
    except Exception as e:
        logger.error(f"Error enabling RSS feed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/feeds/<feed_name>/disable', methods=['POST'])
def disable_rss_feed(feed_name):
    """Disable an RSS feed"""
    try:
        if not DATA_COLLECTION_AVAILABLE or not feed_scheduler:
            return jsonify({'error': 'RSS feed scheduler not available'}), 503
        
        success = feed_scheduler.rss_service.disable_feed(feed_name)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Feed {feed_name} disabled'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Feed {feed_name} not found'
            }), 404
        
    except Exception as e:
        logger.error(f"Error disabling RSS feed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/feeds/add', methods=['POST'])
def add_custom_rss_feed():
    """Add a custom RSS feed"""
    try:
        if not DATA_COLLECTION_AVAILABLE or not feed_scheduler:
            return jsonify({'error': 'RSS feed scheduler not available'}), 503
        
        data = request.get_json() or {}
        name = data.get('name', '').strip()
        url = data.get('url', '').strip()
        category = data.get('category', 'General').strip()
        country = data.get('country', 'Unknown').strip()
        priority = data.get('priority', 2)
        
        if not name or not url:
            return jsonify({'error': 'Name and URL are required'}), 400
        
        success = feed_scheduler.rss_service.add_custom_feed(name, url, category, country, priority)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Custom feed {name} added successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to add custom feed (invalid URL or duplicate)'
            }), 400
        
    except Exception as e:
        logger.error(f"Error adding custom RSS feed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/test-feed', methods=['POST'])
def test_rss_feed():
    """Test if an RSS feed URL is valid"""
    try:
        if not DATA_COLLECTION_AVAILABLE or not feed_scheduler:
            return jsonify({'error': 'RSS feed scheduler not available'}), 503
        
        data = request.get_json() or {}
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'URL is required'}), 400
        
        test_result = feed_scheduler.rss_service.test_feed(url)
        
        return jsonify({
            'success': True,
            'test_result': test_result
        })
        
    except Exception as e:
        logger.error(f"Error testing RSS feed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/collection-history')
def get_rss_collection_history():
    """Get RSS collection history"""
    try:
        if not DATA_COLLECTION_AVAILABLE or not feed_scheduler:
            return jsonify({'error': 'RSS feed scheduler not available'}), 503
        
        hours = request.args.get('hours', 24, type=int)
        history = feed_scheduler.get_collection_history(hours)
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        logger.error(f"Error getting RSS collection history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/update-interval', methods=['POST'])
def update_rss_collection_interval():
    """Update RSS collection interval"""
    try:
        if not DATA_COLLECTION_AVAILABLE or not feed_scheduler:
            return jsonify({'error': 'RSS feed scheduler not available'}), 503
        
        data = request.get_json() or {}
        minutes = data.get('minutes', 30)
        
        if minutes < 5:
            return jsonify({'error': 'Minimum collection interval is 5 minutes'}), 400
        
        success = feed_scheduler.update_collection_interval(minutes)
        
        if success:
            return jsonify({
                'success': True,
                'message': f'Collection interval updated to {minutes} minutes'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update collection interval'
            }), 400
        
    except Exception as e:
        logger.error(f"Error updating RSS collection interval: {e}")
        return jsonify({'error': str(e)}), 500

# RSS Collection Progress Tracking API Endpoints
# ============================================================================

@app.route('/api/rss/progress/<collection_id>')
def get_rss_collection_progress(collection_id):
    """Get progress for a specific RSS collection"""
    try:
        if not DATA_COLLECTION_AVAILABLE:
            return jsonify({'error': 'RSS features not available'}), 503
        
        progress = progress_tracker.get_progress(collection_id)
        
        if not progress:
            return jsonify({'error': 'Collection not found'}), 404
        
        return jsonify({
            'success': True,
            'progress': progress.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting RSS collection progress: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/progress')
def get_all_rss_collection_progress():
    """Get all active RSS collection progress"""
    try:
        if not DATA_COLLECTION_AVAILABLE:
            return jsonify({'error': 'RSS features not available'}), 503
        
        active_collections = progress_tracker.get_active_collections()
        
        return jsonify({
            'success': True,
            'active_collections': {
                collection_id: progress.to_dict() 
                for collection_id, progress in active_collections.items()
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting RSS collection progress: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/rss/progress/<collection_id>/cancel', methods=['POST'])
def cancel_rss_collection(collection_id):
    """Cancel a running RSS collection"""
    try:
        if not DATA_COLLECTION_AVAILABLE:
            return jsonify({'error': 'RSS features not available'}), 503
        
        progress = progress_tracker.get_progress(collection_id)
        
        if not progress:
            return jsonify({'error': 'Collection not found'}), 404
        
        if progress.status != 'running':
            return jsonify({'error': 'Collection is not running'}), 400
        
        progress_tracker.cancel_collection(collection_id)
        
        return jsonify({
            'success': True,
            'message': f'Collection {collection_id} cancelled'
        })
        
    except Exception as e:
        logger.error(f"Error cancelling RSS collection: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# STORYLINE TRACKING API ENDPOINTS
# ============================================================================

@app.route('/api/storyline/topic-cloud')
def get_topic_cloud():
    """Generate topic cloud and breaking news summary"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        days = request.args.get('days', 1, type=int)
        if days < 1 or days > 30:
            return jsonify({'error': 'Days must be between 1 and 30'}), 400
        
        storyline_tracker = StorylineTracker(DB_CONFIG)
        result = storyline_tracker.generate_topic_cloud(days)
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error generating topic cloud: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/storyline/dossier/<story_id>')
def get_story_dossier(story_id):
    """Create comprehensive dossier for a specific story"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        include_rag = request.args.get('include_rag', 'true').lower() == 'true'
        
        storyline_tracker = StorylineTracker(DB_CONFIG)
        result = storyline_tracker.create_story_dossier(story_id, include_rag)
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error creating story dossier: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/storyline/evolution/<story_id>')
def get_story_evolution(story_id):
    """Track story evolution over time"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        days = request.args.get('days', 7, type=int)
        if days < 1 or days > 90:
            return jsonify({'error': 'Days must be between 1 and 90'}), 400
        
        storyline_tracker = StorylineTracker(DB_CONFIG)
        result = storyline_tracker.track_story_evolution(story_id, days)
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error tracking story evolution: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# DEDUPLICATION API ENDPOINTS
# ============================================================================

@app.route('/api/deduplication/detect')
def detect_duplicates():
    """Detect duplicate articles in the system"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        similarity_threshold = request.args.get('similarity_threshold', type=float)
        max_articles = request.args.get('max_articles', 1000, type=int)
        
        dedup_service = ContentDeduplicationService(DB_CONFIG)
        result = dedup_service.detect_duplicates(similarity_threshold, max_articles)
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error detecting duplicates: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/deduplication/remove', methods=['POST'])
def remove_duplicates():
    """Remove duplicate articles from the system"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        data = request.get_json() or {}
        auto_remove = data.get('auto_remove', False)
        similarity_threshold = data.get('similarity_threshold', type=float)
        
        dedup_service = ContentDeduplicationService(DB_CONFIG)
        result = dedup_service.remove_duplicates(auto_remove, similarity_threshold)
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error removing duplicates: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/deduplication/stats')
def get_deduplication_stats():
    """Get deduplication statistics"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        dedup_service = ContentDeduplicationService(DB_CONFIG)
        result = dedup_service.get_deduplication_stats()
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error getting deduplication stats: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# DAILY BRIEFING API ENDPOINTS
# ============================================================================

@app.route('/api/briefing/daily')
def generate_daily_briefing():
    """Generate daily intelligence briefing"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        briefing_date_str = request.args.get('date')
        briefing_date = None
        
        if briefing_date_str:
            try:
                briefing_date = datetime.strptime(briefing_date_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        include_deduplication = request.args.get('include_deduplication', 'true').lower() == 'true'
        include_storylines = request.args.get('include_storylines', 'true').lower() == 'true'
        
        briefing_service = DailyBriefingService(DB_CONFIG)
        result = briefing_service.generate_daily_briefing(
            briefing_date, include_deduplication, include_storylines
        )
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error generating daily briefing: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/briefing/weekly')
def generate_weekly_briefing():
    """Generate weekly intelligence briefing"""
    try:
        if not ML_AVAILABLE:
            return jsonify({'error': 'ML module not available'}), 503
        
        week_start_str = request.args.get('week_start')
        week_start_date = None
        
        if week_start_str:
            try:
                week_start_date = datetime.strptime(week_start_str, '%Y-%m-%d')
            except ValueError:
                return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400
        
        briefing_service = DailyBriefingService(DB_CONFIG)
        result = briefing_service.generate_weekly_briefing(week_start_date)
        
        return jsonify({
            'success': True,
            'result': result
        })
        
    except Exception as e:
        logger.error(f"Error generating weekly briefing: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# AUTOMATED PIPELINE ORCHESTRATOR ENDPOINTS
# ============================================================================

# Global pipeline orchestrator instance
pipeline_orchestrator = None

def get_pipeline_orchestrator():
    """Get or create pipeline orchestrator instance"""
    global pipeline_orchestrator
    if pipeline_orchestrator is None:
        from modules.automation import PipelineOrchestrator
        pipeline_orchestrator = PipelineOrchestrator(DB_CONFIG)
    return pipeline_orchestrator

@app.route('/api/automation/pipeline/status', methods=['GET'])
def get_pipeline_status():
    """Get automated pipeline status"""
    try:
        orchestrator = get_pipeline_orchestrator()
        status = orchestrator.get_pipeline_status()
        
        return jsonify({
            'success': True,
            'data': status
        })
        
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/pipeline/start', methods=['POST'])
def start_automated_pipeline():
    """Start the automated pipeline"""
    try:
        orchestrator = get_pipeline_orchestrator()
        success = orchestrator.start_automated_pipeline()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Automated pipeline started successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to start automated pipeline'
            }), 500
            
    except Exception as e:
        logger.error(f"Error starting automated pipeline: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/pipeline/stop', methods=['POST'])
def stop_automated_pipeline():
    """Stop the automated pipeline"""
    try:
        orchestrator = get_pipeline_orchestrator()
        orchestrator.stop_automated_pipeline()
        
        return jsonify({
            'success': True,
            'message': 'Automated pipeline stopped successfully'
        })
        
    except Exception as e:
        logger.error(f"Error stopping automated pipeline: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/pipeline/collect', methods=['POST'])
def trigger_manual_collection():
    """Trigger manual RSS collection"""
    try:
        orchestrator = get_pipeline_orchestrator()
        result = orchestrator.trigger_manual_collection()
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error triggering manual collection: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/pipeline/process', methods=['POST'])
def trigger_manual_processing():
    """Trigger manual processing pipeline"""
    try:
        orchestrator = get_pipeline_orchestrator()
        result = orchestrator.trigger_manual_processing()
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error triggering manual processing: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/pipeline/config', methods=['PUT'])
def update_pipeline_config():
    """Update pipeline configuration"""
    try:
        data = request.get_json() or {}
        orchestrator = get_pipeline_orchestrator()
        
        success = orchestrator.update_configuration(data)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Pipeline configuration updated successfully',
                'config': orchestrator.config
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to update pipeline configuration'
            }), 400
            
    except Exception as e:
        logger.error(f"Error updating pipeline configuration: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/preprocessing/status', methods=['GET'])
def get_preprocessing_status():
    """Get enhanced preprocessing status and statistics"""
    try:
        from modules.automation import PipelineOrchestrator
        orchestrator = PipelineOrchestrator(DB_CONFIG)
        
        stats = orchestrator.enhanced_preprocessor.get_preprocessing_statistics()
        
        return jsonify({
            'success': True,
            'data': stats
        })
        
    except Exception as e:
        logger.error(f"Error getting preprocessing status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/preprocessing/run', methods=['POST'])
def run_enhanced_preprocessing():
    """Run enhanced preprocessing on new articles"""
    try:
        from modules.automation import PipelineOrchestrator
        orchestrator = PipelineOrchestrator(DB_CONFIG)
        
        data = request.get_json() or {}
        batch_size = data.get('batch_size', 50)
        
        result = orchestrator.enhanced_preprocessor.process_new_articles(batch_size)
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error running enhanced preprocessing: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/master-articles', methods=['GET'])
def get_master_articles():
    """Get master articles (consolidated articles)"""
    try:
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        category = request.args.get('category')
        min_sources = request.args.get('min_sources', 1, type=int)
        
        # Build query
        query = """
            SELECT id, title, content, summary, source, sources, source_count,
                   source_priority, category, published_at, url, tags,
                   preprocessing_status, created_at
            FROM master_articles
            WHERE source_count >= %s
        """
        params = [min_sources]
        
        if category:
            query += " AND category = %s"
            params.append(category)
        
        query += " ORDER BY source_priority DESC, published_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        articles = cursor.fetchall()
        
        # Get total count
        count_query = "SELECT COUNT(*) as total FROM master_articles WHERE source_count >= %s"
        count_params = [min_sources]
        
        if category:
            count_query += " AND category = %s"
            count_params.append(category)
        
        cursor.execute(count_query, count_params)
        total_count = cursor.fetchone()['total']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': [dict(article) for article in articles],
            'total': total_count,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"Error getting master articles: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/living-narrator/status', methods=['GET'])
def get_living_narrator_status():
    """Get Living Story Narrator status"""
    try:
        from modules.automation import PipelineOrchestrator
        orchestrator = PipelineOrchestrator(DB_CONFIG)
        
        status = orchestrator.living_story_narrator.get_pipeline_status()
        
        return jsonify({
            'success': True,
            'data': status
        })
        
    except Exception as e:
        logger.error(f"Error getting Living Story Narrator status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/living-narrator/consolidate', methods=['POST'])
def trigger_story_consolidation():
    """Trigger manual story consolidation"""
    try:
        from modules.automation import PipelineOrchestrator
        orchestrator = PipelineOrchestrator(DB_CONFIG)
        
        result = orchestrator.living_story_narrator._consolidate_evolving_stories()
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error triggering story consolidation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/living-narrator/digest', methods=['POST'])
def generate_daily_digest():
    """Generate daily digest manually"""
    try:
        from modules.automation import PipelineOrchestrator
        orchestrator = PipelineOrchestrator(DB_CONFIG)
        
        result = orchestrator.living_story_narrator._generate_daily_digest()
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error generating daily digest: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/automation/living-narrator/cleanup', methods=['POST'])
def trigger_database_cleanup():
    """Trigger database cleanup manually"""
    try:
        from modules.automation import PipelineOrchestrator
        orchestrator = PipelineOrchestrator(DB_CONFIG)
        
        result = orchestrator.living_story_narrator._perform_database_cleanup()
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        logger.error(f"Error triggering database cleanup: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/daily-digests', methods=['GET'])
def get_daily_digests():
    """Get daily digests"""
    try:
        from psycopg2.extras import RealDictCursor
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get query parameters
        limit = request.args.get('limit', 10, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        cursor.execute("""
            SELECT id, title, content, stories_included, digest_date, created_at
            FROM daily_digests
            ORDER BY digest_date DESC
            LIMIT %s OFFSET %s
        """, (limit, offset))
        
        digests = cursor.fetchall()
        
        # Get total count
        cursor.execute("SELECT COUNT(*) as total FROM daily_digests")
        total_count = cursor.fetchone()['total']
        
        conn.close()
        
        return jsonify({
            'success': True,
            'data': [dict(digest) for digest in digests],
            'total': total_count,
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        logger.error(f"Error getting daily digests: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Serve React frontend - this must be the last route before error handlers
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_react_app(path):
    """Serve the React frontend for all non-API routes"""
    # Don't serve React for API routes
    if path.startswith('api/'):
        return jsonify({'error': 'API route not found'}), 404
    
    # Static routes are handled by the dedicated static route above
    
    # Try to serve the specific file if it exists
    if path:
        file_path = os.path.join(REACT_BUILD_DIR, path)
        logger.info(f"Requested path: {path}")
        logger.info(f"Full file path: {file_path}")
        logger.info(f"File exists: {os.path.exists(file_path)}")
        if os.path.exists(file_path):
            logger.info(f"Serving file: {file_path}")
            return send_from_directory(REACT_BUILD_DIR, path)
        else:
            # Log the attempted path for debugging
            logger.warning(f"File not found: {file_path}")
    
    # Otherwise serve the main index.html for React routing
    response = send_from_directory(REACT_BUILD_DIR, 'index.html')
    
    # Add cache control headers to prevent caching of the main HTML file
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# Cleanup functions for background services
def cleanup_background_processor():
    """Cleanup background ML processor on app shutdown"""
    if background_ml_processor:
        logger.info("Stopping background ML processor...")
        background_ml_processor.stop_workers()

def cleanup_feed_scheduler():
    """Cleanup RSS feed scheduler on app shutdown"""
    if feed_scheduler:
        logger.info("Stopping RSS feed scheduler...")
        feed_scheduler.stop()

# Register cleanup functions
import atexit
atexit.register(cleanup_background_processor)
atexit.register(cleanup_feed_scheduler)

if __name__ == '__main__':
    logger.info("Starting News Intelligence System Web Application v2.8.0")
    logger.info("Unified frontend and backend will be available at http://localhost:8000")
    logger.info("React frontend and API endpoints served from single port")
    
    try:
        # Auto-start the ML pipeline
        logger.info("🚀 Auto-starting ML pipeline...")
        try:
            orchestrator = get_pipeline_orchestrator()
            success = orchestrator.start_automated_pipeline()
            if success:
                logger.info("✅ ML pipeline started successfully - running every 15 minutes")
            else:
                logger.warning("⚠️ Failed to start ML pipeline automatically")
        except Exception as e:
            logger.error(f"❌ Error auto-starting ML pipeline: {e}")
        
        # Run the Flask app
        app.run(
            host='0.0.0.0',
            port=8000,
            debug=True,
            threaded=True
        )
    finally:
        # Ensure cleanup on exit
        cleanup_background_processor()
