"""
Unit tests for USD Purchasing Power Tracker Alerts Service.
"""

import sys
import os
from unittest.mock import Mock, patch

# Add the project root to the Python path
sys.path.insert(0, '/home/pete/Documents/projects/News Intelligence')

# Set environment variables to prevent connection issues during import
os.environ['FRED_API_KEY'] = 'test_key_for_testing'
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'test_db'
os.environ['DB_USER'] = 'test_user'
os.environ['DB_PASSWORD'] = 'test_pass'

from api.services.usd_purchasing_power_tracker_alerts import (
    USDPurchasingPowerTrackerAlerts,
    check_usd_purchasing_power_tracker_alerts
)


class TestUSDPurchasingPowerTrackerAlerts:
    """Test cases for USDPurchasingPowerTrackerAlerts."""

    def setup_method(self):
        """Set up test fixtures."""
        self.alert_service = USDPurchasingPowerTrackerAlerts()

    def test_init_creates_service(self):
        """Test that initialization creates the tracker service."""
        assert hasattr(self.alert_service, 'tracker_service')
        assert self.alert_service.thresholds["PDOLLAR_min"] == 80.0
        assert self.alert_service.thresholds["CPI_YoY_max"] == 5.0
        assert self.alert_service.thresholds["CORECPI_YoY_max"] == 4.0
        assert self.alert_service.thresholds["DXY_max"] == 110.0
        assert self.alert_service.thresholds["DXY_min"] == 90.0
        assert self.alert_service.thresholds["GOLD_max"] == 2500.0
        assert self.alert_service.thresholds["GOLD_min"] == 1500.0

    def test_check_thresholds_no_breaches(self):
        """Test checking thresholds when no breaches occur."""
        # Normal data within thresholds
        data = {
            "series": {
                "PDOLLAR": {"value": 85.0, "date": "2024-01-15"},
                "CPIAUCSL": {"value": 120.0, "date": "2024-01-15"},
                "CORECPIAUCSL": {"value": 115.0, "date": "2024-01-15"},
                "DXY": {"value": 100.0, "date": "2024-01-15"},
                "GD1CIAMDG": {"value": 2000.0, "date": "2024-01-15"}
            }
        }
        
        alerts = self.alert_service.check_thresholds(data)
        assert len(alerts) == 0

    def test_check_thresholds_pdollar_breach(self):
        """Test checking thresholds when PDOLLAR breaches minimum."""
        data = {
            "series": {
                "PDOLLAR": {"value": 75.0, "date": "2024-01-15"},  # Below 80.0 threshold
                "CPIAUCSL": {"value": 120.0, "date": "2024-01-15"},
                "CORECPIAUCSL": {"value": 115.0, "date": "2024-01-15"},
                "DXY": {"value": 100.0, "date": "2024-01-15"},
                "GD1CIAMDG": {"value": 2000.0, "date": "2024-01-15"}
            }
        }
        
        alerts = self.alert_service.check_thresholds(data)
        assert len(alerts) == 1
        assert alerts[0]["metric"] == "PDOLLAR"
        assert alerts[0]["condition"] == "below_minimum"
        assert alerts[0]["severity"] == "high"
        assert "below threshold" in alerts[0]["message"]

    def test_check_thresholds_dxy_breach(self):
        """Test checking thresholds when DXY breaches maximum."""
        data = {
            "series": {
                "PDOLLAR": {"value": 85.0, "date": "2024-01-15"},
                "CPIAUCSL": {"value": 120.0, "date": "2024-01-15"},
                "CORECPIAUCSL": {"value": 115.0, "date": "2024-01-15"},
                "DXY": {"value": 115.0, "date": "2024-01-15"},  # Above 110.0 threshold
                "GD1CIAMDG": {"value": 2000.0, "date": "2024-01-15"}
            }
        }
        
        alerts = self.alert_service.check_thresholds(data)
        assert len(alerts) == 1
        assert alerts[0]["metric"] == "DXY"
        assert alerts[0]["condition"] == "above_maximum"
        assert alerts[0]["severity"] == "medium"
        assert "above threshold" in alerts[0]["message"]

    def test_check_thresholds_gold_breach(self):
        """Test checking thresholds when Gold breaches maximum."""
        data = {
            "series": {
                "PDOLLAR": {"value": 85.0, "date": "2024-01-15"},
                "CPIAUCSL": {"value": 120.0, "date": "2024-01-15"},
                "CORECPIAUCSL": {"value": 115.0, "date": "2024-01-15"},
                "DXY": {"value": 100.0, "date": "2024-01-15"},
                "GD1CIAMDG": {"value": 2600.0, "date": "2024-01-15"}  # Above 2500.0 threshold
            }
        }
        
        alerts = self.alert_service.check_thresholds(data)
        assert len(alerts) == 1
        assert alerts[0]["metric"] == "GD1CIAMDG"
        assert alerts[0]["condition"] == "above_maximum"
        assert alerts[0]["severity"] == "medium"
        assert "above threshold" in alerts[0]["message"]

    def test_check_thresholds_multiple_breaches(self):
        """Test checking thresholds when multiple breaches occur."""
        data = {
            "series": {
                "PDOLLAR": {"value": 75.0, "date": "2024-01-15"},  # Below 80.0
                "CPIAUCSL": {"value": 120.0, "date": "2024-01-15"},
                "CORECPIAUCSL": {"value": 115.0, "date": "2024-01-15"},
                "DXY": {"value": 115.0, "date": "2024-01-15"},  # Above 110.0
                "GD1CIAMDG": {"value": 2600.0, "date": "2024-01-15"}  # Above 2500.0
            }
        }
        
        alerts = self.alert_service.check_thresholds(data)
        assert len(alerts) == 3  # PDOLLAR, DXY, and Gold breaches
        
        # Check that we have alerts for each metric
        metrics = [alert["metric"] for alert in alerts]
        assert "PDOLLAR" in metrics
        assert "DXY" in metrics
        assert "GD1CIAMDG" in metrics

    @patch('api.services.usd_purchasing_power_tracker_alerts.USDPurchasingPowerTrackerService')
    def test_check_and_alert_no_breaches(self, mock_tracker_service_class):
        """Test check_and_alert when no breaches occur."""
        # Setup mock
        mock_tracker_service = Mock()
        mock_tracker_service_class.return_value = mock_tracker_service
        mock_tracker_service.load_data.return_value = {
            "series": {
                "PDOLLAR": {"value": 85.0, "date": "2024-01-15"},
                "CPIAUCSL": {"value": 120.0, "date": "2024-01-15"},
                "CORECPIAUCSL": {"value": 115.0, "date": "2024-01-15"},
                "DXY": {"value": 100.0, "date": "2024-01-15"},
                "GD1CIAMDG": {"value": 2000.0, "date": "2024-01-15"}
            }
        }
        
        # Replace the service's tracker service with our mock
        self.alert_service.tracker_service = mock_tracker_service
        
        # Execute
        alerts = self.alert_service.check_and_alert()
        
        # Assertions
        assert len(alerts) == 0
        mock_tracker_service.load_data.assert_called_once()

    @patch('api.services.usd_purchasing_power_tracker_alerts.USDPurchasingPowerTrackerService')
    def test_check_and_alert_with_breaches(self, mock_tracker_service_class):
        """Test check_and_alert when breaches occur."""
        # Setup mock
        mock_tracker_service = Mock()
        mock_tracker_service_class.return_value = mock_tracker_service
        mock_tracker_service.load_data.return_value = {
            "series": {
                "PDOLLAR": {"value": 75.0, "date": "2024-01-15"},  # Below threshold
                "CPIAUCSL": {"value": 120.0, "date": "2024-01-15"},
                "CORECPIAUCSL": {"value": 115.0, "date": "2024-01-15"},
                "DXY": {"value": 100.0, "date": "2024-01-15"},
                "GD1CIAMDG": {"value": 2000.0, "date": "2024-01-15"}
            }
        }
        
        # Replace the service's tracker service with our mock
        self.alert_service.tracker_service = mock_tracker_service
        
        # Execute
        alerts = self.alert_service.check_and_alert()
        
        # Assertions
        assert len(alerts) == 1
        assert alerts[0]["metric"] == "PDOLLAR"
        mock_tracker_service.load_data.assert_called_once()

    def test_send_alerts_logs_correctly(self):
        """Test that send_alerts logs alerts appropriately."""
        alerts = [
            {
                "metric": "PDOLLAR",
                "value": 75.0,
                "threshold": 80.0,
                "condition": "below_minimum",
                "message": "Purchasing Power of $1 (75.00) is below threshold (80.00)",
                "severity": "high",
                "timestamp": "2024-01-15T10:30:00"
            },
            {
                "metric": "DXY",
                "value": 115.0,
                "threshold": 110.0,
                "condition": "above_maximum",
                "message": "DXY Dollar Strength (115.00) is above threshold (110.00)",
                "severity": "medium",
                "timestamp": "2024-01-15T10:30:00"
            }
        ]
        
        # This should not raise an exception
        result = self.alert_service.send_alerts(alerts)
        assert result is True


def test_convenience_function():
    """Test the convenience function."""
    with patch('api.services.usd_purchasing_power_tracker_alerts.USDPurchasingPowerTrackerAlerts') as mock_class:
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        mock_instance.check_and_alert.return_value = [{"metric": "TEST"}]
        
        result = check_usd_purchasing_power_tracker_alerts()
        
        assert len(result) == 1
        assert result[0]["metric"] == "TEST"
        mock_class.assert_called_once()
        mock_instance.check_and_alert.assert_called_once()


if __name__ == "__main__":
    # Simple test runner
    test_instance = TestUSDPurchasingPowerTrackerAlerts()
    test_instance.setup_method()
    
    print("Running USD Purchasing Power Tracker Alerts tests...")
    
    try:
        test_instance.test_init_creates_service()
        print("✓ test_init_creates_service passed")
    except Exception as e:
        print(f"✗ test_init_creates_service failed: {e}")
    
    try:
        test_instance.test_check_thresholds_no_breaches()
        print("✓ test_check_thresholds_no_breaches passed")
    except Exception as e:
        print(f"✗ test_check_thresholds_no_breaches failed: {e}")
    
    try:
        test_instance.test_check_thresholds_pdollar_breach()
        print("✓ test_check_thresholds_pdollar_breach passed")
    except Exception as e:
        print(f"✗ test_check_thresholds_pdollar_breach failed: {e}")
    
    try:
        test_instance.test_check_thresholds_dxy_breach()
        print("✓ test_check_thresholds_dxy_breach passed")
    except Exception as e:
        print(f"✗ test_check_thresholds_dxy_breach failed: {e}")
    
    try:
        test_instance.test_check_thresholds_gold_breach()
        print("✓ test_check_thresholds_gold_breach passed")
    except Exception as e:
        print(f"✗ test_check_thresholds_gold_breach failed: {e}")
    
    try:
        test_instance.test_check_thresholds_multiple_breaches()
        print("✓ test_check_thresholds_multiple_breaches passed")
    except Exception as e:
        print(f"✗ test_check_thresholds_multiple_breaches failed: {e}")
    
    try:
        test_instance.test_convenience_function()
        print("✓ test_convenience_function passed")
    except Exception as e:
        print(f"✗ test_convenience_function failed: {e}")
    
    print("Tests completed.")