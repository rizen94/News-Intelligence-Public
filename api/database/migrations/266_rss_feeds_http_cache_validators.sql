-- Add HTTP cache validators for conditional RSS GETs (ETag / Last-Modified).
-- Applied to all pipeline-active domain schemas.

DO $$
DECLARE
    schemas text[] := ARRAY[
        'legal',
        'medicine',
        'artificial_intelligence',
        'politics',
        'finance'
    ];
    schema text;
BEGIN
    FOREACH schema IN ARRAY schemas
    LOOP
        EXECUTE format(
            $f$
            ALTER TABLE %I.rss_feeds
                ADD COLUMN IF NOT EXISTS http_etag text,
                ADD COLUMN IF NOT EXISTS http_last_modified text
            $f$,
            schema
        );
        EXECUTE format(
            $f$
            COMMENT ON COLUMN %I.rss_feeds.http_etag IS
                'Last ETag from feed HTTP response; used for If-None-Match'
            $f$,
            schema
        );
        EXECUTE format(
            $f$
            COMMENT ON COLUMN %I.rss_feeds.http_last_modified IS
                'Last-Modified header value; used for If-Modified-Since'
            $f$,
            schema
        );
    END LOOP;
END $$;
