#!/usr/bin/env python3
"""
Import Fix Script for News Intelligence System v3.0
Updates all database imports to use the unified configuration
"""

import os
import sys
import re
from pathlib import Path

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

def fix_imports_in_file(file_path: Path) -> int:
    """Fix imports in a single file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        changes_made = 0
        
        # Fix database imports
        old_imports = [
            'from config.database import',
            'from config.database import',
            'from config.database import'
        ]
        
        for old_import in old_imports:
            if old_import in content:
                # Replace with new import
                content = content.replace(old_import, 'from config.database import')
                changes_made += 1
        
        # Fix specific import patterns
        import_patterns = [
            (r'from database\.connection import get_db', 'from config.database import get_db'),
            (r'from database\.connection import get_db_config', 'from config.database import get_db_config'),
            (r'from database\.connection import get_database_url', 'from config.database import get_database_url'),
            (r'from database\.connection import test_database_connection', 'from config.database import test_database_connection'),
            (r'from config\.robust_database import get_db', 'from config.database import get_db'),
            (r'from config\.robust_database import get_db_config', 'from config.database import get_db_config'),
            (r'from config\.unified_database import get_db', 'from config.database import get_db'),
            (r'from config\.unified_database import get_db_config', 'from config.database import get_db_config'),
        ]
        
        for pattern, replacement in import_patterns:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                changes_made += 1
        
        # Only write if changes were made
        if changes_made > 0:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Fixed {changes_made} imports in {file_path.relative_to(Path.cwd())}")
        
        return changes_made
        
    except Exception as e:
        print(f"Error fixing imports in {file_path}: {e}")
        return 0

def main():
    """Main function to fix all imports"""
    project_root = Path(__file__).parent.parent.parent
    api_dir = project_root / 'api'
    
    print("Fixing database imports across the codebase...")
    
    total_files = 0
    total_changes = 0
    
    # Find all Python files in the API directory
    python_files = list(api_dir.rglob('*.py'))
    
    for py_file in python_files:
        # Skip __pycache__ directories
        if '__pycache__' in str(py_file):
            continue
        
        total_files += 1
        changes = fix_imports_in_file(py_file)
        total_changes += changes
    
    print(f"\nImport fix completed:")
    print(f"  Files processed: {total_files}")
    print(f"  Total changes made: {total_changes}")
    
    if total_changes > 0:
        print("\n✅ All database imports have been updated to use config.database")
    else:
        print("\n✅ No import changes needed")

if __name__ == "__main__":
    main()
