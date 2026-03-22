-- Speed domain_keys overlap queries (report, commodity geo, cross-domain jobs).
CREATE INDEX IF NOT EXISTS idx_tracked_events_domain_keys_gin
  ON intelligence.tracked_events USING GIN (domain_keys);
