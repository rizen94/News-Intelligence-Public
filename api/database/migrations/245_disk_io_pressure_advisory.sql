-- Single-row advisory for Widow USB-root disk write pressure.
-- Written by AutomationManager / widow_disk_io_governor; read by automation gates + apt wrapper.
CREATE TABLE IF NOT EXISTS public.disk_io_pressure_advisory (
    id integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    source text NOT NULL DEFAULT 'api',
    device text NOT NULL DEFAULT '',
    util_pct double precision NOT NULL DEFAULT 0,
    write_kb_s double precision NOT NULL DEFAULT 0,
    defer_heavy_writes boolean NOT NULL DEFAULT false,
    defer_new_work boolean NOT NULL DEFAULT false,
    updated_at timestamptz NOT NULL DEFAULT now(),
    detail jsonb NOT NULL DEFAULT '{}'::jsonb
);

INSERT INTO public.disk_io_pressure_advisory (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'newsapp') THEN
    GRANT SELECT, INSERT, UPDATE ON public.disk_io_pressure_advisory TO newsapp;
  END IF;
END $$;

COMMENT ON TABLE public.disk_io_pressure_advisory IS
  'Cross-process disk IO pressure on Widow root device; gates apt + new automation schedules.';
