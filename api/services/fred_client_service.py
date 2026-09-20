"""
FRED client for USD Purchasing Power Tracker.
Provides methods to fetch the specific economic indicators needed for the tracker.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from domains.finance.data_sources.fred import get_client, FREDDataSource
from domains.finance.data.api_cache import FRED_TTL
from domains.finance.data.api_cache import get as cache_get
from domains.finance.data.api_cache import set as cache_set
from config.settings import FRED_API_KEY

logger = logging.getLogger(__name__)

# Series IDs for our tracker
SERIES_IDS = {
    "PDOLLAR": "PAYEMS",  # We'll calculate this from CPI
    "CPIAUCSL": "CPIAUCSL",  # CPI All Items
    "CORECPIAUCSL": "CORECPIAUCSL",  # Core CPI
    "DXY": "DTWEXBGS",  # Trade Weighted Dollar Index (DXY proxy)
    "GD1CIAMDG": "GD1CIAMDG"  # Gold Price in USD
}

# Human-readable names for display
SERIES_NAMES = {
    "PDOLLAR": "Purchasing Power of $1",
    "CPIAUCSL": "CPI All Items",
    "CORECPIAUCSL": "Core CPI",
    "DXY": "DXY (Dollar Strength)",
    "GD1CIAMDG": "Gold Price (USD/oz)"
}

class FREDTrackerClient:
    """Client for fetching data for the USD Purchasing Power Tracker."""
    
    def __init__(self):
        self.client: Optional[FREDDataSource] = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the FRED client if API key is available."""
        if not FRED_API_KEY:
            logger.warning("FRED_API_KEY not set - tracker will use cached/mock data only")
            return
        
        try:
            self.client = get_client()
            logger.info("FRED client initialized for tracker")
        except Exception as e:
            logger.error(f"Failed to initialize FRED client: {e}")
            self.client = None
    
    def is_available(self) -> bool:
        """Check if FRED client is available and configured."""
        return self.client is not None and bool(FRED_API_KEY)
    
    def get_latest_observation(self, series_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent observation for a series.
        
        Args:
            series_id: FRED series identifier
            
        Returns:
            Dictionary with date and value, or None if unavailable
        """
        if not self.is_available():
            return None
            
        try:
            # Try cache first
            cache_key = {"series_id": series_id, "start": None, "end": None}
            cached = cache_get("fred", cache_key)
            if cached:
                obs = cached.get("observations", [])
                if obs:
                    latest = obs[-1]  # Most recent
                    value = latest.get("value")
                    if value not in (".", ""):
                        return {
                            "date": latest.get("date"),
                            "value": float(value)
                        }
            
            # Fetch fresh data
            result = self.client.fetch_observations(
                series_id=series_id,
                store=True
            )
            
            if result.success and result.data:
                latest = result.data[-1]  # Most recent
                value = latest.get("value")
                if value not in (".", ""):
                    return {
                        "date": latest.get("date"),
                        "value": float(value)
                    }
            
            logger.warning(f"No valid data for series {series_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error fetching {series_id}: {e}")
            return None
    
    def get_historical_data(self, series_id: str, days_back: int = 365) -> list:
        """
        Get historical data for a series.
        
        Args:
            series_id: FRED series identifier
            days_back: Number of days of history to retrieve
            
        Returns:
            List of observations sorted by date (oldest first)
        """
        if not self.is_available():
            return []
            
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            result = self.client.fetch_observations(
                series_id=series_id,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                store=True
            )
            
            if result.success and result.data:
                # Filter out invalid values and convert
                valid_data = []
                for obs in result.data:
                    value = obs.get("value")
                    if value not in (".", ""):
                        try:
                            valid_data.append({
                                "date": obs.get("date"),
                                "value": float(value)
                            })
                        except (ValueError, TypeError):
                            continue
                return sorted(valid_data, key=lambda x: x["date"])
            
            return []
            
        except Exception as e:
            logger.error(f"Error fetching historical data for {series_id}: {e}")
            return []
    
    def calculate_purchasing_power(self, cpi_value: float, base_year_cpi: float = 258.81) -> float:
        """
        Calculate purchasing power of $1 based on CPI.
        
        Args:
            cpi_value: Current CPI value
            base_year_cpi: CPI value for base year (2024-01-01 CPIAUCSL = 308.42)
            
        Returns:
            Purchasing power index (base year = 100)
        """
        if cpi_value <= 0:
            return 0.0
        return (base_year_cpi / cpi_value) * 100
    
    def fetch_all_indicators(self) -> Dict[str, Any]:
        """
        Fetch all indicators needed for the tracker.
        
        Returns:
            Dictionary containing all indicator data with metadata
        """
        data = {
            "timestamp": datetime.now().isoformat(),
            "indicators": {},
            "errors": []
        }
        
        # Fetch each indicator
        for key, series_id in SERIES_IDS.items():
            try:
                if key == "PDOLLAR":
                    # Special handling: calculate from CPI
                    cpi_data = self.get_latest_observation("CPIAUCSL")
                    if cpi_data and cpi_data.get("value"):
                        # Use 2024-01-01 as base (CPI = 308.42 from our sample data)
                        pp_value = self.calculate_purchasing_power(cpi_data["value"], 308.42)
                        data["indicators"][key] = {
                            "value": round(pp_value, 2),
                            "date": cpi_data["date"],
                            "source": "calculated_from_CPIAUCSL"
                        }
                    else:
                        data["errors"].append(f"Could not fetch CPI for PDOLLAR calculation")
                else:
                    obs = self.get_latest_observation(series_id)
                    if obs:
                        data["indicators"][key] = {
                            "value": round(obs["value"], 2),
                            "date": obs["date"],
                            "source": "FRED"
                        }
                    else:
                        data["errors"].append(f"Could not fetch {key} ({series_id})")
            except Exception as e:
                error_msg = f"Error processing {key}: {str(e)}"
                data["errors"].append(error_msg)
                logger.error(error_msg)
        
        return data
    
    def calculate_changes(self, current_value: float, historical_data: list) -> Dict[str, float]:
        """
        Calculate percentage changes over different periods.
        
        Args:
            current_value: Current value
            historical_data: List of historical observations (date, value)
            
        Returns:
            Dictionary with 1d, 7d, 30d changes
        """
        if not historical_data or len(historical_data) < 2:
            return {"1d": 0.0, "7d": 0.0, "30d": 0.0}
        
        # Sort by date (most recent first)
        sorted_data = sorted(historical_data, key=lambda x: x["date"], reverse=True)
        
        changes = {"1d": 0.0, "7d": 0.0, "30d": 0.0}
        
        # Find closest dates for each period
        today = datetime.now()
        
        for period, days in [("1d", 1), ("7d", 7), ("30d", 30)]:
            target_date = today - timedelta(days=days)
            
            # Find closest date on or before target_date
            closest_val = None
            for point in sorted_data:
                try:
                    point_date = datetime.strptime(point["date"], "%Y-%m-%d")
                    if point_date <= target_date:
                        closest_val = point["value"]
                        break
                except ValueError:
                    continue
            
            if closest_val is not None and closest_val != 0:
                changes[period] = round(((current_value - closest_val) / closest_val) * 100, 2)
        
        return changes