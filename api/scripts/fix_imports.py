#!/usr/bin/env python3
"""
News Intelligence System v3.3.0 - Import Path Fixer
Automatically fixes import paths across the project to match standards
"""

import os
import sys
from pathlib import Path
from typing import Any

# Add the project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.import_standards import fix_imports, validate_all_imports


def fix_all_imports(project_root: str = None) -> dict[str, Any]:
    """
    Fix imports across the entire project

    Args:
        project_root: Root directory of the project

    Returns:
        Dict containing fix results
    """
    if project_root is None:
        project_root = str(PROJECT_ROOT)

    results = {
        "total_files": 0,
        "fixed_files": 0,
        "error_files": 0,
        "file_results": [],
        "summary": {},
    }

    # Find all Python files
    python_files = []
    for root, dirs, files in os.walk(project_root):
        # Skip certain directories
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]

        for file in files:
            if file.endswith(".py") and not file.startswith("."):
                python_files.append(os.path.join(root, file))

    results["total_files"] = len(python_files)

    # Fix each file
    for file_path in python_files:
        print(f"Processing: {file_path}")
        file_result = fix_imports(file_path)
        results["file_results"].append(file_result)

        if file_result["fixed"]:
            results["fixed_files"] += 1
            print(f"  ✓ Fixed {len(file_result['changes'])} imports")
        elif file_result["errors"]:
            results["error_files"] += 1
            print(f"  ✗ Errors: {file_result['errors']}")
        else:
            print("  - No changes needed")

    # Create summary
    results["summary"] = {
        "fix_rate": results["fixed_files"] / results["total_files"]
        if results["total_files"] > 0
        else 0,
        "total_changes": sum(len(r["changes"]) for r in results["file_results"]),
        "total_errors": sum(len(r["errors"]) for r in results["file_results"]),
    }

    return results


def fix_specific_imports():
    """
    Fix specific known import issues
    """
    fixes = [
        {
            "file": "api/services/article_processing_service.py",
            "old": "from .deduplication_integration_service import DeduplicationIntegrationService",
            "new": "from services.deduplication_integration_service import DeduplicationIntegrationService",
        },
        {
            "file": "api/services/rss_fetcher_service.py",
            "old": "from .rss_service import RSSService",
            "new": "from services.rss_service import RSSService",
        },
    ]

    for fix in fixes:
        file_path = os.path.join(PROJECT_ROOT, fix["file"])
        if os.path.exists(file_path):
            print(f"Fixing: {fix['file']}")
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()

                if fix["old"] in content:
                    content = content.replace(fix["old"], fix["new"])

                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)

                    print(f"  ✓ Fixed: {fix['old']} -> {fix['new']}")
                else:
                    print(f"  - Pattern not found: {fix['old']}")

            except Exception as e:
                print(f"  ✗ Error: {e}")
        else:
            print(f"  - File not found: {fix['file']}")


def main():
    """Main function to run import fixes"""
    print("News Intelligence System v3.3.0 - Import Path Fixer")
    print("=" * 60)

    # First, validate current state
    print("\n1. Validating current imports...")
    validation_results = validate_all_imports()

    print(f"Total files: {validation_results['total_files']}")
    print(f"Valid files: {validation_results['valid_files']}")
    print(f"Invalid files: {validation_results['invalid_files']}")
    print(f"Validation rate: {validation_results['summary']['validation_rate']:.2%}")

    # Fix specific known issues
    print("\n2. Fixing specific import issues...")
    fix_specific_imports()

    # Run general import fixes
    print("\n3. Running general import fixes...")
    fix_results = fix_all_imports()

    print("\nFix Results:")
    print(f"Total files processed: {fix_results['total_files']}")
    print(f"Files fixed: {fix_results['fixed_files']}")
    print(f"Files with errors: {fix_results['error_files']}")
    print(f"Total changes made: {fix_results['summary']['total_changes']}")

    # Validate again
    print("\n4. Validating after fixes...")
    final_validation = validate_all_imports()

    print("Final validation:")
    print(f"Valid files: {final_validation['valid_files']}")
    print(f"Invalid files: {final_validation['invalid_files']}")
    print(f"Validation rate: {final_validation['summary']['validation_rate']:.2%}")

    if final_validation["summary"]["total_errors"] > 0:
        print(f"\nRemaining errors: {final_validation['summary']['total_errors']}")
        print("Files with errors:")
        for file_result in final_validation["file_results"]:
            if file_result["errors"]:
                print(f"  {file_result['file_path']}:")
                for error in file_result["errors"]:
                    print(f"    - {error}")

    print("\nImport path standardization complete!")


if __name__ == "__main__":
    main()
