-- Public web auth: user_profiles roles + minimal table if missing.
-- Apply: PYTHONPATH=api uv run python api/scripts/run_migration_217.py
-- Ledger: PYTHONPATH=api uv run python api/scripts/register_applied_migration.py 217 ...

CREATE TABLE IF NOT EXISTS public.user_profiles (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL DEFAULT '',
    password_hash VARCHAR(255),
    full_name VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    roles JSONB NOT NULL DEFAULT '["guest"]'::jsonb
);

ALTER TABLE public.user_profiles
    ADD COLUMN IF NOT EXISTS roles JSONB NOT NULL DEFAULT '["guest"]'::jsonb;

ALTER TABLE public.user_profiles
    ADD COLUMN IF NOT EXISTS last_login TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON public.user_profiles (username);
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON public.user_profiles (email);
