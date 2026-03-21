"""Unit tests for orchestrator utils — DataResult normalization."""

from domains.finance.orchestrator_utils import normalize_to_data_result
from shared.data_result import DataResult


def test_normalize_passthrough_data_result():
    """_normalize_to_data_result passes through DataResult unchanged."""
    dr = DataResult.ok([1, 2, 3])
    out = normalize_to_data_result(dr)
    assert out.success is True
    assert out.data == [1, 2, 3]


def test_normalize_raw_list():
    """_normalize_to_data_result wraps raw list in DataResult(success=True)."""
    out = normalize_to_data_result([1, 2, 3])
    assert out.success is True
    assert out.data == [1, 2, 3]


def test_normalize_raw_dict():
    """_normalize_to_data_result wraps raw dict in DataResult(success=True)."""
    d = {"sources": ["gold"]}
    out = normalize_to_data_result(d)
    assert out.success is True
    assert out.data == d


def test_normalize_none():
    """_normalize_to_data_result converts None to DataResult failure."""
    out = normalize_to_data_result(None)
    assert out.success is False
    assert "None" in (out.error or "")


def test_normalize_exception():
    """_normalize_to_data_result converts exception to DataResult failure."""
    exc = ConnectionError("network unreachable")
    out = normalize_to_data_result(exc)
    assert out.success is False
    assert "network" in (out.error or "").lower()


def test_normalize_empty_list():
    """_normalize_to_data_result wraps empty list as success."""
    out = normalize_to_data_result([])
    assert out.success is True
    assert out.data == []


def test_normalize_empty_dict():
    """_normalize_to_data_result wraps empty dict as success."""
    out = normalize_to_data_result({})
    assert out.success is True
    assert out.data == {}


def test_normalize_string_as_error():
    """_normalize_to_data_result treats bare string as error message."""
    out = normalize_to_data_result("something went wrong")
    assert out.success is False
    assert "something" in (out.error or "")


def test_normalize_data_result_fail():
    """_normalize_to_data_result passes through DataResult.fail unchanged."""
    dr = DataResult.fail("rate limit", "rate_limit")
    out = normalize_to_data_result(dr)
    assert out.success is False
    assert out.error == "rate limit"
    assert out.error_type == "rate_limit"
