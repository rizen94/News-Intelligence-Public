# Official Government and SEC RSS Feeds

## Summary
This document lists official government and SEC RSS feeds that should be added to the appropriate domains for high-quality primary source content.

## Finance Domain Feeds

### SEC (Securities and Exchange Commission)
1. **SEC Press Releases**
   - URL: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=100&output=atom`
   - Description: SEC official press releases and announcements
   - Priority: High (Tier 1 - Official source)

2. **SEC EDGAR Filings Feed**
   - URL: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=100&output=atom`
   - Description: SEC EDGAR company filings
   - Priority: High (Tier 1 - Official source)

### Federal Reserve
3. **Federal Reserve Press Releases**
   - URL: `https://www.federalreserve.gov/feeds/press_all.xml`
   - Description: Federal Reserve Board official press releases
   - Priority: High (Tier 1 - Official source)

### Treasury
4. **Treasury Direct Announcements**
   - URL: `https://www.treasurydirect.gov/rss/announcements.xml`
   - Description: Treasury offering announcements and updates
   - Priority: High (Tier 1 - Official source)

### Other Financial Regulators
5. **FDIC News Releases**
   - URL: `https://www.fdic.gov/news/news/press/feed.xml`
   - Description: FDIC official news releases
   - Priority: Medium (Tier 2 - Regulatory)

6. **CFTC News Releases**
   - URL: `https://www.cftc.gov/PressRoom/PressReleases/index.htm`
   - Description: Commodity Futures Trading Commission news releases
   - Priority: Medium (Tier 2 - Regulatory)

## Politics Domain Feeds

### Executive Branch
1. **White House Briefings**
   - URL: `https://www.whitehouse.gov/briefing-room/feed/`
   - Description: White House official briefings and statements
   - Priority: High (Tier 1 - Official source)

2. **Department of State Press Releases**
   - URL: `https://www.state.gov/rss-feed/press-releases/feed/`
   - Description: U.S. Department of State official press releases
   - Priority: High (Tier 1 - Official source)

3. **Department of Justice Press Releases**
   - URL: `https://www.justice.gov/opa/rss/doj-press-releases.xml`
   - Description: DOJ official press releases and announcements
   - Priority: High (Tier 1 - Official source)

4. **Department of Defense News**
   - URL: `https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=944&max=20`
   - Description: DOD official news and press releases
   - Priority: High (Tier 1 - Official source)

### Legislative Branch
5. **Congressional Research Service**
   - URL: `https://crsreports.congress.gov/rss`
   - Description: Congressional Research Service reports and analysis
   - Priority: High (Tier 1 - Official source)

6. **GAO Reports**
   - URL: `https://www.gao.gov/rss/reports.xml`
   - Description: Government Accountability Office reports
   - Priority: High (Tier 1 - Official source)

7. **CBO Publications**
   - URL: `https://www.cbo.gov/rss/publications.xml`
   - Description: Congressional Budget Office publications
   - Priority: High (Tier 1 - Official source)

## Science-Tech Domain Feeds

### Federal Science Agencies
1. **NASA News**
   - URL: `https://www.nasa.gov/rss/dyn/breaking_news.rss`
   - Description: NASA official news and press releases
   - Priority: High (Tier 1 - Official source)

2. **NSF News**
   - URL: `https://www.nsf.gov/news/news_summ.jsp?cntn_id=&org=NSF&from=news`
   - Description: National Science Foundation news
   - Priority: High (Tier 1 - Official source)

3. **NIST News**
   - URL: `https://www.nist.gov/news-events/news/feed`
   - Description: National Institute of Standards and Technology news
   - Priority: High (Tier 1 - Official source)

4. **Department of Energy News**
   - URL: `https://www.energy.gov/feeds/all`
   - Description: DOE official news and press releases
   - Priority: High (Tier 1 - Official source)

5. **NIH News Releases**
   - URL: `https://www.nih.gov/news-events/news-releases/rss`
   - Description: National Institutes of Health news releases
   - Priority: High (Tier 1 - Official source)

## Implementation Notes

### Why These Feeds Are Important
- **Primary Sources**: These are official government sources, not third-party reporting
- **High Quality**: Press releases and official statements are authoritative
- **Preserved by Filters**: Our filtering system explicitly preserves press releases, official statements, and filings
- **Regulatory Compliance**: SEC filings and regulatory announcements are critical for finance domain

### Filtering Behavior
These feeds will be:
- ✅ **Preserved** by clickbait filter (press releases are not clickbait)
- ✅ **Preserved** by ad filter (official announcements are not ads)
- ✅ **High Quality Scores**: Official sources get quality score boosts
- ✅ **High Impact Scores**: Government announcements are high-impact news

### Adding Feeds
To add these feeds, use the domain-specific schema insertion:

```sql
-- Example for finance domain
INSERT INTO finance.rss_feeds 
(feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
VALUES 
('SEC Press Releases', 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=100&output=atom', true, 3600, NOW())
ON CONFLICT (feed_url) DO NOTHING;
```

Or use the API endpoint (when domain support is added):
```bash
curl -X POST "http://localhost:8000/api/v4/{domain}/rss_feeds" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_name": "SEC Press Releases",
    "feed_url": "https://www.sec.gov/...",
    "is_active": true,
    "fetch_interval_seconds": 3600
  }'
```

## Current Status
- ✅ Filtering system implemented to preserve official sources
- ⏳ Feeds need to be added to database (pending database access)
- ✅ Collection system ready to process these feeds

