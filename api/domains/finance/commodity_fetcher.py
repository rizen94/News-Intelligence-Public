"""
Commodity fetcher — silver, platinum (and gold via gold_amalgamator).
Silver/platinum are stubbed: record request to evidence ledger, return empty results
until real APIs (e.g. FreeGoldPrice.org or other precious-metals APIs) are wired.
"""

import logging
from datetime import datetime, timezone

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("finance")
except Exception:
    logger = logging.getLogger(__name__)


def fetch_commodity(
    topic: str,
    start: str | None = None,
    end: str | None = None,
    store: bool = True,
) -> dict[str, list[dict]]:
    """
    Fetch commodity data. topic in ("gold", "silver", "platinum").
    Gold delegates to gold_amalgamator. Silver/platinum: stub (record only, no external API yet).
    Returns {source_id: [obs, ...]}.
    """
    topic = (topic or "gold").lower()
    if topic == "gold":
        from domains.finance.gold_amalgamator import fetch_all
        return fetch_all(start=start, end=end, store=store)

    # Silver/platinum: stub — record that we requested, return empty. Real APIs can be added later.
    report_id = f"{topic}_fetch_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    try:
        from domains.finance.data.evidence_ledger import record as ledger_record
        ledger_record(
            report_id=report_id,
            source_type=f"{topic}_price",
            source_id=f"stub_{topic}",
            evidence_data={
                "status": "stub",
                "observations_count": 0,
                "description": f"{topic} collection requested; no external API wired yet",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except Exception as e:
        logger.debug("Commodity fetcher ledger record failed: %s", e)
    logger.info("Commodity fetcher: %s stub run (no API yet)", topic)
    return {f"stub_{topic}": []}
