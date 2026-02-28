#!/usr/bin/env python3
"""
Verify finance/API environment — report missing packages with install commands.
Run from project root: python scripts/verify_environment.py
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_DIR = PROJECT_ROOT / "api"
sys.path.insert(0, str(API_DIR))
os.chdir(API_DIR)  # config, domains resolve from api dir

REQUIRED = [
    ("fastapi", "fastapi"),
    ("uvicorn", "uvicorn[standard]"),
    ("psycopg2", "psycopg2-binary"),
    ("requests", "requests"),
    ("pydantic", "pydantic"),
    ("yaml", "pyyaml"),
    ("dotenv", "python-dotenv"),
]

FINANCE_EXTRAS = [
    ("chromadb", "chromadb"),
    ("sentence_transformers", "sentence-transformers"),
    ("torch", "torch"),
    ("pandas", "pandas"),
    ("numpy", "numpy"),
]


def check(module_name: str, pip_name: str) -> bool:
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def main():
    print("Environment verification")
    print("=" * 50)
    all_ok = True
    for mod, pip in REQUIRED:
        ok = check(mod, pip)
        status = "OK" if ok else "MISSING"
        if not ok:
            all_ok = False
            print(f"  {mod}: {status} — pip install {pip}")
        else:
            print(f"  {mod}: {status}")

    print("\nFinance extras (optional):")
    for mod, pip in FINANCE_EXTRAS:
        ok = check(mod, pip)
        status = "OK" if ok else "MISSING"
        if not ok:
            print(f"  {mod}: {status} — pip install {pip}")
        else:
            print(f"  {mod}: {status}")

    if not all_ok:
        print("\nInstall missing packages: pip install -e '.[finance]' or pip install <package>")
        sys.exit(1)
    print("\nAll required packages present.")
    sys.exit(0)


if __name__ == "__main__":
    main()
