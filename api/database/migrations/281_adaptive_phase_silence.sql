-- Migration 281: Adaptive phase silence — silence is a backoff, not a retirement.
-- Records the queue depth observed when a phase was silenced so the scheduler can
-- lift the silence once genuinely new work arrives (or on RSS intake), instead of
-- holding it until an operator intervenes / the API restarts.

ALTER TABLE public.phase_silence_state
    ADD COLUMN IF NOT EXISTS silenced_at_backlog INTEGER,
    ADD COLUMN IF NOT EXISTS lift_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_lifted_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_lift_reason TEXT;

COMMENT ON COLUMN public.phase_silence_state.silenced_at_backlog IS
    'Phase queue depth when silenced. Silence lifts when depth grows past this (new work arrived).';
COMMENT ON COLUMN public.phase_silence_state.lift_count IS
    'How many times this silence has been auto-lifted for a retry (flap observability).';
COMMENT ON COLUMN public.phase_silence_state.last_lifted_at IS
    'When the silence was last auto-lifted to retry the phase.';
COMMENT ON COLUMN public.phase_silence_state.last_lift_reason IS
    'Trigger for the last auto-lift: rss_intake | queue_growth | operator.';

-- Active silences predate backlog capture; treat them as lift-on-any-pending.
UPDATE public.phase_silence_state
   SET silenced_at_backlog = 0
 WHERE cleared_at IS NULL AND silenced_at_backlog IS NULL;
