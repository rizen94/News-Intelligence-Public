-- Migration 128: Add Official Government and SEC RSS Feeds
-- Adds high-quality primary source feeds to appropriate domains

-- Finance Domain Feeds
INSERT INTO finance.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
VALUES 
    ('SEC Press Releases', 'https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=100&output=atom', true, 3600, NOW()),
    ('Federal Reserve Press Releases', 'https://www.federalreserve.gov/feeds/press_all.xml', true, 3600, NOW()),
    ('Treasury Direct Announcements', 'https://www.treasurydirect.gov/rss/announcements.xml', true, 3600, NOW()),
    ('FDIC News Releases', 'https://www.fdic.gov/news/news/press/feed.xml', true, 3600, NOW())
ON CONFLICT (feed_url) DO NOTHING;

-- Politics Domain Feeds
INSERT INTO politics.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
VALUES 
    ('White House Briefings', 'https://www.whitehouse.gov/briefing-room/feed/', true, 3600, NOW()),
    ('Department of State Press Releases', 'https://www.state.gov/rss-feed/press-releases/feed/', true, 3600, NOW()),
    ('Department of Justice Press Releases', 'https://www.justice.gov/opa/rss/doj-press-releases.xml', true, 3600, NOW()),
    ('Department of Defense News', 'https://www.defense.gov/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=944&max=20', true, 3600, NOW()),
    ('Congressional Research Service', 'https://crsreports.congress.gov/rss', true, 3600, NOW()),
    ('GAO Reports', 'https://www.gao.gov/rss/reports.xml', true, 3600, NOW()),
    ('CBO Publications', 'https://www.cbo.gov/rss/publications.xml', true, 3600, NOW())
ON CONFLICT (feed_url) DO NOTHING;

-- Science-Tech Domain Feeds
INSERT INTO science_tech.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
VALUES 
    ('NASA News', 'https://www.nasa.gov/rss/dyn/breaking_news.rss', true, 3600, NOW()),
    ('NIST News', 'https://www.nist.gov/news-events/news/feed', true, 3600, NOW()),
    ('Department of Energy News', 'https://www.energy.gov/feeds/all', true, 3600, NOW()),
    ('NIH News Releases', 'https://www.nih.gov/news-events/news-releases/rss', true, 3600, NOW())
ON CONFLICT (feed_url) DO NOTHING;

-- Note: Some feeds may need URL validation or may not have RSS feeds available
-- The ON CONFLICT clause ensures we don't duplicate existing feeds

