"""Congress trades summary SQL must escape ILIKE %% for psycopg2 pyformat.

Bare '%purchase%' alongside a %s bind param raises IndexError at execute time
(empty or non-empty tables). See Widow post-deploy /trades/summary 500.
"""

from __future__ import annotations

import inspect
from datetime import date

from domains.politics.routes import quiver_trades as qt


def test_summary_handler_escapes_ilike_percents_for_psycopg2():
    src = inspect.getsource(qt.get_congress_trade_summary)
    assert "%%purchase%%" in src
    assert "%%sale%%" in src
    assert "%%exchange%%" in src
    assert "ILIKE '%purchase%'" not in src
    assert "ILIKE '%sale%'" not in src


def test_escaped_ilike_sql_accepts_single_bind_via_percent_format():
    """Mirrors pyformat: %% → literal %, one %s consumes the cutoff bind."""
    query = """
        SELECT COUNT(*) AS total_trades,
               SUM(CASE WHEN transaction_type ILIKE '%%purchase%%' THEN 1 ELSE 0 END) AS purchases
        FROM intelligence.quiver_congress_trades
        WHERE filed_date >= %s
    """
    cutoff = date(2026, 1, 1)
    rendered = query % (cutoff,)
    assert "ILIKE '%purchase%'" in rendered
    assert "2026-01-01" in rendered


def test_unescaped_ilike_sql_breaks_percent_format():
    query = """
        SELECT SUM(CASE WHEN transaction_type ILIKE '%purchase%' THEN 1 ELSE 0 END)
        FROM intelligence.quiver_congress_trades
        WHERE filed_date >= %s
    """
    try:
        _ = query % (date(2026, 1, 1),)
        raise AssertionError("expected percent-format failure for unescaped ILIKE")
    except (ValueError, TypeError, IndexError):
        pass
