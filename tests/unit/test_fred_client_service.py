"""
Unit tests for FRED client service.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from api.services.fred_client_service import FREDClientService


class TestFREDClientService:
    """Test cases for FREDClientService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.client = FREDClientService()

    @patch('api.services.fred_client_service.get_client')
    def test_initialize_client_success(self, mock_get_client):
        """Test successful client initialization."""
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        
        client = FREDClientService()
        assert client.client == mock_client
        mock_get_client.assert_called_once()

    @patch('api.services.fred_client_service.get_client')
    def test_initialize_client_failure(self, mock_get_client):
        """Test client initialization failure."""
        mock_get_client.side_effect = Exception("Connection failed")
        
        client = FREDClientService()
        assert client.client is None

    def test_initialize_client_no_api_key(self):
        """Test client initialization with no API key."""
        with patch('api.services.fred_client_service.FRED_API_KEY', ''):
            client = FREDClientService()
            assert client.client is None

    @patch('api.services.fred_client_service.cache_get')
    @patch('api.services.fred_client_service.get_client')
    def test_get_latest_observation_from_cache(self, mock_get_client, mock_cache_get):
        """Test getting latest observation from cache."""
        # Setup mocks
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_cache_get.return_value = {
            "observations": [
                {"date": "2024-01-15", "value": "100.5"},
                {"date": "2024-01-16", "value": "101.0"}
            ]
        }
        
        client = FREDClientService()
        result = client.get_latest_observation("CPIAUCSL")
        
        # Assertions
        assert result is not None
        assert result["date"] == "2024-01-16"
        assert result["value"] == 101.0
        mock_cache_get.assert_called_once()

    @patch('api.services.fred_client_service.cache_get')
    @patch('api.services.fred_client_service.get_client')
    def test_get_latest_observation_no_cache(self, mock_get_client, mock_cache_get):
        """Test getting latest observation when cache miss."""
        # Setup mocks
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_cache_get.return_value = None
        
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = [
            {"date": "2024-01-15", "value": "100.5"},
            {"date": "2024-01-16", "value": "101.0"}
        ]
        mock_client.fetch_observations.return_value = mock_result
        
        client = FREDClientService()
        result = client.get_latest_observation("CPIAUCSL")
        
        # Assertions
        assert result is not None
        assert result["date"] == "2024-01-16"
        assert result["value"] == 101.0
        mock_client.fetch_observations.assert_called_once_with(
            series_id="CPIAUCSL",
            store=True
        )

    @patch('api.services.fred_client_service.cache_get')
    @patch('api.services.fred_client_service.get_client')
    def test_get_latest_observation_no_data(self, mock_get_client, mock_cache_get):
        """Test getting latest observation when no data available."""
        # Setup mocks
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_cache_get.return_value = None
        
        mock_result = Mock()
        mock_result.success = False
        mock_result.data = []
        mock_client.fetch_observations.return_value = mock_result
        
        client = FREDClientService()
        result = client.get_latest_observation("CPIAUCSL")
        
        # Assertions
        assert result is None

    @patch('api.services.fred_client_service.get_client')
    def test_get_latest_observation_client_unavailable(self, mock_get_client):
        """Test getting latest observation when client unavailable."""
        # Setup mocks
        mock_get_client.return_value = None
        
        client = FREDClientService()
        result = client.get_latest_observation("CPIAUCSL")
        
        # Assertions
        assert result is None

    @patch('api.services.fred_client_service.cache_get')
    @patch('api.services.fred_client_service.get_client')
    def test_get_historical_data(self, mock_get_client, mock_cache_get):
        """Test getting historical data."""
        # Setup mocks
        mock_client = Mock()
        mock_get_client.return_value = mock_client
        mock_cache_get.return_value = None
        
        mock_result = Mock()
        mock_result.success = True
        mock_result.data = [
            {"date": "2024-01-01", "value": "100.0"},
            {"date": "2024-01-02", "value": "100.5"},
            {"date": "2024-01-03", "value": "."},  # Invalid value to filter out
            {"date": "2024-01-04", "value": "101.0"}
        ]
        mock_client.fetch_observations.return_value = mock_result
        
        client = FREDClientService()
        result = client.get_historical_data("CPIAUCSL", days_back=30)
        
        # Assertions
        assert len(result) == 3  # One invalid value filtered out
        assert result[0]["date"] == "2024-01-01"
        assert result[0]["value"] == 100.0
        assert result[1]["date"] == "2024-01-02"
        assert result[1]["value"] == 100.5
        assert result[2]["date"] == "2024-01-04"
        assert result[2]["value"] == 101.0
        # Check sorted by date
        assert result[0]["date"] <= result[1]["date"] <= result[2]["date"]

    def test_calculate_purchasing_power(self):
        """Test purchasing power calculation."""
        client = FREDClientService()
        
        # Test normal calculation
        result = client.calculate_purchasing_power(120.0, 100.0)
        assert result == 83.33  # (100/120)*100
        
        # Test edge case
        result = client.calculate_purchasing_power(0.0)
        assert result == 0.0

    @patch('api.services.fred_client_service.get_latest_observation')
    @patch('api.services.fred_client_service.calculate_purchasing_power')
    def test_fetch_all_indicators_success(self, mock_calc_pp, mock_get_latest):
        """Test fetching all indicators successfully."""
        # Setup mocks
        mock_get_latest.side_effect = [
            {"date": "2024-01-15", "value": 120.0},  # CPIAUCSL
            {"date": "2024-01-15", "value": 115.0},  # CORECPIAUCSL
            {"date": "2024-01-15", "value": 105.0},  # DXY
            {"date": "2024-01-15", "value": 1800.0}  # GD1CIAMDG
        ]
        mock_calc_pp.return_value = 83.33
        
        client = FREDClientService()
        result = client.fetch_all_indicators()
        
        # Assertions
        assert "timestamp" in result
        assert "indicators" in result
        assert "errors" in result
        assert len(result["errors"]) == 0
        assert "PDOLLAR" in result["indicators"]
        assert result["indicators"]["PDOLLAR"]["value"] == 83.33
        assert result["indicators"]["CPIAUCSL"]["value"] == 120.0
        assert result["indicators"]["CORECPIAUCSL"]["value"] == 115.0
        assert result["indicators"]["DXY"]["value"] == 105.0
        assert result["indicators"]["GD1CIAMDG"]["value"] == 1800.0

    @patch('api.services.fred_client_service.get_latest_observation')
    def test_fetch_all_indicators_partial_failure(self, mock_get_latest):
        """Test fetching indicators with some failures."""
        # Setup mocks - CPI fails, others succeed
        mock_get_latest.side_effect = [
            Exception("API error"),  # CPIAUCSL fails
            {"date": "2024-01-15", "value": 115.0},  # CORECPIAUCSL succeeds
            {"date": "2024-01-15", "value": 105.0},  # DXY succeeds
            {"date": "2024-01-15", "value": 1800.0}  # GD1CIAMDG succeeds
        ]
        
        client = FREDClientService()
        result = client.fetch_all_indicators()
        
        # Assertions
        assert len(result["errors"]) == 1
        assert "CPIAUCSL" in result["errors"][0]
        assert "PDOLLAR" not in result["indicators"]  # Should not be calculated if CPI fails
        assert "CORECPIAUCSL" in result["indicators"]
        assert "DXY" in result["indicators"]
        assert "GD1CIAMDG" in result["indicators"]

    def test_calculate_changes_insufficient_data(self):
        """Test calculating changes with insufficient data."""
        client = FREDClientService()
        result = client.calculate_changes(100.0, [])
        assert result == {"1d": 0.0, "7d": 0.0, "30d": 0.0}
        
        result = client.calculate_changes(100.0, [50.0])  # Only 1 day
        assert result == {"1d": 0.0, "7d": 0.0, "30d": 0.0}

    def test_calculate_changes_sufficient_data(self):
        """Test calculating changes with sufficient data."""
        client = FREDClientService()
        # Historical data: [1 day ago, 7 days ago, 30 days ago]
        historical = [90.0, 80.0, 70.0]  # 10% increase 1d, 25% increase 7d, ~43% increase 30d
        result = client.calculate_changes(100.0, historical)
        
        assert result["1d"] == 11.11  # (100-90)/90 * 100
        assert result["7d"] == 25.0   # (100-80)/80 * 100
        assert result["30d"] == 42.86  # (100-70)/70 * 100

    def test_calculate_changes_zero_division(self):
        """Test calculating changes avoids division by zero."""
        client = FREDClientService()
        historical = [0.0, 80.0, 70.0]  # 1 day ago is 0
        result = client.calculate_changes(100.0, historical)
        
        assert result["1d"] == 0.0  # Should handle zero division
        assert result["7d"] == 25.0   # (100-80)/80 * 100
        assert result["30d"] == 42.86  # (100-70)/70 * 100