-- Migration 173: Expand science_tech RSS — universities, journals, agencies, research news
-- Public RSS/Atom feeds; ON CONFLICT avoids duplicates when re-run.

INSERT INTO science_tech.rss_feeds (feed_name, feed_url, is_active, fetch_interval_seconds, created_at)
SELECT v.feed_name, v.feed_url, v.is_active, v.fetch_interval_seconds, NOW()
FROM (VALUES
    ('MIT News', 'https://news.mit.edu/rss', true, 3600),
    ('Stanford News', 'https://news.stanford.edu/feed/', true, 3600),
    ('Harvard Gazette', 'https://news.harvard.edu/gazette/feed/', true, 3600),
    ('Berkeley News', 'https://news.berkeley.edu/feed/', true, 3600),
    ('Caltech News', 'https://www.caltech.edu/about/news/rss.xml', true, 3600),
    ('Nature News', 'https://www.nature.com/nature.rss', true, 3600),
    ('Science (AAAS) News', 'https://www.science.org/rss/news_current.xml', true, 3600),
    ('IEEE Spectrum', 'https://spectrum.ieee.org/rss/fulltext', true, 3600),
    ('Ars Technica Science', 'https://feeds.arstechnica.com/arstechnica/science/', true, 3600),
    ('NSF News', 'https://www.nsf.gov/rss/news.xml', true, 3600),
    ('Phys.org', 'https://phys.org/rss-feed/', true, 3600),
    ('MIT Technology Review', 'https://www.technologyreview.com/feed/', true, 3600),
    ('CDC Media', 'https://www.cdc.gov/media/rss.xml', true, 3600),
    ('Scientific American', 'https://rss.sciam.com/ScientificAmerican-News', true, 3600),
    ('New Scientist', 'https://www.newscientist.com/feed/home', true, 3600),
    ('Medical Xpress', 'https://medicalxpress.com/rss-feed/', true, 3600),
    ('Space.com', 'https://www.space.com/feeds/all', true, 3600),
    ('ScienceDaily Top', 'https://www.sciencedaily.com/rss/top.xml', true, 3600)
) AS v(feed_name, feed_url, is_active, fetch_interval_seconds)
WHERE NOT EXISTS (SELECT 1 FROM science_tech.rss_feeds f WHERE f.feed_url = v.feed_url);
