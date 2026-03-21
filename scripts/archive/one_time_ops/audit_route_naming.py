#!/usr/bin/env python3
"""
Route Naming Consistency Audit
Identifies all route paths that don't follow snake_case convention
"""

import os
import re
from pathlib import Path

# Standard: Routes should use snake_case, not kebab-case
# Find all kebab-case patterns in route definitions

PROJECT_ROOT = Path(__file__).parent.parent
API_DIR = PROJECT_ROOT / "api"
WEB_DIR = PROJECT_ROOT / "web"

# Patterns to find
ROUTE_PATTERN = r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']'
PREFIX_PATTERN = r'prefix=["\']([^"\']+)["\']'
FRONTEND_API_PATTERN = r'["\'](/api/v4/[^"\']+)["\']'

# Kebab-case detection
KEBAB_CASE = re.compile(r'[a-z]+-[a-z]+')

issues = {
    'backend_routes': [],
    'backend_prefixes': [],
    'frontend_calls': []
}

def find_kebab_case_in_path(path_str):
    """Find all kebab-case segments in a path"""
    segments = path_str.split('/')
    kebab_segments = []
    for seg in segments:
        if KEBAB_CASE.search(seg):
            kebab_segments.append(seg)
    return kebab_segments

# Scan backend routes
for py_file in API_DIR.rglob("*.py"):
    if 'venv' in str(py_file) or '__pycache__' in str(py_file):
        continue
    
    try:
        content = py_file.read_text(encoding='utf-8')
        
        # Find route definitions
        for match in re.finditer(ROUTE_PATTERN, content):
            route_path = match.group(2)
            kebab_segments = find_kebab_case_in_path(route_path)
            if kebab_segments:
                issues['backend_routes'].append({
                    'file': str(py_file.relative_to(PROJECT_ROOT)),
                    'line': content[:match.start()].count('\n') + 1,
                    'route': route_path,
                    'kebab_segments': kebab_segments
                })
        
        # Find router prefixes
        for match in re.finditer(PREFIX_PATTERN, content):
            prefix = match.group(1)
            kebab_segments = find_kebab_case_in_path(prefix)
            if kebab_segments:
                issues['backend_prefixes'].append({
                    'file': str(py_file.relative_to(PROJECT_ROOT)),
                    'line': content[:match.start()].count('\n') + 1,
                    'prefix': prefix,
                    'kebab_segments': kebab_segments
                })
    except Exception as e:
        print(f"Error reading {py_file}: {e}")

# Scan frontend API calls
for js_file in WEB_DIR.rglob("*.{js,ts,tsx,jsx}"):
    if 'node_modules' in str(js_file) or '.next' in str(js_file):
        continue
    
    try:
        content = js_file.read_text(encoding='utf-8')
        
        for match in re.finditer(FRONTEND_API_PATTERN, content):
            api_path = match.group(1)
            kebab_segments = find_kebab_case_in_path(api_path)
            if kebab_segments:
                issues['frontend_calls'].append({
                    'file': str(js_file.relative_to(PROJECT_ROOT)),
                    'line': content[:match.start()].count('\n') + 1,
                    'path': api_path,
                    'kebab_segments': kebab_segments
                })
    except Exception as e:
        print(f"Error reading {js_file}: {e}")

# Print report
print("=" * 80)
print("ROUTE NAMING CONSISTENCY AUDIT")
print("=" * 80)
print(f"\nBackend Routes with kebab-case: {len(issues['backend_routes'])}")
print(f"Backend Prefixes with kebab-case: {len(issues['backend_prefixes'])}")
print(f"Frontend API Calls with kebab-case: {len(issues['frontend_calls'])}")
print("\n" + "=" * 80)

if issues['backend_routes']:
    print("\nBACKEND ROUTES:")
    for issue in issues['backend_routes']:
        print(f"  {issue['file']}:{issue['line']}")
        print(f"    Route: {issue['route']}")
        print(f"    Kebab segments: {', '.join(issue['kebab_segments'])}")
        print()

if issues['backend_prefixes']:
    print("\nBACKEND PREFIXES:")
    for issue in issues['backend_prefixes']:
        print(f"  {issue['file']}:{issue['line']}")
        print(f"    Prefix: {issue['prefix']}")
        print(f"    Kebab segments: {', '.join(issue['kebab_segments'])}")
        print()

if issues['frontend_calls']:
    print("\nFRONTEND API CALLS:")
    for issue in issues['frontend_calls'][:20]:  # Limit to first 20
        print(f"  {issue['file']}:{issue['line']}")
        print(f"    Path: {issue['path']}")
        print(f"    Kebab segments: {', '.join(issue['kebab_segments'])}")
        print()
    if len(issues['frontend_calls']) > 20:
        print(f"  ... and {len(issues['frontend_calls']) - 20} more")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"Total issues found: {len(issues['backend_routes']) + len(issues['backend_prefixes']) + len(issues['frontend_calls'])}")
print("\nAll routes should use snake_case, not kebab-case!")

