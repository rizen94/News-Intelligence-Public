#!/usr/bin/env python3
"""Restore all __init__.py package markers in the News Intelligence project.

Reads file list from git HEAD and creates bare __init__.py files (empty is sufficient for packages).
Works on both local dev machine and remote Widow server."""

import os
import subprocess
import sys

def get_init_files():
    """Get list of all tracked __init__.py files from git HEAD."""
    result = subprocess.run(
        ["git", "-C", "/home/pete/Documents/projects/news_intelligence", "ls-files"],
        capture_output=True, text=True
    )
    paths = [p for p in result.stdout.strip().splitlines() if "__init__.py" in p]
    return paths

def write_init_py(base_dir: str, rel_path: str):
    """Write an empty __init__.py at base_dir/rel_path."""
    full_path = os.path.join(base_dir, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    
    # Don't overwrite if it already has meaningful content
    if os.path.exists(full_path):
        existing = open(full_path).read()
        if existing.strip():
            print(f"SKIP (has content): {full_path}")
            return
    
    with open(full_path, "w") as f:
        # Minimal package marker
        f.write('"""Package marker."""\n')
    print(f"OK: {full_path}")

def main():
    init_files = get_init_files()
    print(f"Found {len(init_files)} __init__.py files in git HEAD")
    
    # Restore to local machine
    for f in init_files:
        write_init_py("/home/pete/Documents/projects/news_intelligence", f)
    
    # Deploy to Widow via SSH
    ssh_dir = "/opt/news-intelligence/api"
    for f in init_files:
        if not f.startswith("api/"):
            continue  # Skip non-api files (like tests/)
        write_init_py(ssh_dir, f)

if __name__ == "__main__":
    main()
