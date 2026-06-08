BEGIN;

-- Add columns to rss_feeds table for caught-up tracking
ALTER TABLE rss_feeds 
ADD COLUMN IF NOT EXISTS is_caught_up BOOLEAN DEFAULT FALSE;

ALTER TABLE rss_feeds 
ADD COLUMN IF NOT EXISTS caught_up_since TIMESTAMPTZ;

ALTER TABLE rss_feeds 
ADD COLUMN IF NOT EXISTS last_caught_up_check TIMESTAMPTZ;

-- Add indexes for better performance of caught-up queries
CREATE INDEX IF NOT EXISTS idx_rss_feeds_is_caught_up 
ON rss_feeds (is_caught_up);

CREATE INDEX IF NOT EXISTS idx_rss_feeds_caught_up_since 
ON rss_feeds (caught_up_since);

CREATE INDEX IF NOT EXISTS idx_rss_feeds_last_caught_up_check 
ON rss_feeds (last_caught_up_check);

COMMENT ON COLUMN rss_feeds.is_caught_up IS 
    'Whether this feed has processed all available content and is caught up';

COMMENT ON COLUMN rss_feeds.caught_up_since IS 
    'Timestamp when this feed became caught up';

COMMENT ON COLUMN rss_feeds.last_caught_up_check IS 
    'Timestamp of the last caught-up status check';

COMMIT;