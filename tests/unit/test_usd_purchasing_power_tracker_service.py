"""
Unit tests for USD Purchasing Power Tracker Service.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from api.services.usd_purchasing_power_tracker_service import (
    USDPurchasingPowerTrackerService,
    update_usd_purchasing_power_tracker
)


class TestUSDPurchasingPowerTrackerService:
    """Test cases for USDPurchasingPowerTrackerService."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "test_tracker_data"
        self.service = USDPurchasingPowerTrackerService(data_dir=str(self.data_dir))

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_creates_directories(self):
        """Test that initialization creates necessary directories."""
        assert self.data_dir.exists()
        assert Path("40_Reference/Trackers").exists()

    def test_get_default_data(self):
        """Test getting default data structure."""
        data = self.service._get_default_data()
        assert "last_updated" in data
        assert "series" in data
        assert "historical_references" in data
        assert isinstance(data["series"], dict)
        assert isinstance(data["historical_references"], dict)

    def test_load_data_file_exists(self):
        """Test loading data when file exists."""
        # Create test data file
        test_data = {
            "last_updated": "2024-01-01T00:00:00",
            "series": {"TEST": {"value": 100.0}},
            "historical_references": {}
        }
        self.service.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.service.data_file, 'w') as f:
            json.dump(test_data, f)
        
        # Load data
        loaded_data = self.service.load_data()
        assert loaded_data == test_data

    def test_load_data_file_not_exists(self):
        """Test loading data when file doesn't exist."""
        # Ensure file doesn't exist
        if self.service.data_file.exists():
            self.service.data_file.unlink()
        
        # Load data
        loaded_data = self.service.load_data()
        assert loaded_data == self.service._get_default_data()

    def test_save_data(self):
        """Test saving data to file."""
        test_data = {
            "last_updated": "2024-01-01T00:00:00",
            "series": {"TEST": {"value": 100.0}},
            "historical_references": {}
        }
        
        result = self.service.save_data(test_data)
        assert result is True
        assert self.service.data_file.exists()
        
        # Verify content
        with open(self.service.data_file, 'r') as f:
            loaded_data = json.load(f)
        assert loaded_data == test_data

    def test_save_data_failure(self):
        """Test saving data handles errors gracefully."""
        # Make directory read-only to cause write failure
        self.service.data_file.parent.chmod(0o444)
        
        try:
            test_data = {"test": "data"}
            result = self.service.save_data(test_data)
            assert result is False
        finally:
            # Restore permissions for cleanup
            self.service.data_file.parent.chmod(0o755)

    @patch('api.services.usd_purchasing_power_tracker_service.FREDClientService')
    def test_fetch_latest_data_success(self, mock_fred_client_class):
        """Test fetching latest data successfully."""
        # Setup mock FRED client
        mock_fred_client = Mock()
        mock_fred_client_class.return_value = mock_fred_client
        mock_fred_client.is_available.return_value = True
        
        # Mock responses for each series
        def mock_get_latest_observation(series_id):
            if series_id == "CPIAUCSL":
                return {"date": "2024-01-15", "value": "120.0"}
            elif series_id == "CORECPIAUCSL":
                return {"date": "2024-01-15", "value": "115.0"}
            elif series_id == "DTWEXBGS":
                return {"date": "2024-01-15", "value": "105.0"}
            elif series_id == "GD1CIAMDG":
                return {"date": "2024-01-15", "value": "1800.0"}
            return None
        
        mock_fred_client.get_latest_observation.side_effect = mock_get_latest_observation
        
        # Replace the service's fred_client with our mock
        self.service.fred_client = mock_fred_client
        
        # Execute
        result = self.service.fetch_latest_data()
        
        # Assertions
        assert "PDOLLAR" in result
        assert "CPIAUCSL" in result
        assert "CORECPIAUCSL" in result
        assert "DXY" in result
        assert "GD1CIAMDG" in result
        
        # Check PDOLLAR calculation (should be (257.97/120.0)*100)
        expected_pdollar = round((257.97 / 120.0) * 100, 2)
        assert result["PDOLLAR"]["value"] == expected_pdollar
        assert result["CPIAUCSL"]["value"] == 120.0
        assert result["CORECPIAUCSL"]["value"] == 115.0
        assert result["DXY"]["value"] == 105.0
        assert result["GD1CIAMDG"]["value"] == 1800.0

    @patch('api.services.usd_purchasing_power_tracker_service.FREDClientService')
    def test_fetch_latest_data_client_unavailable(self, mock_fred_client_class):
        """Test fetching latest data when FRED client unavailable."""
        # Setup mock FRED client as unavailable
        mock_fred_client = Mock()
        mock_fred_client_class.return_value = mock_fred_client
        mock_fred_client.is_available.return_value = False
        
        # Replace the service's fred_client with our mock
        self.service.fred_client = mock_fred_client
        
        # Execute
        result = self.service.fetch_latest_data()
        
        # Should return fallback data
        assert "PDOLLAR" in result
        assert result["PDOLLAR"]["value"] == 85.42  # fallback value
        assert result["PDOLLAR"]["source"] == "fallback"

    def test_determine_status(self):
        """Test status determination based on thresholds."""
        # Test PDOLLAR above threshold
        status = self.service.determine_status("PDOLLAR", 85.0)
        assert status == "🟢"  # Green
        
        # Test PDOLLAR below threshold
        status = self.service.determine_status("PDOLLAR", 75.0)
        assert status == "🔴"  # Red
        
        # Test DXY within range
        status = self.service.determine_status("DXY", 100.0)
        assert status == "🟢"  # Green
        
        # Test DXY above max
        status = self.service.determine_status("DXY", 115.0)
        assert status == "🔴"  # Red
        
        # Test DXY below min
        status = self.service.determine_status("DXY", 85.0)
        assert status == "🔴"  # Red
        
        # Test Gold within range
        status = self.service.determine_status("GD1CIAMDG", 2000.0)
        assert status == "🟢"  # Green
        
        # Test Gold above max
        status = self.service.determine_status("GD1CIAMDG", 2600.0)
        assert status == "🔴"  # Red
        
        # Test Gold below min
        status = self.service.determine_status("GD1CIAMDG", 1400.0)
        assert status == "🔴"  # Red

    def test_generate_markdown(self):
        """Test markdown generation."""
        test_data = {
            "last_updated": "2024-01-15T10:30:00",
            "series": {
                "PDOLLAR": {"value": 85.42, "date": "2024-01-15", "source": "calculated_from_CPIAUCSL"},
                "CPIAUCSL": {"value": 120.0, "date": "2024-01-15", "source": "FRED"},
                "CORECPIAUCSL": {"value": 115.0, "date": "2024-01-15", "source": "FRED"},
                "DXY": {"value": 105.0, "date": "2024-01-15", "source": "FRED"},
                "GD1CIAMDG": {"value": 1800.0, "date": "2024-01-15", "source": "FRED"}
            },
            "historical_references": {}
        }
        
        markdown = self.service.generate_markdown(test_data)
        
        # Check that key elements are present
        assert "# USD Purchasing Power Tracker (in vault)" in markdown
        assert "## Current Values (as of" in markdown
        assert "PDOLLAR" in markdown
        assert "85.42" in markdown
        assert "CPIAUCSL" in markdown
        assert "120.0" in markdown
        assert "## Alert Thresholds" in markdown
        assert "## Data Sources & Methodology" in markdown

    @patch('api.services.usd_purchasing_power_tracker_service.USDPurchasingPowerTrackerService.fetch_latest_data')
    @patch('api.services.usd_purchasing_power_tracker_service.USDPurchasingPowerTrackerService.save_data')
    def test_update_tracker_success(self, mock_save_data, mock_fetch_latest_data):
        """Test successful tracker update."""
        # Setup mocks
        mock_fetch_latest_data.return_value = {
            "PDOLLAR": {"value": 85.42, "date": "2024-01-15", "source": "calculated_from_CPIAUCSL"},
            "CPIAUCSL": {"value": 120.0, "date": "2024-01-15", "source": "FRED"},
            "CORECPIAUCSL": {"value": 115.0, "date": "2024-01-15", "source": "FRED"},
            "DXY": {"value": 105.0, "date": "2024-01-15", "source": "FRED"},
            "GD1CIAMDG": {"value": 1800.0, "date": "2024-01-15", "source": "FRED"}
        }
        mock_save_data.return_value = True
        
        # Execute
        result = self.service.update_tracker()
        
        # Assertions
        assert result is True
        mock_fetch_latest_data.assert_called_once()
        mock_save_data.assert_called_once()
        
        # Check that data was saved with expected structure
        saved_data = mock_save_data.call_args[0][0]
        assert "series" in saved_data
        assert "last_updated" in saved_data
        assert saved_data["series"]["PDOLLAR"]["value"] == 85.42

    @patch('api.services.usd_purchasing_power_tracker_service.USDPurchasingPowerTrackerService.fetch_latest_data')
    @patch('api.services.usd_purchasing_power_tracker_service.USDPurchasingPowerTrackerService.save_data')
    def test_update_tracker_save_failure(self, mock_save_data, mock_fetch_latest_data):
        """Test tracker update when save fails."""
        # Setup mocks
        mock_fetch_latest_data.return_value = {
            "PDOLLAR": {"value": 85.42, "date": "2024-01-15", "source": "calculated_from_CPIAUCSL"}
        }
        mock_save_data.return_value = False  # Save fails
        
        # Execute
        result = self.service.update_tracker()
        
        # Assertions
        assert result is False
        mock_fetch_latest_data.assert_called_once()
        mock_save_data.assert_called_once()

    def test_convenience_function(self):
        """Test the convenience function."""
        with patch('api.services.usd_purchasing_power_tracker_service.USDPurchasingPowerTrackerService') as mock_service_class:
            mock_service = Mock()
            mock_service_class.return_value = mock_service
            mock_service.update_tracker.return_value = True
            
            result = update_usd_purchasing_power_tracker()
            
            assert result is True
            mock_service_class.assert_called_once()
            mock_service.update_tracker.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])