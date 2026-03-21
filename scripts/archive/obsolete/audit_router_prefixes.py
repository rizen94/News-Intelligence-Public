#!/usr/bin/env python3
"""
Router Prefix Audit Script
Checks all routers for correct prefix usage to prevent double prefix issues
"""

import os
import re
import sys
from pathlib import Path

# Colors for output
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color

def find_router_files(base_path):
    """Find all Python files that define APIRouter"""
    router_files = []
    for root, dirs, files in os.walk(base_path):
        # Skip __pycache__ and .venv
        dirs[:] = [d for d in dirs if d not in ['__pycache__', '.venv', 'venv']]
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if 'APIRouter' in content:
                        router_files.append((filepath, content))
    return router_files

def extract_router_definition(content):
    """Extract APIRouter definition from file content"""
    pattern = r'router\s*=\s*APIRouter\s*\([^)]*\)'
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
    if match:
        return match.group(0)
    return None

def extract_prefix(router_def):
    """Extract prefix from router definition"""
    if not router_def:
        return None
    match = re.search(r'prefix=["\']([^"\']+)["\']', router_def)
    if match:
        return match.group(1)
    return None

def check_router_inclusion(content):
    """Check if router includes other routers"""
    includes = []
    pattern = r'include_router\(([^)]+)\)'
    for match in re.finditer(pattern, content):
        included = match.group(1).strip()
        includes.append(included)
    return includes

def main():
    base_path = Path(__file__).parent.parent / 'api' / 'domains'
    
    if not base_path.exists():
        print(f"{RED}Error: {base_path} does not exist{NC}")
        sys.exit(1)
    
    print(f"{BLUE}Router Prefix Audit{NC}")
    print("=" * 80)
    print()
    
    router_files = find_router_files(str(base_path))
    
    # Map of routers included in main_v4.py
    main_routers = {
        'domains/news_aggregation/routes/news_aggregation.py',
        'domains/news_aggregation/routes/rss_duplicate_management.py',
        'domains/content_analysis/routes/content_analysis.py',
        'domains/content_analysis/routes/topic_management.py',
        'domains/content_analysis/routes/article_deduplication.py',
        'domains/storyline_management/routes/__init__.py',
        'domains/storyline_management/routes/storyline_automation.py',
        'domains/intelligence_hub/routes/intelligence_hub.py',
        'domains/user_management/routes/user_management.py',
        'domains/system_monitoring/routes/system_monitoring.py',
    }
    
    issues = []
    correct = []
    
    for filepath, content in router_files:
        # Get relative path
        rel_path = os.path.relpath(filepath, str(base_path.parent))
        rel_path = rel_path.replace('\\', '/')  # Normalize path separators
        
        router_def = extract_router_definition(content)
        prefix = extract_prefix(router_def)
        includes = check_router_inclusion(content)
        
        is_main_router = rel_path in main_routers
        is_sub_router = '/routes/' in rel_path and rel_path not in main_routers
        
        if is_main_router:
            # Main routers should have /api/v4 prefix
            if not prefix or not prefix.startswith('/api/v4'):
                issues.append({
                    'file': rel_path,
                    'type': 'main_router_missing_prefix',
                    'prefix': prefix,
                    'expected': '/api/v4 or /api/v4/...'
                })
            else:
                correct.append({
                    'file': rel_path,
                    'type': 'main_router',
                    'prefix': prefix
                })
        
        elif is_sub_router:
            # Sub-routers should NOT have /api/v4 prefix
            if prefix and prefix.startswith('/api/v4'):
                issues.append({
                    'file': rel_path,
                    'type': 'sub_router_has_prefix',
                    'prefix': prefix,
                    'expected': 'No prefix (inherits from parent)'
                })
            else:
                correct.append({
                    'file': rel_path,
                    'type': 'sub_router',
                    'prefix': prefix or 'None'
                })
    
    # Print results
    print(f"{GREEN}✅ Correct Routers ({len(correct)}):{NC}")
    for item in correct:
        print(f"  {item['file']}")
        print(f"    Type: {item['type']}, Prefix: {item['prefix']}")
    
    print()
    if issues:
        print(f"{RED}❌ Issues Found ({len(issues)}):{NC}")
        for issue in issues:
            print(f"  {issue['file']}")
            print(f"    Type: {issue['type']}")
            print(f"    Current: {issue['prefix']}")
            print(f"    Expected: {issue['expected']}")
            print()
        return 1
    else:
        print(f"{GREEN}✅ No router prefix issues found!{NC}")
        return 0

if __name__ == '__main__':
    sys.exit(main())

