"""UIE topic_tags must write article_keywords.source (not missing in_headline)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "api"))

from services.unified_intake_extraction_service import _store_topic_tags  # noqa: E402


def test_store_topic_tags_uses_source_column_not_in_headline():
    cur = MagicMock()
    conn = MagicMock()
    cur.connection = conn
    sql_holder: dict[str, str] = {}

    def _capture(cur_, conn_, name, sql, params):
        sql_holder["sql"] = sql
        sql_holder["params"] = params
        return True

    with patch(
        "shared.pg_savepoint.execute_with_savepoint",
        side_effect=_capture,
    ):
        _store_topic_tags(
            cur,
            "legal",
            123,
            [{"keyword": "lien", "type": "subject", "confidence": 0.9, "in_headline": True}],
        )

    sql = sql_holder["sql"]
    assert "in_headline" not in sql
    assert "source" in sql
    assert sql_holder["params"] == (123, "lien", "subject", "headline", 0.9)
