-- Single-row advisory so remote workers (PopOS) can see Widow API pool pressure
-- without sharing in-process waiter counters.
CREATE TABLE IF NOT EXISTS public.db_pool_pressure_advisory (
    id integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    source text NOT NULL DEFAULT 'api',
    worker_in_use integer NOT NULL DEFAULT 0,
    worker_max integer NOT NULL DEFAULT 0,
    worker_waiters integer NOT NULL DEFAULT 0,
    worker_utilization double precision NOT NULL DEFAULT 0,
    worker_pressure double precision NOT NULL DEFAULT 0,
    defer_new_work boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now(),
    detail jsonb NOT NULL DEFAULT '{}'::jsonb
);

INSERT INTO public.db_pool_pressure_advisory (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;

COMMENT ON TABLE public.db_pool_pressure_advisory IS
  'Cross-process DB pool pressure signal; written by AutomationManager, read by PopOS workers.';
