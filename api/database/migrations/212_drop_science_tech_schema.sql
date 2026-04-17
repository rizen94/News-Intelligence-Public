-- Migration 212: Remove retired science-tech Postgres silo (schema science_tech).
-- Prerequisites: migration 210 applied (intelligence.domain_key strings repointed off science-tech).
-- Destructive: DROP SCHEMA CASCADE removes all tables/data in science_tech.

BEGIN;

DELETE FROM public.domain_metadata
WHERE domain_id IN (SELECT id FROM public.domains WHERE domain_key = 'science-tech');

DELETE FROM public.domains WHERE domain_key = 'science-tech';

DROP SCHEMA IF EXISTS science_tech CASCADE;

COMMIT;
