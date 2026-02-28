#!/bin/bash
# Add official government and SEC RSS feeds via API

BASE_URL="http://localhost:8000/api/v4"

echo "📰 Adding Official Government and SEC RSS Feeds"
echo "============================================================"

# Finance Domain Feeds
echo ""
echo "📂 FINANCE Domain:"
echo "------------------"

# SEC Press Releases
echo "Adding SEC Press Releases..."
curl -s -X POST "${BASE_URL}/rss_feeds" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_name": "SEC Press Releases",
    "feed_url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=&company=&dateb=&owner=include&start=0&count=100&output=atom",
    "is_active": true,
    "fetch_interval_seconds": 3600
  }' | python3 -m json.tool | grep -E "(success|message|feed_id)" | head -3

sleep 1

# Federal Reserve
echo "Adding Federal Reserve Press Releases..."
curl -s -X POST "${BASE_URL}/rss_feeds" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_name": "Federal Reserve Press Releases",
    "feed_url": "https://www.federalreserve.gov/feeds/press_all.xml",
    "is_active": true,
    "fetch_interval_seconds": 3600
  }' | python3 -m json.tool | grep -E "(success|message|feed_id)" | head -3

sleep 1

# Treasury Direct
echo "Adding Treasury Direct Announcements..."
curl -s -X POST "${BASE_URL}/rss_feeds" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_name": "Treasury Direct Announcements",
    "feed_url": "https://www.treasurydirect.gov/rss/announcements.xml",
    "is_active": true,
    "fetch_interval_seconds": 3600
  }' | python3 -m json.tool | grep -E "(success|message|feed_id)" | head -3

sleep 1

# Politics Domain Feeds
echo ""
echo "📂 POLITICS Domain:"
echo "-------------------"

# White House
echo "Adding White House Briefings..."
curl -s -X POST "${BASE_URL}/rss_feeds" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_name": "White House Briefings",
    "feed_url": "https://www.whitehouse.gov/briefing-room/feed/",
    "is_active": true,
    "fetch_interval_seconds": 3600
  }' | python3 -m json.tool | grep -E "(success|message|feed_id)" | head -3

sleep 1

# State Department
echo "Adding Department of State Press Releases..."
curl -s -X POST "${BASE_URL}/rss_feeds" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_name": "Department of State Press Releases",
    "feed_url": "https://www.state.gov/rss-feed/press-releases/feed/",
    "is_active": true,
    "fetch_interval_seconds": 3600
  }' | python3 -m json.tool | grep -E "(success|message|feed_id)" | head -3

sleep 1

# DOJ
echo "Adding Department of Justice Press Releases..."
curl -s -X POST "${BASE_URL}/rss_feeds" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_name": "Department of Justice Press Releases",
    "feed_url": "https://www.justice.gov/opa/rss/doj-press-releases.xml",
    "is_active": true,
    "fetch_interval_seconds": 3600
  }' | python3 -m json.tool | grep -E "(success|message|feed_id)" | head -3

sleep 1

# Science-Tech Domain Feeds
echo ""
echo "📂 SCIENCE-TECH Domain:"
echo "------------------------"

# NASA
echo "Adding NASA News..."
curl -s -X POST "${BASE_URL}/rss_feeds" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_name": "NASA News",
    "feed_url": "https://www.nasa.gov/rss/dyn/breaking_news.rss",
    "is_active": true,
    "fetch_interval_seconds": 3600
  }' | python3 -m json.tool | grep -E "(success|message|feed_id)" | head -3

sleep 1

# NSF
echo "Adding NSF News..."
curl -s -X POST "${BASE_URL}/rss_feeds" \
  -H "Content-Type: application/json" \
  -d '{
    "feed_name": "NSF News",
    "feed_url": "https://www.nsf.gov/news/news_summ.jsp?cntn_id=&org=NSF&from=news",
    "is_active": true,
    "fetch_interval_seconds": 3600
  }' | python3 -m json.tool | grep -E "(success|message|feed_id)" | head -3

echo ""
echo "✅ Feed addition complete!"
echo "============================================================"

