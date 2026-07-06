-- Kit schema version marker (runs after baseline on fresh installs only if added to initdb).
INSERT INTO public.automation_state (key, value)
VALUES ('kit_schema_version', '"1"'::jsonb)
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW();
