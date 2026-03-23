-- pg_trgm for claim subject → entity_profile fuzzy matching (similarity()).
-- Safe if already created by historical migrations; required on fresh DBs without them.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
