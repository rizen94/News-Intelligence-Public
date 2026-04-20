-- Migration 163: Content feedback (usefulness, not interested) for briefings and article/storyline ranking.
-- Optional: low-priority entity/keyword blocklist is loaded from config (briefing_filters.yaml), not DB.

-- Content feedback: user signals for briefing and list ordering (single user / device for now).
CREATE TABLE IF NOT EXISTS public.content_feedback (
    id SERIAL PRIMARY KEY,
    domain VARCHAR(50) NOT NULL,
    item_type VARCHAR(20) NOT NULL,  -- 'article' | 'storyline' | 'briefing'
    item_id INTEGER,                  -- article_id or storyline_id; NULL for whole-briefing rating
    rating SMALLINT,                 -- 1-5 usefulness; NULL if only not_interested
    not_interested BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT content_feedback_rating_range CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),
    CONSTRAINT content_feedback_item_type_check CHECK (item_type IN ('article', 'storyline', 'briefing'))
);

CREATE INDEX IF NOT EXISTS idx_content_feedback_domain ON public.content_feedback(domain);
CREATE INDEX IF NOT EXISTS idx_content_feedback_item ON public.content_feedback(domain, item_type, item_id);
CREATE INDEX IF NOT EXISTS idx_content_feedback_not_interested ON public.content_feedback(domain, not_interested) WHERE not_interested = TRUE;

COMMENT ON TABLE public.content_feedback IS 'User feedback for briefing and list ordering: usefulness 1-5 and not interested';
