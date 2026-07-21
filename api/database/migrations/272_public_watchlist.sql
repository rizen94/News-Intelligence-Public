-- Migration 272: public watchlist + watchlist_alerts (Phase 5 tables never migrated)
-- Restores DDL expected by api/services/watchlist_service.py.

CREATE TABLE IF NOT EXISTS public.watchlist (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER NOT NULL,
    domain_key VARCHAR(64),
    user_label TEXT,
    notes TEXT,
    alert_on_reactivation BOOLEAN NOT NULL DEFAULT TRUE,
    weekly_digest BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT watchlist_storyline_id_unique UNIQUE (storyline_id)
);

COMMENT ON TABLE public.watchlist IS
    'User/operator long-term storyline tracking; domain_key optional for silo joins.';

CREATE INDEX IF NOT EXISTS idx_watchlist_domain_storyline
    ON public.watchlist (domain_key, storyline_id)
    WHERE domain_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS public.watchlist_alerts (
    id BIGSERIAL PRIMARY KEY,
    watchlist_id INTEGER NOT NULL REFERENCES public.watchlist(id) ON DELETE CASCADE,
    storyline_id INTEGER NOT NULL,
    event_id BIGINT,
    alert_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watchlist_alerts_unread
    ON public.watchlist_alerts (watchlist_id, created_at DESC)
    WHERE is_read = FALSE;

CREATE INDEX IF NOT EXISTS idx_watchlist_alerts_storyline
    ON public.watchlist_alerts (storyline_id, created_at DESC);

COMMENT ON TABLE public.watchlist_alerts IS
    'Alerts for watchlist reactivation / digest events.';
