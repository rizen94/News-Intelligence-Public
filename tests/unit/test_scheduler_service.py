"""
Unit tests for scheduler service.
"""

import pytest
from unittest.mock import patch, MagicMock

from api.services.scheduler_service import (
    SchedulerService,
    run_usd_purchasing_power_tracker_update,
    run_daily_maintenance_tasks
)


class TestSchedulerService:
    """Test cases for SchedulerService."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = SchedulerService()

    def test_init(self):
        """Test scheduler service initialization."""
        assert self.service is not None
        assert hasattr(self.service, 'logger')

    def test_run_usd_purchasing_power_tracker_update_success(self):
        """Test successful tracker update."""
        with patch('api.services.scheduler_service.update_usd_purchasing_power_tracker', return_value=True):
            result = self.service.run_usd_purchasing_power_tracker_update()
            assert result is True

    def test_run_usd_purchasing_power_tracker_update_failure(self):
        """Test failed tracker update."""
        with patch('api.services.scheduler_service.update_usd_purchasing_power_tracker', return_value=False):
            result = self.service.run_usd_purchasing_power_tracker_update()
            assert result is False

    def test_run_usd_purchasing_power_tracker_update_exception(self):
        """Test tracker update when exception occurs."""
        with patch('api.services.scheduler_service.update_usd_purchasing_power_tracker', side_effect=Exception("Test error")):
            result = self.service.run_usd_purchasing_power_tracker_update()
            assert result is False

    def test_scheduler_health_check_healthy(self):
        """Test health check when tracker service is healthy."""
        mock_health = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00",
            "service": "usd_purchasing_power_tracker"
        }
        
        with patch('api.services.scheduler_service.USDPurchasingPowerTrackerService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            mock_service.health_check.return_value = mock_health
            
            result = self.service.scheduler_health_check()
            
            assert result["status"] == "healthy"
            assert result["service"] == "scheduler"
            assert "dependencies" in result
            assert result["dependencies"]["usd_purchasing_power_tracker"]["status"] == "healthy"

    def test_scheduler_health_check_unhealthy(self):
        """Test health check when tracker service is unhealthy."""
        mock_health = {
            "status": "unhealthy",
            "timestamp": "2024-01-01T00:00:00",
            "service": "usd_purchasing_power_tracker",
            "error": "Test error"
        }
        
        with patch('api.services.scheduler_service.USDPurchasingPowerTrackerService') as mock_service_class:
            mock_service = MagicMock()
            mock_service_class.return_value = mock_service
            mock_service.health_check.return_value = mock_health
            
            result = self.service.scheduler_health_check()
            
            assert result["status"] == "unhealthy"
            assert result["service"] == "scheduler"
            assert "dependencies" in result
            assert result["dependencies"]["usd_purchasing_power_tracker"]["status"] == "unhealthy"

    def test_scheduler_health_check_exception(self):
        """Test health check when exception occurs."""
        with patch('api.services.scheduler_service.USDPurchasingPowerTrackerService', side_effect=Exception("Import error")):
            result = self.service.scheduler_health_check()
            
            assert result["status"] == "unhealthy"
            assert "error" in result
            assert "Import error" in result["error"]

    def test_run_daily_maintenance_tasks_success(self):
        """Test successful daily maintenance tasks."""
        with patch.object(self.service, 'run_usd_purchasing_power_tracker_update', return_value=True):
            result = self.service.run_daily_maintenance_tasks()
            assert result is True

    def test_run_daily_maintenance_tasks_failure(self):
        """Test failed daily maintenance tasks."""
        with patch.object(self.service, 'run_usd_purchasing_power_tracker_update', return_value=False):
            result = self.service.run_daily_maintenance_tasks()
            assert result is False

    def test_convenience_functions(self):
        """Test convenience functions."""
        with patch('api.services.scheduler_service.scheduler_service') as mock_service:
            mock_service.run_usd_purchasing_power_tracker_update.return_value = True
            result = run_usd_purchasing_power_tracker_update()
            assert result is True
            mock_service.run_usd_purchasing_power_tracker_update.assert_called_once()

            mock_service.run_daily_maintenance_tasks.return_value = False
            result = run_daily_maintenance_tasks()
            assert result is False
            mock_service.run_daily_maintenance_tasks.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])