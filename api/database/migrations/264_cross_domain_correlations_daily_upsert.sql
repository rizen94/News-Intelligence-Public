-- 264: cross_domain_correlations daily snapshot uniqueness + collapse duplicates
-- One row per (domain_1, domain_2, correlation_type, as_of_date).

ALTER TABLE intelligence.cross_domain_correlations
  ADD COLUMN IF NOT EXISTS as_of_date date;

UPDATE intelligence.cross_domain_correlations
SET as_of_date = COALESCE(discovered_at::date, CURRENT_DATE)
WHERE as_of_date IS NULL;

ALTER TABLE intelligence.cross_domain_correlations
  ALTER COLUMN as_of_date SET DEFAULT CURRENT_DATE;

ALTER TABLE intelligence.cross_domain_correlations
  ALTER COLUMN as_of_date SET NOT NULL;

-- Keep latest row per (pair, type, day); delete extras.
DELETE FROM intelligence.cross_domain_correlations c
USING (
  SELECT correlation_id
  FROM (
    SELECT correlation_id,
           ROW_NUMBER() OVER (
             PARTITION BY domain_1, domain_2, correlation_type, as_of_date
             ORDER BY discovered_at DESC NULLS LAST, correlation_id DESC
           ) AS rn
    FROM intelligence.cross_domain_correlations
  ) ranked
  WHERE rn > 1
) doomed
WHERE c.correlation_id = doomed.correlation_id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_cross_domain_correlations_pair_type_day
  ON intelligence.cross_domain_correlations (domain_1, domain_2, correlation_type, as_of_date);

CREATE INDEX IF NOT EXISTS idx_cross_domain_correlations_as_of_date
  ON intelligence.cross_domain_correlations (as_of_date DESC);
