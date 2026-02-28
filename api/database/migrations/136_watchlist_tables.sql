-- v5.0 Phase 5: Watchlist and notification tables

CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    user_label VARCHAR(255),
    notes TEXT,
    alert_on_reactivation BOOLEAN DEFAULT TRUE,
    weekly_digest BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (storyline_id)
);

CREATE TABLE IF NOT EXISTS watchlist_alerts (
    id SERIAL PRIMARY KEY,
    watchlist_id INTEGER NOT NULL REFERENCES watchlist(id) ON DELETE CASCADE,
    storyline_id INTEGER NOT NULL REFERENCES storylines(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES chronological_events(id) ON DELETE SET NULL,
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN (
        'reactivation', 'new_event', 'source_corroboration',
        'escalation', 'resolution', 'weekly_digest'
    )),
    title VARCHAR(300) NOT NULL,
    body TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_watchlist_storyline ON watchlist (storyline_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_alerts_unread ON watchlist_alerts (is_read) WHERE is_read = FALSE;
CREATE INDEX IF NOT EXISTS idx_watchlist_alerts_created ON watchlist_alerts (created_at DESC);
