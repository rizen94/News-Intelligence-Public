from unittest.mock import MagicMock, patch

from nri_core.evidence.entity_bridge import bridge_auto_link, upsert_entity_bridge


def test_bridge_auto_link_calls_upsert_and_cache():
    with patch("nri_core.evidence.entity_bridge.upsert_entity_bridge") as upsert, patch(
        "nri_core.evidence.entity_bridge.sync_ftm_entity_cache"
    ) as sync:
        bridge_auto_link(42, "abc123", 0.95)
        upsert.assert_called_once_with(42, "abc123", 0.95)
        sync.assert_called_once_with("abc123")


def test_upsert_entity_bridge_executes_sql():
    mock_conn = MagicMock()
    mock_cur = MagicMock()
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

    with patch("nri_core.evidence.entity_bridge.ni_reader.news_intel_connection") as ctx:
        ctx.return_value.__enter__ = MagicMock(return_value=mock_conn)
        ctx.return_value.__exit__ = MagicMock(return_value=False)
        upsert_entity_bridge(1, "ftm-x", 0.92)

    assert mock_cur.execute.called
    assert mock_conn.commit.called
