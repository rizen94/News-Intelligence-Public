"""
Centralized path definitions. All modules import from here.
PROJECT_ROOT is derived once; everything else follows.
"""

from pathlib import Path

# api/config/paths.py -> config -> api -> project root
CONFIG_DIR = Path(__file__).resolve().parent
_API_DIR = CONFIG_DIR.parent
PROJECT_ROOT = _API_DIR.parent

SOURCES_YAML = CONFIG_DIR / "sources.yaml"
FINANCE_SCHEDULE_YAML = CONFIG_DIR / "finance_schedule.yaml"

# Core directories
DATA_DIR = PROJECT_ROOT / "data"
REPORTS_DIR = PROJECT_ROOT / "reports"
LOG_DIR = PROJECT_ROOT / "logs"

# Reports output
MANIFESTS_DIR = REPORTS_DIR / "manifests"
REPORTS_OUTPUT_DIR = REPORTS_DIR / "output"

# Shared data
CACHE_DB_PATH = DATA_DIR / "cache.db"
CHROMA_DIR = DATA_DIR / "chroma"

# Finance domain (siloed)
FINANCE_DATA_DIR = DATA_DIR / "finance"
FINANCE_CACHE_DB = FINANCE_DATA_DIR / "api_cache.db"
FINANCE_MARKET_DB = FINANCE_DATA_DIR / "market_data.db"
FINANCE_CHROMA_DIR = FINANCE_DATA_DIR / "chroma"
FINANCE_MANIFESTS_DIR = MANIFESTS_DIR / "finance"
FINANCE_REPORTS_DIR = REPORTS_OUTPUT_DIR / "finance"
