"""Unit tests for development DB host guard."""

from __future__ import annotations

import os

import pytest

from shared.dev_guard import (
    DevGuardError,
    assert_dev_db_host_safe,
    is_development_environment,
    is_production_db_host,
)


def test_widow_ip_is_production_host():
    assert is_production_db_host("192.168.93.101")
    assert is_production_db_host("WIDOW")


def test_localhost_is_not_production():
    assert not is_production_db_host("127.0.0.1")
    assert not is_production_db_host("localhost")


def test_dev_mode_refuses_widow(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(DevGuardError):
        assert_dev_db_host_safe("192.168.93.101")


def test_dev_mode_allows_local(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    assert_dev_db_host_safe("127.0.0.1")


def test_non_dev_allows_widow(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert_dev_db_host_safe("192.168.93.101")


def test_is_development_environment(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    assert is_development_environment()
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert not is_development_environment()
