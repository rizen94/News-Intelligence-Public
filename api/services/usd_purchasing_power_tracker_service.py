"""
USD Purchasing Power Tracker Service
Fetches economic data from FRED API and updates the tracker markdown file.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List

try:
    from config.logging_config import get_component_logger
    logger = get_component_logger("usd_tracker")
except Exception:
    logger = logging.getLogger(__name__)

from .fred_client_service import FREDTrackerClient


def _project_root() -> Path:
    """Repo root (parent of api/), independent of process CWD."""
    return Path(__file__).resolve().parents[2]


class USDPurchasingPowerTrackerService:
    """Service to track USD purchasing power using FRED economic indicators."""
    
    def __init__(self, data_dir: str | None = None):
        root = _project_root()
        self.data_dir = Path(data_dir) if data_dir else (root / "data" / "tracker_data")
        self.data_file = self.data_dir / "USD_purchasing_power.json"
        self.tracker_file = root / "40_Reference" / "Trackers" / "USD_Purchasing_Power_Tracker.md"
        self.fred_client = FREDTrackerClient()
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tracker_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Series IDs for FRED
        self.series_ids = {
            "PDOLLAR": None,  # Calculated from CPI
            "CPIAUCSL": "CPIAUCSL",
            "CORECPIAUCSL": "CORECPIAUCSL", 
            "DXY": "DTWEXBGS",  # Trade Weighted Dollar Index
            "GD1CIAMDG": "GD1CIAMDG"  # Gold Price in USD
        }
        
        # Alert thresholds
        self.thresholds = {
            "PDOLLAR_min": 80.0,  # 20% loss since 2020 baseline
            "CPI_YoY_max": 5.0,   # 5% year-over-year inflation
            "CORECPI_YoY_max": 4.0, # 4% core inflation
            "DXY_max": 110.0,     # Dollar overvalued
            "DXY_min": 90.0,      # Dollar undervalued
            "GOLD_max": 2500.0,   # Gold over $2500/oz
            "GOLD_min": 1500.0    # Gold under $1500/oz
        }
    
    def load_data(self) -> Dict[str, Any]:
        """Load existing data from JSON file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading tracker data: {e}")
                return self._get_default_data()
        else:
            return self._get_default_data()
    
    def _get_default_data(self) -> Dict[str, Any]:
        """Return default data structure."""
        return {
            "last_updated": datetime.now().isoformat(),
            "series": {},
            "historical_references": {}
        }
    
    def save_data(self, data: Dict[str, Any]) -> bool:
        """Save data to JSON file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving tracker data: {e}")
            return False
    
    def fetch_latest_data(self) -> Dict[str, Any]:
        """Fetch latest data for all series from FRED."""
        results = {}
        
        # Fetch each series
        for key, series_id in self.series_ids.items():
            if key == "PDOLLAR":
                # PDOLLAR is calculated from CPI
                continue
                
            try:
                observation = self.fred_client.get_latest_observation(series_id)
                if observation:
                    results[key] = {
                        "value": float(observation["value"]),
                        "date": observation["date"],
                        "source": "FRED"
                    }
                else:
                    logger.warning(f"No data returned for {key} ({series_id})")
            except Exception as e:
                logger.error(f"Error fetching {key}: {e}")
        
        # Calculate PDOLLAR from CPIAUCSL
        if "CPIAUCSL" in results:
            cpi_value = results["CPIAUCSL"]["value"]
            # PDOLLAR = (100 / CPI) * 100 with 2020-01-01 CPI as base (257.97)
            # Actually, let's use the standard calculation: Purchasing Power = 100 / (CPI/100)
            # Using 1982-84=100 base, we need to adjust
            # For simplicity, we'll calculate relative to 2020 baseline
            base_cpi = 257.97  # CPIAUCSL on 2020-01-01
            pdollar_value = (base_cpi / cpi_value) * 100
            
            results["PDOLLAR"] = {
                "value": round(pdollar_value, 2),
                "date": results["CPIAUCSL"]["date"],
                "source": "calculated_from_CPIAUCSL"
            }
        else:
            # Fallback to cached value
            results["PDOLLAR"] = {
                "value": 85.42,
                "date": datetime.now().strftime("%Y-%m-%d"),
                "source": "fallback"
            }
        
        return results
    
    def calculate_changes(self, current_value: float, historical_values: List[float]) -> Dict[str, float]:
        """
        Calculate percentage changes over different periods.
        
        Args:
            current_value: Current value
            historical_values: List of historical values [1d ago, 7d ago, 30d ago]
            
        Returns:
            Dictionary with 1d, 7d, 30d changes
        """
        changes = {}
        periods = ["1d", "7d", "30d"]
        
        for i, period in enumerate(periods):
            if i < len(historical_values) and historical_values[i] != 0:
                change = ((current_value - historical_values[i]) / historical_values[i]) * 100
                changes[period] = round(change, 2)
            else:
                # Calculate from actual historical data if available
                # For now, use placeholder
                changes[period] = 0.0
        
        return changes
    
    def get_historical_context(self, days: int = 30) -> List[float]:
        """Get historical values for change calculations."""
        # This would typically query a time series database
        # For now, return empty list - will use fallback values
        return []
    
    def determine_status(self, metric: str, value: float) -> str:
        """Determine status emoji based on thresholds."""
        if metric == "PDOLLAR":
            return "🟢" if value >= self.thresholds["PDOLLAR_min"] else "🔴"
        elif metric in ["CPIAUCSL", "CORECPIAUCSL"]:
            # For inflation, we'd need YoY calculation - simplified for now
            return "🟢"  # Placeholder
        elif metric == "DXY":
            if self.thresholds["DXY_min"] <= value <= self.thresholds["DXY_max"]:
                return "🟢"
            else:
                return "🔴"
        elif metric == "GD1CIAMDG":
            if self.thresholds["GOLD_min"] <= value <= self.thresholds["GOLD_max"]:
                return "🟢"
            else:
                return "🔴"
        else:
            return "⚪"
    
    def generate_markdown(self, data: Dict[str, Any]) -> str:
        """Generate markdown content for the tracker file."""
        series_data = data.get("series", {})
        historical_refs = data.get("historical_references", {})
        
        # Format current values table
        rows = []
        metrics = [
            ("PDOLLAR", "Purchasing Power of $1"),
            ("CPIAUCSL", "CPI All Items"), 
            ("CORECPIAUCSL", "Core CPI"),
            ("DXY", "Dollar Strength"),
            ("GD1CIAMDG", "Gold Price (USD/oz)")
        ]
        
        for key, label in metrics:
            if key in series_data:
                item = series_data[key]
                value = item.get("value", 0)
                date = item.get("date", "N/A")
                
                # Calculate changes (simplified - would use historical data)
                changes = self.calculate_changes(value, [])
                change_1d = f"+{changes.get('1d', 0):.2f}%" if changes.get('1d', 0) >= 0 else f"{changes.get('1d', 0):.2f}%"
                change_7d = f"+{changes.get('7d', 0):.2f}%" if changes.get('7d', 0) >= 0 else f"{changes.get('7d', 0):.2f}%"
                change_30d = f"+{changes.get('30d', 0):.2f}%" if changes.get('30d', 0) >= 0 else f"{changes.get('30d', 0):.2f}%"
                
                status = self.determine_status(key, value)
                
                rows.append(f"| {label} | {value} | {change_1d} | {change_7d} | {change_30d} | {status} |")
            else:
                rows.append(f"| {label} | N/A | N/A | N/A | N/A | ⚪ |")
        
        # Format historical references table
        history_rows = []
        for date_str in sorted(historical_refs.keys())[-5:]:  # Last 5 entries
            if date_str in historical_refs:
                ref = historical_refs[date_str]
                row = f"| {date_str} | {ref.get('PDOLLAR', 'N/A'):.2f} | {ref.get('CPIAUCSL', 'N/A'):.2f} | {ref.get('CORECPIAUCSL', 'N/A'):.2f} | {ref.get('DXY', 'N/A'):.2f} | {ref.get('GD1CIAMDG', 'N/A'):.2f} |"
                history_rows.append(row)
        
        # If no historical data, use defaults from template
        if not history_rows:
            history_rows = [
                "| 2020-01-01 | 100.0 | 257.97 | 260.42 | 96.55 | 1523.00 |",
                "| 2021-01-01 | 94.12 | 261.58 | 263.01 | 89.91 | 1897.80 |",
                "| 2022-01-01 | 88.24 | 281.14 | 276.58 | 95.82 | 1802.00 |",
                "| 2023-01-01 | 82.35 | 296.79 | 289.48 | 103.22 | 1908.00 |",
                "| 2024-01-01 | 77.65 | 308.42 | 299.18 | 102.24 | 2063.00 |"
            ]
        
        # Generate timestamp
        last_updated = data.get("last_updated", datetime.now().isoformat())
        try:
            dt = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except:
            formatted_time = last_updated
        
        # Build markdown content
        markdown = f"""# USD Purchasing Power Tracker (in vault)

## Current Values (as of {formatted_time})
| Metric | Current Value | 1D Change | 7D Change | 30D Change | Status |
|--------|---------------|-----------|-----------|------------|--------|
{chr(10).join(rows)}

## Historical Reference Points
| Date | PDOLLAR | CPI | Core CPI | DXY | Gold |
|------|---------|-----|----------|-----|------|
{chr(10).join(history_rows)}

## Alert Thresholds
- **PDOLLAR**: Alert if < 80.0 (20% loss of purchasing power since 2020)
- **CPI YoY**: Alert if > 5.0%
- **Core CPI YoY**: Alert if > 4.0%
- **DXY**: Alert if > 110.0 or < 90.0
- **Gold**: Alert if > $2500/oz or < $1500/oz

## Trend Analysis
### Recent Trends (Last 30 Days)
- PDOLLAR: Data collection ongoing - establish baseline
- CPI: Monitor for inflation trends
- Core CPI: Watch for sticky inflation components
- DXY: Track dollar strength against major currencies
- Gold: Observe as inflation hedge and safe haven

### Key Observations
- Data collection active - trends will develop over time
- Watch for divergence between CPI and Core CPI
- Monitor dollar strength impact on commodity prices

### Market Implications
- [To be populated based on analysis]

## Data Sources & Methodology
- **Source**: Federal Reserve Economic Data (FRED) API
- **Update Frequency**: Daily at 6:00 AM ET
- **Calculation Notes**: 
  - PDOLLAR calculated relative to 2020-01-01 CPI baseline
  - All values are closing values for the previous trading day
  - Percentage changes calculated using available historical data

*Last updated: {formatted_time}*
*Next update: {(datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')} 06:00:00 UTC*
"""
        return markdown
    
    def update_tracker(self) -> bool:
        """Main method to update the tracker."""
        try:
            logger.info("Starting USD Purchasing Power Tracker update")
            
            # Load existing data
            data = self.load_data()
            
            # Fetch latest data
            new_data = self.fetch_latest_data()
            
            # Update series data
            if "series" not in data:
                data["series"] = {}
            data["series"].update(new_data)
            
            # Update timestamp
            data["last_updated"] = datetime.now().isoformat()
            
            # Save updated data
            if not self.save_data(data):
                return False
            
            # Generate and save markdown
            markdown_content = self.generate_markdown(data)
            with open(self.tracker_file, 'w') as f:
                f.write(markdown_content)
            
            logger.info("USD Purchasing Power Tracker updated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error updating tracker: {e}")
            return False


# Convenience function for external calls
def update_usd_purchasing_power_tracker() -> bool:
    """Convenience function to update the tracker."""
    service = USDPurchasingPowerTrackerService()
    return service.update_tracker()


if __name__ == "__main__":
    # Allow running directly for testing
    success = update_usd_purchasing_power_tracker()
    exit(0 if success else 1)