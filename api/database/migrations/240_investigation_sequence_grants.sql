-- Grant newsapp access to investigation_* sequences (created by postgres in 239).

BEGIN;

GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA intelligence TO newsapp;

COMMIT;
