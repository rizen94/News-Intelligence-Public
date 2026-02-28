#!/usr/bin/env python3
"""
Pytest configuration and shared fixtures
"""

import pytest
import os
from unittest.mock import Mock, patch

# Set test environment
os.environ['ENVIRONMENT'] = 'test'
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_NAME'] = 'news_intelligence_test'
os.environ['DB_USER'] = 'newsapp'
os.environ['DB_PASSWORD'] = 'newsapp_password'


@pytest.fixture(scope="session")
def mock_db_connection():
    """Mock database connection for testing"""
    mock_conn = Mock()
    mock_cur = Mock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cur
    mock_conn.cursor.return_value.__exit__.return_value = None
    return mock_conn


@pytest.fixture(autouse=True)
def reset_mocks():
    """Reset mocks before each test"""
    yield
    # Cleanup if needed

