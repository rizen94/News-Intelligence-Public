-- Domain-shaped protein ledgers: research claims (medicine/AI) + matter dockets (legal).
-- Do not use linear curated arcs for these domains.

CREATE TABLE IF NOT EXISTS intelligence.research_claim_ledger (
    id BIGSERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL,
    canonical_entity_id BIGINT,
    protein_id INTEGER,
    article_id INTEGER,
    document_id INTEGER,
    hypothesis_text TEXT,
    finding_summary TEXT,
    verdict TEXT NOT NULL DEFAULT 'inconclusive'
        CHECK (verdict IN (
            'substantiated',
            'proved',
            'disproved',
            'inconclusive',
            'not_applicable'
        )),
    evidence_strength TEXT,
    study_type TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_claim_ledger_entity
    ON intelligence.research_claim_ledger (domain_key, canonical_entity_id);
CREATE INDEX IF NOT EXISTS idx_research_claim_ledger_protein
    ON intelligence.research_claim_ledger (domain_key, protein_id);
CREATE INDEX IF NOT EXISTS idx_research_claim_ledger_verdict
    ON intelligence.research_claim_ledger (verdict);

CREATE TABLE IF NOT EXISTS intelligence.research_subject_proteins (
    id BIGSERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL,
    canonical_entity_id BIGINT NOT NULL,
    storyline_id INTEGER NOT NULL,
    parent_entity_id BIGINT,
    subtype_label TEXT,
    severity_label TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (domain_key, canonical_entity_id, storyline_id)
);

CREATE INDEX IF NOT EXISTS idx_research_subject_proteins_entity
    ON intelligence.research_subject_proteins (domain_key, canonical_entity_id);
CREATE INDEX IF NOT EXISTS idx_research_subject_proteins_parent
    ON intelligence.research_subject_proteins (domain_key, parent_entity_id);

CREATE TABLE IF NOT EXISTS intelligence.matter_docket_status (
    id BIGSERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL DEFAULT 'legal',
    storyline_id INTEGER NOT NULL,
    legal_status TEXT NOT NULL DEFAULT 'unsettled'
        CHECK (legal_status IN ('legal', 'not_legal', 'contested', 'unsettled')),
    status_rationale TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (domain_key, storyline_id)
);

CREATE TABLE IF NOT EXISTS intelligence.matter_ruling_events (
    id BIGSERIAL PRIMARY KEY,
    domain_key TEXT NOT NULL DEFAULT 'legal',
    storyline_id INTEGER NOT NULL,
    decision_date DATE,
    court TEXT,
    holding_summary TEXT,
    status_delta TEXT
        CHECK (
            status_delta IS NULL
            OR status_delta IN ('legal', 'not_legal', 'contested', 'unsettled')
        ),
    article_id INTEGER,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_matter_ruling_events_storyline
    ON intelligence.matter_ruling_events (domain_key, storyline_id, decision_date DESC);
