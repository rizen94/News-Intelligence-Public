"""
News Intelligence System v3.3.0 - Import Standards and Path Configuration
Provides standardized import paths and configuration for all services
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Standard import paths for the News Intelligence System
IMPORT_PATHS = {
    # Core configuration
    'config': 'config',
    'config.database': 'config.database',
    'config.logging_config': 'config.logging_config',
    'config.import_standards': 'config.import_standards',
    
    # Database and models
    'database': 'database',
    'database.init': 'database.init',
    'database.migrations': 'database.migrations',
    
    # Services
    'services': 'services',
    'services.article_processing_service': 'services.article_processing_service',
    'services.storyline_service': 'services.storyline_service',
    'services.rss_service': 'services.rss_service',
    'services.log_storage_service': 'services.log_storage_service',
    'services.deduplication_integration_service': 'services.deduplication_integration_service',
    
    # Routes
    'routes': 'routes',
    'routes.articles': 'routes.articles',
    'routes.rss_feeds': 'routes.rss_feeds',
    'routes.storylines': 'routes.storylines',
    'routes.health': 'routes.health',
    'routes.monitoring': 'routes.monitoring',
    'routes.intelligence': 'routes.intelligence',
    'routes.dashboard': 'routes.dashboard',
    'routes.article_processing': 'routes.article_processing',
    'routes.deduplication_simple': 'routes.deduplication_simple',
    'routes.log_management': 'routes.log_management',
    'routes.api_documentation': 'routes.api_documentation',
    'routes.pipeline_monitoring': 'routes.pipeline_monitoring',
    
    # Schemas
    'schemas': 'schemas',
    'schemas.robust_schemas': 'schemas.robust_schemas',
    'schemas.api_documentation': 'schemas.api_documentation',
    
    # Middleware
    'middleware': 'middleware',
    'middleware.error_handling': 'middleware.error_handling',
    
    # Modules
    'modules': 'modules',
    'modules.ml': 'modules.ml',
    'modules.ml.ml_pipeline': 'modules.ml.ml_pipeline',
    'modules.ml.summarization_service': 'modules.ml.summarization_service',
    'modules.ml.content_analyzer': 'modules.ml.content_analyzer',
    'modules.ml.quality_scorer': 'modules.ml.quality_scorer',
    'modules.deduplication': 'modules.deduplication',
    'modules.deduplication.advanced_deduplication_service': 'modules.deduplication.advanced_deduplication_service',
    'modules.data_collection': 'modules.data_collection',
    'modules.data_collection.rss_feed_service': 'modules.data_collection.rss_feed_service',
    
    # Utils
    'utils': 'utils',
}

# Standard import patterns
STANDARD_IMPORTS = {
    # Standard library imports (should come first)
    'standard_library': [
        'os', 'sys', 'json', 'logging', 'datetime', 'time', 'hashlib', 're',
        'asyncio', 'typing', 'pathlib', 'collections', 'itertools', 'functools',
        'contextlib', 'dataclasses', 'enum', 'abc', 'threading', 'multiprocessing'
    ],
    
    # Third-party imports (should come second)
    'third_party': [
        'fastapi', 'pydantic', 'sqlalchemy', 'psycopg2', 'redis', 'requests',
        'feedparser', 'beautifulsoup4', 'numpy', 'pandas', 'scikit-learn',
        'transformers', 'torch', 'tensorflow', 'ollama', 'aiohttp', 'httpx'
    ],
    
    # Local imports (should come last)
    'local': [
        'config', 'services', 'routes', 'schemas', 'middleware', 'modules', 'utils'
    ]
}

# Import validation rules
IMPORT_RULES = {
    'forbidden_patterns': [
        'from ..',  # Relative imports beyond parent
        'from ...',  # Relative imports beyond grandparent
        'import *',  # Wildcard imports
    ],
    
    'required_patterns': [
        'from config.',  # Should use config imports
        'from services.',  # Should use services imports
        'from routes.',  # Should use routes imports
    ],
    
    'preferred_patterns': [
        'from config.database import',  # Database imports
        'from config.logging_config import',  # Logging imports
        'from services.',  # Service imports
        'from schemas.',  # Schema imports
    ]
}

def validate_imports(file_path: str) -> Dict[str, Any]:
    """
    Validate imports in a Python file against standards
    
    Args:
        file_path: Path to the Python file to validate
        
    Returns:
        Dict containing validation results
    """
    results = {
        'file_path': file_path,
        'valid': True,
        'errors': [],
        'warnings': [],
        'suggestions': []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        import_lines = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith('import ') or stripped.startswith('from '):
                import_lines.append((i, stripped))
        
        # Check for forbidden patterns
        for line_num, import_line in import_lines:
            for pattern in IMPORT_RULES['forbidden_patterns']:
                if pattern in import_line:
                    results['errors'].append(f"Line {line_num}: Forbidden pattern '{pattern}' in '{import_line}'")
                    results['valid'] = False
        
        # Check for relative imports
        for line_num, import_line in import_lines:
            if import_line.startswith('from .'):
                results['warnings'].append(f"Line {line_num}: Relative import '{import_line}' - consider using absolute import")
        
        # Check import order
        standard_imports = []
        third_party_imports = []
        local_imports = []
        
        for line_num, import_line in import_lines:
            if any(std_lib in import_line for std_lib in STANDARD_IMPORTS['standard_library']):
                standard_imports.append((line_num, import_line))
            elif any(third_party in import_line for third_party in STANDARD_IMPORTS['third_party']):
                third_party_imports.append((line_num, import_line))
            elif any(local in import_line for local in STANDARD_IMPORTS['local']):
                local_imports.append((line_num, import_line))
        
        # Check if imports are in correct order
        if third_party_imports and local_imports:
            last_third_party = max(third_party_imports, key=lambda x: x[0])[0]
            first_local = min(local_imports, key=lambda x: x[0])[0]
            if first_local < last_third_party:
                results['warnings'].append("Import order issue: local imports should come after third-party imports")
        
    except Exception as e:
        results['errors'].append(f"Error reading file: {e}")
        results['valid'] = False
    
    return results

def fix_imports(file_path: str) -> Dict[str, Any]:
    """
    Fix imports in a Python file to match standards
    
    Args:
        file_path: Path to the Python file to fix
        
    Returns:
        Dict containing fix results
    """
    results = {
        'file_path': file_path,
        'fixed': False,
        'changes': [],
        'errors': []
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Fix relative imports
        import re
        
        # Fix relative imports to absolute imports
        relative_pattern = r'from \.([a-zA-Z_][a-zA-Z0-9_]*) import'
        matches = re.findall(relative_pattern, content)
        
        for match in matches:
            # Determine the correct absolute import based on file location
            if 'services' in file_path:
                new_import = f'from services.{match} import'
            elif 'routes' in file_path:
                new_import = f'from routes.{match} import'
            elif 'config' in file_path:
                new_import = f'from config.{match} import'
            elif 'schemas' in file_path:
                new_import = f'from schemas.{match} import'
            elif 'middleware' in file_path:
                new_import = f'from middleware.{match} import'
            elif 'modules' in file_path:
                new_import = f'from modules.{match} import'
            else:
                new_import = f'from {match} import'
            
            old_pattern = f'from .{match} import'
            content = content.replace(old_pattern, new_import)
            results['changes'].append(f"Fixed relative import: {old_pattern} -> {new_import}")
        
        # Fix double relative imports
        double_relative_pattern = r'from \.\.([a-zA-Z_][a-zA-Z0-9_]*) import'
        matches = re.findall(double_relative_pattern, content)
        
        for match in matches:
            new_import = f'from {match} import'
            old_pattern = f'from ..{match} import'
            content = content.replace(old_pattern, new_import)
            results['changes'].append(f"Fixed double relative import: {old_pattern} -> {new_import}")
        
        # Write back if changes were made
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            results['fixed'] = True
        
    except Exception as e:
        results['errors'].append(f"Error fixing file: {e}")
    
    return results

def get_standard_imports(module_type: str) -> List[str]:
    """
    Get standard imports for a specific module type
    
    Args:
        module_type: Type of module (service, route, schema, etc.)
        
    Returns:
        List of standard import statements
    """
    base_imports = [
        "import os",
        "import sys",
        "import logging",
        "from datetime import datetime",
        "from typing import Dict, List, Any, Optional, Union",
        "from pathlib import Path"
    ]
    
    if module_type == 'service':
        return base_imports + [
            "from config.database import get_db_config",
            "from config.logging_config import get_component_logger",
            "import psycopg2",
            "from psycopg2.extras import RealDictCursor",
            "import json"
        ]
    elif module_type == 'route':
        return base_imports + [
            "from fastapi import APIRouter, Depends, HTTPException, Query, Path",
            "from sqlalchemy.orm import Session",
            "from config.database import get_db",
            "from config.logging_config import get_component_logger",
            "from schemas.robust_schemas import APIResponse"
        ]
    elif module_type == 'schema':
        return base_imports + [
            "from pydantic import BaseModel, Field, validator",
            "from typing import Optional, List, Dict, Any, Union",
            "from datetime import datetime",
            "from enum import Enum"
        ]
    elif module_type == 'middleware':
        return base_imports + [
            "from fastapi import Request, Response",
            "from fastapi.responses import JSONResponse",
            "from config.logging_config import get_component_logger",
            "import traceback"
        ]
    else:
        return base_imports

def create_import_template(module_type: str, module_name: str) -> str:
    """
    Create a template with standard imports for a new module
    
    Args:
        module_type: Type of module (service, route, schema, etc.)
        module_name: Name of the module
        
    Returns:
        Template string with standard imports
    """
    imports = get_standard_imports(module_type)
    
    template = f'''"""
News Intelligence System v3.3.0 - {module_name.title()}
{module_type.title()} module with standardized imports
"""

{chr(10).join(imports)}

# Module-specific imports
# Add your module-specific imports here

# Configure logging
logger = get_component_logger('{module_name}')

# Your module code here
'''
    
    return template

# Global import validation function
def validate_all_imports(project_root: str = None) -> Dict[str, Any]:
    """
    Validate imports across the entire project
    
    Args:
        project_root: Root directory of the project
        
    Returns:
        Dict containing validation results for all files
    """
    if project_root is None:
        project_root = str(PROJECT_ROOT)
    
    results = {
        'total_files': 0,
        'valid_files': 0,
        'invalid_files': 0,
        'file_results': [],
        'summary': {}
    }
    
    # Find all Python files
    python_files = []
    for root, dirs, files in os.walk(project_root):
        # Skip certain directories
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
        
        for file in files:
            if file.endswith('.py') and not file.startswith('.'):
                python_files.append(os.path.join(root, file))
    
    results['total_files'] = len(python_files)
    
    # Validate each file
    for file_path in python_files:
        file_result = validate_imports(file_path)
        results['file_results'].append(file_result)
        
        if file_result['valid']:
            results['valid_files'] += 1
        else:
            results['invalid_files'] += 1
    
    # Create summary
    results['summary'] = {
        'validation_rate': results['valid_files'] / results['total_files'] if results['total_files'] > 0 else 0,
        'total_errors': sum(len(r['errors']) for r in results['file_results']),
        'total_warnings': sum(len(r['warnings']) for r in results['file_results']),
        'total_suggestions': sum(len(r['suggestions']) for r in results['file_results'])
    }
    
    return results
