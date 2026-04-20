#!/usr/bin/env python3
"""
Verify all external connections from the News Intelligence venv:
- NAS database (via SSH tunnel)
- Internet (outbound HTTPS)
- Ollama (LLM service)
- Redis (optional)
"""

import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, os.path.join(_PROJECT_ROOT, "api"))

# Ensure DB env for tunnel
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5433")


def check_nas_database():
    """Verify connection to NAS PostgreSQL via SSH tunnel."""
    print("=" * 60)
    print("1. NAS Database (via SSH tunnel localhost:5433)")
    print("=" * 60)
    try:
        from shared.database.connection import get_db_connection
        conn = get_db_connection()
        if not conn:
            print("   FAILED: get_db_connection() returned None")
            return False
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        conn.close()
        print("   OK: Connected to news_intelligence database")
        return True
    except Exception as e:
        print(f"   FAILED: {e}")
        return False


def check_internet():
    """Verify outbound HTTPS connectivity."""
    print("\n" + "=" * 60)
    print("2. Internet (outbound HTTPS)")
    print("=" * 60)
    try:
        import urllib.request
        urllib.request.urlopen("https://www.google.com", timeout=10)
        print("   OK: HTTPS to google.com succeeded")
        return True
    except Exception as e:
        print(f"   FAILED: {e}")
        return False


def check_ollama():
    """Verify Ollama API is reachable."""
    print("\n" + "=" * 60)
    print("3. Ollama (LLM service localhost:11434)")
    print("=" * 60)
    try:
        import urllib.request
        req = urllib.request.Request("http://localhost:11434/api/version")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = resp.read().decode()
        print(f"   OK: Ollama reachable")
        return True
    except Exception as e:
        print(f"   FAILED: {e}")
        print("   (Start with: ollama serve)")
        return False


def check_redis():
    """Verify Redis (optional - used for caching)."""
    print("\n" + "=" * 60)
    print("4. Redis (optional)")
    print("=" * 60)
    try:
        import subprocess
        r = subprocess.run(
            ["docker", "exec", "news-intelligence-redis", "redis-cli", "ping"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if r.returncode == 0 and "PONG" in r.stdout:
            print("   OK: Redis container responding")
            return True
        print("   SKIP: Redis container not running or not found")
        return True  # Non-blocking
    except Exception as e:
        print(f"   SKIP: {e}")
        return True  # Non-blocking


def main():
    print("NEWS INTELLIGENCE — Connection Verification")
    print(f"Python: {sys.executable}")
    print()

    results = {
        "nas_database": check_nas_database(),
        "internet": check_internet(),
        "ollama": check_ollama(),
        "redis": check_redis(),
    }

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"   {name}: {status}")

    critical = ["nas_database", "internet"]
    if all(results.get(k, False) for k in critical):
        print("\nCritical connections OK. Venv can access NAS and internet.")
    else:
        print("\nSome critical connections failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
