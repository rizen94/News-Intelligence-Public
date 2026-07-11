# USD Purchasing Power Tracker (in vault)

## Overview
Tracks key economic indicators to monitor the purchasing power of the US dollar and inflation trends. Data is automatically updated daily via the FRED API.

## Current Values (as of LAST_UPDATED)
| Metric | Current Value | 1D Change | 7D Change | 30D Change | Status |
|--------|---------------|-----------|-----------|------------|--------|
| PDOLLAR (Purchasing Power of $1) | $VALUE | ±X% | ±X% | ±X% | 🟢/🟡/🔴 |
| CPI All Items | $VALUE | ±X% | ±X% | ±X% | 🟢/🟡/🔴 |
| Core CPI | $VALUE | ±X% | ±X% | ±X% | 🟢/🟡/🔴 |
| DXY (Dollar Strength) | $VALUE | ±X% | ±X% | ±X% | 🟢/🟡/🔴 |
| Gold Price (USD/oz) | $VALUE | ±X% | ±X% | ±X% | 🟢/🟡/🔴 |

## Historical Reference Points
| Date | PDOLLAR | CPI | Core CPI | DXY | Gold |
|------|---------|-----|----------|-----|------|
| 2020-01-01 | 100.0 | 257.97 | 260.42 | 96.55 | 1523.00 |
| 2021-01-01 | 94.12 | 261.58 | 263.01 | 89.91 | 1897.80 |
| 2022-01-01 | 88.24 | 281.14 | 276.58 | 95.82 | 1802.00 |
| 2023-01-01 | 82.35 | 296.79 | 289.48 | 103.22 | 1908.00 |
| 2024-01-01 | 77.65 | 308.42 | 299.18 | 102.24 | 2063.00 |

## Alert Thresholds
- **PDOLLAR**: Alert if < 80.0 (20% loss of purchasing power since 2020)
- **CPI YoY**: Alert if > 5.0%
- **Core CPI YoY**: Alert if > 4.0%
- **DXY**: Alert if > 110.0 or < 90.0
- **Gold**: Alert if > $2500/oz or < $1500/oz

## Trend Analysis
### Recent Trends (Last 30 Days)
- PDOLLAR: [DESCRIPTION OF TREND]
- CPI: [DESCRIPTION OF TREND]
- etc.

### Key Observations
- [INSIGHTS BASED ON DATA]

### Market Implications
- [INTERPRETATION FOR INVESTORS/POLICYMAKERS]

## Data Sources & Methodology
- **Source**: Federal Reserve Economic Data (FRED) API
- **Update Frequency**: Daily at 6:00 AM ET via automated scheduler
- **Calculation Notes**: 
  - PDOLLAR calculated as (100 / CPIAUCSL) * 100 (baseline 2020=100)
  - All values are closing values for the previous trading day
  - Percentage changes calculated using appropriate periods

## Implementation Details
- **Tracker Service**: `api/services/usd_purchasing_power_tracker_service.py`
- **FRED Client**: `api/services/fred_client_service.py` 
- **Scheduler Service**: `api/services/scheduler_service.py`
- **Data Storage**: `data/tracker_data/USD_purchasing_power.json`
- **Configuration**: Requires `FRED_API_KEY` in `.env` file

*Last updated: LAST_UPDATED*
*Next update: NEXT_SCHEDULED_UPDATE*