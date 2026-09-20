#!/usr/bin/env python3
"""
Verification script for USD Purchasing Power Tracker.
"""

import sys
from pathlib import Path


def check_file_exists(filepath, description):
    """Check if a file exists."""
    if filepath.exists():
        print(f"✓ {description} found: {filepath}")
        return True
    else:
        print(f"✗ {description} NOT found: {filepath}")
        return False


def check_directory_exists(dirpath, description):
    """Check if a directory exists."""
    if dirpath.exists() and dirpath.is_dir():
        print(f"✓ {description} found: {dirpath}")
        return True
    else:
        print(f"✗ {description} NOT found: {dirpath}")
        return False


def main():
    """Main verification function."""
    project_root = Path(__file__).parent.parent
    all_checks_passed = True
    
    print("Verifying USD Purchasing Power Tracker installation...")
    print("=" * 50)
    
    # Check source files
    print("\nChecking source files:")
    all_checks_passed &= check_file_exists(
        project_root / "api/services/fred_client_service.py",
        "FRED client service"
    )
    
    all_checks_passed &= check_file_exists(
        project_root / "api/services/usd_purchasing_power_tracker_service.py",
        "Tracker service"
    )
    
    all_checks_passed &= check_file_exists(
        project_root / "api/services/scheduler_service.py",
        "Scheduler service"
    )
    
    # Check directories
    print("\nChecking directories:")
    all_checks_passed &= check_directory_exists(
        project_root / "data/tracker_data",
        "Tracker data directory"
    )
    
    all_checks_passed &= check_directory_exists(
        project_root / "40_Reference/Trackers",
        "Tracker documentation directory"
    )
    
    # Check documentation files
    print("\nChecking documentation files:")
    all_checks_passed &= check_file_exists(
        project_root / "40_Reference/Trackers/USD_Purchasing_Power_Tracker.md",
        "Tracker markdown template"
    )
    
    # Check data files
    print("\nChecking data files:")
    all_checks_passed &= check_file_exists(
        project_root / "data/tracker_data/USD_purchasing_power.json",
        "Initial JSON data structure"
    )
    
    # Check test files
    print("\nChecking test files:")
    all_checks_passed &= check_file_exists(
        project_root / "tests/unit/test_fred_client_service.py",
        "FRED client service tests"
    )
    
    all_checks_passed &= check_file_exists(
        project_root / "tests/unit/test_usd_purchasing_power_tracker_service.py",
        "Tracker service tests"
    )
    
    # Check environment variables (from .env.example)
    print("\nChecking environment variables (from .env.example):")
    env_example_path = project_root / ".env.example"
    if env_example_path.exists():
        with open(env_example_path, 'r') as f:
            content = f.read()
            # Extract FRED_API_KEY mention
            if "FRED_API_KEY" in content:
                print("✓ FRED_API_KEY mentioned in .env.example")
            else:
                print("✗ FRED_API_KEY not found in .env.example")
                all_checks_passed = False
    else:
        print("✗ .env.example file not found")
        all_checks_passed = False
    
    # Summary
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("✓ All checks passed! The USD Purchasing Power Tracker appears to be properly configured.")
        print("\nNext steps:")
        print("1. Set FRED_API_KEY in your .env file (get free key at https://fred.stlouisfed.org/account/api-keys)")
        print("2. Run the tracker manually: python -c \"from api.services.usd_purchasing_power_tracker_service import update_usd_purchasing_power_tracker; update_usd_purchasing_power_tracker()\"")
        print("3. Or use the scheduler: python -c \"from api.services.scheduler_service import run_usd_purchasing_power_tracker_update; run_usd_purchasing_power_tracker_update()\"")
        return 0
    else:
        print("✗ Some checks failed. Please review the output above and fix any issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())