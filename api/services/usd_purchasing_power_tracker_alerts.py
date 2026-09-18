"""
Alerting mechanism for USD Purchasing Power Tracker.
Checks for threshold breaches and sends notifications.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("usd_tracker_alerts")
except Exception:
    logger = logging.getLogger(__name__)

from .usd_purchasing_power_tracker_service import USDPurchasingPowerTrackerService


class USDPurchasingPowerTrackerAlerts:
    """Alerting mechanism for USD Purchasing Power Tracker threshold breaches."""
    
    def __init__(self):
        """Initialize the alerting service."""
        self.tracker_service = USDPurchasingPowerTrackerService()
        
        # Define alert thresholds (same as in tracker service)
        self.thresholds = {
            "PDOLLAR_min": 80.0,      # 20% loss since 2020 baseline
            "CPI_YoY_max": 5.0,       # 5% year-over-year inflation
            "CORECPI_YoY_max": 4.0,   # 4% core inflation
            "DXY_max": 110.0,         # Dollar overvalued
            "DXY_min": 90.0,          # Dollar undervalued
            "GOLD_max": 2500.0,       # Gold over $2500/oz
            "GOLD_min": 1500.0        # Gold under $1500/oz
        }
    
    def check_thresholds(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Check tracker data against thresholds and return any breaches.
        
        Args:
            data: Tracker data dictionary from get_latest_data() or load_data()
            
        Returns:
            List of alert dictionaries for any threshold breaches
        """
        alerts = []
        series_data = data.get("series", {})
        
        # Check PDOLLAR (Purchasing Power of $1)
        if "PDOLLAR" in series_data:
            pdollar_value = series_data["PDOLLAR"].get("value", 0)
            if pdollar_value < self.thresholds["PDOLLAR_min"]:
                alerts.append({
                    "metric": "PDOLLAR",
                    "value": pdollar_value,
                    "threshold": self.thresholds["PDOLLAR_min"],
                    "condition": "below_minimum",
                    "message": f"Purchasing Power of $1 ({pdollar_value:.2f}) is below threshold ({self.thresholds['PDOLLAR_min']:.2f})",
                    "severity": "high",
                    "timestamp": datetime.now().isoformat()
                })
        
        # Note: For CPI and Core CPI, we would need year-over-year calculation
        # For now, we'll skip these as they require historical data comparison
        # In a production implementation, we would calculate YoY changes
        
        # Check DXY (Dollar Strength)
        if "DXY" in series_data:
            dxy_value = series_data["DXY"].get("value", 0)
            if dxy_value > self.thresholds["DXY_max"]:
                alerts.append({
                    "metric": "DXY",
                    "value": dxy_value,
                    "threshold": self.thresholds["DXY_max"],
                    "condition": "above_maximum",
                    "message": f"DXY Dollar Strength ({dxy_value:.2f}) is above threshold ({self.thresholds['DXY_max']:.2f})",
                    "severity": "medium",
                    "timestamp": datetime.now().isoformat()
                })
            elif dxy_value < self.thresholds["DXY_min"]:
                alerts.append({
                    "metric": "DXY",
                    "value": dxy_value,
                    "threshold": self.thresholds["DXY_min"],
                    "condition": "below_minimum",
                    "message": f"DXY Dollar Strength ({dxy_value:.2f}) is below threshold ({self.thresholds['DXY_min']:.2f})",
                    "severity": "medium",
                    "timestamp": datetime.now().isoformat()
                })
        
        # Check Gold Price
        if "GD1CIAMDG" in series_data:
            gold_value = series_data["GD1CIAMDG"].get("value", 0)
            if gold_value > self.thresholds["GOLD_max"]:
                alerts.append({
                    "metric": "GD1CIAMDG",
                    "value": gold_value,
                    "threshold": self.thresholds["GOLD_max"],
                    "condition": "above_maximum",
                    "message": f"Gold Price (${gold_value:.2f}/oz) is above threshold (${self.thresholds['GOLD_max']:.2f}/oz)",
                    "severity": "medium",
                    "timestamp": datetime.now().isoformat()
                })
            elif gold_value < self.thresholds["GOLD_min"]:
                alerts.append({
                    "metric": "GD1CIAMDG",
                    "value": gold_value,
                    "threshold": self.thresholds["GOLD_min"],
                    "condition": "below_minimum",
                    "message": f"Gold Price (${gold_value:.2f}/oz) is below threshold (${self.thresholds['GOLD_min']:.2f}/oz)",
                    "severity": "medium",
                    "timestamp": datetime.now().isoformat()
                })
        
        return alerts
    
    def send_alerts(self, alerts: List[Dict[str, Any]]) -> bool:
        """
        Send alerts via configured channels.
        
        Args:
            alerts: List of alert dictionaries to send
            
        Returns:
            bool: True if all alerts were processed successfully
        """
        if not alerts:
            return True
            
        success = True
        for alert in alerts:
            try:
                # Log the alert
                log_msg = f"[{alert['severity'].upper()}] {alert['message']}"
                if alert["severity"] == "high":
                    logger.error(log_msg)
                elif alert["severity"] == "medium":
                    logger.warning(log_msg)
                else:
                    logger.info(log_msg)
                
                # In a full implementation, we would also send via:
                # - Email
                # - Slack/webhook
                # - SMS
                # - etc.
                
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
                success = False
        
        return success
    
    def check_and_alert(self) -> List[Dict[str, Any]]:
        """
        Check current tracker data for threshold breaches and send alerts.
        
        Returns:
            List of alert dictionaries that were triggered
        """
        try:
            # Load current tracker data
            data = self.tracker_service.load_data()
            
            # Check for threshold breaches
            alerts = self.check_thresholds(data)
            
            # Send alerts if any were found
            if alerts:
                self.send_alerts(alerts)
                logger.info(f"Generated {len(alerts)} alerts for USD Purchasing Power Tracker")
            else:
                logger.debug("No threshold breaches detected in USD Purchasing Power Tracker")
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking thresholds for USD Purchasing Power Tracker: {e}")
            return []


def check_usd_purchasing_power_tracker_alerts() -> List[Dict[str, Any]]:
    """
    Convenience function to check for and send USD Purchasing Power Tracker alerts.
    
    Returns:
        List of alert dictionaries that were triggered
    """
    alert_service = USDPurchasingPowerTrackerAlerts()
    return alert_service.check_and_alert()


if __name__ == "__main__":
    # Allow running directly for testing
    alerts = check_usd_purchasing_power_tracker_alerts()
    if alerts:
        print(f"Generated {len(alerts)} alerts:")
        for alert in alerts:
            print(f"  [{alert['severity'].upper()}] {alert['message']}")
    else:
        print("No alerts generated.")