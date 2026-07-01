#!/usr/bin/env python3
"""One-off patch for /opt/news-intelligence/api/main.py on Widow."""
from pathlib import Path

p = Path("/opt/news-intelligence/api/main.py")
text = p.read_text()

text = text.replace(
    "from domains.storyline_management.routes.storyline import main_router as storyline_management_router",
    "from domains.storyline_management.routes import router as storyline_management_router",
)

marker = '        try:\n            from domains.content_analysis.services.topic_extraction_queue_worker import ('
if "NEWS_INTEL_DISABLE_TOPIC_QUEUE_WORKERS" not in text:
    if marker not in text:
        raise SystemExit("topic worker block not found")
    replacement = '''        if env_bool("NEWS_INTEL_DISABLE_TOPIC_QUEUE_WORKERS", False):
            logger.info(
                "Topic extraction queue workers disabled (NEWS_INTEL_DISABLE_TOPIC_QUEUE_WORKERS=true)"
            )
        else:
            try:
                from domains.content_analysis.services.topic_extraction_queue_worker import ('''
    text = text.replace(marker, replacement, 1)
    text = text.replace(
        "            logger.error(f\"❌ Failed to start topic extraction queue workers: {e}\")\n    except Exception as e:\n        logger.error(f\"Failed to start automation manager: {e}\")",
        "                logger.error(f\"❌ Failed to start topic extraction queue workers: {e}\")\n    except Exception as e:\n        logger.error(f\"Failed to start automation manager: {e}\")",
        1,
    )
    # Indent the block between else: try and its except by 4 spaces
    start = text.index('                from domains.content_analysis.services.topic_extraction_queue_worker import (')
    end = text.index('                logger.error(f"❌ Failed to start topic extraction queue workers: {e}")') + len(
        '                logger.error(f"❌ Failed to start topic extraction queue workers: {e}")'
    )
    block = text[start:end]
    lines = block.splitlines()
    fixed = []
    for line in lines:
        if line.startswith("                "):
            fixed.append("    " + line)
        else:
            fixed.append(line)
    text = text[:start] + "\n".join(fixed) + text[end:]

p.write_text(text)
print("patched", p)
