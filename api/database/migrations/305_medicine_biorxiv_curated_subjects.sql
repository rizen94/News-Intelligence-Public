-- Medicine: replace bioRxiv subject=all firehose with curated clinical/translational subjects.
-- Neuroscience intentionally omitted (neurodiversity silo).
-- Safe to re-run.

BEGIN;

-- Deactivate leftover broad firehose
UPDATE medicine.rss_feeds
SET is_active = false,
    updated_at = NOW()
WHERE feed_url ILIKE '%biorxiv_xml.php?subject=all%'
  AND COALESCE(is_active, true) = true;

-- Seed curated bioRxiv subject feeds (INSERT-only; skip if URL already present)
INSERT INTO medicine.rss_feeds (feed_name, feed_url, category, is_active, created_at, updated_at)
SELECT v.feed_name, v.feed_url, 'General', true, NOW(), NOW()
FROM (VALUES
  ('bioRxiv — Pathology', 'https://connect.biorxiv.org/biorxiv_xml.php?subject=pathology'),
  ('bioRxiv — Immunology', 'https://connect.biorxiv.org/biorxiv_xml.php?subject=immunology'),
  ('bioRxiv — Microbiology', 'https://connect.biorxiv.org/biorxiv_xml.php?subject=microbiology'),
  ('bioRxiv — Pharmacology & Toxicology', 'https://connect.biorxiv.org/biorxiv_xml.php?subject=pharmacology_and_toxicology'),
  ('bioRxiv — Genetics', 'https://connect.biorxiv.org/biorxiv_xml.php?subject=genetics'),
  ('bioRxiv — Genomics', 'https://connect.biorxiv.org/biorxiv_xml.php?subject=genomics'),
  ('bioRxiv — Cancer Biology', 'https://connect.biorxiv.org/biorxiv_xml.php?subject=cancer_biology'),
  ('bioRxiv — Epidemiology', 'https://connect.biorxiv.org/biorxiv_xml.php?subject=epidemiology'),
  ('bioRxiv — Clinical Trials', 'https://connect.biorxiv.org/biorxiv_xml.php?subject=clinical_trials'),
  ('bioRxiv — Physiology', 'https://connect.biorxiv.org/biorxiv_xml.php?subject=physiology')
) AS v(feed_name, feed_url)
WHERE NOT EXISTS (
  SELECT 1 FROM medicine.rss_feeds rf WHERE rf.feed_url = v.feed_url
);

-- Re-activate curated subjects if previously deactivated
UPDATE medicine.rss_feeds
SET is_active = true,
    updated_at = NOW()
WHERE feed_url ILIKE '%biorxiv_xml.php?subject=%'
  AND feed_url NOT ILIKE '%subject=all%'
  AND feed_url NOT ILIKE '%subject=neuroscience%'
  AND COALESCE(is_active, true) = false
  AND (
    feed_url ILIKE '%subject=pathology%'
    OR feed_url ILIKE '%subject=immunology%'
    OR feed_url ILIKE '%subject=microbiology%'
    OR feed_url ILIKE '%subject=pharmacology_and_toxicology%'
    OR feed_url ILIKE '%subject=genetics%'
    OR feed_url ILIKE '%subject=genomics%'
    OR feed_url ILIKE '%subject=cancer_biology%'
    OR feed_url ILIKE '%subject=epidemiology%'
    OR feed_url ILIKE '%subject=clinical_trials%'
    OR feed_url ILIKE '%subject=physiology%'
  );

COMMIT;
