-- Soften chronological_events sequence trigger so insert fan-out is not killed
-- by statement_timeout when renumbering large storylines.
--
-- Prior behavior: AFTER INSERT/UPDATE ran calculate_event_sequence(storyline_id),
-- which UPDATE'd every dated event for that storyline. Large arcs timed out and
-- aborted the whole UIE transaction.
--
-- New behavior:
-- - Skip blank/null storyline_id
-- - Catch query_canceled / others so the event row still commits
-- - calculate_event_sequence itself still available for manual/batch rebuilds

CREATE OR REPLACE FUNCTION public.trigger_update_event_sequence()
RETURNS trigger
LANGUAGE plpgsql
AS $function$
BEGIN
    IF NEW.storyline_id IS NULL OR btrim(NEW.storyline_id) = '' THEN
        RETURN NEW;
    END IF;

    BEGIN
        -- Bound work on the hot path; stale positions beat failed inserts.
        PERFORM set_config('statement_timeout', '2500', true);
        PERFORM public.calculate_event_sequence(NEW.storyline_id);
    EXCEPTION
        WHEN query_canceled THEN
            NULL;
        WHEN OTHERS THEN
            NULL;
    END;

    RETURN NEW;
END;
$function$;
