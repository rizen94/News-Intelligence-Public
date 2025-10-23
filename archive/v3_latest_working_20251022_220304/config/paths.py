#!/usr/bin/env python3
"""
Path Configuration for News Intelligence System v3.0
Centralized path management to avoid hardcoded paths
"""

import os
from pathlib import Path

def get_project_root() -> str:
    """Get the project root directory"""
    # Get the directory of this file (api/config/paths.py)
    current_file = Path(__file__).resolve()
    # Go up two levels: api/config/ -> api/ -> project root
    project_root = current_file.parent.parent.parent
    return str(project_root)

def get_logs_dir() -> str:
    """Get the logs directory"""
    return os.path.join(get_project_root(), 'logs')

def get_scripts_dir() -> str:
    """Get the scripts directory"""
    return os.path.join(get_project_root(), 'scripts')

def get_api_dir() -> str:
    """Get the API directory"""
    return os.path.join(get_project_root(), 'api')

def get_database_dir() -> str:
    """Get the database directory"""
    return os.path.join(get_api_dir(), 'database')

def get_migrations_dir() -> str:
    """Get the migrations directory"""
    return os.path.join(get_database_dir(), 'migrations')

def get_web_dir() -> str:
    """Get the web directory"""
    return os.path.join(get_project_root(), 'web')

def get_archive_dir() -> str:
    """Get the archive directory"""
    return os.path.join(get_project_root(), 'archive')

def get_backups_dir() -> str:
    """Get the backups directory"""
    return os.path.join(get_project_root(), 'backups')

def get_data_dir() -> str:
    """Get the data directory"""
    return os.path.join(get_project_root(), 'data')

def get_config_dir() -> str:
    """Get the config directory"""
    return os.path.join(get_project_root(), 'configs')

def ensure_directories():
    """Ensure all necessary directories exist"""
    directories = [
        get_logs_dir(),
        get_scripts_dir(),
        get_migrations_dir(),
        get_archive_dir(),
        get_backups_dir(),
        get_data_dir(),
        get_config_dir()
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

# Environment variable overrides
def get_env_path(env_var: str, default_func) -> str:
    """Get path from environment variable or use default function"""
    env_path = os.getenv(env_var)
    if env_path:
        return env_path
    return default_func()

# Public API
PROJECT_ROOT = get_project_root()
LOGS_DIR = get_logs_dir()
SCRIPTS_DIR = get_scripts_dir()
API_DIR = get_api_dir()
DATABASE_DIR = get_database_dir()
MIGRATIONS_DIR = get_migrations_dir()
WEB_DIR = get_web_dir()
ARCHIVE_DIR = get_archive_dir()
BACKUPS_DIR = get_backups_dir()
DATA_DIR = get_data_dir()
CONFIG_DIR = get_config_dir()

# Ensure directories exist on import
ensure_directories()
