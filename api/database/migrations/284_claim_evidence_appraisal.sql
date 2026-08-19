-- Migration 284: claim_evidence_appraisal + ledger/embedding vocabulary alignment.
-- Local-first scaffolding for v11 corpus evidence appraisal. Idempotent where practical.

BEGIN;

-- ---------------------------------------------------------------------------
-- intelligence.claim_evidence_appraisal
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intelligence.claim_evidence_appraisal (
    id BIGSERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL,
    document_id INTEGER
        REFERENCES intelligence.processed_documents (id) ON DELETE SET NULL,
    article_id INTEGER,
    finding_text TEXT,
    hypothesis_text TEXT,
    study_design TEXT NOT NULL DEFAULT 'unknown'
        CHECK (study_design IN (
            'meta_analysis',
            'systematic_review',
            'rct',
            'cohort',
            'case_control',
            'cross_sectional',
            'case_report',
            'animal_in_vitro',
            'modeling',
            'opinion',
            'unknown'
        )),
    peer_review_status TEXT NOT NULL DEFAULT 'unknown'
        CHECK (peer_review_status IN (
            'peer_reviewed',
            'preprint',
            'registry_record',
            'gray_literature',
            'unknown'
        )),
    paper_support TEXT NOT NULL DEFAULT 'insufficient_reporting'
        CHECK (paper_support IN (
            'supported_by_own_evidence',
            'partially_supported',
            'not_supported_by_own_evidence',
            'insufficient_reporting'
        )),
    replication_status TEXT NOT NULL DEFAULT 'single_study'
        CHECK (replication_status IN (
            'replicated_independent',
            'replicated_same_group',
            'single_study',
            'contradicted',
            'needs_follow_up'
        )),
    evidence_grade TEXT NOT NULL DEFAULT 'preliminary'
        CHECK (evidence_grade IN (
            'strong',
            'moderate',
            'limited',
            'preliminary',
            'unsubstantiated'
        )),
    sample_size_text TEXT,
    reported_effect_text TEXT,
    limitations_quote TEXT,
    evidence_quotes JSONB NOT NULL DEFAULT '[]'::jsonb,
    grader_model TEXT,
    prompt_version TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    event_date TIMESTAMPTZ,
    ingestion_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    vintage_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_appraisal_domain
    ON intelligence.claim_evidence_appraisal (domain_key);

CREATE INDEX IF NOT EXISTS idx_claim_evidence_appraisal_document
    ON intelligence.claim_evidence_appraisal (document_id)
    WHERE document_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_claim_evidence_appraisal_article
    ON intelligence.claim_evidence_appraisal (domain_key, article_id)
    WHERE article_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_claim_evidence_appraisal_grade
    ON intelligence.claim_evidence_appraisal (evidence_grade);

COMMENT ON TABLE intelligence.claim_evidence_appraisal IS
  'v11 corpus evidence appraisal rows (study design / peer review / support / replication / grade)';

-- ---------------------------------------------------------------------------
-- research_claim_ledger: extend verdict + align evidence_strength / study_type
-- ---------------------------------------------------------------------------
ALTER TABLE intelligence.research_claim_ledger
    DROP CONSTRAINT IF EXISTS research_claim_ledger_verdict_check;

ALTER TABLE intelligence.research_claim_ledger
    ADD CONSTRAINT research_claim_ledger_verdict_check
    CHECK (verdict IN (
        'substantiated',
        'proved',
        'disproved',
        'inconclusive',
        'not_applicable',
        'needs_follow_up'
    ));

COMMENT ON COLUMN intelligence.research_claim_ledger.verdict IS
  'substantiated|proved|disproved|inconclusive|not_applicable|needs_follow_up '
  '(needs_follow_up ≠ false/contradicted)';

-- Soft alignment: coerce legacy values, then constrain when set (NULL allowed).
UPDATE intelligence.research_claim_ledger
SET evidence_strength = NULL
WHERE evidence_strength IS NOT NULL
  AND evidence_strength NOT IN (
    'strong', 'moderate', 'limited', 'preliminary', 'unsubstantiated'
  );

UPDATE intelligence.research_claim_ledger
SET study_type = NULL
WHERE study_type IS NOT NULL
  AND study_type NOT IN (
    'meta_analysis',
    'systematic_review',
    'rct',
    'cohort',
    'case_control',
    'cross_sectional',
    'case_report',
    'animal_in_vitro',
    'modeling',
    'opinion',
    'unknown'
  );

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'research_claim_ledger_evidence_strength_check'
      AND conrelid = 'intelligence.research_claim_ledger'::regclass
  ) THEN
    ALTER TABLE intelligence.research_claim_ledger
      ADD CONSTRAINT research_claim_ledger_evidence_strength_check
      CHECK (
        evidence_strength IS NULL
        OR evidence_strength IN (
          'strong', 'moderate', 'limited', 'preliminary', 'unsubstantiated'
        )
      );
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'research_claim_ledger_study_type_check'
      AND conrelid = 'intelligence.research_claim_ledger'::regclass
  ) THEN
    ALTER TABLE intelligence.research_claim_ledger
      ADD CONSTRAINT research_claim_ledger_study_type_check
      CHECK (
        study_type IS NULL
        OR study_type IN (
          'meta_analysis',
          'systematic_review',
          'rct',
          'cohort',
          'case_control',
          'cross_sectional',
          'case_report',
          'animal_in_vitro',
          'modeling',
          'opinion',
          'unknown'
        )
      );
  END IF;
END $$;

COMMENT ON COLUMN intelligence.research_claim_ledger.evidence_strength IS
  'Aligned with EVIDENCE_GRADES: strong|moderate|limited|preliminary|unsubstantiated';
COMMENT ON COLUMN intelligence.research_claim_ledger.study_type IS
  'Aligned with STUDY_DESIGNS vocabulary (shared.evidence_grade)';

-- ---------------------------------------------------------------------------
-- embedding_chunks: allow processed_document source_type
-- ---------------------------------------------------------------------------
ALTER TABLE intelligence.embedding_chunks
    DROP CONSTRAINT IF EXISTS embedding_chunks_source_type_check;

ALTER TABLE intelligence.embedding_chunks
    ADD CONSTRAINT embedding_chunks_source_type_check
    CHECK (source_type IN (
        'article',
        'reference_event',
        'wikipedia',
        'context',
        'arc_report',
        'processed_document'
    ));

COMMENT ON COLUMN intelligence.embedding_chunks.source_type IS
  'article|reference_event|wikipedia|context|arc_report|processed_document';

COMMIT;
