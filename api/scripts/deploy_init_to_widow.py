#!/usr/bin/env python3
"""Deploy __init__.py package markers to /opt/news-intelligence on Widow."""
import os

# All tracked __init__.py files from git HEAD (excluding non-api ones)
INIT_FILES = [
    "api/__init__.py",
    "api/archive/tier5/__init__.py",
    "api/config/__init__.py",
    "api/database/__init__.py",
    "api/domains/__init__.py",
    "api/domains/content_analysis/routes/__init__.py",
    "api/domains/content_analysis/services/__init__.py",
    "api/domains/finance/__init__.py",
    "api/domains/finance/data/__init__.py",
    "api/domains/finance/data_sources/__init__.py",
    "api/domains/finance/gold_sources/__init__.py",
    "api/domains/finance/routes/__init__.py",
    "api/domains/intelligence_hub/__init__.py",
    "api/domains/intelligence_hub/routes/__init__.py",
    "api/domains/news_aggregation/routes/__init__.py",
    "api/domains/politics/__init__.py",
    "api/domains/politics/routes/__init__.py",
    "api/domains/public_auth/__init__.py",
    "api/domains/public_auth/routes/__init__.py",
    "api/domains/reader/__init__.py",
    "api/domains/reader/routes/__init__.py",
    "api/domains/reader/services/__init__.py",
    "api/domains/storyline_management/routes/__init__.py",
    "api/domains/storyline_management/schemas/__init__.py",
    "api/domains/system_monitoring/__init__.py",
    "api/domains/system_monitoring/routes/__init__.py",
    "api/domains/user_management/__init__.py",
    "api/domains/user_management/routes/__init__.py",
    "api/middleware/__init__.py",
    "api/modules/__init__.py",
    "api/modules/deduplication/__init__.py",
    "api/modules/ml/__init__.py",
    "api/services/__init__.py",
    "api/services/automation/__init__.py",
    "api/services/executors/__init__.py",
    "api/services/rag/__init__.py",
    "api/services/rss/__init__.py",
    "api/shared/__init__.py",
    "api/shared/auth/__init__.py",
    "api/shared/automation/__init__.py",
    "api/shared/database/__init__.py",
    "api/shared/http/__init__.py",
    "api/shared/kernel/__init__.py",
    "api/shared/llm/__init__.py",
    "api/shared/logging/__init__.py",
    "api/shared/middleware/__init__.py",
    "api/shared/recovery/__init__.py",
    "api/shared/services/__init__.py",
    "api/shared/utils/__init__.py",
    "api/tests/reader/__init__.py",
]

BASE = "/opt/news-intelligence"

for rel in INIT_FILES:
    full = os.path.join(BASE, rel)
    d = os.path.dirname(full)
    os.makedirs(d, exist_ok=True)
    
    if os.path.exists(full):
        content = open(full).read()
        if content.strip():
            print(f"SKIP (has content): {full}")
            continue
    
    with open(full, "w") as fh:
        fh.write('"""Package marker."""\n')
    print(f"OK: {full}")
