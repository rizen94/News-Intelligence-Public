--
-- PostgreSQL database dump
--

\restrict IwsbMNY9dvIczavK6ffQc4J45Wv1r6kNVQJKwVqjgZznHJV5b0eCD4CL1m9CW3j

-- Dumped from database version 15.14
-- Dumped by pg_dump version 15.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: check_rate_limit(character varying, character varying, integer, integer); Type: FUNCTION; Schema: public; Owner: newsapp
--

CREATE FUNCTION public.check_rate_limit(p_resource_type character varying, p_resource_key character varying, p_max_requests integer, p_window_duration_seconds integer) RETURNS boolean
    LANGUAGE plpgsql
    AS $$
DECLARE
    current_count INTEGER;
    window_start TIMESTAMP;
BEGIN
    window_start := CURRENT_TIMESTAMP - INTERVAL '1 second' * p_window_duration_seconds;
    
    SELECT COALESCE(SUM(request_count), 0)
    INTO current_count
    FROM rate_limiting
    WHERE resource_type = p_resource_type 
      AND resource_key = p_resource_key
      AND window_start >= window_start;
    
    IF current_count >= p_max_requests THEN
        RETURN FALSE;
    END IF;
    
    -- Record this request
    INSERT INTO rate_limiting (resource_type, resource_key, max_requests, window_duration_seconds)
    VALUES (p_resource_type, p_resource_key, p_max_requests, p_window_duration_seconds)
    ON CONFLICT (resource_type, resource_key, window_start) 
    DO UPDATE SET request_count = rate_limiting.request_count + 1;
    
    RETURN TRUE;
END;
$$;


ALTER FUNCTION public.check_rate_limit(p_resource_type character varying, p_resource_key character varying, p_max_requests integer, p_window_duration_seconds integer) OWNER TO newsapp;

--
-- Name: run_cleanup_policies(); Type: FUNCTION; Schema: public; Owner: newsapp
--

CREATE FUNCTION public.run_cleanup_policies() RETURNS TABLE(policy_name text, cleaned_count integer)
    LANGUAGE plpgsql
    AS $$
DECLARE
    policy RECORD;
    cleaned_count INTEGER;
BEGIN
    FOR policy IN 
        SELECT * FROM storage_cleanup_policies WHERE is_active = true
    LOOP
        EXECUTE format('DELETE FROM %I WHERE %s', policy.table_name, policy.cleanup_condition);
        GET DIAGNOSTICS cleaned_count = ROW_COUNT;
        
        UPDATE storage_cleanup_policies 
        SET last_run = CURRENT_TIMESTAMP, last_cleaned_count = cleaned_count
        WHERE id = policy.id;
        
        policy_name := policy.policy_name;
        RETURN NEXT;
    END LOOP;
END;
$$;


ALTER FUNCTION public.run_cleanup_policies() OWNER TO newsapp;

--
-- Name: update_ml_task_queue_updated_at(); Type: FUNCTION; Schema: public; Owner: newsapp
--

CREATE FUNCTION public.update_ml_task_queue_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_ml_task_queue_updated_at() OWNER TO newsapp;

--
-- Name: update_scaling_metrics(); Type: FUNCTION; Schema: public; Owner: newsapp
--

CREATE FUNCTION public.update_scaling_metrics() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
    INSERT INTO system_scaling_metrics (
        total_articles,
        raw_articles,
        processing_articles,
        completed_articles,
        failed_articles,
        total_timeline_events,
        active_storylines,
        database_size_bytes
    )
    SELECT 
        (SELECT COUNT(*) FROM articles),
        (SELECT COUNT(*) FROM articles WHERE processing_status = 'raw'),
        (SELECT COUNT(*) FROM articles WHERE processing_status = 'ml_processing'),
        (SELECT COUNT(*) FROM articles WHERE processing_status = 'completed'),
        (SELECT COUNT(*) FROM articles WHERE processing_status = 'failed'),
        (SELECT COUNT(*) FROM timeline_events),
        (SELECT COUNT(*) FROM story_expectations WHERE is_active = true),
        pg_database_size('news_system');
END;
$$;


ALTER FUNCTION public.update_scaling_metrics() OWNER TO newsapp;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: newsapp
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO newsapp;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: api_cache; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.api_cache (
    id integer NOT NULL,
    cache_key character varying(64) NOT NULL,
    service character varying(50) NOT NULL,
    query text NOT NULL,
    response_data jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.api_cache OWNER TO newsapp;

--
-- Name: api_cache_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.api_cache_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.api_cache_id_seq OWNER TO newsapp;

--
-- Name: api_cache_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.api_cache_id_seq OWNED BY public.api_cache.id;


--
-- Name: api_usage_tracking; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.api_usage_tracking (
    id integer NOT NULL,
    service character varying(50) NOT NULL,
    endpoint character varying(255) NOT NULL,
    request_count integer DEFAULT 1,
    response_size integer DEFAULT 0,
    processing_time_ms integer DEFAULT 0,
    success boolean DEFAULT true,
    error_message text,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.api_usage_tracking OWNER TO newsapp;

--
-- Name: api_usage_tracking_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.api_usage_tracking_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.api_usage_tracking_id_seq OWNER TO newsapp;

--
-- Name: api_usage_tracking_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.api_usage_tracking_id_seq OWNED BY public.api_usage_tracking.id;


--
-- Name: application_metrics; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.application_metrics (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    articles_processed integer DEFAULT 0,
    articles_failed integer DEFAULT 0,
    processing_time_ms integer DEFAULT 0,
    queue_size integer DEFAULT 0,
    active_workers integer DEFAULT 0,
    tasks_completed integer DEFAULT 0,
    tasks_failed integer DEFAULT 0,
    avg_processing_time_ms numeric(10,2) DEFAULT 0,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.application_metrics OWNER TO newsapp;

--
-- Name: application_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.application_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.application_metrics_id_seq OWNER TO newsapp;

--
-- Name: application_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.application_metrics_id_seq OWNED BY public.application_metrics.id;


--
-- Name: article_clusters; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.article_clusters (
    id integer NOT NULL,
    main_article_id integer,
    cluster_type character varying(50) DEFAULT 'story'::character varying,
    topic text,
    summary text,
    article_count integer DEFAULT 1,
    cohesion_score numeric(3,2) DEFAULT 0.0,
    created_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.article_clusters OWNER TO newsapp;

--
-- Name: article_clusters_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.article_clusters_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.article_clusters_id_seq OWNER TO newsapp;

--
-- Name: article_clusters_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.article_clusters_id_seq OWNED BY public.article_clusters.id;


--
-- Name: article_processing_batches; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.article_processing_batches (
    id integer NOT NULL,
    batch_id character varying(255) NOT NULL,
    batch_type character varying(50) NOT NULL,
    total_articles integer NOT NULL,
    processed_articles integer DEFAULT 0,
    failed_articles integer DEFAULT 0,
    status character varying(20) DEFAULT 'pending'::character varying,
    priority integer DEFAULT 2,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    error_message text,
    metadata jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE public.article_processing_batches OWNER TO newsapp;

--
-- Name: article_processing_batches_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.article_processing_batches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.article_processing_batches_id_seq OWNER TO newsapp;

--
-- Name: article_processing_batches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.article_processing_batches_id_seq OWNED BY public.article_processing_batches.id;


--
-- Name: article_volume_metrics; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.article_volume_metrics (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    total_articles integer NOT NULL,
    new_articles_last_hour integer DEFAULT 0,
    new_articles_last_day integer DEFAULT 0,
    articles_by_source jsonb,
    articles_by_category jsonb,
    avg_article_length integer DEFAULT 0,
    processing_success_rate numeric(5,2) DEFAULT 0,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.article_volume_metrics OWNER TO newsapp;

--
-- Name: article_volume_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.article_volume_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.article_volume_metrics_id_seq OWNER TO newsapp;

--
-- Name: article_volume_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.article_volume_metrics_id_seq OWNED BY public.article_volume_metrics.id;


--
-- Name: articles; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.articles (
    id integer NOT NULL,
    title text NOT NULL,
    content text,
    summary text,
    url text,
    source character varying(255),
    published_at timestamp without time zone,
    category character varying(100),
    language character varying(10) DEFAULT 'en'::character varying,
    quality_score numeric(3,2) DEFAULT 0.0,
    processing_status character varying(50) DEFAULT 'raw'::character varying,
    content_hash character varying(64),
    deduplication_status character varying(50) DEFAULT 'pending'::character varying,
    content_similarity_score numeric(3,2),
    normalized_content text,
    ml_data jsonb,
    rag_keep_longer boolean DEFAULT false,
    rag_context_needed boolean DEFAULT false,
    rag_priority integer DEFAULT 0,
    processing_started_at timestamp without time zone,
    processing_completed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    word_count integer DEFAULT 0,
    reading_time integer DEFAULT 0,
    feed_id integer,
    tags jsonb DEFAULT '[]'::jsonb,
    sentiment_score numeric(3,2),
    entities jsonb DEFAULT '{}'::jsonb,
    readability_score numeric(3,2)
);


ALTER TABLE public.articles OWNER TO newsapp;

--
-- Name: articles_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.articles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.articles_id_seq OWNER TO newsapp;

--
-- Name: articles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.articles_id_seq OWNED BY public.articles.id;


--
-- Name: automation_logs; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.automation_logs (
    id integer NOT NULL,
    operation character varying(100) NOT NULL,
    status character varying(20) DEFAULT 'started'::character varying NOT NULL,
    "timestamp" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    articles_affected integer DEFAULT 0,
    processing_time double precision DEFAULT 0.0,
    details jsonb DEFAULT '{}'::jsonb,
    error_message text,
    triggered_by character varying(50) DEFAULT 'system'::character varying
);


ALTER TABLE public.automation_logs OWNER TO newsapp;

--
-- Name: TABLE automation_logs; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.automation_logs IS 'Logs automation pipeline activities and operations';


--
-- Name: COLUMN automation_logs.operation; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.automation_logs.operation IS 'Type of operation: pipeline, consolidation, digest, cleanup, etc.';


--
-- Name: COLUMN automation_logs.articles_affected; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.automation_logs.articles_affected IS 'Number of articles affected by the operation';


--
-- Name: COLUMN automation_logs.processing_time; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.automation_logs.processing_time IS 'Processing time in seconds';


--
-- Name: COLUMN automation_logs.details; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.automation_logs.details IS 'JSON object with operation-specific details';


--
-- Name: automation_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.automation_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.automation_logs_id_seq OWNER TO newsapp;

--
-- Name: automation_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.automation_logs_id_seq OWNED BY public.automation_logs.id;


--
-- Name: automation_tasks; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.automation_tasks (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    enabled boolean DEFAULT true,
    schedule character varying(100) NOT NULL,
    last_run timestamp with time zone,
    next_run timestamp with time zone,
    status character varying(20) DEFAULT 'idle'::character varying,
    run_count integer DEFAULT 0,
    success_count integer DEFAULT 0,
    failure_count integer DEFAULT 0,
    avg_execution_time double precision DEFAULT 0.0,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.automation_tasks OWNER TO newsapp;

--
-- Name: TABLE automation_tasks; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.automation_tasks IS 'Scheduled automation tasks and their status';


--
-- Name: COLUMN automation_tasks.schedule; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.automation_tasks.schedule IS 'Cron-like schedule expression';


--
-- Name: COLUMN automation_tasks.next_run; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.automation_tasks.next_run IS 'Next scheduled execution time';


--
-- Name: COLUMN automation_tasks.avg_execution_time; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.automation_tasks.avg_execution_time IS 'Average execution time in seconds';


--
-- Name: automation_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.automation_tasks_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.automation_tasks_id_seq OWNER TO newsapp;

--
-- Name: automation_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.automation_tasks_id_seq OWNED BY public.automation_tasks.id;


--
-- Name: briefing_templates; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.briefing_templates (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    sections jsonb DEFAULT '[]'::jsonb,
    schedule character varying(20) DEFAULT 'daily'::character varying,
    enabled boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(100) DEFAULT 'system'::character varying
);


ALTER TABLE public.briefing_templates OWNER TO newsapp;

--
-- Name: TABLE briefing_templates; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.briefing_templates IS 'Templates for generating daily briefings';


--
-- Name: COLUMN briefing_templates.sections; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.briefing_templates.sections IS 'JSON array of briefing sections to include';


--
-- Name: COLUMN briefing_templates.schedule; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.briefing_templates.schedule IS 'Schedule frequency: daily, weekly, monthly';


--
-- Name: briefing_templates_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.briefing_templates_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.briefing_templates_id_seq OWNER TO newsapp;

--
-- Name: briefing_templates_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.briefing_templates_id_seq OWNED BY public.briefing_templates.id;


--
-- Name: cluster_articles; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.cluster_articles (
    id integer NOT NULL,
    cluster_id integer,
    article_id integer,
    similarity_score numeric(3,2),
    added_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.cluster_articles OWNER TO newsapp;

--
-- Name: cluster_articles_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.cluster_articles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.cluster_articles_id_seq OWNER TO newsapp;

--
-- Name: cluster_articles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.cluster_articles_id_seq OWNED BY public.cluster_articles.id;


--
-- Name: collection_rules; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.collection_rules (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    rule_type character varying(50) NOT NULL,
    rule_config jsonb NOT NULL,
    feed_id integer,
    max_articles_per_collection integer DEFAULT 50,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.collection_rules OWNER TO newsapp;

--
-- Name: collection_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.collection_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.collection_rules_id_seq OWNER TO newsapp;

--
-- Name: collection_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.collection_rules_id_seq OWNED BY public.collection_rules.id;


--
-- Name: content_hashes; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.content_hashes (
    id integer NOT NULL,
    content_hash character varying(64) NOT NULL,
    article_id integer,
    hash_type character varying(20) DEFAULT 'sha256'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.content_hashes OWNER TO newsapp;

--
-- Name: content_hashes_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.content_hashes_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.content_hashes_id_seq OWNER TO newsapp;

--
-- Name: content_hashes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.content_hashes_id_seq OWNED BY public.content_hashes.id;


--
-- Name: content_priority_assignments; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.content_priority_assignments (
    id integer NOT NULL,
    article_id integer,
    thread_id integer,
    priority_level_id integer,
    assigned_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    assigned_by character varying(100),
    notes text
);


ALTER TABLE public.content_priority_assignments OWNER TO newsapp;

--
-- Name: content_priority_assignments_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.content_priority_assignments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.content_priority_assignments_id_seq OWNER TO newsapp;

--
-- Name: content_priority_assignments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.content_priority_assignments_id_seq OWNED BY public.content_priority_assignments.id;


--
-- Name: content_priority_levels; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.content_priority_levels (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    description text,
    color character varying(7) DEFAULT '#2196f3'::character varying,
    sort_order integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.content_priority_levels OWNER TO newsapp;

--
-- Name: content_priority_levels_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.content_priority_levels_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.content_priority_levels_id_seq OWNER TO newsapp;

--
-- Name: content_priority_levels_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.content_priority_levels_id_seq OWNED BY public.content_priority_levels.id;


--
-- Name: database_metrics; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.database_metrics (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    connection_count integer DEFAULT 0,
    active_queries integer DEFAULT 0,
    slow_queries integer DEFAULT 0,
    avg_query_time_ms numeric(10,2) DEFAULT 0,
    database_size_mb numeric(10,2) DEFAULT 0,
    table_sizes jsonb,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.database_metrics OWNER TO newsapp;

--
-- Name: database_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.database_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.database_metrics_id_seq OWNER TO newsapp;

--
-- Name: database_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.database_metrics_id_seq OWNED BY public.database_metrics.id;


--
-- Name: deduplication_settings; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.deduplication_settings (
    id integer NOT NULL,
    similarity_threshold numeric(4,3) DEFAULT 0.85,
    auto_remove boolean DEFAULT false,
    min_article_length integer DEFAULT 100,
    max_articles_to_process integer DEFAULT 1000,
    enabled_algorithms jsonb DEFAULT '["content_similarity", "title_similarity", "url_similarity"]'::jsonb,
    exclude_sources jsonb DEFAULT '[]'::jsonb,
    include_sources jsonb DEFAULT '[]'::jsonb,
    time_window_hours integer DEFAULT 24,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.deduplication_settings OWNER TO newsapp;

--
-- Name: TABLE deduplication_settings; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.deduplication_settings IS 'Stores configuration for duplicate detection algorithms';


--
-- Name: COLUMN deduplication_settings.similarity_threshold; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.deduplication_settings.similarity_threshold IS 'Minimum similarity score to consider articles as duplicates';


--
-- Name: COLUMN deduplication_settings.enabled_algorithms; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.deduplication_settings.enabled_algorithms IS 'JSON array of enabled detection algorithms';


--
-- Name: deduplication_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.deduplication_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.deduplication_settings_id_seq OWNER TO newsapp;

--
-- Name: deduplication_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.deduplication_settings_id_seq OWNED BY public.deduplication_settings.id;


--
-- Name: deduplication_stats; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.deduplication_stats (
    id integer NOT NULL,
    date date NOT NULL,
    total_duplicates integer DEFAULT 0,
    pending_review integer DEFAULT 0,
    high_similarity integer DEFAULT 0,
    very_high_similarity integer DEFAULT 0,
    medium_similarity integer DEFAULT 0,
    low_similarity integer DEFAULT 0,
    removed_count integer DEFAULT 0,
    rejected_count integer DEFAULT 0,
    accuracy_rate numeric(5,2) DEFAULT 0.0,
    processing_time double precision DEFAULT 0.0,
    articles_processed integer DEFAULT 0,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.deduplication_stats OWNER TO newsapp;

--
-- Name: TABLE deduplication_stats; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.deduplication_stats IS 'Daily statistics for deduplication performance';


--
-- Name: deduplication_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.deduplication_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.deduplication_stats_id_seq OWNER TO newsapp;

--
-- Name: deduplication_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.deduplication_stats_id_seq OWNED BY public.deduplication_stats.id;


--
-- Name: entities; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.entities (
    id integer NOT NULL,
    text character varying(255) NOT NULL,
    type character varying(50) NOT NULL,
    frequency integer DEFAULT 1,
    confidence numeric(3,2) DEFAULT 0.0,
    first_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    metadata jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.entities OWNER TO newsapp;

--
-- Name: entities_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.entities_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.entities_id_seq OWNER TO newsapp;

--
-- Name: entities_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.entities_id_seq OWNED BY public.entities.id;


--
-- Name: feed_categories; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.feed_categories (
    id integer NOT NULL,
    name character varying(50) NOT NULL,
    description text,
    parent_category character varying(50),
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.feed_categories OWNER TO newsapp;

--
-- Name: TABLE feed_categories; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.feed_categories IS 'Categories for organizing RSS feeds';


--
-- Name: feed_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.feed_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.feed_categories_id_seq OWNER TO newsapp;

--
-- Name: feed_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.feed_categories_id_seq OWNED BY public.feed_categories.id;


--
-- Name: feed_filtering_rules; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.feed_filtering_rules (
    id integer NOT NULL,
    feed_id integer,
    rule_type character varying(50) NOT NULL,
    rule_config jsonb NOT NULL,
    is_active boolean DEFAULT true,
    priority integer DEFAULT 5,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.feed_filtering_rules OWNER TO newsapp;

--
-- Name: TABLE feed_filtering_rules; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.feed_filtering_rules IS 'Individual filtering rules for specific feeds';


--
-- Name: feed_filtering_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.feed_filtering_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.feed_filtering_rules_id_seq OWNER TO newsapp;

--
-- Name: feed_filtering_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.feed_filtering_rules_id_seq OWNED BY public.feed_filtering_rules.id;


--
-- Name: feed_performance_metrics; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.feed_performance_metrics (
    id integer NOT NULL,
    feed_id integer NOT NULL,
    date date NOT NULL,
    articles_fetched integer DEFAULT 0,
    articles_filtered_out integer DEFAULT 0,
    articles_accepted integer DEFAULT 0,
    duplicates_found integer DEFAULT 0,
    success_rate numeric(5,2) DEFAULT 0.0,
    avg_response_time integer DEFAULT 0,
    error_count integer DEFAULT 0,
    last_check timestamp with time zone,
    last_success timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.feed_performance_metrics OWNER TO newsapp;

--
-- Name: TABLE feed_performance_metrics; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.feed_performance_metrics IS 'Daily performance metrics for RSS feeds';


--
-- Name: feed_performance_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.feed_performance_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.feed_performance_metrics_id_seq OWNER TO newsapp;

--
-- Name: feed_performance_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.feed_performance_metrics_id_seq OWNED BY public.feed_performance_metrics.id;


--
-- Name: generated_briefings; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.generated_briefings (
    id integer NOT NULL,
    template_id integer,
    title character varying(255) NOT NULL,
    content text NOT NULL,
    generated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    status character varying(20) DEFAULT 'generated'::character varying,
    article_count integer DEFAULT 0,
    word_count integer DEFAULT 0,
    metadata jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE public.generated_briefings OWNER TO newsapp;

--
-- Name: TABLE generated_briefings; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.generated_briefings IS 'Generated briefings based on templates';


--
-- Name: generated_briefings_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.generated_briefings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.generated_briefings_id_seq OWNER TO newsapp;

--
-- Name: generated_briefings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.generated_briefings_id_seq OWNED BY public.generated_briefings.id;


--
-- Name: global_filtering_config; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.global_filtering_config (
    id integer NOT NULL,
    config_name character varying(100) NOT NULL,
    config_data jsonb NOT NULL,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.global_filtering_config OWNER TO newsapp;

--
-- Name: TABLE global_filtering_config; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.global_filtering_config IS 'Global filtering configuration for all feeds';


--
-- Name: global_filtering_config_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.global_filtering_config_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.global_filtering_config_id_seq OWNER TO newsapp;

--
-- Name: global_filtering_config_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.global_filtering_config_id_seq OWNED BY public.global_filtering_config.id;


--
-- Name: system_metrics; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.system_metrics (
    id integer NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now(),
    cpu_percent numeric(5,2) NOT NULL,
    memory_percent numeric(5,2) NOT NULL,
    memory_used_mb bigint NOT NULL,
    memory_total_mb bigint NOT NULL,
    disk_percent numeric(5,2) NOT NULL,
    disk_used_gb numeric(10,2) NOT NULL,
    disk_total_gb numeric(10,2) NOT NULL,
    load_avg_1m numeric(5,2),
    load_avg_5m numeric(5,2),
    load_avg_15m numeric(5,2),
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.system_metrics OWNER TO newsapp;

--
-- Name: metrics_last_week; Type: VIEW; Schema: public; Owner: newsapp
--

CREATE VIEW public.metrics_last_week AS
 SELECT 'system'::text AS metric_type,
    system_metrics."timestamp",
    jsonb_build_object('cpu_percent', system_metrics.cpu_percent, 'memory_percent', system_metrics.memory_percent, 'memory_used_mb', system_metrics.memory_used_mb, 'memory_total_mb', system_metrics.memory_total_mb, 'disk_percent', system_metrics.disk_percent, 'load_avg_1m', system_metrics.load_avg_1m) AS data
   FROM public.system_metrics
  WHERE (system_metrics."timestamp" > (now() - '7 days'::interval))
UNION ALL
 SELECT 'application'::text AS metric_type,
    application_metrics."timestamp",
    jsonb_build_object('articles_processed', application_metrics.articles_processed, 'articles_failed', application_metrics.articles_failed, 'processing_time_ms', application_metrics.processing_time_ms, 'queue_size', application_metrics.queue_size, 'active_workers', application_metrics.active_workers, 'tasks_completed', application_metrics.tasks_completed, 'avg_processing_time_ms', application_metrics.avg_processing_time_ms) AS data
   FROM public.application_metrics
  WHERE (application_metrics."timestamp" > (now() - '7 days'::interval))
UNION ALL
 SELECT 'article_volume'::text AS metric_type,
    article_volume_metrics."timestamp",
    jsonb_build_object('total_articles', article_volume_metrics.total_articles, 'new_articles_last_hour', article_volume_metrics.new_articles_last_hour, 'new_articles_last_day', article_volume_metrics.new_articles_last_day, 'articles_by_source', article_volume_metrics.articles_by_source, 'processing_success_rate', article_volume_metrics.processing_success_rate) AS data
   FROM public.article_volume_metrics
  WHERE (article_volume_metrics."timestamp" > (now() - '7 days'::interval))
UNION ALL
 SELECT 'database'::text AS metric_type,
    database_metrics."timestamp",
    jsonb_build_object('connection_count', database_metrics.connection_count, 'active_queries', database_metrics.active_queries, 'avg_query_time_ms', database_metrics.avg_query_time_ms, 'database_size_mb', database_metrics.database_size_mb) AS data
   FROM public.database_metrics
  WHERE (database_metrics."timestamp" > (now() - '7 days'::interval))
  ORDER BY 2 DESC;


ALTER TABLE public.metrics_last_week OWNER TO newsapp;

--
-- Name: ml_model_performance; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.ml_model_performance (
    id integer NOT NULL,
    model_name character varying(100) NOT NULL,
    model_version character varying(20) NOT NULL,
    metric_name character varying(50) NOT NULL,
    metric_value double precision NOT NULL,
    measured_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    context jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE public.ml_model_performance OWNER TO newsapp;

--
-- Name: TABLE ml_model_performance; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.ml_model_performance IS 'Stores ML model performance metrics over time';


--
-- Name: COLUMN ml_model_performance.metric_name; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.ml_model_performance.metric_name IS 'Performance metric: accuracy, precision, recall, f1_score, latency, throughput, etc.';


--
-- Name: COLUMN ml_model_performance.metric_value; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.ml_model_performance.metric_value IS 'Metric value (0.0-1.0 for accuracy metrics, seconds for latency, etc.)';


--
-- Name: COLUMN ml_model_performance.context; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.ml_model_performance.context IS 'JSON object with additional context about the measurement';


--
-- Name: ml_model_performance_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.ml_model_performance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ml_model_performance_id_seq OWNER TO newsapp;

--
-- Name: ml_model_performance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.ml_model_performance_id_seq OWNED BY public.ml_model_performance.id;


--
-- Name: ml_performance_metrics; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.ml_performance_metrics (
    id integer NOT NULL,
    task_type character varying(50) NOT NULL,
    avg_duration numeric(10,2),
    success_rate numeric(5,2),
    total_tasks integer DEFAULT 0,
    successful_tasks integer DEFAULT 0,
    failed_tasks integer DEFAULT 0,
    last_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.ml_performance_metrics OWNER TO newsapp;

--
-- Name: ml_performance_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.ml_performance_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ml_performance_metrics_id_seq OWNER TO newsapp;

--
-- Name: ml_performance_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.ml_performance_metrics_id_seq OWNED BY public.ml_performance_metrics.id;


--
-- Name: ml_resource_usage; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.ml_resource_usage (
    id integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    cpu_usage numeric(5,2),
    memory_usage numeric(5,2),
    gpu_usage numeric(5,2),
    active_tasks integer DEFAULT 0,
    queue_size integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.ml_resource_usage OWNER TO newsapp;

--
-- Name: ml_resource_usage_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.ml_resource_usage_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ml_resource_usage_id_seq OWNER TO newsapp;

--
-- Name: ml_resource_usage_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.ml_resource_usage_id_seq OWNED BY public.ml_resource_usage.id;


--
-- Name: ml_task_dependencies; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.ml_task_dependencies (
    id integer NOT NULL,
    task_id character varying(255) NOT NULL,
    depends_on_task_id character varying(255) NOT NULL,
    dependency_type character varying(50) DEFAULT 'sequential'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.ml_task_dependencies OWNER TO newsapp;

--
-- Name: ml_task_dependencies_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.ml_task_dependencies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ml_task_dependencies_id_seq OWNER TO newsapp;

--
-- Name: ml_task_dependencies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.ml_task_dependencies_id_seq OWNED BY public.ml_task_dependencies.id;


--
-- Name: ml_task_queue; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.ml_task_queue (
    id integer NOT NULL,
    task_id character varying(255) NOT NULL,
    task_type character varying(50) NOT NULL,
    priority integer DEFAULT 2 NOT NULL,
    storyline_id character varying(255),
    article_id integer,
    payload jsonb DEFAULT '{}'::jsonb,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    result jsonb,
    error text,
    retry_count integer DEFAULT 0,
    max_retries integer DEFAULT 3,
    estimated_duration integer DEFAULT 30,
    resource_requirements jsonb DEFAULT '{}'::jsonb,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.ml_task_queue OWNER TO newsapp;

--
-- Name: ml_task_queue_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.ml_task_queue_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.ml_task_queue_id_seq OWNER TO newsapp;

--
-- Name: ml_task_queue_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.ml_task_queue_id_seq OWNED BY public.ml_task_queue.id;


--
-- Name: performance_metrics; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.performance_metrics (
    id integer NOT NULL,
    metric_name character varying(100) NOT NULL,
    metric_value numeric(10,2),
    metric_unit character varying(20),
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    metadata jsonb
);


ALTER TABLE public.performance_metrics OWNER TO newsapp;

--
-- Name: performance_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.performance_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.performance_metrics_id_seq OWNER TO newsapp;

--
-- Name: performance_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.performance_metrics_id_seq OWNED BY public.performance_metrics.id;


--
-- Name: performance_monitoring; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.performance_monitoring (
    id integer NOT NULL,
    operation_type character varying(50) NOT NULL,
    operation_id character varying(255),
    duration_ms integer NOT NULL,
    success boolean NOT NULL,
    error_message text,
    resource_usage jsonb DEFAULT '{}'::jsonb,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.performance_monitoring OWNER TO newsapp;

--
-- Name: performance_monitoring_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.performance_monitoring_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.performance_monitoring_id_seq OWNER TO newsapp;

--
-- Name: performance_monitoring_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.performance_monitoring_id_seq OWNED BY public.performance_monitoring.id;


--
-- Name: priority_rules; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.priority_rules (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    condition text NOT NULL,
    priority character varying(20) DEFAULT 'medium'::character varying NOT NULL,
    enabled boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    created_by character varying(100) DEFAULT 'system'::character varying
);


ALTER TABLE public.priority_rules OWNER TO newsapp;

--
-- Name: TABLE priority_rules; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.priority_rules IS 'Rules for content prioritization';


--
-- Name: COLUMN priority_rules.condition; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.priority_rules.condition IS 'SQL-like condition for matching articles';


--
-- Name: COLUMN priority_rules.priority; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.priority_rules.priority IS 'Priority level: critical, high, medium, low';


--
-- Name: priority_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.priority_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.priority_rules_id_seq OWNER TO newsapp;

--
-- Name: priority_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.priority_rules_id_seq OWNED BY public.priority_rules.id;


--
-- Name: rate_limiting; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.rate_limiting (
    id integer NOT NULL,
    resource_type character varying(50) NOT NULL,
    resource_key character varying(255) NOT NULL,
    request_count integer DEFAULT 1,
    window_start timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    max_requests integer NOT NULL,
    window_duration_seconds integer NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.rate_limiting OWNER TO newsapp;

--
-- Name: rate_limiting_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.rate_limiting_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.rate_limiting_id_seq OWNER TO newsapp;

--
-- Name: rate_limiting_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.rate_limiting_id_seq OWNED BY public.rate_limiting.id;


--
-- Name: rss_feeds; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.rss_feeds (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    url text NOT NULL,
    description text,
    tier integer DEFAULT 2 NOT NULL,
    priority integer DEFAULT 5,
    language character varying(10) DEFAULT 'en'::character varying,
    country character varying(100),
    category character varying(50) NOT NULL,
    subcategory character varying(50),
    is_active boolean DEFAULT true,
    status character varying(20) DEFAULT 'active'::character varying,
    update_frequency integer DEFAULT 30,
    max_articles_per_update integer DEFAULT 50,
    success_rate numeric(5,2) DEFAULT 0.0,
    avg_response_time integer DEFAULT 0,
    reliability_score numeric(3,2) DEFAULT 0.0,
    last_fetched timestamp with time zone,
    last_success timestamp with time zone,
    last_error text,
    warning_message text,
    tags jsonb DEFAULT '[]'::jsonb,
    custom_headers jsonb DEFAULT '{}'::jsonb,
    filters jsonb DEFAULT '{}'::jsonb,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rss_feeds_priority_check CHECK (((priority >= 1) AND (priority <= 10))),
    CONSTRAINT rss_feeds_tier_check CHECK ((tier = ANY (ARRAY[1, 2, 3])))
);


ALTER TABLE public.rss_feeds OWNER TO newsapp;

--
-- Name: TABLE rss_feeds; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.rss_feeds IS 'Enhanced RSS feed registry with tier system and comprehensive management';


--
-- Name: COLUMN rss_feeds.tier; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.rss_feeds.tier IS 'Feed tier: 1=wire services (Reuters, AP), 2=institutions (BBC, CNN), 3=specialized (TechCrunch, Ars)';


--
-- Name: COLUMN rss_feeds.priority; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.rss_feeds.priority IS 'Processing priority: 1=highest, 10=lowest';


--
-- Name: COLUMN rss_feeds.reliability_score; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.rss_feeds.reliability_score IS 'Overall reliability score (0.0-1.0) based on accuracy and consistency';


--
-- Name: COLUMN rss_feeds.tags; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.rss_feeds.tags IS 'JSON array of tags for categorization and filtering';


--
-- Name: COLUMN rss_feeds.custom_headers; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.rss_feeds.custom_headers IS 'JSON object of custom HTTP headers for requests';


--
-- Name: COLUMN rss_feeds.filters; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.rss_feeds.filters IS 'JSON object of content filtering rules';


--
-- Name: rss_feeds_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.rss_feeds_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.rss_feeds_id_seq OWNER TO newsapp;

--
-- Name: rss_feeds_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.rss_feeds_id_seq OWNED BY public.rss_feeds.id;


--
-- Name: search_logs; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.search_logs (
    id integer NOT NULL,
    query text NOT NULL,
    results_count integer DEFAULT 0,
    search_time double precision DEFAULT 0.0,
    user_id integer,
    "timestamp" timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    filters jsonb DEFAULT '{}'::jsonb,
    search_type character varying(20) DEFAULT 'full_text'::character varying
);


ALTER TABLE public.search_logs OWNER TO newsapp;

--
-- Name: TABLE search_logs; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.search_logs IS 'Logs search queries and results for analytics and optimization';


--
-- Name: COLUMN search_logs.search_time; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.search_logs.search_time IS 'Search execution time in seconds';


--
-- Name: COLUMN search_logs.filters; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.search_logs.filters IS 'JSON object of search filters applied';


--
-- Name: COLUMN search_logs.search_type; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.search_logs.search_type IS 'Type of search: full_text, semantic, hybrid';


--
-- Name: search_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.search_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.search_logs_id_seq OWNER TO newsapp;

--
-- Name: search_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.search_logs_id_seq OWNED BY public.search_logs.id;


--
-- Name: similarity_scores; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.similarity_scores (
    id integer NOT NULL,
    article_id_1 integer,
    article_id_2 integer,
    similarity_score numeric(3,2) NOT NULL,
    comparison_method character varying(50),
    compared_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.similarity_scores OWNER TO newsapp;

--
-- Name: similarity_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.similarity_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.similarity_scores_id_seq OWNER TO newsapp;

--
-- Name: similarity_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.similarity_scores_id_seq OWNED BY public.similarity_scores.id;


--
-- Name: sources; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.sources (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    url text NOT NULL,
    category character varying(50) NOT NULL,
    description text,
    language character varying(10) DEFAULT 'en'::character varying,
    country character varying(100),
    is_active boolean DEFAULT true,
    status character varying(20) DEFAULT 'active'::character varying,
    article_count integer DEFAULT 0,
    articles_today integer DEFAULT 0,
    articles_this_week integer DEFAULT 0,
    last_article_date timestamp without time zone,
    success_rate numeric(5,2) DEFAULT 0.0,
    avg_response_time integer DEFAULT 0,
    reliability_score numeric(3,2) DEFAULT 0.0,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.sources OWNER TO newsapp;

--
-- Name: TABLE sources; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.sources IS 'Stores news sources with metadata and performance metrics';


--
-- Name: COLUMN sources.category; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.sources.category IS 'Source category: news, technology, business, politics, sports, entertainment, science, health, world, local, other';


--
-- Name: COLUMN sources.status; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.sources.status IS 'Current status: active, inactive, error, warning';


--
-- Name: COLUMN sources.success_rate; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.sources.success_rate IS 'Percentage of successful article collection attempts';


--
-- Name: COLUMN sources.avg_response_time; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.sources.avg_response_time IS 'Average response time in milliseconds';


--
-- Name: COLUMN sources.reliability_score; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.sources.reliability_score IS 'Overall reliability score (0.0-1.0) based on accuracy and consistency';


--
-- Name: sources_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.sources_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.sources_id_seq OWNER TO newsapp;

--
-- Name: sources_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.sources_id_seq OWNED BY public.sources.id;


--
-- Name: storage_cleanup_policies; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.storage_cleanup_policies (
    id integer NOT NULL,
    policy_name character varying(100) NOT NULL,
    table_name character varying(100) NOT NULL,
    retention_days integer NOT NULL,
    cleanup_condition text NOT NULL,
    is_active boolean DEFAULT true,
    last_run timestamp without time zone,
    last_cleaned_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.storage_cleanup_policies OWNER TO newsapp;

--
-- Name: storage_cleanup_policies_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.storage_cleanup_policies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.storage_cleanup_policies_id_seq OWNER TO newsapp;

--
-- Name: storage_cleanup_policies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.storage_cleanup_policies_id_seq OWNED BY public.storage_cleanup_policies.id;


--
-- Name: story_threads; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.story_threads (
    id integer NOT NULL,
    title character varying(255) NOT NULL,
    summary text,
    priority_level_id integer,
    status character varying(50) DEFAULT 'active'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.story_threads OWNER TO newsapp;

--
-- Name: story_threads_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.story_threads_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.story_threads_id_seq OWNER TO newsapp;

--
-- Name: story_threads_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.story_threads_id_seq OWNED BY public.story_threads.id;


--
-- Name: storyline_articles; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.storyline_articles (
    id integer NOT NULL,
    storyline_id integer,
    article_id integer,
    relevance_score double precision DEFAULT 0.0,
    importance_score double precision DEFAULT 0.0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.storyline_articles OWNER TO newsapp;

--
-- Name: storyline_articles_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.storyline_articles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.storyline_articles_id_seq OWNER TO newsapp;

--
-- Name: storyline_articles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.storyline_articles_id_seq OWNED BY public.storyline_articles.id;


--
-- Name: system_alerts; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.system_alerts (
    id integer NOT NULL,
    title character varying(255) NOT NULL,
    message text NOT NULL,
    severity character varying(20) DEFAULT 'info'::character varying NOT NULL,
    category character varying(50) DEFAULT 'system'::character varying,
    resolved boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    resolved_at timestamp with time zone,
    resolved_by character varying(100),
    context jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE public.system_alerts OWNER TO newsapp;

--
-- Name: TABLE system_alerts; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON TABLE public.system_alerts IS 'System alerts and notifications for monitoring';


--
-- Name: COLUMN system_alerts.severity; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.system_alerts.severity IS 'Alert severity: critical, warning, info';


--
-- Name: COLUMN system_alerts.category; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.system_alerts.category IS 'Alert category: system, performance, security, etc.';


--
-- Name: COLUMN system_alerts.context; Type: COMMENT; Schema: public; Owner: newsapp
--

COMMENT ON COLUMN public.system_alerts.context IS 'JSON object with additional context about the alert';


--
-- Name: system_alerts_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.system_alerts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.system_alerts_id_seq OWNER TO newsapp;

--
-- Name: system_alerts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.system_alerts_id_seq OWNED BY public.system_alerts.id;


--
-- Name: system_logs; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.system_logs (
    id integer NOT NULL,
    level character varying(20) NOT NULL,
    message text NOT NULL,
    source character varying(100),
    metadata jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.system_logs OWNER TO newsapp;

--
-- Name: system_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.system_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.system_logs_id_seq OWNER TO newsapp;

--
-- Name: system_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.system_logs_id_seq OWNED BY public.system_logs.id;


--
-- Name: system_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.system_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.system_metrics_id_seq OWNER TO newsapp;

--
-- Name: system_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.system_metrics_id_seq OWNED BY public.system_metrics.id;


--
-- Name: system_scaling_metrics; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.system_scaling_metrics (
    id integer NOT NULL,
    "timestamp" timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    total_articles integer DEFAULT 0,
    raw_articles integer DEFAULT 0,
    processing_articles integer DEFAULT 0,
    completed_articles integer DEFAULT 0,
    failed_articles integer DEFAULT 0,
    total_timeline_events integer DEFAULT 0,
    active_storylines integer DEFAULT 0,
    queue_size integer DEFAULT 0,
    running_tasks integer DEFAULT 0,
    database_size_bytes bigint DEFAULT 0,
    avg_processing_time_seconds numeric(10,2) DEFAULT 0,
    success_rate numeric(5,2) DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.system_scaling_metrics OWNER TO newsapp;

--
-- Name: system_scaling_metrics_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.system_scaling_metrics_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.system_scaling_metrics_id_seq OWNER TO newsapp;

--
-- Name: system_scaling_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.system_scaling_metrics_id_seq OWNED BY public.system_scaling_metrics.id;


--
-- Name: timeline_analysis; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.timeline_analysis (
    id integer NOT NULL,
    storyline_id character varying(255) NOT NULL,
    analysis_date date NOT NULL,
    total_events integer DEFAULT 0,
    high_importance_events integer DEFAULT 0,
    event_types jsonb DEFAULT '{}'::jsonb,
    key_entities jsonb DEFAULT '[]'::jsonb,
    geographic_coverage jsonb DEFAULT '[]'::jsonb,
    sentiment_trend numeric(3,2) DEFAULT 0.0,
    complexity_score numeric(3,2) DEFAULT 0.0,
    narrative_coherence numeric(3,2) DEFAULT 0.0,
    ml_insights jsonb DEFAULT '{}'::jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.timeline_analysis OWNER TO newsapp;

--
-- Name: timeline_analysis_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.timeline_analysis_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.timeline_analysis_id_seq OWNER TO newsapp;

--
-- Name: timeline_analysis_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.timeline_analysis_id_seq OWNED BY public.timeline_analysis.id;


--
-- Name: timeline_events; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.timeline_events (
    id integer NOT NULL,
    event_id character varying(255) NOT NULL,
    storyline_id character varying(255) NOT NULL,
    title text NOT NULL,
    description text,
    event_date date NOT NULL,
    event_time time without time zone,
    source character varying(255),
    url text,
    importance_score numeric(3,2) DEFAULT 0.0,
    event_type character varying(100) DEFAULT 'general'::character varying,
    location character varying(255),
    entities jsonb DEFAULT '[]'::jsonb,
    tags text[] DEFAULT '{}'::text[],
    ml_generated boolean DEFAULT true,
    confidence_score numeric(3,2) DEFAULT 0.0,
    source_article_ids integer[] DEFAULT '{}'::integer[],
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_confidence_score CHECK (((confidence_score >= 0.0) AND (confidence_score <= 1.0))),
    CONSTRAINT chk_importance_score CHECK (((importance_score >= 0.0) AND (importance_score <= 1.0)))
);


ALTER TABLE public.timeline_events OWNER TO newsapp;

--
-- Name: timeline_events_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.timeline_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.timeline_events_id_seq OWNER TO newsapp;

--
-- Name: timeline_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.timeline_events_id_seq OWNED BY public.timeline_events.id;


--
-- Name: timeline_generation_log; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.timeline_generation_log (
    id integer NOT NULL,
    storyline_id character varying(255) NOT NULL,
    generation_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    events_generated integer DEFAULT 0,
    articles_analyzed integer DEFAULT 0,
    ml_model_used character varying(255),
    generation_time_seconds integer DEFAULT 0,
    success boolean DEFAULT true,
    error_message text,
    parameters jsonb DEFAULT '{}'::jsonb
);


ALTER TABLE public.timeline_generation_log OWNER TO newsapp;

--
-- Name: timeline_generation_log_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.timeline_generation_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.timeline_generation_log_id_seq OWNER TO newsapp;

--
-- Name: timeline_generation_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.timeline_generation_log_id_seq OWNED BY public.timeline_generation_log.id;


--
-- Name: timeline_milestones; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.timeline_milestones (
    id integer NOT NULL,
    storyline_id character varying(255) NOT NULL,
    event_id character varying(255) NOT NULL,
    milestone_type character varying(100) NOT NULL,
    significance_score numeric(3,2) DEFAULT 0.0,
    impact_description text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.timeline_milestones OWNER TO newsapp;

--
-- Name: timeline_milestones_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.timeline_milestones_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.timeline_milestones_id_seq OWNER TO newsapp;

--
-- Name: timeline_milestones_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.timeline_milestones_id_seq OWNED BY public.timeline_milestones.id;


--
-- Name: timeline_periods; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.timeline_periods (
    id integer NOT NULL,
    storyline_id character varying(255) NOT NULL,
    period character varying(50) NOT NULL,
    start_date date NOT NULL,
    end_date date NOT NULL,
    event_count integer DEFAULT 0,
    key_events jsonb DEFAULT '[]'::jsonb,
    summary text,
    ml_generated boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.timeline_periods OWNER TO newsapp;

--
-- Name: timeline_periods_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.timeline_periods_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.timeline_periods_id_seq OWNER TO newsapp;

--
-- Name: timeline_periods_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.timeline_periods_id_seq OWNED BY public.timeline_periods.id;


--
-- Name: user_rules; Type: TABLE; Schema: public; Owner: newsapp
--

CREATE TABLE public.user_rules (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    rule_type character varying(50) NOT NULL,
    rule_config jsonb NOT NULL,
    priority_level_id integer,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.user_rules OWNER TO newsapp;

--
-- Name: user_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: newsapp
--

CREATE SEQUENCE public.user_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_rules_id_seq OWNER TO newsapp;

--
-- Name: user_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: newsapp
--

ALTER SEQUENCE public.user_rules_id_seq OWNED BY public.user_rules.id;


--
-- Name: api_cache id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.api_cache ALTER COLUMN id SET DEFAULT nextval('public.api_cache_id_seq'::regclass);


--
-- Name: api_usage_tracking id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.api_usage_tracking ALTER COLUMN id SET DEFAULT nextval('public.api_usage_tracking_id_seq'::regclass);


--
-- Name: application_metrics id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.application_metrics ALTER COLUMN id SET DEFAULT nextval('public.application_metrics_id_seq'::regclass);


--
-- Name: article_clusters id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.article_clusters ALTER COLUMN id SET DEFAULT nextval('public.article_clusters_id_seq'::regclass);


--
-- Name: article_processing_batches id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.article_processing_batches ALTER COLUMN id SET DEFAULT nextval('public.article_processing_batches_id_seq'::regclass);


--
-- Name: article_volume_metrics id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.article_volume_metrics ALTER COLUMN id SET DEFAULT nextval('public.article_volume_metrics_id_seq'::regclass);


--
-- Name: articles id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.articles ALTER COLUMN id SET DEFAULT nextval('public.articles_id_seq'::regclass);


--
-- Name: automation_logs id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.automation_logs ALTER COLUMN id SET DEFAULT nextval('public.automation_logs_id_seq'::regclass);


--
-- Name: automation_tasks id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.automation_tasks ALTER COLUMN id SET DEFAULT nextval('public.automation_tasks_id_seq'::regclass);


--
-- Name: briefing_templates id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.briefing_templates ALTER COLUMN id SET DEFAULT nextval('public.briefing_templates_id_seq'::regclass);


--
-- Name: cluster_articles id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.cluster_articles ALTER COLUMN id SET DEFAULT nextval('public.cluster_articles_id_seq'::regclass);


--
-- Name: collection_rules id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.collection_rules ALTER COLUMN id SET DEFAULT nextval('public.collection_rules_id_seq'::regclass);


--
-- Name: content_hashes id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_hashes ALTER COLUMN id SET DEFAULT nextval('public.content_hashes_id_seq'::regclass);


--
-- Name: content_priority_assignments id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_priority_assignments ALTER COLUMN id SET DEFAULT nextval('public.content_priority_assignments_id_seq'::regclass);


--
-- Name: content_priority_levels id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_priority_levels ALTER COLUMN id SET DEFAULT nextval('public.content_priority_levels_id_seq'::regclass);


--
-- Name: database_metrics id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.database_metrics ALTER COLUMN id SET DEFAULT nextval('public.database_metrics_id_seq'::regclass);


--
-- Name: deduplication_settings id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.deduplication_settings ALTER COLUMN id SET DEFAULT nextval('public.deduplication_settings_id_seq'::regclass);


--
-- Name: deduplication_stats id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.deduplication_stats ALTER COLUMN id SET DEFAULT nextval('public.deduplication_stats_id_seq'::regclass);


--
-- Name: entities id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.entities ALTER COLUMN id SET DEFAULT nextval('public.entities_id_seq'::regclass);


--
-- Name: feed_categories id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.feed_categories ALTER COLUMN id SET DEFAULT nextval('public.feed_categories_id_seq'::regclass);


--
-- Name: feed_filtering_rules id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.feed_filtering_rules ALTER COLUMN id SET DEFAULT nextval('public.feed_filtering_rules_id_seq'::regclass);


--
-- Name: feed_performance_metrics id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.feed_performance_metrics ALTER COLUMN id SET DEFAULT nextval('public.feed_performance_metrics_id_seq'::regclass);


--
-- Name: generated_briefings id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.generated_briefings ALTER COLUMN id SET DEFAULT nextval('public.generated_briefings_id_seq'::regclass);


--
-- Name: global_filtering_config id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.global_filtering_config ALTER COLUMN id SET DEFAULT nextval('public.global_filtering_config_id_seq'::regclass);


--
-- Name: ml_model_performance id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_model_performance ALTER COLUMN id SET DEFAULT nextval('public.ml_model_performance_id_seq'::regclass);


--
-- Name: ml_performance_metrics id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_performance_metrics ALTER COLUMN id SET DEFAULT nextval('public.ml_performance_metrics_id_seq'::regclass);


--
-- Name: ml_resource_usage id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_resource_usage ALTER COLUMN id SET DEFAULT nextval('public.ml_resource_usage_id_seq'::regclass);


--
-- Name: ml_task_dependencies id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_task_dependencies ALTER COLUMN id SET DEFAULT nextval('public.ml_task_dependencies_id_seq'::regclass);


--
-- Name: ml_task_queue id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_task_queue ALTER COLUMN id SET DEFAULT nextval('public.ml_task_queue_id_seq'::regclass);


--
-- Name: performance_metrics id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.performance_metrics ALTER COLUMN id SET DEFAULT nextval('public.performance_metrics_id_seq'::regclass);


--
-- Name: performance_monitoring id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.performance_monitoring ALTER COLUMN id SET DEFAULT nextval('public.performance_monitoring_id_seq'::regclass);


--
-- Name: priority_rules id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.priority_rules ALTER COLUMN id SET DEFAULT nextval('public.priority_rules_id_seq'::regclass);


--
-- Name: rate_limiting id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.rate_limiting ALTER COLUMN id SET DEFAULT nextval('public.rate_limiting_id_seq'::regclass);


--
-- Name: rss_feeds id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.rss_feeds ALTER COLUMN id SET DEFAULT nextval('public.rss_feeds_id_seq'::regclass);


--
-- Name: search_logs id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.search_logs ALTER COLUMN id SET DEFAULT nextval('public.search_logs_id_seq'::regclass);


--
-- Name: similarity_scores id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.similarity_scores ALTER COLUMN id SET DEFAULT nextval('public.similarity_scores_id_seq'::regclass);


--
-- Name: sources id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.sources ALTER COLUMN id SET DEFAULT nextval('public.sources_id_seq'::regclass);


--
-- Name: storage_cleanup_policies id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.storage_cleanup_policies ALTER COLUMN id SET DEFAULT nextval('public.storage_cleanup_policies_id_seq'::regclass);


--
-- Name: story_threads id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.story_threads ALTER COLUMN id SET DEFAULT nextval('public.story_threads_id_seq'::regclass);


--
-- Name: storyline_articles id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.storyline_articles ALTER COLUMN id SET DEFAULT nextval('public.storyline_articles_id_seq'::regclass);


--
-- Name: system_alerts id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.system_alerts ALTER COLUMN id SET DEFAULT nextval('public.system_alerts_id_seq'::regclass);


--
-- Name: system_logs id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.system_logs ALTER COLUMN id SET DEFAULT nextval('public.system_logs_id_seq'::regclass);


--
-- Name: system_metrics id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.system_metrics ALTER COLUMN id SET DEFAULT nextval('public.system_metrics_id_seq'::regclass);


--
-- Name: system_scaling_metrics id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.system_scaling_metrics ALTER COLUMN id SET DEFAULT nextval('public.system_scaling_metrics_id_seq'::regclass);


--
-- Name: timeline_analysis id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_analysis ALTER COLUMN id SET DEFAULT nextval('public.timeline_analysis_id_seq'::regclass);


--
-- Name: timeline_events id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_events ALTER COLUMN id SET DEFAULT nextval('public.timeline_events_id_seq'::regclass);


--
-- Name: timeline_generation_log id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_generation_log ALTER COLUMN id SET DEFAULT nextval('public.timeline_generation_log_id_seq'::regclass);


--
-- Name: timeline_milestones id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_milestones ALTER COLUMN id SET DEFAULT nextval('public.timeline_milestones_id_seq'::regclass);


--
-- Name: timeline_periods id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_periods ALTER COLUMN id SET DEFAULT nextval('public.timeline_periods_id_seq'::regclass);


--
-- Name: user_rules id; Type: DEFAULT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.user_rules ALTER COLUMN id SET DEFAULT nextval('public.user_rules_id_seq'::regclass);


--
-- Data for Name: api_cache; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.api_cache (id, cache_key, service, query, response_data, created_at) FROM stdin;
\.


--
-- Data for Name: api_usage_tracking; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.api_usage_tracking (id, service, endpoint, request_count, response_size, processing_time_ms, success, error_message, created_at) FROM stdin;
\.


--
-- Data for Name: application_metrics; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.application_metrics (id, "timestamp", articles_processed, articles_failed, processing_time_ms, queue_size, active_workers, tasks_completed, tasks_failed, avg_processing_time_ms, created_at) FROM stdin;
\.


--
-- Data for Name: article_clusters; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.article_clusters (id, main_article_id, cluster_type, topic, summary, article_count, cohesion_score, created_date, updated_at) FROM stdin;
\.


--
-- Data for Name: article_processing_batches; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.article_processing_batches (id, batch_id, batch_type, total_articles, processed_articles, failed_articles, status, priority, created_at, started_at, completed_at, error_message, metadata) FROM stdin;
\.


--
-- Data for Name: article_volume_metrics; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.article_volume_metrics (id, "timestamp", total_articles, new_articles_last_hour, new_articles_last_day, articles_by_source, articles_by_category, avg_article_length, processing_success_rate, created_at) FROM stdin;
\.


--
-- Data for Name: articles; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.articles (id, title, content, summary, url, source, published_at, category, language, quality_score, processing_status, content_hash, deduplication_status, content_similarity_score, normalized_content, ml_data, rag_keep_longer, rag_context_needed, rag_priority, processing_started_at, processing_completed_at, created_at, updated_at, word_count, reading_time, feed_id, tags, sentiment_score, entities, readability_score) FROM stdin;
1	Sample Article 1	This is sample content for testing the API integration.	\N	https://example.com/article1	BBC News	2025-09-08 22:15:35.136093	Technology	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-08 22:15:35.136093	2025-09-08 22:15:35.136093	150	1	1	[]	\N	{}	\N
2	Sample Article 2	Another sample article for testing purposes.	\N	https://example.com/article2	Reuters	2025-09-08 22:15:35.136093	Business	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-08 22:15:35.136093	2025-09-08 22:15:35.136093	200	2	2	[]	\N	{}	\N
3	Sample Article 3	Third sample article to verify the system works.	\N	https://example.com/article3	TechCrunch	2025-09-08 22:15:35.136093	Technology	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-08 22:15:35.136093	2025-09-08 22:15:35.136093	100	1	3	[]	\N	{}	\N
4	England's NHS trust league tables revealed - find out where yours ranks	The new league tables score trusts on measures including finances and patient access to care.	\N	https://www.bbc.com/news/articles/cq8eqxlypv7o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 09:31:06	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.051587	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
5	Mandelson called Epstein 'best pal' in birthday message	The description is contained an alleged 50th "birthday book" given to the disgraced financier that has been released by US lawmakers.	\N	https://www.bbc.com/news/articles/cwy9dwe50leo?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 11:51:04	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.055969	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
6	Bridget Phillipson and Emily Thornberry join Labour deputy leader race	Hopefuls have until the end of Thursday to secure enough backing from Labour MPs to take part.	\N	https://www.bbc.com/news/articles/c3rvqv9yg4eo?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 12:53:56	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.057399	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
7	Prince Harry donates £1.1m to Children in Need	Prince Harry offers support to a project tackling youth violence in Nottingham.	\N	https://www.bbc.com/news/articles/ckg2xknwyp7o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 13:26:01	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.058568	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
8	Plans to cool Arctic using geo-engineering are dangerous, scientists warn	Controversial approaches to cooling the planet are unlikely to work, according to dozens of polar scientists.	\N	https://www.bbc.com/news/articles/c5yqw996q1ko?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 09:06:36	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.059561	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
9	'I'm angry. It's not right' - locals want asylum hotels shut, but are shared houses the answer?	The BBC's UK editor, Ed Thomas, meets local people and asylum seekers in two towns in north-west England.	\N	https://www.bbc.com/news/articles/c07vn1y2jz2o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 05:05:09	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.060548	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
10	Girl stabbed six times as she shielded sister from Southport attacker, inquiry hears	An inquiry into the attacks hears the father of the girl fainted in shock when he saw his daughter.	\N	https://www.bbc.com/news/articles/c8exw9l1jxpo?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 14:37:53	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.061485	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
11	'No one is irreplaceable', says BBC chief after scandals	Tim Davie tells MPs he is "not letting anything lie" when it comes to rooting out abuses of power.	\N	https://www.bbc.com/news/articles/cj07r78gg32o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 11:35:13	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.062398	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
12	Mystery donor offers £100k to find student who went missing after house party	Mother of Jack O’Sullivan, who disappeared in Bristol in March 2024, says she is "overcome" by the offer.	\N	https://www.bbc.com/news/articles/c04qpd7y9k0o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 06:26:49	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.063188	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
13	Anastacia: Arnold Schwarzenegger made me sing Whatta Man 12 times	As she celebrates 25 years in music, Anastacia reflects on the gigs she played on her way to the top.	\N	https://www.bbc.com/news/articles/cm2zmd2rmnko?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 00:34:21	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.063907	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
14	Who could replace Angela Rayner as Labour deputy leader?	The winning candidate - voted for by Labour members - will be announced on 25 October.	\N	https://www.bbc.com/news/articles/c8jm9lk19v3o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 14:08:09	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.064443	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
15	Inside Kyiv government building hit by missile strike	The BBC's Sarah Rainsford says Sunday's attack caused "a huge amount of damage".	\N	https://www.bbc.com/news/videos/cwyn3gnnvv3o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 10:52:51	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.065281	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
16	Graham Linehan: I don't regret my online posts	The Father Ted writer tells the BBC he stands by his online posts which led to his arrest last week.	\N	https://www.bbc.com/news/articles/c7v13v3z6lgo?at_medium=RSS&at_campaign=rss	BBC News	2025-09-08 21:50:24	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.065884	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
17	Why are young people protesting in Nepal and what are their demands?	Protests in Nepal turned violent after thousands of youngsters marched against the blocking of social media platforms.	\N	https://www.bbc.com/news/articles/crkj0lzlr3ro?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 13:19:41	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.066428	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
18	'I want to change the game' - meet Black Ferns star Jorja Miller	New Zealand's 21-year-old flanker Jorja Miller has emerged as one of the stars of the Women's Rugby World Cup.	\N	https://www.bbc.com/sport/rugby-union/articles/cj6xzexydy6o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 06:18:22	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.067219	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
19	What we know as 'birthday book' of messages to Epstein released	A US congressional panel has released a redacted copy of an alleged "birthday book" given to Epstein.	\N	https://www.bbc.com/news/articles/cr5q68j2169o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 11:21:48	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.067913	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
20	Play now	Think you can work out where's hotter and colder than you today? Find out by playing our game	\N	https://www.bbc.com/weather/articles/cwy5r7xwq8xo?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 04:30:18	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.068692	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
21	White House denies Trump's alleged birthday message to Epstein is authentic	The message purportedly written by Trump is inside a 238-page book released by a House committee.	\N	https://www.bbc.com/news/articles/cvgqnn4ngvdo?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 12:48:55	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.069247	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
22	Russian air strike kills 24 in pension queue, Ukraine says	The attack targeted the eastern village of Yarova, officials say, a few kilometres from the front line.	\N	https://www.bbc.com/news/articles/c1jz08j8313o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 14:36:46	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.069856	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
23	Mitchum deodorant recalled after 'itchy, burning armpits' claims	Mitchum recalled its roll-on products after users complained of soreness and "weeping" skin.	\N	https://www.bbc.com/news/articles/cly0gkrqq7ko?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 14:22:59	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.070416	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
24	Early deaths of people with learning disabilities 'shocking'	People with learning disabilities die 20 years younger than those without, data shows.	\N	https://www.bbc.com/news/articles/c2ezpx1mjz8o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 05:23:02	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.071138	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
25	Mum of soldier who took her own life after sexual assault says army failing women	Leighann McCready made the remarks after her daughter's superior pleaded guilty to sexual assault.	\N	https://www.bbc.com/news/articles/cj9z079yedvo?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 10:34:45	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.072148	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
26	Children's TV favourite Bagpuss to reawaken for new film	It will be the first new official Bagpuss production since the original beloved 1974 series.	\N	https://www.bbc.com/news/articles/crrjwlvxknko?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 03:49:19	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.073096	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
27	BBC News app	Top stories, breaking news, live reporting, and follow news topics that match your interests	\N	https://www.bbc.co.uk/news/10628994?at_medium=RSS&at_campaign=rss	BBC News	2025-04-30 14:04:28	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.074019	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
28	Has Labour Just Moved Towards the Right?	With Angela Rayner out, is Keir Starmer’s government more right wing?	\N	https://www.bbc.co.uk/sounds/play/p0m1cyhy?at_medium=RSS&at_campaign=rss	BBC News	2025-09-07 11:54:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.074852	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
29	The Global Story: The deal that broke Ukraine's trust	An exploration of the 1994 Budapest Memorandum, intended to enshrine Ukraine's security.	\N	https://www.bbc.co.uk/programmes/w3ct714l?at_medium=RSS&at_campaign=rss	BBC News	2025-09-04 05:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.07544	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
30	From building dream careers to losing everything	Unveiling a hidden scandal affecting a group of former players of the Premier League	\N	https://www.bbc.co.uk/iplayer/episode/m002d2kp/footballs-financial-shame-the-story-of-the-v11?at_mid=OgibwZ9HpE&at_campaign=Footballs_Financial_Shame_The_Story_of_the_V11&at_medium=display_ad&at_campaign_type=owned&at_nation=NET&at_audience_id=SS&at_product=iplayer&at_brand=m002d2kp&at_ptr_name=bbc&at_ptr_type=media&at_format=image&at_objective=consumption&at_link_title=Footballs_Financial_Shame_The_Story_of_the_V11&at_bbc_team=BBC	BBC News	2025-09-02 05:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.075899	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
31	Postecoglou replaces Nuno as Forest manager	Tactical analysis and fan opinion as Ange Postecoglou returns to the Premier League, three months after being sacked by Tottenham.	\N	https://www.bbc.com/sport/football/articles/cvgq6495gd6o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 12:31:37	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.076284	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
32	'Spotlight on Tuchel for Serbia test after drab displays'	Thomas Tuchel will face his toughest test as England coach against Serbia in the intimidating surroundings of Belgrade, says chief football writer Phil McNulty.	\N	https://www.bbc.com/sport/football/articles/c864wqezwgeo?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 05:17:26	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.076658	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
33	Premier League clubs seek clarity over Man City 'settlement'	Premier League clubs want more clarity about the settlement of a legal dispute with Manchester City over the rules that govern commercial deals, BBC Sport has been told.	\N	https://www.bbc.com/sport/football/articles/cy859l0xw89o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 14:03:27	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.077026	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
34	England recall Curran for first South Africa T20	All-rounder Sam Curran receives his first call-up under Brendon McCullum for the start of the three-match T20 series in Cardiff on Wednesday.	\N	https://www.bbc.com/sport/cricket/articles/cy8rypk0739o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 12:29:27	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.077375	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
35	Japan heatwave will be challenge for athletes - Coe	Japan has endured its hottest summer on record, with Saturday's opening day forecast to be 32C.	\N	https://www.bbc.com/sport/athletics/articles/cx23vy582q6o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 12:23:05	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.077727	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
36	Women's World Cup director defends one-sided games	Fans will never complain about "too many tries" at the Women's World Cup, says competition director Yvonne Nolan.	\N	https://www.bbc.com/sport/rugby-union/articles/c1mxr88g0e3o?at_medium=RSS&at_campaign=rss	BBC News	2025-09-09 12:03:15	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.077915	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
37	Apple Intelligence: Everything you need to know about Apple’s AI model and services	Apple Intelligence was designed to leverage things that generative AI already does well, like text and image generation, to improve upon existing features.	\N	https://techcrunch.com/2025/09/09/apple-intelligence-everything-you-need-to-know-about-apples-ai-model-and-services/	TechCrunch	2025-09-09 14:51:52	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.335147	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
38	Where top VCs are betting next: Index, Greylock, and Felicis share 2026 priorities at TechCrunch Disrupt 2025	Where are top VCs placing bets in 2026? Hear from Index Ventures’ Nina Achadjian, Greylock’s Jerry Chen, and Felicis’ Viviana Faga on the Builders Stage at TechCrunch Disrupt 2025, October 27–29 in San Francisco.	\N	https://techcrunch.com/2025/09/09/want-to-know-where-vcs-are-investing-next-be-in-the-room-at-techcrunch-disrupt-2025/	TechCrunch	2025-09-09 14:36:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.336508	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
39	Geothermal is too expensive, but Dig Energy’s impossibly small drill rig might fix that	Dig Energy's water-jet drilling right promises to cut drilling costs by up to 80%, helping geothermal heating hit price parity with fossil fuel furnaces.	\N	https://techcrunch.com/2025/09/09/geothermal-is-too-expensive-but-dig-energys-impossibly-small-drill-rig-might-fix-that/	TechCrunch	2025-09-09 14:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.337244	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
40	Plex urges users to change passwords after data breach	Customers are urged to take action after a database containing scrambled passwords and authentication information was compromised.	\N	https://techcrunch.com/2025/09/09/plex-urges-users-to-change-passwords-after-data-breach/	TechCrunch	2025-09-09 13:47:22	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.338215	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
41	Nuclearn gets $10.5M to help the nuclear industry embrace AI	Nuclearn has developed AI tools to help reactor operators automate routine paperwork. "Think of it as the junior employee," the company tells customers.	\N	https://techcrunch.com/2025/09/09/nuclearn-gets-10-5m-to-help-the-nuclear-industry-embrace-ai/	TechCrunch	2025-09-09 12:45:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.338999	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
73	NZ 'suitcase murder': Anti-depressants found in children's bodies	A jury heard Hakyung Lee killed her children in an attempted mass suicide after her husband's death.	\N	https://www.bbc.com/news/articles/c1wgqpx3q1go?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 06:07:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.799513	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
42	What is Mistral AI? Everything to know about the OpenAI competitor	Mistral AI, the French company that develops the AI chatbot, Le Chat, and several foundational large language models, is considered one of France’s most promising tech startups, and is arguably the only European company that could compete with OpenAI. “Go and download Le Chat, which is made by Mistral, rather than ChatGPT by OpenAI — [&#8230;]	\N	https://techcrunch.com/2025/09/09/what-is-mistral-ai-everything-to-know-about-the-openai-competitor/	TechCrunch	2025-09-09 12:15:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.339866	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
43	Blackrock-backed Minute Media acquires Indian AI startup that extracts sports highlights	VideoVerse is an Indian AI startup that lets broadcasters extract highlights and create content from sports footage.	\N	https://techcrunch.com/2025/09/09/blackrock-backed-minute-media-acquires-indian-ai-startup-that-extracts-sports-highlights/	TechCrunch	2025-09-09 12:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.341168	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
44	OpenAI denies that it’s weighing a ‘last-ditch’ California exit amid regulatory pressure over its restructuring	OpenAI executives are discussing a potential relocation out of California as increasing political resistance threatens the company's efforts to convert from nonprofit to for-profit status, according to The WSJ, but the company says it has no plans to leave.	\N	https://techcrunch.com/2025/09/08/openai-denies-that-its-weighing-a-last-ditch-california-exit-amid-regulatory-pressure-over-its-restructuring/	TechCrunch	2025-09-09 06:00:44	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.342046	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
45	ReOrbit lands record funding to take on Musk’s Starlink from Europe	Finnish startup ReOrbit, has raised a record €45 million Series A for the country to offer "sovereign" satellites.	\N	https://techcrunch.com/2025/09/08/reorbit-lands-record-funding-to-take-on-musks-starlink-from-europe/	TechCrunch	2025-09-09 04:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.342383	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
46	Nepal reverses social media ban as protests turn deadly	Nepal has reversed its social media ban following nationwide “Gen Z” protests and public backlash.	\N	https://techcrunch.com/2025/09/08/nepal-reverses-social-media-ban-as-protests-turn-deadly/	TechCrunch	2025-09-09 02:46:32	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.342657	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
47	Snap breaks into ‘startup squads’ as ad revenue stalls	CEO Evan Spiegel just announced the company is restructuring around small "startup squads" of 10 to 15 people to regain agility against larger competitors.	\N	https://techcrunch.com/2025/09/08/snap-breaks-into-startup-squads-as-ad-revenue-stalls/	TechCrunch	2025-09-09 01:41:29	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.342836	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
48	Intel’s chief executive of products departs among other leadership changes	Intel also announced the creation of a central engineering group that will build custom chips for outside customers.	\N	https://techcrunch.com/2025/09/08/intels-chief-executive-of-products-departs-among-other-leadership-changes/	TechCrunch	2025-09-08 23:22:13	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.343012	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
49	Netskope follows Rubrik as a rare cybersecurity IPO, both backed by Lightspeed	The 13-year-old company could be valued up to $6.5, with Lightspeed's stake worth $1.1 billion.	\N	https://techcrunch.com/2025/09/08/netskope-follows-rubrik-as-a-rare-cybersecurity-ipo-both-backed-lightspeed/	TechCrunch	2025-09-08 22:35:58	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.343418	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
50	Sam Altman says that bots are making social media feel ‘fake’	After watching Reddit's OpenAI and Anthropic communities, Sam Altman thinks social media cannot be trusted. And bots are to blame.	\N	https://techcrunch.com/2025/09/08/sam-altman-says-that-bots-are-making-social-media-feel-fake/	TechCrunch	2025-09-08 22:24:42	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.343604	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
51	Nuclear startup Deep Fission goes public in a curious SPAC	Deep Fission had been seeking to raise $15 million in a seed round as recently as April. The reverse merger will raise twice that amount.	\N	https://techcrunch.com/2025/09/08/nuclear-startup-deep-fission-goes-public-in-a-curious-spac/	TechCrunch	2025-09-08 20:08:40	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.343807	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
52	Bluesky adds private bookmarks	Bluesky adds bookmarks so users can privately save posts they want to reference later.	\N	https://techcrunch.com/2025/09/08/bluesky-adds-private-bookmarks/	TechCrunch	2025-09-08 19:40:51	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.343989	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
53	Pinecone founder Edo Liberty discusses why the next big AI breakthrough starts with search, at TechCrunch Disrupt 2025	At TechCrunch Disrupt 2025, Pinecone founder and CEO Edo Liberty will explain why the next wave of AI-native apps won’t be driven by bigger models, but by smarter search.	\N	https://techcrunch.com/2025/09/08/pinecone-founder-edo-liberty-explores-the-real-missing-link-in-enterprise-ai-at-techcrunch-disrupt-2025/	TechCrunch	2025-09-08 19:14:54	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.344273	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
54	Flexport’s Ryan Petersen on building through chaos at TechCrunch Disrupt 2025	Ryan Petersen, CEO of Flexport, joins the Builders Stage at TechCrunch Disrupt 2025, happening October 27–29 at Moscone West in San Francisco. Register to join.	\N	https://techcrunch.com/2025/09/08/find-out-how-flexports-ceo-ryan-petersen-builds-when-the-rules-keep-changing-at-techcrunch-disrupt-2025/	TechCrunch	2025-09-08 19:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.344419	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
55	Space DOTS raises $1.5M seed round to provide insights on orbital threats	Cefalo is the founder of Space DOTs, which launched in 2022 to detect space threats. She and her team have created a software platform for space tech manufacturers and operators to help them capture various data points, like radiation interference, as well as track any in-orbit anomalies, to help make space travel safer.	\N	https://techcrunch.com/2025/09/08/space-dots-raises-1-5m-seed-round-to-provide-insights-on-orbital-threats/	TechCrunch	2025-09-08 19:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.344575	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
56	VC giant Insight Partners notifies staff and limited partners after data breach	The venture capital giant, behind cyber giants Wiz and Databricks, said it has notified current and former employees and the firm's limited partners of its January breach.	\N	https://techcrunch.com/2025/09/08/vc-giant-insight-partners-notifies-staff-and-limited-partners-after-data-breach/	TechCrunch	2025-09-08 18:56:04	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.344734	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
57	Hyundai’s out-of-this-world EV concept is a glimpse at the upcoming Ioniq 3	Hyundai is out with a new concept car that previews a smaller EV that could slot below the Ioniq 5. And while the design is pretty bold, and full of what seems to be veiled references to Star Wars, the idea of a smaller (and hopefully less expensive) electric hatchback is surely one of the [&#8230;]	\N	https://www.theverge.com/news/774315/hyundai-concept-three-ev-ioniq-3-star-wars	The Verge	2025-09-09 14:34:26	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.477818	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
95	Why monsoon rains have been so deadly in India this year	Rains have caused landslides and severe floods in parts of the country and killed hundreds.	\N	https://www.bbc.com/news/articles/c9wdr08wq2zo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 23:02:59	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.809561	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
58	Google’s Veo 3 can now generate vertical AI videos	Google has added support for 1080p resolution and vertical video formats to its Veo 3 AI video generator. According to the announcement on Google’s developer blog, both Veo 3 and Veo 3 Fast — a faster, and more affordable version of the video model that produces lower-quality results — now allow users to generate videos [&#8230;]	\N	https://www.theverge.com/news/774352/google-veo-3-ai-vertical-video-1080p-support	The Verge	2025-09-09 14:23:51	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.47932	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
59	Motorola’s budget Razr is even more affordable now that it’s $100 off	If you’ve been eyeing a flip phone but have been put off by the price, now’s your chance to snag one at a serious discount. Motorola’s latest Razr is currently matching its all-time low price of $599.99 ($100 off) at Amazon, Best Buy, and Motorola’s online storefront, making what was already an affordable flip phone [&#8230;]	\N	https://www.theverge.com/tech/773288/motorola-razr-2025-superman-4k-ultra-hd-deal-sale	The Verge	2025-09-09 14:15:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.480792	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
60	Apple iPhone 17 launch event: how to watch	It’s that time of year again: Apple is getting ready to reveal all of the changes coming to its latest generation of iPhones. This year’s “awe dropping” event is expected to include spec bumps across the iPhone 17 lineup, in addition to an ultra-thin iPhone 17 Air. Rumors suggest that we may even get a [&#8230;]	\N	https://www.theverge.com/news/773176/apple-iphone-17-launch-event-watch-time-date	The Verge	2025-09-09 14:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.482425	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
61	This Atari handheld with retro controls is finally available for preorder	Nearly two years after it was first announced at CES 2024, My Arcade’s Atari Gamestation Go handheld is finally available for preorder for $179.99 through the company’s website, with shipping expected to start in October 2025. That’s a small price bump from the expected $149.99 pricing announced earlier this year during CES 2025, but the [&#8230;]	\N	https://www.theverge.com/news/774305/atari-gamestation-go-retro-handheld-trackball-paddle	The Verge	2025-09-09 13:18:10	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.483791	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
62	Canon is bringing back a point-and-shoot from 2016 with fewer features and a higher price (it’s viral)	Canon seems to be riding the TikTok digicam resurgence and is rereleasing a mid-2010s point-and-shoot — the PowerShot Elph 360 HS A. It’s mostly the same camera as the original Elph 360 HS, first launched in the very different world of 2016 and recently anointed the darling pocket camera of celebrities like Kendall Jenner and [&#8230;]	\N	https://www.theverge.com/news/774095/canon-powershot-elph-360-hsa-kendall-jenner-reissue-price-specs	The Verge	2025-09-09 13:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.485223	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
63	Guillermo del Toro makes Frankenstein his own	Frankenstein is one of those stories that's been retold countless times. And yet, Guillermo del Toro has managed to make a version that not only feels true to Mary Shelley's original, but is also imbued with the trademarks the director is known for. Maybe that shouldn't be too surprising - when presenting the film at [&#8230;]	\N	https://www.theverge.com/toronto-international-film-festival/774035/tiff-2025-reviews-frankenstein-normal-eternity	The Verge	2025-09-09 12:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.486654	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
64	Google pulls the Pixel 10’s Daily Hub to ‘enhance its performance’	When Google launched the Pixel 10 line last month, it gave as much attention to its AI-enabled software tricks as it did the hardware upgrades. But now, less than two weeks after the Pixel 10 series hit store shelves, its already pulled one of those AI features: Daily Hub, which collects the weather and your [&#8230;]	\N	https://www.theverge.com/news/774274/google-pulls-the-pixel-10s-daily-hub-to-enhance-its-performance	The Verge	2025-09-09 11:50:45	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.487828	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
65	New Beats earbuds leak hours before Apple&#8217;s big event	Apple teased the upcoming Powerbeats Fit last month, and now renders and specifications for the sporty wireless earbuds have appeared online that give us a closer look at what to expect. According to trusted leaker Evan Blass, the new Beats earbuds will be available in four colorways — orange, gray, black, and pink — and [&#8230;]	\N	https://www.theverge.com/news/774250/beats-powerbeats-fit-apple-wireless-earbuds-leak	The Verge	2025-09-09 11:00:20	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.488906	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
66	Firefox launches ‘shake to summarize’ on iPhones	Firefox will soon let you shake your iPhone to get an AI-generated summary of the webpage you’re on. The feature rolls out this week, and will operate using Apple’s on-device AI model on the iPhone 15 Pro or newer once iOS 26 launches. On older iOS versions, Mozilla will use its own cloud-based AI system [&#8230;]	\N	https://www.theverge.com/news/774129/firefox-shake-to-summarize-ios-ai-launch	The Verge	2025-09-09 10:51:49	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.489933	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
67	Israeli strike targets senior Hamas leadership in Qatar	A Hamas official says the group's negotiating team was targeted during a meeting in Doha.	\N	https://www.bbc.com/news/articles/ced58zywdwno?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 14:50:38	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.791272	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
68	White House denies Trump's alleged birthday message to Epstein is authentic	The message purportedly written by Trump is inside a 238-page book released by a House committee.	\N	https://www.bbc.com/news/articles/cvgqnn4ngvdo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 12:48:55	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.79261	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
69	Israeli military orders all Gaza City residents to evacuate ahead of ground assault	Prime Minister Netanyahu says recent strikes on high-rises are "only the beginning of the main, intensive operation" to capture the city.	\N	https://www.bbc.com/news/articles/cvg47kvld8go?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 11:48:49	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.793927	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
70	Russian air strike kills 24 in pension queue, Ukraine says	The attack targeted the eastern village of Yarova, officials say, a few kilometres from the front line.	\N	https://www.bbc.com/news/articles/c1jz08j8313o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 14:36:46	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.795332	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
71	First photos of site where NZ bushman hid children released	Police also found a stash of firearms and ammunition at the campsite surrounded by dense vegetation.	\N	https://www.bbc.com/news/articles/cj4y9ev2rw4o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 04:32:15	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.796711	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
72	Macron under pressure to name new PM as France simmers ahead of protests	François Bayrou has handed in his resignation, leaving France without a prime minister on the eve of nationwide protests.	\N	https://www.bbc.com/news/articles/c4gqx0zk72lo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 13:57:55	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.798137	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
74	At least 10 dead after train crashes into bus in Mexico	An investigation is under way after a freight train hit a bus as it tried to cross railway tracks.	\N	https://www.bbc.com/news/articles/c98elewrepko?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 09:40:09	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.800634	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
75	ICC hears war crimes case against Ugandan rebel leader	This is the court's first-ever confirmation of charges hearing without the accused present.	\N	https://www.bbc.com/news/articles/c1kwe02vyvdo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 11:31:06	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.801299	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
76	Greta Thunberg's Gaza flotilla hit by drone, organisers claim	Global Sumud Flotilla says a fire was started but Tunisian authorities deny that a drone was involved.	\N	https://www.bbc.com/news/articles/cly67g7pdlko?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 10:08:50	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.801856	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
77	Thai court rules ex-PM Thaksin must serve one year in jail	The Supreme Court ruling is yet another blow to the influential Shinawatra political dynasty.	\N	https://www.bbc.com/news/articles/cly7k2g37g4o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 06:41:09	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.802216	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
78	Ferrari chair to do community service over tax case	John Elkann and two of his siblings will pay €183m to settle an Italian inheritance tax dispute.	\N	https://www.bbc.com/news/articles/c8d7q99yd06o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 23:36:20	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.802799	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
79	Norway's left clinches vote win as populist right surges into second place	Labour has a chance of forming a narrow majority if it secures the support of four smaller parties on the centre left.	\N	https://www.bbc.com/news/articles/cq65255l27qo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 07:38:58	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.803175	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
80	NZ 'suitcase murder': Anti-depressants found in children's bodies	A jury heard Hakyung Lee killed her children in an attempted mass suicide after her husband's death.	\N	https://www.bbc.com/news/articles/c1wgqpx3q1go?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 06:07:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.803822	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
81	Murdochs reach deal in succession battle over media empire	Lachlan Murdoch will retain control of the conservative Fox and News Corp empire under the deal.	\N	https://www.bbc.com/news/articles/cn825x71g4do?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 10:01:36	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.804157	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
82	Greta Thunberg's Gaza flotilla hit by drone, organisers claim	Global Sumud Flotilla says a fire was started but Tunisian authorities deny that a drone was involved.	\N	https://www.bbc.com/news/articles/cly67g7pdlko?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 10:08:50	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.804629	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
83	Six Israelis killed by Palestinian gunmen at Jerusalem bus stop	Israeli police say two gunmen were killed after the attack, which was one of the deadliest in the city in years.	\N	https://www.bbc.com/news/articles/cr70ny0l7vgo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 13:09:39	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.8049	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
84	Hamas discussing US 'ideas' for Gaza ceasefire after Trump's 'last warning'	Hamas says it received "some ideas" from the US through mediators on how to reach a Gaza ceasefire deal.	\N	https://www.bbc.com/news/articles/cn0rxl7jwwpo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 18:08:14	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.805178	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
85	South Korean worker tells BBC of panic during US immigration raid at Hyundai plant	Some 400 US agents took part in the immigration raid on the Hyundai facility, detaining hundreds of workers, many South Korean nationals.	\N	https://www.bbc.com/news/articles/c5yqg0rln74o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-07 23:14:55	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.805759	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
86	Supreme Court lifts limits on  LA immigration raids	US top court says that immigration agents can stop people based solely on their race, language or job.	\N	https://www.bbc.com/news/articles/c784697j2v8o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 21:41:45	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.80604	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
87	Lisbon funicular crash victim was 'transport enthusiast'	Sixteen people died when the funicular crashed into a building in the Portuguese capital.	\N	https://www.bbc.com/news/articles/cq8ev844egpo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 13:08:20	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.806628	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
88	French doctor goes on trial for poisoning 30 patients, 12 fatally	Frédéric Péchier, considered by colleagues to be a highly-talented practitioner, maintains there is no proof of any poisoning.	\N	https://www.bbc.com/news/articles/crl5ngj9zwgo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 11:00:18	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.806959	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
89	Nepal anti-corruption protests explained	Protests in Nepal turned violent after thousands of youngsters marched against the blocking of social media platforms.	\N	https://www.bbc.com/news/articles/crkj0lzlr3ro?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 13:19:41	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.807195	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
90	Protect Arctic from 'dangerous' climate engineering, scientists warn	Controversial approaches to cooling the planet are unlikely to work, according to dozens of polar scientists.	\N	https://www.bbc.com/news/articles/c5yqw996q1ko?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 09:06:36	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.807808	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
91	What we know as 'birthday book' of messages to Epstein released	A US congressional panel has released a redacted copy of an alleged "birthday book" given to Epstein.	\N	https://www.bbc.com/news/articles/cr5q68j2169o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 11:21:48	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.80804	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
92	Why has the French PM had to go and what happens next?	France's prime minister has lost a confidence vote, sending parliament into another period of chaos and uncertainty.	\N	https://www.bbc.com/news/articles/cy4r7dmxgxmo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 17:18:52	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.808756	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
93	The pride of Ethiopia - What it took to build Africa's largest hydro-electric dam	In a fractious nation, the dam's construction has brought people together despite controversy abroad.	\N	https://www.bbc.com/news/articles/cr4qx6377qgo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-09 12:05:52	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.808983	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
94	How the coup trial of Jair Bolsonaro has divided Brazil	The ex-president is accused of trying to overturn his election loss but his supporters say it is a witch hunt.	\N	https://www.bbc.com/news/articles/cn4wx9zlpj5o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 14:37:59	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.809218	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
96	Japan is set to choose its fourth PM in five years - who could be next?	Japan's next leader will face the challenge of steering a much weakened government.	\N	https://www.bbc.com/news/articles/c62l9488ljlo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 22:00:24	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.809771	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
97	Huge drugs bust reveals battles on cocaine 'superhighway'	An audacious attempt to smuggle tonnes of cocaine was stopped, but pressure from drug cartels remains.	\N	https://www.bbc.com/news/articles/c5yvplyrrwno?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 05:02:40	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.809908	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
98	'Playing perfectly' - how does Alcaraz rank v men's tennis legends at 22?	BBC Sport explores Carlos Alcaraz's stunning record compared to tennis' biggest legends in the men's game after his sixth Grand Slam triumph.	\N	https://www.bbc.com/sport/tennis/articles/czew374r499o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 15:16:05	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.809989	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
99	Watch: Glitz, glamour and emotional speeches at VMAs 2025	The MTV Video Music Awards (VMAs) have taken place in New York, with high profile figures in the music industry taking to the red carpet.	\N	https://www.bbc.com/news/videos/crl5ngr2069o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 09:04:06	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.810247	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
100	What it was like inside court as mushroom murderer was jailed for life	The BBC's Katy Watson was in the courtroom as Erin Patterson was sentenced to life.	\N	https://www.bbc.com/news/videos/c15k4y5nwz7o?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-08 03:32:23	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.810723	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
101	Timelapse shows Blood Moon rising around the world	As the Moon passes through the Earth's shadow, it takes on a deep red hue, creating a striking "Blood Moon".	\N	https://www.bbc.com/news/videos/c93071yz5zzo?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-07 19:00:54	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.810946	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
102	Thousands flock to Vatican as teenager made first millennial saint	Pope Leo canonises the London-born Italian boy nicknamed "God's influencer" for his online skills.	\N	https://www.bbc.com/news/videos/cy9njpyp09do?at_medium=RSS&at_campaign=rss	BBC World News	2025-09-07 16:32:36	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.811193	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
103	Switch modder owes Nintendo $2 million after representing himself in court	Daly's defense asserted, in part, that Nintendo's "alleged copyrights are invalid."	\N	https://arstechnica.com/gaming/2025/09/switch-modder-who-acted-as-his-own-lawyer-now-owes-nintendo-2-million/	Ars Technica	2025-09-09 14:29:04	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.915357	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
104	Geoengineering will not save humankind from climate change	New research debunks some speculative climate fixes.	\N	https://arstechnica.com/science/2025/09/geoengineering-will-not-save-humankind-from-climate-change/	Ars Technica	2025-09-09 13:24:40	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.916623	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
105	Why accessibility might be AI’s biggest breakthrough	UK study findings may challenge assumptions about who benefits most from AI tools.	\N	https://arstechnica.com/information-technology/2025/09/study-finds-neurodiverse-workers-more-satisfied-with-ai-assistants/	Ars Technica	2025-09-09 11:08:44	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.917767	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
106	Software packages with more than 2 billion weekly downloads hit in supply-chain attack	Incident hitting npm users is likely the biggest supply-chain attack ever.	\N	https://arstechnica.com/security/2025/09/software-packages-with-more-than-2-billion-weekly-downloads-hit-in-supply-chain-attack/	Ars Technica	2025-09-09 00:37:04	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.918854	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
107	Former WhatsApp security boss in lawsuit likens Meta’s culture to a “cult”	Meta allegedly prioritized user growth over security, lawsuit said.	\N	https://arstechnica.com/security/2025/09/former-whatsapp-security-boss-sues-meta-for-systemic-cybersecurity-failures/	Ars Technica	2025-09-08 20:26:02	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.919719	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
108	In court filing, Google concedes the open web is in “rapid decline”	Google's position on the state of the Internet is murky to say the least.	\N	https://arstechnica.com/google/2025/09/in-court-filing-google-concedes-the-open-web-is-in-rapid-decline/	Ars Technica	2025-09-08 19:29:40	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.920855	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
109	Nobel laureate David Baltimore dead at 87	Celebrated molecular biologist weathered late '80s controversy to become Caltech president.	\N	https://arstechnica.com/science/2025/09/nobel-laureate-david-baltimore-dead-at-87/	Ars Technica	2025-09-08 19:18:02	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.921633	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
110	On a day of rebranding at the Pentagon, this name change slipped under the radar	We'll see how long the Department of War lasts. Space Force Combat Forces Command might stick around.	\N	https://arstechnica.com/space/2025/09/the-pentagons-department-of-war-rebrand-extends-to-space/	Ars Technica	2025-09-08 18:45:02	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.922571	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
111	EchoStar to sell spectrum to SpaceX after FCC threatened to revoke licenses	Starlink says $17 billion spectrum purchase will improve its cellphone service.	\N	https://arstechnica.com/tech-policy/2025/09/spacex-complaints-to-fcc-pay-off-with-17-billion-spectrum-buy-from-echostar/	Ars Technica	2025-09-08 18:31:26	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.923241	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
112	The Polestar 5 electric sedan makes its world debut	The electric grand tourer charges fast, accelerates even faster.	\N	https://arstechnica.com/cars/2025/09/polestar-unveils-electric-gt-rival-to-the-porsche-taycan/	Ars Technica	2025-09-08 18:00:49	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.924612	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
113	Benoit Blanc goes full Gothic in Wake Up Dead Man trailer	"To understand this case, we need to look around the myth that's being constructed."	\N	https://arstechnica.com/culture/2025/09/wake-up-dead-man-trailer-teases-classic-locked-room-puzzle/	Ars Technica	2025-09-08 17:40:21	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.925886	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
114	AI will consume all of IT by 2030—but not all IT jobs, Gartner says	AI still threatens entry-level IT jobs.	\N	https://arstechnica.com/information-technology/2025/09/no-ai-jobs-bloodbath-as-ai-permeates-all-it-work-over-the-next-5-years/	Ars Technica	2025-09-08 17:17:49	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.927261	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
115	Trump’s attempt to fire FTC Democrat gets a boost from Supreme Court	John Roberts issuing stay means FTC Democrat has to leave her post again.	\N	https://arstechnica.com/tech-policy/2025/09/supreme-court-chief-justice-lets-trump-fire-ftc-democrat-at-least-for-now/	Ars Technica	2025-09-08 16:54:38	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.92854	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
116	F1 in Italy: Look what happens when the downforce comes off	The excitement came at the start and toward the end of this rather quick race.	\N	https://arstechnica.com/cars/2025/09/f1-in-italy-look-what-happens-when-the-downforce-comes-off/	Ars Technica	2025-09-08 16:44:56	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.92982	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
117	All 54 lost clickwheel iPod games have now been preserved for posterity	Finding working copies of the last few titles was an "especially cursed" journey.	\N	https://arstechnica.com/gaming/2025/09/all-54-lost-clickwheel-ipod-games-have-now-been-preserved-for-posterity/	Ars Technica	2025-09-08 16:24:59	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.930913	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
118	Congress and Trump may compromise on the SLS rocket by axing its costly upper stage	"At $4 billion a launch, you don’t have a Moon program."	\N	https://arstechnica.com/space/2025/09/congress-and-trump-may-compromise-on-the-sls-rocket-by-axing-its-costly-upper-stage/	Ars Technica	2025-09-08 15:54:31	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.932207	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
119	Tiny Vinyl is a new pocketable record format for the Spotify age	Format is "more aligned with how artists are making and releasing music in the streaming era."	\N	https://arstechnica.com/gadgets/2025/09/tiny-vinyl-is-a-new-pocketable-record-format-for-the-spotify-age/	Ars Technica	2025-09-08 11:00:51	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.933149	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
120	Porsche’s insanely clever hybrid engine comes to the 911 Turbo S	The new 911 variant is 14 seconds quicker around the Nürburgring Nordschleife.	\N	https://arstechnica.com/cars/2025/09/porsches-insanely-clever-hybrid-engine-comes-to-the-911-turbo-s/	Ars Technica	2025-09-07 13:00:58	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.933971	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
121	GOP may finally succeed in unrelenting quest to kill two NASA climate satellites	One scientist says it's like buying a car and running it into a tree to save on gas money.	\N	https://arstechnica.com/space/2025/09/gop-may-finally-succeed-in-unrelenting-quest-to-kill-two-nasa-climate-satellites/	Ars Technica	2025-09-06 00:01:43	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.934646	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
122	Who can get a COVID vaccine—and how? It’s complicated.	We’re working with a patchwork system, and there are a lot of gray areas.	\N	https://arstechnica.com/health/2025/09/who-can-get-a-covid-vaccine-and-how-its-complicated/	Ars Technica	2025-09-05 22:20:39	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:55.935116	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
123	Israel launches attack on Hamas in Qatar	Explosions heard as political leadership of Palestinian militant group targeted in Gulf state for first time	\N	https://www.ft.com/content/4a6e4781-eec5-4ee9-9a12-c683bb576fa8	Financial Times	2025-09-09 14:55:22	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.385713	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
124	Israel orders evacuation of Gaza City	Benjamin Netanyahu has argued assault is needed to break Hamas	\N	https://www.ft.com/content/b9f4875c-24d9-48ba-a3d4-5bb7217c76be	Financial Times	2025-09-09 09:51:19	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.38723	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
125	Who’s who in Jeffrey Epstein’s birthday book	Document released by House Democrats has apparent contributions from Trump, Clinton, Mandelson and Leon Black	\N	https://www.ft.com/content/d0294fd9-5836-4b2d-8c96-bf467a5f7844	Financial Times	2025-09-09 14:15:01	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.388544	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
126	America’s left cannot exploit Trump’s failures	The president’s genius is to keep pushing the Democrats into a reactive defence of the status quo	\N	https://www.ft.com/content/dfcacf73-afe0-465b-9e97-70b7e2dcf9ad	Financial Times	2025-09-09 10:00:05	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.389848	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
127	Six reasons to be cheerful about the stock market	And South Korea revisited	\N	https://www.ft.com/content/6f3c1b4a-a6b3-449a-870e-dd89521c575b	Financial Times	2025-09-09 05:30:01	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.391012	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
128	US hiring growth revised down by 911,000 jobs in year to March	Bureau of Labor Statistics’s updated figures are based on more comprehensive employment data	\N	https://www.ft.com/content/6a9c93f6-9ee7-422a-9851-6a41d2b07c03	Financial Times	2025-09-09 14:10:04	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.392306	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
129	France joins Eurozone’s ‘periphery’ as turmoil deepens, say investors	French borrowing costs have climbed above those of Greece and close to Italy’s	\N	https://www.ft.com/content/23cfb45e-c6d5-4a70-832d-0105d3427859	Financial Times	2025-09-09 13:33:34	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.393586	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
130	Macron scouts for new prime minister to quell turmoil	French president has no easy fixes after another government falls and could turn to a loyalist	\N	https://www.ft.com/content/7da60de0-ab87-46b4-9a1d-5fd8f731d8f4	Financial Times	2025-09-09 06:51:21	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.394587	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
131	Murdoch seals $3.3bn succession deal to hand empire to eldest son	Lachlan takes control as three siblings receive $1.1bn each to settle long-running family feud	\N	https://www.ft.com/content/f2162505-6b0c-4193-ab94-4a531642590f	Financial Times	2025-09-08 21:51:45	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.395341	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
132	Russian air strike kills Ukrainian pensioners	Civilians including retirees waiting to collect benefits killed in eastern Ukraine, according to authorities	\N	https://www.ft.com/content/064f4992-24bf-4a4b-a8a4-e943af4fba73	Financial Times	2025-09-09 13:06:30	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.396377	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
133	Ukraine battles air defence shortage as Pentagon slows shipments	Moscow has stepped up attacks during Trump’s attempts to broker a peace deal, heaping pressure on Kyiv’s stocks	\N	https://www.ft.com/content/26df4030-9613-498d-9ce8-44691aee4346	Financial Times	2025-09-09 10:17:09	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.397266	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
134	All the Dyson Hair Tools You’ll Ever Need (2025)	Not your grandma’s blow-dryer.	\N	https://www.wired.com/gallery/best-dyson-hair-tools/	Wired	2025-09-09 14:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.506424	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
135	The 15 Best Fans to Cool You Year Round (2025)	From tower and pedestal styles to utilitarian box fans, these are our WIRED-tested favorites.	\N	https://www.wired.com/gallery/best-fans/	Wired	2025-09-09 13:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.50753	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
136	The United Arab Emirates Releases a Tiny But Powerful AI Model	K2 Think compares well with reasoning models from OpenAI and DeepSeek but is smaller and more efficient, say researchers based in Abu Dhabi.	\N	https://www.wired.com/story/uae-releases-a-tiny-but-powerful-reasoning-model/	Wired	2025-09-09 12:33:44	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.507961	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
137	Hasan Piker Will Never Run for Office	The Twitch streamer could pivot from influencer to candidate. But he tells WIRED’s Big Interview podcast he’d rather use his platform to tell Dems “you can’t podcast your way out of this problem.”	\N	https://www.wired.com/story/uncanny-valley-podcast-big-interview-hasan-piker/	Wired	2025-09-09 11:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.508362	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
138	Apple Event Live Blog: Updates on iPhone 17, iPhone Air, Apple Watch 11, AirPods Pro 3	Join us for live coverage of the launch of the iPhone 17, iPhone Air, and Apple Watch Series 11. We'll be reporting from Apple headquarters in Cupertino, California.	\N	https://www.wired.com/live/apple-event-iphone-17-iphone-air/	Wired	2025-09-09 10:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.50874	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
139	A New Platform Offers Privacy Tools to Millions of Public Servants	From data-removal services to threat monitoring, the Public Service Alliance says its new marketplace will help public servants defend themselves in an era of data brokers and political violence.	\N	https://www.wired.com/story/public-service-alliance-marketplace-privacy-threats/	Wired	2025-09-09 10:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.509004	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
140	Massive Leak Shows How a Chinese Company Is Exporting the Great Firewall to the World	Geedge Networks, a company with ties to the founder of China’s mass censorship infrastructure, is selling its censorship and surveillance systems to at least four other countries in Asia and Africa.	\N	https://www.wired.com/story/geedge-networks-mass-censorship-leak/	Wired	2025-09-09 03:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.509381	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
141	Save $60 on the DJI Mic Mini Kit—Price Drops to Just $109 Today	Show off your social side with this kit from DJI, which includes two microphones and a charging case. Our reviewers love it.	\N	https://www.wired.com/story/save-dollar60-on-a-dji-mic-mini-bundle/	Wired	2025-09-08 17:52:41	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.509669	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
142	Why Your Office Chair Should Have Lumbar Support	Office chairs and gaming chairs often tout lumbar support as a must-have feature. I spoke to some experts to see if it’s as essential as claimed.	\N	https://www.wired.com/story/does-your-office-chair-need-lumbar-support/	Wired	2025-09-08 13:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.509895	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
143	The iPhone 17 Air Could Use a Silicon-Carbon Battery. What Is It?	Phones with thinner designs are enjoying a moment. But while thin phones usually suffer poor battery life, batteries with silicon-carbon anodes are helping circumvent that notion.	\N	https://www.wired.com/story/iphone-17-air-silicon-carbon-battery-what-is-it/	Wired	2025-09-08 11:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.510156	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
144	Why Former NFL All-Pros Are Turning to Psychedelics	Research into whether drugs like ayahuasca can mitigate the effects of traumatic brain injury is in its infancy. Pro athletes like Jordan Poyer are forging ahead anyway.	\N	https://www.wired.com/story/can-psychedelics-reduce-traumatic-brain-injury-one-nfl-all-pro-thinks-so/	Wired	2025-09-08 11:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.510298	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
145	I Hate My AI Friend	The chatbot-enabled Friend necklace eavesdrops on your life and provides a running commentary that’s snarky and unhelpful. Worse, it can also make the people around you uneasy.	\N	https://www.wired.com/story/i-hate-my-ai-friend/	Wired	2025-09-08 10:30:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.510399	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
146	Bose QuietComfort Ultra Earbuds (2nd Gen): Excellent Buds	With slight, useful changes like wireless charging and better processing, these noise-canceling buds remain at the top of the pile.	\N	https://www.wired.com/review/bose-qc-ultra-2/	Wired	2025-09-08 10:01:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.510709	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
147	How to Add WIRED as a Preferred Source on Google (2025)	The new Google Preferred Sources tool helps you see more of what you want in your search results.	\N	https://www.wired.com/story/wired-google-preferred-source/	Wired	2025-09-07 14:04:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.510925	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
148	The New Math of Quantum Cryptography	In theory, quantum physics can bypass the hard mathematical problems at the root of modern encryption. A new proof shows how.	\N	https://www.wired.com/story/the-new-math-of-quantum-cryptography/	Wired	2025-09-07 11:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.511226	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
149	Psychological Tricks Can Get AI to Break the Rules	Researchers convinced large language model chatbots to comply with “forbidden” requests using a variety of conversational tactics.	\N	https://www.wired.com/story/psychological-tricks-can-get-ai-to-break-the-rules/	Wired	2025-09-07 10:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.511461	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
150	6 Best Phones You Can’t Buy in the US (2025), Tested and Reviewed	Wondering what you’re missing out on? Here are our favorite smartphones not officially sold stateside but are available in markets like the UK and Europe.	\N	https://www.wired.com/gallery/best-phones-you-cant-buy-in-the-united-states/	Wired	2025-09-07 06:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.511673	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
151	The Best Pixel 10 Cases and Accessories (2025)	Slap a case and screen protector on your shiny new Pixel, whether you have the Pixel 10 or Pixel 10 Pro XL. We also have Qi2 chargers and accessory recommendations.	\N	https://www.wired.com/gallery/best-pixel-10-cases-and-accessories/	Wired	2025-09-06 13:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.511954	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
152	How to Babyproof Your Home (2025)	If you’re a new parent, learning how to keep Baby safe in your home can be daunting. Check every box—and cover every outlet—with this comprehensive guide from a new mom who just went through it.	\N	https://www.wired.com/story/how-to-babyproof-your-home/	Wired	2025-09-06 11:33:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.512059	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
153	Meraki Espresso Machine Review: Fine Grind, Loose Fit	Meraki’s impressive new espresso machine offers features long reserved for more expensive machines, but it’s not perfect.	\N	https://www.wired.com/review/meraki-espresso-maker/	Wired	2025-09-06 11:32:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.512431	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
154	The 49 Best Shows on Netflix Right Now (September 2025)	Wednesday, Long Story Short, and Hostage are just a few of the shows you need to watch on Netflix this month.	\N	https://www.wired.com/story/netflix-best-shows-this-week/	Wired	2025-09-06 11:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.512716	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
155	How to Watch Apple’s iPhone 17 Announcement, and What to Expect	It’s Apple season, when the company announces the new iPhone, Apple Watch, and other hardware. Here’s how to watch, and what you might see during Tuesday's big show.	\N	https://www.wired.com/story/apple-iphone-17-event-how-to-watch-what-to-expect/	Wired	2025-09-06 11:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.512879	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
156	The 49 Best Movies on Netflix Right Now (September 2025)	The Thursday Murder Club, Jaws, and Ziam are just a few of the movies you should watch on Netflix this month.	\N	https://www.wired.com/story/netflix-best-movies-this-week/	Wired	2025-09-06 11:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.513172	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
157	Real Estate Speculators Are Swooping In to Buy Disaster-Hit Homes	“We buy homes” companies are procuring disaster-damaged properties for cheap. Survivors say they’re taking advantage of tragedy.	\N	https://www.wired.com/story/disasters-destroyed-their-homes-then-the-real-estate-vultures-swooped-in/	Wired	2025-09-06 11:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.513293	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
158	The 21 Best Movies on Amazon Prime Right Now (September 2025)	American Fiction, Heads of State, and Air are just a few of the movies you should be watching on Amazon Prime Video this week.	\N	https://www.wired.com/story/best-amazon-prime-movies/	Wired	2025-09-06 11:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.513545	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
159	ICE Has Spyware Now	Plus: An AI chatbot system is linked to a widespread hack, details emerge of a US plan to plant a spy device in North Korea, your job’s security training isn’t working, and more.	\N	https://www.wired.com/story/ice-has-spyware-now/	Wired	2025-09-06 10:30:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.51374	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
160	Where's the Fun in AI Gambling?	On this episode of Uncanny Valley, we break down the role of AI in the online gambling scene.	\N	https://www.wired.com/story/uncanny-valley-podcast-wheres-the-fun-in-ai-gambling/	Wired	2025-09-06 10:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.513858	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
161	Gear News of the Week: Veo 3 Comes to Google Photos, and Garmin Adds Satellite Comms to a Watch	Plus: The Polar Loop looks a lot like the Whoop band, JBL’s comically massive speakers are ready to party, and ExpressVPN splits its subscription plan into three tiers.	\N	https://www.wired.com/story/gear-news-of-the-week-veo-3-comes-to-google-photos-and-garmin-adds-satellite-comms-to-a-watch/	Wired	2025-09-06 10:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.513984	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
162	Lovense Ferri Panty Vibrator Review: Super Comfy	The Lovense Ferri is a panty vibrator that’s actually comfortable, and it’s great for long-distance couples.	\N	https://www.wired.com/review/lovense-ferri-panty-vibrator/	Wired	2025-09-06 08:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.514121	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
163	The Top New Gadgets We Saw at IFA Berlin 2025	A tennis-playing robot, a projector in a party speaker, and a whole bunch of new AI-powered wearables. Here are some of the best gadgets we saw at IFA 2025.	\N	https://www.wired.com/story/all-the-top-new-gadgets-we-saw-at-ifa-berlin-2025/	Wired	2025-09-06 06:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.51446	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
164	Tesla Proposes a Trillion-Dollar Bet That It's More Than Just Cars	Tesla’s board wants to give Elon Musk an unprecedented $1 trillion pay package. To get all the money, he has to make robots and robotaxis work.	\N	https://www.wired.com/story/elon-musk-trillion-dollar-tesla-pay-package/	Wired	2025-09-05 22:26:44	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.514598	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
165	Defense Department Scrambles to Pretend It’s Called the War Department	President Donald Trump said the so-called Department of War branding is to counter the “woke” Department of Defense name.	\N	https://www.wired.com/story/department-of-defense-department-of-war/	Wired	2025-09-05 22:22:27	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.514747	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
166	Anthropic Agrees to Pay Authors at Least $1.5 Billion in AI Copyright Settlement	Anthropic will pay at least $3,000 for each copyrighted work that it pirated. The company downloaded unauthorized copies of books in early efforts to gather training data for its AI tools.	\N	https://www.wired.com/story/anthropic-settlement-lawsuit-copyright/	Wired	2025-09-05 19:14:28	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.514887	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
167	Top Spec Razer Blade Laptops Are Average 14 Percent Off Right Now	This slim gaming laptop is one of our favorites, with an impressive design and the power to match.	\N	https://www.wired.com/story/save-hundreds-on-the-razer-blade-16-and-18-gaming-laptops/	Wired	2025-09-05 17:52:29	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.515	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
168	The Doomers Who Insist AI Will Kill Us All	Eliezer Yudkowsky, AI’s prince of doom, explains why computers will kill us and provides an unrealistic plan to stop it.	\N	https://www.wired.com/story/the-doomers-who-insist-ai-will-kill-us-all/	Wired	2025-09-05 15:08:21	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.515184	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
169	Tech CEOs Praise Donald Trump at White House Dinner	At a White House dinner Thursday night, America’s tech executives put on an uncanny display of fealty to Donald Trump.	\N	https://www.wired.com/story/tech-ceos-donald-trump-white-house/	Wired	2025-09-05 14:16:59	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.515342	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
170	7 Best Password Managers (2025), Tested and Reviewed	Keep your logins locked down with our favorite password management apps for PC, Mac, Android, iPhone, and web browsers.	\N	https://www.wired.com/story/best-password-managers/	Wired	2025-09-05 13:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.515522	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
171	The 29 Best Energy Drinks, Tested and Reviewed (2025)	The future is here, and it is jacked up on B vitamins, red dye, and taurine. These are the best energy drinks to get from tired to wired.	\N	https://www.wired.com/story/best-energy-drinks/	Wired	2025-09-05 12:39:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.515665	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
172	‘People Are So Proud of This’: How River and Lake Water Is Cooling Buildings	Networks of pipes and heat exchangers can transfer excess heat from buildings into nearby bodies of water—but as the world warms, the cooling potential of some water courses is now diminishing.	\N	https://www.wired.com/story/people-are-so-proud-of-this-how-river-and-lake-water-is-cooling-buildings/	Wired	2025-09-05 10:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.515815	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
173	Lenovo’s ThinkBook VertiFlex Concept Laptop Has a Swiveling Screen	The 14-inch ThinkBook VertiFlex Concept has a screen you can manually twist whenever the mood strikes.	\N	https://www.wired.com/story/lenovo-thinkbook-vertiflex-concept-laptop-can-switch-from-landscape-to-portrait/	Wired	2025-09-05 06:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.516	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
174	Our Favorite Smart Lock for Your Front Door Is Just $164 Right Now	The Yale Approach Lock is easy to install, offers auto-unlock, and is 32% off right now.	\N	https://www.wired.com/story/our-favorite-smart-lock-is-dollar80-off/	Wired	2025-09-04 21:27:22	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.516158	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
175	US Congressman’s Brother Lands No-Bid Contract to Train DHS Snipers	DHS says retired Marine sniper Dan LaLota’s firm is uniquely qualified to meet the government’s needs. LaLota tells WIRED his brother, GOP congressman Nick LaLota, played no role in the contract.	\N	https://www.wired.com/story/us-congressmans-brother-lands-no-bid-contract-to-train-dhs-snipers/	Wired	2025-09-04 19:50:17	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.516299	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
176	Should AI Get Legal Rights?	Model welfare is an emerging field of research that seeks to determine whether AI is conscious and, if so, how humanity should respond.	\N	https://www.wired.com/story/model-welfare-artificial-intelligence-sentience/	Wired	2025-09-04 19:05:56	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.516461	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
177	The 35 Best Movies on HBO Max Right Now (September 2025)	Friendship, Final Destination Bloodlines, and Sinners are just a few of the movies you should be watching on HBO Max this month.	\N	https://www.wired.com/story/best-movies-hbo-max-right-now/	Wired	2025-09-04 19:00:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.51664	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
178	Neuralink’s Bid to Trademark ‘Telepathy’ and ‘Telekinesis’ Faces Legal Issues	The brain implant company cofounded by Elon Musk filed to trademark the product names Telepathy and Telekinesis. But it turns out that another person had already filed to trademark those names.	\N	https://www.wired.com/story/uspto-denies-neuralinks-applications-for-telepathy-telekinesis-marks/	Wired	2025-09-04 18:47:28	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.516803	2025-09-09 15:07:54.87704	0	0	\N	[]	\N	{}	\N
183	Should the Company Trucks Go Electric? Depends on When You Charge	A six-month experiment run by Ford and the Atlanta utility firm Southern Company used custom software to show that EVs can save businesses stress and money. It also exposed the tech’s limits.	\N	https://www.wired.com/story/managed-charging-evs-ford-southern-company/	Wired	2025-09-04 15:30:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.517642	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": [], "events": ["experiment"], "people": [], "status": "success", "topics": ["EVs"], "numbers": ["six-month"], "locations": ["Atlanta"], "organizations": ["Ford", "Southern Company"]}	\N
228	Fossil-fuel firms receive US subsidies worth $31bn each year, study finds	<p>Figure calculated by Oil Change International has more than doubled since 2017 but is likely a vast understatement</p><p>The US currently subsidizes the <a href="https://www.theguardian.com/environment/fossil-fuels">fossil-fuel </a>industry to the tune of nearly $31bn per year, according to a new analysis.</p><p>That figure, calculated by the environmental campaign group Oil Change International, has <a href="https://oilchange.org/fossil-fuel-subsidies/">more than doubled</a> since 2017. And it is likely a vast understatement, due to the difficulty of quantifying the financial gains from some government supports, and to a lack of transparency and reliable data from government sources, the group says.</p> <a href="https://www.theguardian.com/environment/2025/sep/09/fossil-fuels-subisidies-study">Continue reading...</a>	\N	https://www.theguardian.com/environment/2025/sep/09/fossil-fuels-subisidies-study	The Guardian World	2025-09-09 13:00:20	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.669769	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2017", "2025/09/09"], "events": [], "people": [], "status": "success", "topics": ["fossil-fuel industry", "environmental subsidies"], "numbers": ["$31bn per year"], "locations": ["US"], "organizations": ["Oil Change International", "US government"]}	\N
227	US drug dealer afforded clemency by Trump found guilty of parole violation	<p>Jonathan Braun of New York faces up to five years after he was arrested and charged in connection to recent crimes</p><p>A convicted <a href="https://www.theguardian.com/us-news/new-york">New York</a> drug dealer whose federal prison sentence was <a href="https://www.theguardian.com/us-news/2021/jan/20/trump-pardons-and-commutations-the-full-list">commuted</a> by <a href="https://www.theguardian.com/us-news/donaldtrump">Donald Trump</a> during Trump’s first presidency has been found guilty of violating the terms of his release after being arrested and charged in connection with several recent crimes.</p><p>Jonathan Braun now faces up to five years in prison during a sentencing hearing tentatively scheduled for 9 October.</p> <a href="https://www.theguardian.com/us-news/2025/sep/09/new-york-drug-dealer-trump">Continue reading...</a>	\N	https://www.theguardian.com/us-news/2025/sep/09/new-york-drug-dealer-trump	The Guardian World	2025-09-09 13:03:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.669633	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["9 October", "2021/01/20"], "events": ["sentencing hearing"], "people": ["Jonathan Braun", "Donald Trump"], "status": "success", "topics": ["crime", "prison sentence", "commutation"], "numbers": ["five years"], "locations": ["New York"], "organizations": []}	\N
226	Democrats needle Trump over Epstein ‘birthday book’ letter he denied existed	<p>Loyalists insist vulgar and sexual greeting released by House oversight committee is not Trump’s handiwork</p><ul><li><p><a href="https://www.theguardian.com/us-news/live/2025/sep/09/donald-trump-jeffrey-epstein-birthday-note-letter-latest-live-us-politics-news">US politics – live updates</a></p></li></ul><p><a href="https://www.theguardian.com/us-news/house-of-representatives">House</a> <a href="https://www.theguardian.com/us-news/democrats">Democrats</a> needled <a href="https://www.theguardian.com/us-news/donaldtrump">Donald Trump</a> and <a href="https://www.theguardian.com/us-news/republicans">Republicans</a> on Monday after they obtained and released a copy of a birthday scrapbook for Jeffrey Epstein, which included a vulgar and sexual letter Trump has denied sending the convicted sex offender.</p><p>Trump vigorously denied the letter existed when<a href="https://www.wsj.com/us-news/law/epstein-birthday-book-congress-9d79ab34?gaa_at=eafs&amp;gaa_n=ASWzDAgIX1rHZ0o2VmrqqtH4EALD3LbsVd1cl_GNiYdQ0BThB-JT1kRu-iuR01xLKa0%3D&amp;gaa_ts=68c01d84&amp;gaa_sig=ffBnSaDZ07NhWQvIxAB3orkZRIQRnZwRt1UHoIVcY4Y-eZyyyzoWA278aaHkMkYmP1vYXzsAQgwMqNtni_QCTw%3D%3D"> the Wall Street Journal first revealed</a> its existence in July, and sued the outlet for defamation. After <a href="https://oversight.house.gov/wp-content/uploads/2025/08/2025.08.25-Subpoena-and-Schedule-to-Epstein-Estate.pdf">subpoenaing</a> Epstein’s estate, the US House oversight committee obtained the letter, which was among a book of letters sent to Epstein for his 50th birthday.</p> <a href="https://www.theguardian.com/us-news/2025/sep/09/trump-epstein-birthday-letter-reaction-democrats">Continue reading...</a>	\N	https://www.theguardian.com/us-news/2025/sep/09/trump-epstein-birthday-letter-reaction-democrats	The Guardian World	2025-09-09 13:31:58	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.669476	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["July", "2025/09/09"], "events": ["Trump's birthday message controversy", "Jeffrey Epstein's 50th birthday"], "people": ["Donald Trump", "Jeffrey Epstein"], "status": "success", "topics": ["US politics", "Sex scandal"], "numbers": ["50"], "locations": [], "organizations": ["House oversight committee", "US House", "Democrats", "Republicans", "The Wall Street Journal", "Epstein's estate"]}	\N
225	Photo of novelty check suggests Epstein ‘sold’ Trump a woman for $22,500	<p>President and convicted sex offender appear in birthday scrapbook photo with check signed by ‘DJ Trump’</p><ul><li><p><a href="https://www.theguardian.com/us-news/live/2025/sep/09/donald-trump-jeffrey-epstein-birthday-note-letter-latest-live-us-politics-news">US politics live – latest updates</a></p></li></ul><p>A scrapbook for <a href="https://www.theguardian.com/us-news/jeffrey-epstein">Jeffrey Epstein’s</a> 50th birthday released on Monday contains a photo of him holding a novelty check bearing <a href="https://www.theguardian.com/us-news/donaldtrump">Donald Trump</a>’s signature, along with a note suggesting Epstein “sold” him a woman for $22,500, shedding further light on the<a href="https://www.theguardian.com/us-news/2025/jul/18/trump-epstein-friendship"> longtime relationship</a> between the president and the convicted sex offender.</p><p>The photo shows Epstein and Joel Pashcow, a longtime member of Trump’s Mar-a-Lago resort, and a third figure, apparently a woman, whose face is redacted in the image, which was shared on social media by Democrats on the House oversight committee. The caption, apparently from Paschow, reads: “Jeffrey showing early talents with money + women! Sells ‘fully depreciated’ [redaction] to Donald Trump for $22,500.”</p> <a href="https://www.theguardian.com/us-news/2025/sep/09/trump-epstein-photo-check-woman">Continue reading...</a>	\N	https://www.theguardian.com/us-news/2025/sep/09/trump-epstein-photo-check-woman	The Guardian World	2025-09-09 14:40:01	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.669329	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/09", "2025/07/18"], "events": ["Jeffrey Epstein's 50th birthday"], "people": ["Jeffrey Epstein", "Donald Trump", "Joel Pashcow"], "status": "success", "topics": ["US politics", "Sex offense"], "numbers": ["$22,500"], "locations": [], "organizations": ["House oversight committee", "Mar-a-Lago resort", "The Guardian"]}	\N
224	Maga loyalists claim Trump note to Epstein is ‘fake’ after House committee releases image of it – live	<p>Several Trump allies push back on alleged note Trump wrote to Epstein for his 50th birthday</p><ul><li><p><a href="https://www.theguardian.com/us-news/2025/sep/09/trump-epstein-photo-check-woman">Photo of novelty check suggests Epstein ‘sold’ Trump a woman</a></p></li><li><p><a href="https://www.theguardian.com/us-news/gallery/2025/sep/09/jeffrey-epstein-birthday-book-in-pictures">Jeffrey Epstein’s 50th birthday book – in pictures</a></p></li></ul><p>My colleague, <strong>Oliver Holmes</strong>, has been <a href="https://www.theguardian.com/us-news/2025/sep/09/epstein-50th-birthday-book-who-is-in-it-and-what-did-they-say-donald-trump-bill-clinton-peter-mandelson">going through the Jeffrey Epstein 50th birthday album</a> that House Democrats on the oversight committee released on Monday, after they subpoenaed Epstein’s estate.</p><p>As Oliver notes, much of the book seems to be a collection of flattering and celebratory letters – often highly sexualised – from people who knew Epstein. They include photos of him embracing women in bikinis whose faces were redacted, and others showing scenes featuring wild animals having sex.</p><p><strong>Bill Clinton</strong>, who had left the US presidency a couple years before the publication of the book, is listed in the “friends” section.</p><p><strong>Peter Mandelson</strong>, the current UK ambassador to the United States, called Epstein his “best pal”. There are also photographs in the book which show Mandelson in shorts gazing from a balcony and in a white dressing gown laughing with Epstein.</p><p>One of the most striking images in the collection is a drawing of Epstein handing young girls balloons and a lollipop in 1983, alongside another drawing of him 20 years later, receiving a massage from topless women in 2003.</p> <a href="https://www.theguardian.com/us-news/live/2025/sep/09/donald-trump-jeffrey-epstein-birthday-note-letter-latest-live-us-politics-news">Continue reading...</a>	\N	https://www.theguardian.com/us-news/live/2025/sep/09/donald-trump-jeffrey-epstein-birthday-note-letter-latest-live-us-politics-news	The Guardian World	2025-09-09 14:50:52	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.669085	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["1983", "2003", "2025/09/09"], "events": ["Epstein's 50th birthday"], "people": ["Donald Trump", "Jeffrey Epstein", "Oliver Holmes", "Bill Clinton", "Peter Mandelson"], "status": "success", "topics": ["Sex trafficking", "Politics"], "numbers": [], "locations": ["United States"], "organizations": ["House Democrats", "US presidency", "UK embassy"]}	\N
223	Revealed: Boris Johnson approached Elon Musk on behalf of London Evening Standard owner Lebedev	<p>Former PM’s private office forwarded business proposal from peer to owner of X in June 2024, leaked files suggest</p><p>Boris Johnson contacted Elon Musk on behalf of the Evening Standard owner, Evgeny Lebedev, as part of an attempt to get the US tech billionaire to support the ailing newspaper, leaked files suggest.</p><p>Johnson’s private office, which is taxpayer-subsidised, emailed an executive close to Musk in June 2024, forwarding a business proposal from Lord Lebedev.</p> <a href="https://www.theguardian.com/uk-news/2025/sep/09/boris-johnson-elon-musk-evening-standard-evgeny-lebedev">Continue reading...</a>	\N	https://www.theguardian.com/uk-news/2025/sep/09/boris-johnson-elon-musk-evening-standard-evgeny-lebedev	The Guardian World	2025-09-09 13:55:54	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.668939	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["June 2024"], "events": [], "people": ["Boris Johnson", "Elon Musk", "Evgeny Lebedev"], "status": "success", "topics": ["business proposal", "newspaper support"], "numbers": [], "locations": ["US"], "organizations": ["Evening Standard", "UK Government"]}	\N
222	School absence a big factor in child mental illness in England, data shows	<p>Loughborough University and ONS study of 1 million school-age children reveals risks increase with longer absence</p><p>School absences “significantly contribute” to children’s mental ill health, according to research backed by the Office for National Statistics (ONS) that shows the risks increase the longer a child is absent.</p><p>“Our research shows that the more times a child is absent from school, the greater the probability that they will experience mental ill health,” the authors, from Loughborough University and the ONS, concluded.</p> <a href="https://www.theguardian.com/education/2025/sep/09/school-absence-big-factor-child-mental-illness-england-ons-data">Continue reading...</a>	\N	https://www.theguardian.com/education/2025/sep/09/school-absence-big-factor-child-mental-illness-england-ons-data	The Guardian World	2025-09-09 14:13:31	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.668789	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/09"], "events": [], "people": [], "status": "success", "topics": ["school absences", "mental ill health", "child mental illness"], "numbers": ["1 million"], "locations": [], "organizations": ["Loughborough University", "Office for National Statistics (ONS)"]}	\N
221	St George’s cross appears on Westbury white horse monument	<p>Wiltshire landmark assessed for damage after red fabric pinned across it to form England flag</p><p>A 53-metre white horse cut into a Wiltshire hillside about 350 years ago is to be assessed for damage by heritage experts after red fabric was pinned across it to form a St George’s cross.</p><p>English Heritage said the fabric has been removed from the Westbury white horse, which according to local records was originally cut in the late 1600s, possibly to commemorate the attle of Ethandun, thought to have taken place nearby in AD878.</p> <a href="https://www.theguardian.com/uk-news/2025/sep/09/st-georges-cross-appears-on-westbury-white-horse-monument">Continue reading...</a>	\N	https://www.theguardian.com/uk-news/2025/sep/09/st-georges-cross-appears-on-westbury-white-horse-monument	The Guardian World	2025-09-09 14:25:24	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.668652	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["350 years ago", "late 1600s", "AD878"], "events": ["attle of Ethandun"], "people": [], "status": "success", "topics": ["heritage", "monument", "St George’s cross"], "numbers": [53], "locations": ["Wiltshire", "Westbury", "Ethandun", "England"], "organizations": ["English Heritage"]}	\N
220	Phillipson, Thornberry, Ribeiro-Addy and Powell enter Labour deputy race	<p>Alison McGovern and Paula Barker also put their names forward, with Bridget Phillipson favourite to win</p><ul><li><p><a href="https://www.theguardian.com/politics/2025/sep/08/who-is-in-the-running-to-be-the-next-labour-deputy-leader">Who is in the running for deputy leader?</a></p></li></ul><p>Bridget Phillipson has become the most high-profile candidate yet to throw her hat in the ring for the Labour deputy leadership contest, immediately becoming the frontrunner, as she is most likely to meet the threshold for MP nominations.</p><p>The veteran Labour MP Emily Thornberry, the former Commons leader Lucy Powell, the housing minister Alison McGovern, and the leftwing MP for Clapham and Brixton Hill, Bell Ribeiro-Addy, have all joined the education secretary in the race. Senior Labour figures urged MPs to select a woman from outside London to become Keir Starmer’s deputy.</p> <a href="https://www.theguardian.com/politics/2025/sep/09/bridget-phillipson-labour-deputy-leader-race">Continue reading...</a>	\N	https://www.theguardian.com/politics/2025/sep/09/bridget-phillipson-labour-deputy-leader-race	The Guardian World	2025-09-09 14:29:26	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.668514	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/08", "2025/09/09"], "events": ["Labour deputy leadership contest"], "people": ["Alison McGovern", "Paula Barker", "Bridget Phillipson", "Emily Thornberry", "Lucy Powell", "Bell Ribeiro-Addy", "Keir Starmer"], "status": "success", "topics": ["politics"], "numbers": [], "locations": ["London", "Clapham", "Brixton Hill"], "organizations": ["Labour"]}	\N
219	Lucy Powell to stand for Labour deputy leadership after reshuffle sacking – UK politics live	<p>Education secretary up against Emily Thornberry, Bell Ribeiro-Addy, Lucy Powell, Alison McGovern and Paula Barker </p><p><strong>Kemi Badenoch</strong> has just delivered a speech offering to help Labour with legislationg for welfare cuts. I will post key points soon.</p><p>She is now taking questions.</p> <a href="https://www.theguardian.com/politics/live/2025/sep/09/bridget-phillipson-labour-deputy-leader-uk-politics-latest-news-updates-keir-starmer">Continue reading...</a>	\N	https://www.theguardian.com/politics/live/2025/sep/09/bridget-phillipson-labour-deputy-leader-uk-politics-latest-news-updates-keir-starmer	The Guardian World	2025-09-09 14:52:38	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.668378	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/09"], "events": [], "people": ["Kemi Badenoch", "Emily Thornberry", "Bell Ribeiro-Addy", "Lucy Powell", "Alison McGovern", "Paula Barker", "Bridget Phillipson", "Keir Starmer"], "status": "success", "topics": ["welfare cuts", "legislation"], "numbers": [], "locations": [], "organizations": ["Labour"]}	\N
218	‘We’re scared of losing our jobs’: industries in India fear impact of Trump’s 50% tariffs	<p>Textiles, footwear, jewellery, gems and seafood are sectors most affected in trade with US, India’s biggest market</p><p>India has long been one of the world’s great garment houses, turning out everything from cheap T-shirts to intricate embroidery. Last year, textile and garment exports to the US alone fetched £21bn, riding a wave of strong consumer demand.</p><p>Now the trade is in jeopardy. With the stroke of a pen, the US president, Donald Trump, last week slapped a 50% tariff on more than half of India’s £65bn worth of merchandise exports to the country’s largest market. A supply chain once prized for being cheap suddenly became among the priciest.</p> <a href="https://www.theguardian.com/world/2025/sep/05/scared-losing-jobs-industries-india-fear-impact-trump-tariffs">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/05/scared-losing-jobs-industries-india-fear-impact-trump-tariffs	The Guardian World	2025-09-05 04:00:16	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.668237	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["last year", "2025/09/05"], "events": [], "people": ["Donald Trump"], "status": "success", "topics": ["trade", "tariffs", "textiles", "footwear", "jewellery", "gems", "seafood"], "numbers": ["$21bn", "50%", "$65bn"], "locations": ["India", "US"], "organizations": []}	\N
217	Afghan earthquake death toll jumps to more than 2,200, say Taliban	<p>Aid agencies plead for funds as rough terrain hinders relief effort and 98% of buildings in one province are damaged</p><p>The death toll from a major earthquake in Afghanistan this week has jumped to more than 2,200, just as another magnitude 6.2 earthquake hit the southeastern region of the country on Thursday night.</p><p>On Thursday, Taliban spokesperson Hamdullah Fitrat <a href="https://www.theguardian.com/world/2025/sep/04/afghan-earthquake-death-toll-jumps-says-taliban">confirmed that the death toll from Sunday’s earthquake had risen to 2,205</a> – up from previous estimates of 1,400 – making it one of the deadliest natural disasters to hit the country in decades.</p> <a href="https://www.theguardian.com/world/2025/sep/04/afghan-earthquake-death-toll-jumps-says-taliban">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/04/afghan-earthquake-death-toll-jumps-says-taliban	The Guardian World	2025-09-05 10:43:39	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.668127	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["Sunday", "Thursday night", "2025/09/04"], "events": ["Earthquake in Afghanistan"], "people": ["Hamdullah Fitrat"], "status": "success", "topics": ["Natural disasters", "Relief efforts"], "numbers": ["2,200", "1,400", "98%", "6.2", "2,205"], "locations": ["Afghanistan", "Southeastern region"], "organizations": ["Taliban", "Aid agencies"]}	\N
216	‘Everything is gone’: Punjabi farmers suffer worst floods in three decades	<p>Flooding in northern India and Pakistan has destroyed homes – and hundreds of thousands of acres of crops</p><p>For days, farmers in the Indian state of Punjab watched the pounding monsoon rains fall and the rivers rise with mounting apprehension. By Wednesday, many woke to find their fears realised as the worst floods in more than three decades ravaged their farms and decimated their livelihoods.</p><p>Hundreds of thousands of acres of bright green rice paddies – due to be harvested imminently – as well as crops of cotton and sugar cane were left destroyed as they became fully submerged in more than five feet of muddy brown flood waters. The bodies of drowned cattle littered the ground.</p> <a href="https://www.theguardian.com/world/2025/sep/06/everything-gone-punjabi-farmers-suffer-worst-floods-three-decades">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/06/everything-gone-punjabi-farmers-suffer-worst-floods-three-decades	The Guardian World	2025-09-06 04:00:42	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.667966	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["Wednesday", "2025/09/06"], "events": ["Flooding in northern India and Pakistan", "worst floods in more than three decades"], "people": [], "status": "success", "topics": ["flooding", "monsoon rains", "farming", "crops", "natural disaster"], "numbers": ["hundreds of thousands", "three decades", "five feet"], "locations": ["India", "Pakistan", "Punjab"], "organizations": ["The Guardian"]}	\N
215	At least 19 killed in ‘gen Z’ protests against Nepal’s social media ban	<p>Many demonstrators say they are also on the streets over corruption and nepotism they allege is rampant </p><p>At least 19 people have been killed during protests in Nepal over a government ban on dozens of online platforms including Facebook, Instagram, WhatsApp and X.</p><p>The government has faced mounting criticism after imposing a ban on 26 prominent social media platforms and messaging apps last week because they had missed a deadline to register under new regulations.</p> <a href="https://www.theguardian.com/world/2025/sep/08/nepal-bans-26-social-media-sites-including-x-whatsapp-and-youtube">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/08/nepal-bans-26-social-media-sites-including-x-whatsapp-and-youtube	The Guardian World	2025-09-08 15:32:49	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.667651	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/08"], "events": ["protests in Nepal", "government ban on online platforms"], "people": [], "status": "success", "topics": ["corruption", "nepotism", "social media regulation"], "numbers": [19, 26], "locations": ["Nepal"], "organizations": ["Facebook", "Instagram", "WhatsApp", "X", "YouTube"]}	\N
214	Nepal prime minister quits after deaths at protests sparked by social media ban	<p>KP Sharma Oli resigns as police meet protests with deadly force, leaving 19 dead, and federal parliament is set alight </p><p>Nepal’s prime minister has resigned after some of the worst unrest in decades rocked the country this week, set off by a ban on social media and discontent at political corruption and nepotism.</p><p>KP Sharma Oli’s resignation came a day after <a href="https://www.theguardian.com/world/2025/sep/08/nepal-bans-26-social-media-sites-including-x-whatsapp-and-youtube">widespread protests were met with deadly force</a> by police, leaving 19 dead and hundreds injured. The spark for the protests was a government ban on 26 prominent social media apps, but escalated into a larger mass movement against corruption among political elites.</p> <a href="https://www.theguardian.com/world/2025/sep/09/nepal-protests-social-media-ban-lifted-gen-z-kathmandu">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/nepal-protests-social-media-ban-lifted-gen-z-kathmandu	The Guardian World	2025-09-09 12:50:23	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.667366	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/08", "2025/09/09"], "events": ["protests", "social media ban"], "people": ["KP Sharma Oli"], "status": "success", "topics": ["corruption", "nepotism", "politics"], "numbers": ["19", "26", "hundreds"], "locations": ["Nepal", "Kathmandu"], "organizations": []}	\N
213	Boris Johnson secretly lobbied UAE for billion-dollar private venture, leak suggests	<p>Former prime minister courted senior Abu Dhabi official he had hosted in No 10 in apparent breach of rules</p><p>In early 2024, a vape lobbyist, a Vote Leave campaigner and a Vienna banker set out to persuade the rulers of an oil-rich Gulf emirate to give them a billion dollars. For the plan to work, leaked files suggest, they needed a frontman who had some pull with the sheikhs. So they hired Boris Johnson.</p><p>His time as the<strong> </strong>UK’s prime minister had ended less than two years earlier and he had left parliament. But Johnson retained relationships cultivated during his time in power. The Boris Files, a <a href="https://www.theguardian.com/uk-news/2025/sep/08/what-are-the-boris-johnson-files-former-prime-minister">cache of documents</a> seen by the Guardian, suggest he has sought to harness these relationships for self-enrichment.</p> <a href="https://www.theguardian.com/uk-news/2025/sep/09/boris-johnson-secretly-lobbied-uae-business-venture-leak-suggests">Continue reading...</a>	\N	https://www.theguardian.com/uk-news/2025/sep/09/boris-johnson-secretly-lobbied-uae-business-venture-leak-suggests	The Guardian World	2025-09-09 13:47:11	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.667063	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2024", "2025"], "events": [], "people": ["Boris Johnson"], "status": "success", "topics": ["politics", "lobbying"], "numbers": ["$1 billion"], "locations": ["Abu Dhabi", "UK", "Vienna", "Gulf", "No 10"], "organizations": ["Vote Leave", "The Guardian"]}	\N
212	Pro-Palestine activists call for arrest of Israeli president during UK visit	<p>Campaign group accuses Isaac Herzog, arriving in UK next week, of aiding and abetting indiscriminate killing in Gaza</p><ul><li><p><a href="https://www.theguardian.com/world/live/2025/sep/09/israel-gaza-city-evacuation-order-idf-military-offensive-live-updates-middle-east-crisis-latest-news">Middle East crisis – live updates</a></p></li></ul><p>Pro-Palestine activists have requested that an arrest warrant be issued against the Israeli president, Isaac Herzog, for alleged war crimes before his arrival in the UK this week.</p><p>Herzog is accused of aiding and abetting the indiscriminate killing of civilians in Gaza in the request to the director of public prosecutions filed by the Friends of Al-Aqsa campaign group.</p> <a href="https://www.theguardian.com/world/2025/sep/09/pro-palestine-activists-call-for-arrest-israeli-president-isaac-herzog-during-uk-visit">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/pro-palestine-activists-call-for-arrest-israeli-president-isaac-herzog-during-uk-visit	The Guardian World	2025-09-09 13:57:59	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.666768	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/09"], "events": [], "people": ["Isaac Herzog"], "status": "success", "topics": ["war crimes", "Middle East crisis"], "numbers": [], "locations": ["UK", "Gaza", "Israel", "Middle East"], "organizations": ["Friends of Al-Aqsa", "IDF"]}	\N
211	Greta Thunberg flotilla says Gaza aid boat hit by drone attack in Tunisia	<p>Global Sumud Flotilla shares video showing vessel being hit by flaming object at port, but says its mission will go ahead</p><ul><li><p><a href="https://www.theguardian.com/world/live/2025/sep/09/israel-gaza-city-evacuation-order-idf-military-offensive-live-updates-middle-east-crisis-latest-news">Middle East crisis – live updates</a></p></li></ul><p>A flotilla carrying aid for Gaza and pro-Palestinian activists including Greta Thunberg says one its boats has been struck in a drone attack while docked in Tunisia.</p><p>The Global Sumud Flotilla (GSF) shared a video showing one of its boats being hit by a flaming object at Sidi Bou Said port, near the Tunisian capital, Tunis. “One of the flotilla’s main boats … was struck by a drone in Tunisian waters,” GSF said. “The boat is sailing under the Portuguese flag and all six passengers and crew are safe.”</p><p><em>Reuters contributed to this report</em></p> <a href="https://www.theguardian.com/world/2025/sep/09/flotilla-carrying-aid-to-gaza-struck-by-flaming-object-video-shows-sidi-bou-said-port-tunisia">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/flotilla-carrying-aid-to-gaza-struck-by-flaming-object-video-shows-sidi-bou-said-port-tunisia	The Guardian World	2025-09-09 14:06:19	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.666439	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": [], "events": ["drone attack", "Israel-Gaza military offensive"], "people": ["Greta Thunberg"], "status": "success", "topics": ["Middle East crisis", "aid mission"], "numbers": [], "locations": ["Tunisia", "Sidi Bou Said port", "Tunis", "Gaza", "Portugal", "Middle East"], "organizations": ["Global Sumud Flotilla", "Reuters", "IDF"]}	\N
210	Israel launches airstrikes against top Hamas members in Qatar for Gaza ceasefire talks	<p>Israeli officials say US notified before attack, which Doha calls cowardly and a flagrant violation of international law</p><ul><li><p><a href="https://www.theguardian.com/world/live/2025/sep/09/israel-gaza-city-evacuation-order-idf-military-offensive-live-updates-middle-east-crisis-latest-news">Middle East crisis – live updates</a></p></li></ul><p>Israel has launched an attack on senior Hamas members meeting in Doha, reportedly including the group’s chief negotiator, making Qatar the latest Middle Eastern country to be targeted by an Israeli military operation.</p><p>Israel’s Channel 12, citing an Israeli official, claimed Donald Trump had given the green light for the attack, which is especially shocking given that Qatar has acted as a key intermediary in the long and ongoing negotiations to reach a ceasefire in Gaza.</p> <a href="https://www.theguardian.com/world/2025/sep/09/israel-targets-top-hamas-members-in-qatar-for-gaza-ceasefire-talks">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/israel-targets-top-hamas-members-in-qatar-for-gaza-ceasefire-talks	The Guardian World	2025-09-09 14:21:13	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.666163	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/09"], "events": ["Israeli attack on Hamas members", "Gaza ceasefire talks", "Middle East crisis"], "people": ["Donald Trump"], "status": "success", "topics": ["international law", "military operation", "ceasefire negotiations"], "numbers": [], "locations": ["Israel", "Doha", "Qatar", "Gaza", "Middle East"], "organizations": ["Hamas", "IDF", "Channel 12"]}	\N
209	Qatar condemns ‘criminal assault’ as Israel launches airstrikes against Hamas leaders in Doha – Middle East crisis live	<p>Ceasefire negotiators from militant group reportedly survive attacks</p><p><em>Dan Sabbagh is the Guardian’s defence and security editor</em></p><p>Fifty-one Israeli arms makers and the US defence giant behind the F-35 fighters used to bomb Gaza are among the 1,600 exhibitors at the biennial DSEI trade show that begins in London’s Docklands on Tuesday.</p> <a href="https://www.theguardian.com/world/live/2025/sep/09/israel-gaza-city-evacuation-order-idf-military-offensive-live-updates-middle-east-crisis-latest-news">Continue reading...</a>	\N	https://www.theguardian.com/world/live/2025/sep/09/israel-gaza-city-evacuation-order-idf-military-offensive-live-updates-middle-east-crisis-latest-news	The Guardian World	2025-09-09 14:52:24	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.66587	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/09"], "events": ["DSEI trade show"], "people": ["Dan Sabbagh"], "status": "success", "topics": ["defence and security", "military offensive", "Middle East crisis"], "numbers": ["51", "1,600"], "locations": ["London", "Docklands", "Gaza", "Israel"], "organizations": ["Guardian", "IDF"]}	\N
208	Norway’s Labour party wins election after seeing off populist surge	<p>Success for party of the prime minister, Jonas Gahr Støre, despite increased support for rightwing Progress party</p><p>The Norwegian Labour party has secured four more years in government after seeing off a surge of support for the populist right in a polarised election.</p><p>Soon after the polls closed,<strong> </strong>the centre left was projected to win with 89 seats with the centre right taking 80 seats. A minimum of 85 seats are needed for a majority.</p> <a href="https://www.theguardian.com/world/2025/sep/08/norways-labour-party-holds-narrow-lead-in-early-election-results">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/08/norways-labour-party-holds-narrow-lead-in-early-election-results	The Guardian World	2025-09-08 21:48:16	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.665593	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/08"], "events": ["election"], "people": ["Jonas Gahr Støre"], "status": "success", "topics": ["politics", "government"], "numbers": ["4", "89", "80", "85"], "locations": ["Norway"], "organizations": ["Norwegian Labour party", "Progress party"]}	\N
207	Majority in EU’s biggest states believes bloc ‘sold out’ in US tariff deal, poll finds	<p>Average of 77% of respondents across five countries thought agreement would benefit US economy above all</p><ul><li><p><a href="https://www.theguardian.com/world/2025/sep/09/cheese-producers-trump-tariffs-bite-will-theres-a-whey">Where there’s a will there’s a whey: cheese producers lean into their craft as Trump tariffs bite</a></p></li></ul><p>A majority of people across the EU’s five biggest member states believe the European Commission sold citizens out when negotiating a “humiliating” tariff deal with Donald Trump that “benefits the US” far more than Europe, a survey has shown.</p><p><a href="https://legrandcontinent.eu/fr/2025/09/09/10-points-eurobazooka/">The poll, by Cluster17</a> for the European affairs debate platform Le Grand Continent, found 77% of respondents – ranging from 89% in France to 50% in Poland – thought the deal would benefit above all the US economy, with only 2% believing it would benefit Europe’s.</p> <a href="https://www.theguardian.com/world/2025/sep/09/majority-in-eu-biggest-states-believes-bloc-sold-out-in-us-tariff-deal-poll-donald-trump">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/majority-in-eu-biggest-states-believes-bloc-sold-out-in-us-tariff-deal-poll-donald-trump	The Guardian World	2025-09-09 04:00:04	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.665308	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/09"], "events": [], "people": ["Donald Trump"], "status": "success", "topics": ["tariff deal", "economy"], "numbers": ["77%", "89%", "50%", "2%"], "locations": ["US", "Europe", "France", "Poland"], "organizations": ["European Commission", "Le Grand Continent", "Cluster17"]}	\N
206	France to get third PM in a year as Bayrou resigns after confidence vote	<p>Prime minister hands in resignation after thousands of protesters gather to celebrate ousting and plan day of action</p><p></p><p>The French prime minister, François Bayrou, has handed in his resignation after <a href="https://www.theguardian.com/world/2025/sep/08/francois-bayrou-ousted-as-french-pm-after-losing-confidence-vote">losing a confidence vote</a> that has plunged France into government collapse and <a href="https://www.theguardian.com/news/ng-interactive/2025/sep/07/frances-political-crisis-reveals-deep-rift-between-the-people-and-their-politicians">political crisis</a>.</p><p>Emmanuel Macron has said he will appoint a new prime minister in the coming days, who would then have to form a new government. This will be the third French prime minister in a year, whose first task will be the major challenge of agreeing a budget among a divided parliament.</p> <a href="https://www.theguardian.com/world/2025/sep/09/francois-bayrou-france-block-everything-protests-macron">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/francois-bayrou-france-block-everything-protests-macron	The Guardian World	2025-09-09 13:00:27	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.664972	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/08", "2025/09/07", "2025/09/09"], "events": ["confidence vote", "government collapse", "political crisis"], "people": ["François Bayrou", "Emmanuel Macron"], "status": "success", "topics": ["politics"], "numbers": ["third", "thousands", "a year"], "locations": ["France"], "organizations": []}	\N
205	France to get third PM in a year as Bayrou resigns after confidence vote – as it happened	<p>Emmanuel Macron to name successor ‘within days’ as political crisis grips France</p><ul><li><p><a href="https://www.theguardian.com/world/2025/sep/08/francois-bayrou-ousted-as-french-pm-after-losing-confidence-vote">France to get third PM in a year</a></p></li></ul><p><strong>Lithuania</strong> has also said it will strengthen its borders with <strong>Belarus</strong> and <strong>Russia</strong> during the Zapad military exercise, the country’s border guard <a href="https://vsat.lrv.lt/lt/naujienos/pratybu-zapad-2025-metu-lietuvos-vsat-dar-labiau-sustiprins-sienos-apsauga-foto-CnG/">said today.</a></p><p>The authorities said <strong>they would carry “even more active border monitoring, patrols, and other border control measures,”</strong> looking for any potential border violations and provocations against Lithuania.</p> <a href="https://www.theguardian.com/world/live/2025/sep/09/france-crisis-government-emmanuel-macron-europe-latest-live-news-updates">Continue reading...</a>	\N	https://www.theguardian.com/world/live/2025/sep/09/france-crisis-government-emmanuel-macron-europe-latest-live-news-updates	The Guardian World	2025-09-09 14:02:44	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.664652	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/08", "2025/09/09"], "events": ["Zapad military exercise"], "people": ["Emmanuel Macron", "Francois Bayrou"], "status": "success", "topics": ["political crisis", "border control", "government"], "numbers": [], "locations": ["France", "Lithuania", "Belarus", "Russia"], "organizations": []}	\N
204	Spanish government moves to ban smoking on bar terraces	<p>Tobacco law would also prohibit minors from using vapes and stop sale of single-use electronic cigarettes</p><p>The Spanish government has approved a draft tobacco law that would ban smoking and vaping on bar and restaurant terraces, prohibit minors from using vapes and related products, and end the sale of single-use electronic cigarettes.</p><p>The legislation, which was signed off by the cabinet on Tuesday morning, is intended to “reinforce protections on people’s health and to adapt the law to consumption patterns and to the tobacco-product market”, according to the health ministry.</p> <a href="https://www.theguardian.com/world/2025/sep/09/spanish-government-moves-ban-smoking-bar-terraces">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/spanish-government-moves-ban-smoking-bar-terraces	The Guardian World	2025-09-09 14:36:29	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.664238	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["Tuesday", "2025/09/09"], "events": [], "people": [], "status": "success", "topics": ["tobacco law", "vaping", "smoking", "electronic cigarettes"], "numbers": [], "locations": ["Spain"], "organizations": ["Spanish government", "health ministry"]}	\N
203	Herald Sun failed to seek response from Victorian MP Sam Groth and wife before article that invaded privacy, court documents claim	<p>Groth and wife Brittany are suing a News Corp paper for defamation and breach of privacy over incorrect claims of inappropriate relationship</p><ul><li><p>Get our <a href="https://www.theguardian.com/email-newsletters?CMP=cvau_sfl">breaking news email</a>, <a href="https://app.adjust.com/w4u7jx3">free app</a> or <a href="https://www.theguardian.com/australia-news/series/full-story?CMP=cvau_sfl">daily news podcast</a></p></li></ul><p>The Herald Sun failed to seek a response from Brittany Groth, the wife of Sam Groth, the Victorian Liberals deputy leader and former tennis star, before wrongly outing her as a victim of child sexual assault who was preyed upon by her now-husband when he was her coach, the couple allege in federal court documents.</p><p>The Herald and Weekly Times, along with reporter Stephen Drill, who wrote the articles, and his editor Sam Weir, are being sued in the federal court by Brittany Groth, in the first test of a new statutory tort for serious invasions of privacy, and by Sam Groth for defamation.</p> <a href="https://www.theguardian.com/law/2025/sep/09/herald-sun-failed-to-seek-response-from-victorian-mp-sam-groth-and-wife-before-article-that-invaded-privacy-court-documents-claim">Continue reading...</a>	\N	https://www.theguardian.com/law/2025/sep/09/herald-sun-failed-to-seek-response-from-victorian-mp-sam-groth-and-wife-before-article-that-invaded-privacy-court-documents-claim	The Guardian World	2025-09-09 10:18:04	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.663944	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": [], "events": [], "people": ["Brittany Groth", "Sam Groth", "Stephen Drill", "Sam Weir"], "status": "success", "topics": ["defamation", "breach of privacy", "child sexual assault"], "numbers": [], "locations": [], "organizations": ["News Corp", "The Herald Sun", "The Guardian", "Herald and Weekly Times", "Victorian Liberals"]}	\N
202	Brittany Higgins ordered to pay 80% of Linda Reynolds’ legal costs after defamation ruling	<p>Total amount former Liberal staffer has been ordered to pay is not known but is expected to be in the order of hundreds of thousands of dollars</p><p>Brittany Higgins has been ordered to pay 80% of her former boss Linda Reynold’s legal costs from <a href="https://www.theguardian.com/australia-news/2025/aug/28/the-reynolds-v-higgins-defamation-ruling-concludes-a-protracted-legal-battle-but-when-will-the-saga-end-ntwnfb">their high-profile defamation fight</a>.</p><p>Last month, Western Australian supreme court judge Paul Tottle ruled the former defence minister’s reputation was damaged by a 2022 social media post from Higgins’ partner David Sharaz, which Higgins responded to, and an Instagram story published by Higgins in July 2023.</p> <a href="https://www.theguardian.com/law/2025/sep/09/brittany-higgins-ordered-to-pay-80-per-cent-of-linda-reynolds-legal-costs-after-defamation-ruling-ntwnfb">Continue reading...</a>	\N	https://www.theguardian.com/law/2025/sep/09/brittany-higgins-ordered-to-pay-80-per-cent-of-linda-reynolds-legal-costs-after-defamation-ruling-ntwnfb	The Guardian World	2025-09-09 10:29:13	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.663677	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2022", "July 2023"], "events": ["Reynolds v Higgins defamation ruling"], "people": ["Brittany Higgins", "Linda Reynolds", "David Sharaz", "Paul Tottle"], "status": "success", "topics": ["Defamation", "Legal battle"], "numbers": ["80%", "hundreds of thousands of dollars"], "locations": ["Western Australia"], "organizations": []}	\N
201	Lachlan finally has control of Murdoch empire but deal is a win for sibling rivals	<p>Eldest son has succession Rupert craved after agreement for much higher payout to his brother and sisters</p><p>As a keen rock climber, Lachlan Murdoch knows a thing or two about the importance of clinging on to perilous terrain. After the toughest ascent of his life – rising to the top of his father’s business empire – he has finally ensured that his place at its summit is assured.</p><p>The deal Rupert Murdoch’s eldest son <a href="https://www.theguardian.com/us-news/2025/sep/08/rupert-murdoch-lachlan-family-succession-deal">has struck with his oldest siblings, Prudence, Elisabeth and James</a>, will mean they give up their shares in the family business, handing Lachlan the long-term control that he and his father craved.</p> <a href="https://www.theguardian.com/media/2025/sep/09/lachlan-control-murdoch-empire-but-deal-win-sibling-rivals">Continue reading...</a>	\N	https://www.theguardian.com/media/2025/sep/09/lachlan-control-murdoch-empire-but-deal-win-sibling-rivals	The Guardian World	2025-09-09 10:49:06	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.66337	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/08", "2025/09/09"], "events": [], "people": ["Lachlan Murdoch", "Rupert Murdoch", "Prudence Murdoch", "Elisabeth Murdoch", "James Murdoch"], "status": "success", "topics": ["succession", "business empire"], "numbers": [], "locations": [], "organizations": []}	\N
200	Kerry Stokes ordered to pay Ben Roberts-Smith’s $13.5m legal costs after failed defamation suit	<p>Seven boss handed bill by federal court after backing the disgraced former soldier in action against Nine Newspapers</p><ul><li><p><strong>Get our </strong><a href="https://www.theguardian.com/email-newsletters?CMP=cvau_sfl"><strong>breaking news email</strong></a><strong>, </strong><a href="https://app.adjust.com/w4u7jx3"><strong>free app</strong></a><strong> or </strong><a href="https://www.theguardian.com/australia-news/series/full-story?CMP=cvau_sfl"><strong>daily news podcast</strong></a></p></li></ul><p>Seven West Media’s chair, Kerry Stokes, has been ordered to pay $13.5m in legal costs to companies who were unsuccessfully sued for defamation by disgraced former soldier Ben Roberts-Smith.</p><p>On Tuesday, a federal court registrar ordered that Australian Capital Equity Pty Ltd (ACE), Stokes’ private company, pay costs fixed at almost $13.3m, and a further $225,000 in relation to the costs assessment, bringing the total bill to $13.5m.</p> <a href="https://www.theguardian.com/australia-news/2025/sep/09/kerry-stokes-ordered-to-pay-ben-roberts-smiths-135m-legal-costs-after-failed-defamation-suit">Continue reading...</a>	\N	https://www.theguardian.com/australia-news/2025/sep/09/kerry-stokes-ordered-to-pay-ben-roberts-smiths-135m-legal-costs-after-failed-defamation-suit	The Guardian World	2025-09-09 11:52:30	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.663036	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": [], "events": ["defamation suit"], "people": ["Kerry Stokes", "Ben Roberts-Smith"], "status": "success", "topics": ["news", "media", "law", "court cases", "defamation"], "numbers": ["$13.5m", "$13.3m", "$225,000"], "locations": [], "organizations": ["Seven West Media", "Australian Capital Equity Pty Ltd (ACE)", "Nine Newspapers"]}	\N
199	Proposed ‘nation-leading’ NSW childcare reforms to include $500,000 fines	<p>Greens welcome Minns government’s ‘bare-minimum’ changes but say more work is needed to restore faith in the sector</p><ul><li><p>Get our <a href="https://www.theguardian.com/email-newsletters?CMP=cvau_sfl">breaking news email</a>, <a href="https://app.adjust.com/w4u7jx3">free app</a> or <a href="https://www.theguardian.com/australia-news/series/full-story?CMP=cvau_sfl">daily news podcast</a></p></li></ul><p>Large childcare providers found in breach of safety directives will face $500,000 fines – a 900% increase – under new laws to be introduced by New South Wales parliament on Wednesday.</p><p>The proposed legislation will grant greater powers to the early childhood regulator to suspend educators and revoke quality ratings in a suite of measures addressing grave concerns about safety in the sector.</p> <a href="https://www.theguardian.com/australia-news/2025/sep/10/proposed-nation-leading-nsw-childcare-reforms-to-include-500000-fines">Continue reading...</a>	\N	https://www.theguardian.com/australia-news/2025/sep/10/proposed-nation-leading-nsw-childcare-reforms-to-include-500000-fines	The Guardian World	2025-09-09 14:01:43	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.662677	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["Wednesday"], "events": [], "people": [], "status": "success", "topics": ["childcare reforms", "safety directives", "early childhood education"], "numbers": ["$500,000", "900%"], "locations": ["New South Wales"], "organizations": ["Greens", "Minns government", "New South Wales parliament"]}	\N
198	Fugitive father shot dead by police – as it happened	<p>This blog is now closed. Our full report is here: <a href="https://www.theguardian.com/world/2025/sep/08/tom-phillips-new-zealand-fugitive-father-shot-dead-nz-police">Tom Phillips shot dead after attempted burglary, NZ police confirm</a></p><p>The mayor of Waitomo, <strong>John Robertson</strong>, told the Guardian this morning’s events were the worst possible outcome for the community.</p><p>“I’m shattered, to be honest, and there will be many in the community that are devastated that this was the outcome after three and a half, four years,” he said.</p><p>So it’s just devastating news. Really the worst outcome we could have expected.</p><p>No day that goes by that I don’t think about all four of them.</p><p>It hurts every time I see photos of the children and of you, and see some of your stuff that is still here, thinking what could have been if you had not gone away.</p> <a href="https://www.theguardian.com/world/live/2025/sep/08/tom-phillips-shooting-live-updates-nz-police-search-for-children-of-fugitive-father-shot-new-zealand-police-latest-updates">Continue reading...</a>	\N	https://www.theguardian.com/world/live/2025/sep/08/tom-phillips-shooting-live-updates-nz-police-search-for-children-of-fugitive-father-shot-new-zealand-police-latest-updates	The Guardian World	2025-09-08 06:17:21	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.662122	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/08"], "events": ["attempted burglary", "shooting"], "people": ["Tom Phillips", "John Robertson"], "status": "success", "topics": [], "numbers": ["3.5 years", "4 years"], "locations": ["Waitomo", "New Zealand"], "organizations": ["NZ police", "The Guardian"]}	\N
197	Tom Phillips, fugitive father on run with children for nearly four years, shot dead by NZ police in exchange of fire	<p>Phillips, who has been on the run with his children for four years, was shot by police after officers came under fire while investigating burglary in Piopio, authorities said</p><p>A fugitive father who had been hiding in New Zealand’s rugged wilderness with his three children for nearly four years has been shot dead by police investigating an armed burglary, police said on Monday.</p><p>The whereabouts of Tom Phillips has attracted headlines around the world since just before Christmas 2021, when he <a href="https://www.theguardian.com/world/2024/jan/05/new-zealands-two-year-search-in-wilderness-for-fugitive-father-and-three-missing-children">fled into the Waikato wilderness with his children</a> Ember, now 9, Maverick, 10, and Jayda, 12, following a custody dispute with their mother.</p> <a href="https://www.theguardian.com/world/2025/sep/08/tom-phillips-new-zealand-fugitive-father-shot-dead-nz-police">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/08/tom-phillips-new-zealand-fugitive-father-shot-dead-nz-police	The Guardian World	2025-09-08 07:01:03	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.661547	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["Christmas 2021", "Monday (no specific date mentioned)"], "events": ["armed burglary", "custody dispute", "police investigation"], "people": ["Tom Phillips", "Ember", "Maverick", "Jayda"], "status": "success", "topics": ["fugitive father", "missing children"], "numbers": ["4 years", "9", "10", "12"], "locations": ["Piopio", "Waikato wilderness", "New Zealand"], "organizations": ["New Zealand police"]}	\N
196	Images of Tom Phillips’ remote campsite revealed a day after fugitive father shot dead by New Zealand police	<p>After four years on the run with their father, Phillips’ three children have all been located and are ‘doing well under the circumstances’, say authorities</p><p>Police in New Zealand have released images and given details of the campsite where two of fugitive Tom Phillips’ children were found, after their father was shot and killed by police on Monday.</p><p>Phillips had spent nearly four years hiding in the wilderness with his children. He was <a href="https://www.theguardian.com/world/2025/sep/08/tom-phillips-new-zealand-fugitive-father-shot-dead-nz-police">killed</a> in an exchange of fire with police after reports of a burglary in the remote town of Piopio. A police officer is recovering in hospital after being shot in the head by Phillips with a high-powered rifle in the standoff. About 11 hours after Phillips was killed, two of his children were found safe and well at the campsite in Waitomo. It is understood the third child was with Phillips at the time of the shooting.</p> <a href="https://www.theguardian.com/world/2025/sep/09/tom-phillips-new-zealand-remote-campsite-images-pictures-revealed">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/tom-phillips-new-zealand-remote-campsite-images-pictures-revealed	The Guardian World	2025-09-09 04:06:31	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.660855	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/08", "2025/09/09"], "events": ["burglary", "standoff", "shooting"], "people": ["Tom Phillips"], "status": "success", "topics": ["fugitive case"], "numbers": ["four years", "11 hours"], "locations": ["New Zealand", "Piopio", "Waitomo"], "organizations": ["Police in New Zealand", "NZ Police"]}	\N
195	Thaksin Shinawatra jailed by Thailand supreme court for one year in major blow to former prime minister	<p>Case centred on claims that he had not properly served a sentence for corruption and abuse of power, which was handed down in 2023</p><p>Thailand’s former prime minister Thaksin Shinawatra must serve one year in jail, the country’s supreme court has ruled, in a major blow to one of the country’s most prominent and polarising politicians.</p><p>The court ruled that Thaksin had not properly served an eight-year sentence for corruption and abuse of power, which was handed down when <a href="https://www.theguardian.com/world/2023/aug/22/thaksin-shinawatra-anger-and-anticipation-in-thailand-as-exiled-former-pm-expected-to-return">he returned to the country from self-imposed exile in 2023</a>. After arriving back in the country, Thaksin spent less than 24 hours in jail, but was moved to the<a href="https://www.theguardian.com/world/2023/sep/11/air-con-a-fridge-and-sofa-thaksin-shinawatras-vvip-prison-life-in-thailand"> VIP wing of a hospital</a> on health grounds, where he stayed for six months before he was released on parole.<br /><br />\n In its judgment, the supreme court found that the arrangement allowing Thaksin to stay at hospital was unlawful. “The defendant knows his sickness was not an urgent matter, and staying in hospital cannot count as a prison term,” said the ruling read out by a judge.<br /><br />\n “The court will issue a jail warrant and an official from Bangkok Remand Prison will take him,” the judge said.</p> <a href="https://www.theguardian.com/world/2025/sep/09/thaksin-shinawatra-former-prime-minister-jailed-by-thailand-supreme-court-for-one-year-ntwnfb">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/thaksin-shinawatra-former-prime-minister-jailed-by-thailand-supreme-court-for-one-year-ntwnfb	The Guardian World	2025-09-09 04:33:45	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.660181	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2023"], "events": [], "people": ["Thaksin Shinawatra"], "status": "success", "topics": ["corruption", "abuse of power"], "numbers": ["8 years", "1 year", "24 hours", "6 months"], "locations": ["Thailand"], "organizations": ["Bangkok Remand Prison", "Thailand's supreme court"]}	\N
194	Albanese went to Vanuatu to sign a $500m agreement – but leaves empty-handed thanks to concerns about China	<p>Vanuatu’s PM says ‘more discussions’ needed on Nakamal agreement due to concerns over his nation’s ability to seek infrastructure funding from other countries</p><ul><li><p><a href="https://www.theguardian.com/australia-news/live/2025/sep/09/australia-news-live-anthony-albanese-vanuatu-china-pacific-forum-murray-watt-nature-protection-laws-ntwnfb">Follow our Australia news live blog for latest updates</a></p></li><li><p>Get our <a href="https://www.theguardian.com/email-newsletters?CMP=cvau_sfl">breaking news email</a>, <a href="https://app.adjust.com/w4u7jx3">free app</a> or <a href="https://www.theguardian.com/australia-news/series/full-story?CMP=cvau_sfl">daily news podcast</a></p></li></ul><p>The federal government is racing to save a major new agreement with Vanuatu, after Anthony Albanese’s plans to sign the deal were rebuffed over concerns about infrastructure funding from China.</p><p>Speaking alongside Vanuatu’s prime minister, Jotham Napat, on Tuesday, Albanese said he was confident the Nakamal agreement will be “able to be signed soon”, talking up cooperation and proper process with Vanuatu’s governing coalition.</p> <a href="https://www.theguardian.com/australia-news/2025/sep/09/albanese-went-to-vanuatu-to-sign-a-500m-agreement-but-leaves-empty-handed-thanks-to-concerns-about-china">Continue reading...</a>	\N	https://www.theguardian.com/australia-news/2025/sep/09/albanese-went-to-vanuatu-to-sign-a-500m-agreement-but-leaves-empty-handed-thanks-to-concerns-about-china	The Guardian World	2025-09-09 06:31:43	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.659538	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/09"], "events": [], "people": ["Anthony Albanese", "Jotham Napat"], "status": "success", "topics": ["Nakamal agreement", "Infrastructure funding", "Pacific Forum"], "numbers": ["$500m"], "locations": ["Vanuatu", "Australia", "China"], "organizations": ["Vanuatu government", "Australian federal government", "The Guardian"]}	\N
193	LGBTQ+ Americans consider move to Canada to escape Trump: ‘I’m afraid of living here’	<p>LGBTQ+ people in the US contemplate heading north as they wrestle with the president’s assault on the community</p><p>The number of <a href="https://www.theguardian.com/world/lgbt-rights">LGBTQ+</a> Americans inquiring about moving to <a href="https://www.theguardian.com/world/canada">Canada</a> has soared since Donald Trump’s re-election, campaigners have said, as people across the US wrestle with the fallout of rising anti-gay rhetoric, anti-trans executive orders, and the more than 600 bills targeting LGBTQ+ rights.</p><p>“So much is happening in the US right now and a lot of it is terrifying,” said Latoya Nugent of Rainbow Railroad, a North American charity that helps LGBTQI+ individuals escape violence and persecution in their home countries.</p> <a href="https://www.theguardian.com/world/2025/sep/07/trump-lgbtq-americans-canada">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/07/trump-lgbtq-americans-canada	The Guardian World	2025-09-07 10:00:17	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.658819	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": [], "events": [], "people": [], "status": "success", "topics": [], "numbers": [], "locations": [], "organizations": []}	\N
192	Republican condemns Vance for ‘despicable’ comments on Venezuelan boat strike	<p>Rand Paul decries ‘thoughtless’ comment after vice-president defends strike against alleged drug traffickers</p><p>The Republican senator who heads the homeland security committee has criticized JD Vance for “despicable” comments apparently in support of extrajudicial military killings.</p><p>“Killing cartel members who poison our fellow citizens is the highest and best use of our military,” the vice-president said in an X post on Saturday, in defense of Tuesday’s US military <a href="https://www.theguardian.com/us-news/2025/sep/02/trump-venezuela-boat-lethal-strike">strike</a> against a Venezuelan boat in the Caribbean Sea, which killed 11 people the administration alleged were drug traffickers.</p> <a href="https://www.theguardian.com/us-news/2025/sep/07/jd-vance-venezuelan-boat-strike-rand-paul">Continue reading...</a>	\N	https://www.theguardian.com/us-news/2025/sep/07/jd-vance-venezuelan-boat-strike-rand-paul	The Guardian World	2025-09-07 15:56:23	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.658122	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["Tuesday (no specific date mentioned)", "Saturday (no specific date mentioned)", "2025-09-02", "2025-09-07"], "events": ["strike against Venezuelan boat"], "people": ["Rand Paul", "JD Vance"], "status": "success", "topics": ["extrajudicial military killings", "drug trafficking", "homeland security"], "numbers": ["11 people killed"], "locations": ["Venezuela", "Caribbean Sea"], "organizations": ["US military", "Republican Party"]}	\N
191	Argentinians deliver electoral blow to Milei’s scandal-rocked government	<p>President touted contest in Buenos Aires province – 40% of electorate – as ‘life or death battle’ but won only 34% of vote</p><p><a href="https://www.theguardian.com/world/argentina">Argentina</a>’s president, <a href="https://www.theguardian.com/world/javier-milei">Javier Milei</a>, has suffered his worst electoral defeat since taking office, as he faces his administration’s most serious corruption scandal and signs that the economy is slowing.</p><p>In local legislative elections on Sunday for Buenos Aires province – home to almost 40% of the country’s electorate – the coalition led by the self-styled anarcho-capitalist was beaten by the opposition by 47% to 34%.</p> <a href="https://www.theguardian.com/world/2025/sep/08/argentina-election-javier-milei">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/08/argentina-election-javier-milei	The Guardian World	2025-09-08 16:44:16	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.65738	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["Sunday", "2025/09/08"], "events": ["local legislative elections"], "people": ["Javier Milei"], "status": "success", "topics": ["corruption scandal", "economy"], "numbers": ["40%", "34%", "47%"], "locations": ["Argentina", "Buenos Aires province"], "organizations": []}	\N
190	Boris Johnson was paid £240,000 after Maduro meeting, invoice shows	<p>Johnson’s office sent invoice to hedge fund manager, which was paid, weeks after meeting Venezuelan leader last year</p><ul><li><p><a href="https://www.theguardian.com/uk-news/2025/sep/08/revealed-how-boris-johnson-traded-pm-contacts-for-global-business-deals">Revealed: how Boris Johnson traded PM contacts for global business deals</a></p></li></ul><p>From a private jet somewhere over the Caribbean Sea in February last year, Boris Johnson called his old political adversary David Cameron, then the foreign secretary, to notify him of a visit.</p><p>Johnson had taken a day out from a family holiday in the Dominican Republic for an unlikely meeting with the leftwing president of Venezuela, Nicolás Maduro, a man whom Johnson, when in office, had likened to a “dictator of an evil regime”.</p> <a href="https://www.theguardian.com/uk-news/2025/sep/08/boris-johnson-nicolas-maduro-meeting-invoice">Continue reading...</a>	\N	https://www.theguardian.com/uk-news/2025/sep/08/boris-johnson-nicolas-maduro-meeting-invoice	The Guardian World	2025-09-08 18:12:48	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.656659	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["February last year"], "events": ["Meeting between Boris Johnson and Nicolás Maduro", "Boris Johnson's family holiday"], "people": ["Boris Johnson", "David Cameron", "Nicolás Maduro"], "status": "success", "topics": ["Global business deals", "Politics"], "numbers": [], "locations": ["Caribbean Sea", "Dominican Republic", "Venezuela"], "organizations": ["Johnson's office", "The Guardian"]}	\N
189	Peru accused of violating human rights after government rejects reserve for uncontacted people	<p>Campaigners shocked after ministers voted against the 1.2m-hectare Yavari Mirim reserve after 20 years of debate</p><p>Campaigners have accused the Peruvian government of violating international human rights law and putting lives at risk in the Amazon after it rejected a vast new territory to protect some of the world’s most isolated Indigenous communities.</p><p>After two decades of political debate, a government-led commission voted on Friday against creating the Yavari Mirim Indigenous reserve, a 1.2m-hectare (2.9m-acre) expanse of pristine rainforest along the border with Brazil. The tally was decisive: eight against, five in favour, with three members absent from the crucial vote.</p> <a href="https://www.theguardian.com/global-development/2025/sep/09/peru-accused-of-violating-human-rights-after-government-rejects-yavari-mirim-reserve-for-uncontacted-peoples">Continue reading...</a>	\N	https://www.theguardian.com/global-development/2025/sep/09/peru-accused-of-violating-human-rights-after-government-rejects-yavari-mirim-reserve-for-uncontacted-peoples	The Guardian World	2025-09-09 10:32:15	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.655914	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["20 years ago", "Friday (no specific date mentioned)", "2025/09/09"], "events": ["vote on Yavari Mirim Indigenous reserve creation"], "people": [], "status": "success", "topics": ["human rights law", "Indigenous communities", "rainforest conservation"], "numbers": ["1.2m-hectare", "2.9m-acre", "8", "5", "3"], "locations": ["Amazon", "Brazil", "Peru", "Yavari Mirim reserve"], "organizations": ["Peruvian government", "The Guardian"]}	\N
188	Lawyers say men deported by US to Eswatini are being imprisoned illegally	<p>The men, who had been released after serving criminal sentences, are from Laos, Vietnam, Cuba, Jamaica and Yemen</p><p>Lawyers for five men deported by the US to Eswatini, formerly Swaziland, said they are being denied proper access to their clients, who they said are being imprisoned illegally.</p><p>The men from Vietnam, Jamaica, Laos, Yemen and Cuba have criminal convictions, but had all served their sentences and been released in the US, their lawyers said. The US deported them to the small southern African country without warning in July, claiming they were “depraved monsters”.</p> <a href="https://www.theguardian.com/us-news/2025/sep/02/lawyers-say-men-deported-by-us-to-eswatini-are-being-imprisoned-illegally">Continue reading...</a>	\N	https://www.theguardian.com/us-news/2025/sep/02/lawyers-say-men-deported-by-us-to-eswatini-are-being-imprisoned-illegally	The Guardian World	2025-09-03 08:48:53	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.655056	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/02", "July"], "events": ["deportation"], "people": [], "status": "success", "topics": ["immigration", "law", "justice", "human rights"], "numbers": [5], "locations": ["Laos", "Vietnam", "Cuba", "Jamaica", "Yemen", "Eswatini", "Swaziland", "Africa", "US"], "organizations": ["US", "The Guardian"]}	\N
187	Trump’s aid cuts in east Africa led to unwanted abortion and babies being born with HIV – report	<p>Doctors, nurses, patients and other experts describe the loss of decades of progress in beating the virus in 100 days after Pepfar was disrupted</p><p>Aid cuts in east Africa have led to cases of babies being born with HIV because mothers could not get medication, a rise in life-threatening infections, and at least one woman having an unwanted abortion, according to interviews with medical staff, patients and experts.</p><p>A <a href="https://phr.org/our-work/resources/on-the-brink-of-catastrophe-u-s-foreign-aid-disruption-to-hiv-services-in-tanzania-and-uganda/">report by Physicians for Human Rights</a> (PHR) sets out dozens of examples of the impact of disruption to Pepfar – the president’s emergency plan for aids relief – in Tanzania and Uganda.</p> <a href="https://www.theguardian.com/global-development/2025/sep/03/trumps-aid-cuts-in-east-africa-led-to-unwanted-abortions-and-babies-being-born-with-hiv-report">Continue reading...</a>	\N	https://www.theguardian.com/global-development/2025/sep/03/trumps-aid-cuts-in-east-africa-led-to-unwanted-abortions-and-babies-being-born-with-hiv-report	The Guardian World	2025-09-03 13:00:23	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.654186	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2025/09/03"], "events": [], "people": [], "status": "success", "topics": ["HIV", "AIDS", "Foreign Aid Cuts"], "numbers": [100], "locations": ["East Africa", "Tanzania", "Uganda"], "organizations": ["Physicians for Human Rights", "Pepfar"]}	\N
186	Hopes rise for green economy boom at Africa Climate Summit	<p>Renewables are thriving, with Africa breaking solar energy records – but action is needed to plug financing gap</p><p>The first signs of a takeoff of Africa’s green economy are raising hopes that a transformation of the continent’s fortunes may be under way, driven by solar power and an increase in low-carbon investment.</p><p>African leaders are meeting this week in Addis Ababa, Ethiopia, for the <a href="https://africaclimatesummit2.et/">Africa Climate Summit</a>, a precursor to the <a href="https://www.theguardian.com/environment/2025/aug/19/brazil-issues-last-ditch-plea-for-countries-to-submit-climate-plans-ahead-of-cop30">global UN Cop30 in November</a>. They will call for an increase in support from rich countries for Africa’s green resurgence, without which they will warn it could be fragile and spread unevenly.</p> <a href="https://www.theguardian.com/environment/2025/sep/08/green-economy-boom-africa-climate-summit-renewable-energy-solar">Continue reading...</a>	\N	https://www.theguardian.com/environment/2025/sep/08/green-economy-boom-africa-climate-summit-renewable-energy-solar	The Guardian World	2025-09-08 10:38:22	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.653705	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["November", "2025"], "events": ["Africa Climate Summit", "global UN Cop30"], "people": [], "status": "success", "topics": ["green economy", "solar energy", "low-carbon investment", "climate plans", "renewable energy"], "numbers": [], "locations": ["Africa", "Addis Ababa", "Ethiopia", "Brazil"], "organizations": ["UN"]}	\N
185	Ethiopia inaugurates Africa’s largest hydroelectric dam as Egypt rift deepens	<p>Ethiopian PM says dam will electrify entire region but Egypt fears it could restrict water supply during droughts</p><p>Ethiopia has officially inaugurated Africa’s largest hydroelectric dam, a project that will provide energy to millions of Ethiopians while deepening a rift with downstream Egypt that has unsettled the region.</p><p>Ethiopia, the continent’s second most populous nation with more than 120 million people, sees the $5bn (£3.7bn) Grand Ethiopian Renaissance dam (Gerd) on a tributary of the Nile River as central to its economic ambitions. The dam’s power has gradually increased since the first turbine was turned on in 2022, reaching its maximum capacity of 5,150MW on Tuesday. That puts it among the 20 biggest hydroelectric dams in the world – about one-quarter of the capacity of China’s Three Gorges dam.</p> <a href="https://www.theguardian.com/world/2025/sep/09/ethiopia-inaugurates-africa-largest-hydroelectric-dam-egypt-rift-deepens">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/ethiopia-inaugurates-africa-largest-hydroelectric-dam-egypt-rift-deepens	The Guardian World	2025-09-09 11:24:17	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.653063	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2022", "2025/09/09"], "events": ["Inauguration of the Grand Ethiopian Renaissance dam"], "people": [], "status": "success", "topics": ["hydroelectric power", "water supply", "economic development", "energy production"], "numbers": ["120 million", "$5bn", "£3.7bn", "5,150MW"], "locations": ["Africa", "Ethiopia", "Nile River", "China"], "organizations": ["Ethiopian government", "Egyptian government"]}	\N
184	Joseph Kony case in The Hague begins with accounts of alleged atrocities	<p>ICC hearing takes place in absence of Ugandan rebel leader accused of murder, rape, torture and sexual slavery</p><p>An international criminal court hearing into charges of war crimes and crimes against humanity against the Ugandan fugitive rebel leader Joseph Kony has begun with accounts of atrocities allegedly committed by his Lord’s Resistance Army.</p><p>The ICC’s first in-absentia hearing will confirm charges but cannot progress to a trial in Kony’s absence. The warlord faces 39 counts, including murder, rape, sexual slavery, enslavement and torture, allegedly committed in northern Uganda between July 2002 and December 2005.</p><p><em>Reuters and Agence France-Presse contributed to this report</em></p> <a href="https://www.theguardian.com/world/2025/sep/09/joseph-kony-icc-hearing-the-hague-alleged-atrocities">Continue reading...</a>	\N	https://www.theguardian.com/world/2025/sep/09/joseph-kony-icc-hearing-the-hague-alleged-atrocities	The Guardian World	2025-09-09 14:16:54	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.65243	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["July 2002", "December 2005"], "events": ["ICC hearing"], "people": ["Joseph Kony"], "status": "success", "topics": ["war crimes", "crimes against humanity", "murder", "rape", "torture", "sexual slavery"], "numbers": ["39 counts"], "locations": ["Uganda", "The Hague"], "organizations": ["International Criminal Court", "Lord’s Resistance Army", "Reuters", "Agence France-Presse"]}	\N
182	State Department Agents Are Now Working With ICE on Immigration	The State Department’s law enforcement arm is now involved in immigration enforcement, an area solidly outside its usual duties. One source compares it to IRS agents investigating espionage at NASA.	\N	https://www.wired.com/story/state-department-dss-agents-ice-immigration/	Wired	2025-09-04 15:51:23	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.517471	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": [], "events": [], "people": [], "status": "success", "topics": ["immigration enforcement", "law enforcement", "espionage"], "numbers": [], "locations": [], "organizations": ["State Department", "IRS", "NASA"]}	\N
181	Meet Dyson’s Brand-New Lineup: V8 Cyclone, V16 Piston Animal, HushJet Purifier Compact	From an AI-driven robot vacuum to self-emptying stations for its next-gen stick vacuums, Dyson’s lineup will never be the same. You’ll have to wait until 2026 to get your hands on most of it, though.	\N	https://www.wired.com/story/dyson-new-lineup-2026/	Wired	2025-09-04 16:01:00	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.517286	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["2026"], "events": [], "people": [], "status": "success", "topics": ["AI-driven robot vacuum", "self-emptying stations", "stick vacuums"], "numbers": [], "locations": [], "organizations": ["Dyson"]}	\N
180	‘Hollow Knight: Silksong’ Is Already Causing Online Gaming Stores to Crash	After years of waiting for the sequel, a lot of fans trying to buy the game are getting error messages—and they’re not happy about it.	\N	https://www.wired.com/story/hollow-knight-silksong-is-already-causing-online-gaming-stores-to-crash/	Wired	2025-09-04 16:10:13	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.517116	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": ["years"], "events": ["sequel"], "people": [], "status": "success", "topics": ["game", "error messages"], "numbers": [], "locations": [], "organizations": []}	\N
179	Anti-Vaxxers Rejoice at Florida’s Scheme to End Vaccine Mandates for Kids and Everyone Else	As experts warn about possible outbreaks of diseases like polio and measles in Florida, anti-vaxxers declare “freedom.”	\N	https://www.wired.com/story/anti-vaxxers-rejoice-florida-plan-end-vaccine-mandate/	Wired	2025-09-04 17:05:46	\N	en	0.00	raw	\N	pending	\N	\N	\N	f	f	0	\N	\N	2025-09-09 11:07:56.516985	2025-09-09 15:15:17.182611	0	0	\N	[]	\N	{"dates": [], "events": [], "people": [], "status": "success", "topics": ["polio", "measles", "vaccination", "anti-vaxxers"], "numbers": [], "locations": ["Florida"], "organizations": []}	\N
\.


--
-- Data for Name: automation_logs; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.automation_logs (id, operation, status, "timestamp", articles_affected, processing_time, details, error_message, triggered_by) FROM stdin;
\.


--
-- Data for Name: automation_tasks; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.automation_tasks (id, name, description, enabled, schedule, last_run, next_run, status, run_count, success_count, failure_count, avg_execution_time, created_at, updated_at) FROM stdin;
1	RSS Collection	Collect articles from RSS feeds	t	every 15 minutes	\N	\N	idle	0	0	0	0	2025-09-08 18:49:31.380347+00	2025-09-08 18:49:31.380347+00
2	ML Processing	Process articles with ML models	t	every 30 minutes	\N	\N	idle	0	0	0	0	2025-09-08 18:49:31.380347+00	2025-09-08 18:49:31.380347+00
3	Deduplication	Detect and remove duplicate articles	t	every hour	\N	\N	idle	0	0	0	0	2025-09-08 18:49:31.380347+00	2025-09-08 18:49:31.380347+00
4	Story Consolidation	Consolidate related articles into stories	t	every 2 hours	\N	\N	idle	0	0	0	0	2025-09-08 18:49:31.380347+00	2025-09-08 18:49:31.380347+00
5	Daily Briefing Generation	Generate daily briefings	t	daily at 06:00	\N	\N	idle	0	0	0	0	2025-09-08 18:49:31.380347+00	2025-09-08 18:49:31.380347+00
6	Database Cleanup	Clean up old data and optimize database	t	weekly on Sunday at 02:00	\N	\N	idle	0	0	0	0	2025-09-08 18:49:31.380347+00	2025-09-08 18:49:31.380347+00
\.


--
-- Data for Name: briefing_templates; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.briefing_templates (id, name, description, sections, schedule, enabled, created_at, updated_at, created_by) FROM stdin;
1	Executive Summary	High-level overview of key developments	["Top Stories", "Market Impact", "Key Metrics"]	daily	t	2025-09-08 18:49:31.376258+00	2025-09-08 18:49:31.376258+00	system
2	Technology Focus	Technology and innovation highlights	["Tech News", "AI Developments", "Startup Updates"]	daily	t	2025-09-08 18:49:31.376258+00	2025-09-08 18:49:31.376258+00	system
3	Weekly Analysis	Comprehensive weekly analysis	["Trend Analysis", "Market Review", "Forecast"]	weekly	t	2025-09-08 18:49:31.376258+00	2025-09-08 18:49:31.376258+00	system
\.


--
-- Data for Name: cluster_articles; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.cluster_articles (id, cluster_id, article_id, similarity_score, added_at) FROM stdin;
\.


--
-- Data for Name: collection_rules; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.collection_rules (id, name, rule_type, rule_config, feed_id, max_articles_per_collection, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: content_hashes; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.content_hashes (id, content_hash, article_id, hash_type, created_at) FROM stdin;
\.


--
-- Data for Name: content_priority_assignments; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.content_priority_assignments (id, article_id, thread_id, priority_level_id, assigned_at, assigned_by, notes) FROM stdin;
\.


--
-- Data for Name: content_priority_levels; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.content_priority_levels (id, name, description, color, sort_order, created_at) FROM stdin;
1	Critical	Highest priority - immediate attention required	#f44336	1	2025-09-08 18:49:50.378923
2	High	High priority - important content	#ff9800	2	2025-09-08 18:49:50.378923
3	Medium	Medium priority - standard content	#2196f3	3	2025-09-08 18:49:50.378923
4	Low	Low priority - background information	#4caf50	4	2025-09-08 18:49:50.378923
\.


--
-- Data for Name: database_metrics; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.database_metrics (id, "timestamp", connection_count, active_queries, slow_queries, avg_query_time_ms, database_size_mb, table_sizes, created_at) FROM stdin;
\.


--
-- Data for Name: deduplication_settings; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.deduplication_settings (id, similarity_threshold, auto_remove, min_article_length, max_articles_to_process, enabled_algorithms, exclude_sources, include_sources, time_window_hours, created_at, updated_at) FROM stdin;
1	0.850	f	100	1000	["content_similarity", "title_similarity", "url_similarity"]	[]	[]	24	2025-09-08 18:49:30.03925+00	2025-09-08 18:49:30.03925+00
\.


--
-- Data for Name: deduplication_stats; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.deduplication_stats (id, date, total_duplicates, pending_review, high_similarity, very_high_similarity, medium_similarity, low_similarity, removed_count, rejected_count, accuracy_rate, processing_time, articles_processed, created_at) FROM stdin;
\.


--
-- Data for Name: entities; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.entities (id, text, type, frequency, confidence, first_seen, last_seen, metadata, created_at) FROM stdin;
\.


--
-- Data for Name: feed_categories; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.feed_categories (id, name, description, parent_category, is_active, created_at) FROM stdin;
1	politics	Political news and analysis	\N	t	2025-09-08 18:49:31.60893+00
2	economy	Economic news and financial markets	\N	t	2025-09-08 18:49:31.60893+00
3	technology	Technology news and innovation	\N	t	2025-09-08 18:49:31.60893+00
4	climate	Climate change and environmental news	\N	t	2025-09-08 18:49:31.60893+00
5	world	International news and global events	\N	t	2025-09-08 18:49:31.60893+00
6	business	Business news and corporate updates	\N	t	2025-09-08 18:49:31.60893+00
7	health	Health and medical news	\N	t	2025-09-08 18:49:31.60893+00
8	science	Scientific research and discoveries	\N	t	2025-09-08 18:49:31.60893+00
9	security	Cybersecurity and national security	\N	t	2025-09-08 18:49:31.60893+00
10	energy	Energy sector and renewable resources	\N	t	2025-09-08 18:49:31.60893+00
\.


--
-- Data for Name: feed_filtering_rules; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.feed_filtering_rules (id, feed_id, rule_type, rule_config, is_active, priority, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: feed_performance_metrics; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.feed_performance_metrics (id, feed_id, date, articles_fetched, articles_filtered_out, articles_accepted, duplicates_found, success_rate, avg_response_time, error_count, last_check, last_success, created_at) FROM stdin;
\.


--
-- Data for Name: generated_briefings; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.generated_briefings (id, template_id, title, content, generated_at, status, article_count, word_count, metadata) FROM stdin;
\.


--
-- Data for Name: global_filtering_config; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.global_filtering_config (id, config_name, config_data, is_active, created_at, updated_at) FROM stdin;
1	keyword_blacklist	{"gossip": ["rumor", "scandal", "divorce", "marriage", "dating", "relationship", "breakup"], "sports": ["nfl", "nba", "mlb", "nhl", "soccer", "football", "basketball", "baseball", "hockey", "olympics", "world cup"], "lifestyle": ["fashion", "beauty", "makeup", "tiktok", "instagram", "social media", "influencer", "trending", "viral"], "entertainment": ["celebrity", "oscars", "grammy", "emmy", "hollywood", "movie", "film", "actor", "actress", "singer", "musician"]}	t	2025-09-08 18:49:31.649291+00	2025-09-08 18:49:31.649291+00
2	category_whitelist	{"world": ["international", "global", "world", "foreign", "diplomacy", "conflict", "peace", "treaty", "summit"], "climate": ["climate", "environment", "carbon", "renewable", "sustainability", "green", "emissions", "global warming"], "economy": ["market", "economy", "financial", "business", "trade", "inflation", "gdp", "unemployment", "recession"], "politics": ["election", "government", "policy", "legislation", "congress", "senate", "parliament", "democracy", "voting"], "technology": ["tech", "innovation", "ai", "artificial intelligence", "cybersecurity", "digital", "software", "hardware"]}	t	2025-09-08 18:49:31.649291+00	2025-09-08 18:49:31.649291+00
3	nlp_classifier_config	{"threshold": 0.7, "categories": ["politics", "economy", "technology", "climate", "world", "business"], "model_name": "facebook/bart-large-mnli", "exclude_categories": ["entertainment", "sports", "lifestyle", "gossip"]}	t	2025-09-08 18:49:31.649291+00	2025-09-08 18:49:31.649291+00
4	url_patterns	{"exclude_patterns": ["/sports/", "/entertainment/", "/lifestyle/", "/gossip/", "/celebrity/", "/fashion/"], "include_patterns": ["/politics/", "/economy/", "/tech/", "/business/", "/world/", "/climate/", "/environment/"]}	t	2025-09-08 18:49:31.649291+00	2025-09-08 18:49:31.649291+00
\.


--
-- Data for Name: ml_model_performance; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.ml_model_performance (id, model_name, model_version, metric_name, metric_value, measured_at, context) FROM stdin;
1	summarization	1.2.0	accuracy	0.92	2025-09-08 18:49:30.838543+00	{"dataset": "news_articles", "test_size": 1000}
2	summarization	1.2.0	rouge_l	0.87	2025-09-08 18:49:30.838543+00	{"dataset": "news_articles", "test_size": 1000}
3	entity_extraction	2.1.0	precision	0.89	2025-09-08 18:49:30.838543+00	{"dataset": "news_entities", "test_size": 500}
4	entity_extraction	2.1.0	recall	0.91	2025-09-08 18:49:30.838543+00	{"dataset": "news_entities", "test_size": 500}
5	entity_extraction	2.1.0	f1_score	0.9	2025-09-08 18:49:30.838543+00	{"dataset": "news_entities", "test_size": 500}
6	sentiment_analysis	1.5.0	accuracy	0.87	2025-09-08 18:49:30.838543+00	{"dataset": "news_sentiment", "test_size": 800}
7	sentiment_analysis	1.5.0	f1_score	0.85	2025-09-08 18:49:30.838543+00	{"dataset": "news_sentiment", "test_size": 800}
8	clustering	1.0.0	silhouette_score	0.75	2025-09-08 18:49:30.838543+00	{"dataset": "news_clusters", "clusters": 50}
9	deduplication	1.3.0	precision	0.94	2025-09-08 18:49:30.838543+00	{"dataset": "duplicate_pairs", "test_size": 300}
10	deduplication	1.3.0	recall	0.91	2025-09-08 18:49:30.838543+00	{"dataset": "duplicate_pairs", "test_size": 300}
\.


--
-- Data for Name: ml_performance_metrics; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.ml_performance_metrics (id, task_type, avg_duration, success_rate, total_tasks, successful_tasks, failed_tasks, last_updated, created_at) FROM stdin;
\.


--
-- Data for Name: ml_resource_usage; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.ml_resource_usage (id, "timestamp", cpu_usage, memory_usage, gpu_usage, active_tasks, queue_size, created_at) FROM stdin;
\.


--
-- Data for Name: ml_task_dependencies; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.ml_task_dependencies (id, task_id, depends_on_task_id, dependency_type, created_at) FROM stdin;
\.


--
-- Data for Name: ml_task_queue; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.ml_task_queue (id, task_id, task_type, priority, storyline_id, article_id, payload, status, created_at, started_at, completed_at, result, error, retry_count, max_retries, estimated_duration, resource_requirements, updated_at) FROM stdin;
\.


--
-- Data for Name: performance_metrics; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.performance_metrics (id, metric_name, metric_value, metric_unit, "timestamp", metadata) FROM stdin;
\.


--
-- Data for Name: performance_monitoring; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.performance_monitoring (id, operation_type, operation_id, duration_ms, success, error_message, resource_usage, "timestamp") FROM stdin;
\.


--
-- Data for Name: priority_rules; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.priority_rules (id, name, condition, priority, enabled, created_at, updated_at, created_by) FROM stdin;
1	Breaking News	title ILIKE '%breaking%' OR title ILIKE '%urgent%'	critical	t	2025-09-08 18:49:31.378164+00	2025-09-08 18:49:31.378164+00	system
2	High-Impact Technology	category = 'technology' AND entities @> '["AI", "artificial intelligence"]'	high	t	2025-09-08 18:49:31.378164+00	2025-09-08 18:49:31.378164+00	system
3	Financial Markets	category = 'business' AND entities @> '["stock", "market", "economy"]'	high	t	2025-09-08 18:49:31.378164+00	2025-09-08 18:49:31.378164+00	system
4	Political Developments	category = 'politics' AND priority_score > 0.8	medium	t	2025-09-08 18:49:31.378164+00	2025-09-08 18:49:31.378164+00	system
\.


--
-- Data for Name: rate_limiting; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.rate_limiting (id, resource_type, resource_key, request_count, window_start, max_requests, window_duration_seconds, created_at) FROM stdin;
\.


--
-- Data for Name: rss_feeds; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.rss_feeds (id, name, url, description, tier, priority, language, country, category, subcategory, is_active, status, update_frequency, max_articles_per_update, success_rate, avg_response_time, reliability_score, last_fetched, last_success, last_error, warning_message, tags, custom_headers, filters, created_at, updated_at) FROM stdin;
1	BBC News	https://feeds.bbci.co.uk/news/rss.xml	\N	2	5	en	\N	General	\N	t	active	30	50	0.00	0	0.00	2025-09-09 15:07:54.87704+00	\N	\N	\N	[]	{}	{}	2025-09-08 18:49:50.380922+00	2025-09-09 15:07:54.87704+00
2	Reuters	https://feeds.reuters.com/reuters/topNews	\N	2	5	en	\N	General	\N	t	active	30	50	0.00	0	0.00	2025-09-09 15:07:54.87704+00	\N	\N	\N	[]	{}	{}	2025-09-08 18:49:50.380922+00	2025-09-09 15:07:54.87704+00
3	TechCrunch	https://techcrunch.com/feed/	\N	2	5	en	\N	Technology	\N	t	active	30	50	0.00	0	0.00	2025-09-09 15:07:54.87704+00	\N	\N	\N	[]	{}	{}	2025-09-08 18:49:50.380922+00	2025-09-09 15:07:54.87704+00
4	The Verge	https://www.theverge.com/rss/index.xml	\N	2	5	en	\N	Technology	\N	t	active	30	50	0.00	0	0.00	2025-09-09 15:07:54.87704+00	\N	\N	\N	[]	{}	{}	2025-09-08 18:49:50.380922+00	2025-09-09 15:07:54.87704+00
5	CNN Top Stories	https://rss.cnn.com/rss/edition.rss	CNN breaking news and top stories	1	3	en	US	News	Breaking	t	active	15	100	0.00	0	0.00	2025-09-09 15:07:54.87704+00	\N	\N	\N	[]	{}	{}	2025-09-09 00:40:36.21804+00	2025-09-09 15:07:54.87704+00
6	BBC World News	https://feeds.bbci.co.uk/news/world/rss.xml	BBC World News international coverage	1	2	en	UK	News	World	t	active	20	75	0.00	0	0.00	2025-09-09 15:07:54.87704+00	\N	\N	\N	[]	{}	{}	2025-09-09 00:40:40.730838+00	2025-09-09 15:07:54.87704+00
7	Ars Technica	https://feeds.arstechnica.com/arstechnica/index/	Technology news and analysis	2	4	en	US	Technology	Analysis	t	active	30	50	0.00	0	0.00	2025-09-09 15:07:54.87704+00	\N	\N	\N	[]	{}	{}	2025-09-09 00:40:45.024622+00	2025-09-09 15:07:54.87704+00
8	Financial Times	https://www.ft.com/rss/home	Global financial and business news	1	3	en	UK	Business	Finance	t	active	25	60	0.00	0	0.00	2025-09-09 15:07:54.87704+00	\N	\N	\N	[]	{}	{}	2025-09-09 00:40:49.416729+00	2025-09-09 15:07:54.87704+00
9	Wired	https://www.wired.com/feed/rss	Technology, science, and culture	2	5	en	US	Technology	Culture	t	active	45	40	0.00	0	0.00	2025-09-09 15:07:54.87704+00	\N	\N	\N	[]	{}	{}	2025-09-09 00:40:53.796983+00	2025-09-09 15:07:54.87704+00
10	The Guardian World	https://www.theguardian.com/world/rss	The Guardian world news coverage	1	4	en	UK	News	World	t	active	30	80	0.00	0	0.00	2025-09-09 15:07:54.87704+00	\N	\N	\N	[]	{}	{}	2025-09-09 00:40:58.427339+00	2025-09-09 15:07:54.87704+00
\.


--
-- Data for Name: search_logs; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.search_logs (id, query, results_count, search_time, user_id, "timestamp", filters, search_type) FROM stdin;
\.


--
-- Data for Name: similarity_scores; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.similarity_scores (id, article_id_1, article_id_2, similarity_score, comparison_method, compared_at) FROM stdin;
\.


--
-- Data for Name: sources; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.sources (id, name, url, category, description, language, country, is_active, status, article_count, articles_today, articles_this_week, last_article_date, success_rate, avg_response_time, reliability_score, created_at, updated_at) FROM stdin;
1	BBC News	https://www.bbc.com/news	news	British Broadcasting Corporation - International news	en	UK	t	active	0	0	0	\N	0.00	0	0.00	2025-09-08 18:49:30.523482+00	2025-09-08 18:49:30.523482+00
2	CNN	https://www.cnn.com	news	Cable News Network - Breaking news and analysis	en	US	t	active	0	0	0	\N	0.00	0	0.00	2025-09-08 18:49:30.523482+00	2025-09-08 18:49:30.523482+00
3	Reuters	https://www.reuters.com	news	International news agency	en	UK	t	active	0	0	0	\N	0.00	0	0.00	2025-09-08 18:49:30.523482+00	2025-09-08 18:49:30.523482+00
4	TechCrunch	https://techcrunch.com	technology	Technology news and startup coverage	en	US	t	active	0	0	0	\N	0.00	0	0.00	2025-09-08 18:49:30.523482+00	2025-09-08 18:49:30.523482+00
5	The Verge	https://www.theverge.com	technology	Technology, science, art, and culture	en	US	t	active	0	0	0	\N	0.00	0	0.00	2025-09-08 18:49:30.523482+00	2025-09-08 18:49:30.523482+00
6	Ars Technica	https://arstechnica.com	technology	Technology news and analysis	en	US	t	active	0	0	0	\N	0.00	0	0.00	2025-09-08 18:49:30.523482+00	2025-09-08 18:49:30.523482+00
7	Financial Times	https://www.ft.com	business	International business and financial news	en	UK	t	active	0	0	0	\N	0.00	0	0.00	2025-09-08 18:49:30.523482+00	2025-09-08 18:49:30.523482+00
8	Bloomberg	https://www.bloomberg.com	business	Business and financial news	en	US	t	active	0	0	0	\N	0.00	0	0.00	2025-09-08 18:49:30.523482+00	2025-09-08 18:49:30.523482+00
9	The Guardian	https://www.theguardian.com	news	British daily newspaper	en	UK	t	active	0	0	0	\N	0.00	0	0.00	2025-09-08 18:49:30.523482+00	2025-09-08 18:49:30.523482+00
10	NPR	https://www.npr.org	news	National Public Radio - News and analysis	en	US	t	active	0	0	0	\N	0.00	0	0.00	2025-09-08 18:49:30.523482+00	2025-09-08 18:49:30.523482+00
\.


--
-- Data for Name: storage_cleanup_policies; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.storage_cleanup_policies (id, policy_name, table_name, retention_days, cleanup_condition, is_active, last_run, last_cleaned_count, created_at) FROM stdin;
1	old_raw_articles	articles	30	processing_status = 'raw' AND created_at < NOW() - INTERVAL '30 days'	t	\N	0	2025-09-08 18:49:30.288145
2	old_failed_articles	articles	7	processing_status = 'failed' AND created_at < NOW() - INTERVAL '7 days'	t	\N	0	2025-09-08 18:49:30.288145
3	old_timeline_events	timeline_events	90	created_at < NOW() - INTERVAL '90 days'	t	\N	0	2025-09-08 18:49:30.288145
4	old_ml_tasks	ml_task_queue	14	status IN ('completed', 'failed') AND completed_at < NOW() - INTERVAL '14 days'	t	\N	0	2025-09-08 18:49:30.288145
5	old_system_logs	system_logs	30	created_at < NOW() - INTERVAL '30 days'	t	\N	0	2025-09-08 18:49:30.288145
\.


--
-- Data for Name: story_threads; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.story_threads (id, title, summary, priority_level_id, status, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: storyline_articles; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.storyline_articles (id, storyline_id, article_id, relevance_score, importance_score, created_at) FROM stdin;
\.


--
-- Data for Name: system_alerts; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.system_alerts (id, title, message, severity, category, resolved, created_at, resolved_at, resolved_by, context) FROM stdin;
\.


--
-- Data for Name: system_logs; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.system_logs (id, level, message, source, metadata, created_at) FROM stdin;
\.


--
-- Data for Name: system_metrics; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.system_metrics (id, "timestamp", cpu_percent, memory_percent, memory_used_mb, memory_total_mb, disk_percent, disk_used_gb, disk_total_gb, load_avg_1m, load_avg_5m, load_avg_15m, created_at) FROM stdin;
\.


--
-- Data for Name: system_scaling_metrics; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.system_scaling_metrics (id, "timestamp", total_articles, raw_articles, processing_articles, completed_articles, failed_articles, total_timeline_events, active_storylines, queue_size, running_tasks, database_size_bytes, avg_processing_time_seconds, success_rate, created_at) FROM stdin;
\.


--
-- Data for Name: timeline_analysis; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.timeline_analysis (id, storyline_id, analysis_date, total_events, high_importance_events, event_types, key_entities, geographic_coverage, sentiment_trend, complexity_score, narrative_coherence, ml_insights, created_at) FROM stdin;
\.


--
-- Data for Name: timeline_events; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.timeline_events (id, event_id, storyline_id, title, description, event_date, event_time, source, url, importance_score, event_type, location, entities, tags, ml_generated, confidence_score, source_article_ids, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: timeline_generation_log; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.timeline_generation_log (id, storyline_id, generation_date, events_generated, articles_analyzed, ml_model_used, generation_time_seconds, success, error_message, parameters) FROM stdin;
\.


--
-- Data for Name: timeline_milestones; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.timeline_milestones (id, storyline_id, event_id, milestone_type, significance_score, impact_description, created_at) FROM stdin;
\.


--
-- Data for Name: timeline_periods; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.timeline_periods (id, storyline_id, period, start_date, end_date, event_count, key_events, summary, ml_generated, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: user_rules; Type: TABLE DATA; Schema: public; Owner: newsapp
--

COPY public.user_rules (id, name, rule_type, rule_config, priority_level_id, is_active, created_at, updated_at) FROM stdin;
\.


--
-- Name: api_cache_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.api_cache_id_seq', 1, false);


--
-- Name: api_usage_tracking_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.api_usage_tracking_id_seq', 1, false);


--
-- Name: application_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.application_metrics_id_seq', 1, false);


--
-- Name: article_clusters_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.article_clusters_id_seq', 1, false);


--
-- Name: article_processing_batches_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.article_processing_batches_id_seq', 1, false);


--
-- Name: article_volume_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.article_volume_metrics_id_seq', 1, false);


--
-- Name: articles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.articles_id_seq', 228, true);


--
-- Name: automation_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.automation_logs_id_seq', 1, false);


--
-- Name: automation_tasks_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.automation_tasks_id_seq', 6, true);


--
-- Name: briefing_templates_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.briefing_templates_id_seq', 3, true);


--
-- Name: cluster_articles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.cluster_articles_id_seq', 1, false);


--
-- Name: collection_rules_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.collection_rules_id_seq', 1, false);


--
-- Name: content_hashes_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.content_hashes_id_seq', 1, false);


--
-- Name: content_priority_assignments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.content_priority_assignments_id_seq', 1, false);


--
-- Name: content_priority_levels_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.content_priority_levels_id_seq', 4, true);


--
-- Name: database_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.database_metrics_id_seq', 1, false);


--
-- Name: deduplication_settings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.deduplication_settings_id_seq', 1, true);


--
-- Name: deduplication_stats_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.deduplication_stats_id_seq', 1, false);


--
-- Name: entities_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.entities_id_seq', 1, false);


--
-- Name: feed_categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.feed_categories_id_seq', 10, true);


--
-- Name: feed_filtering_rules_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.feed_filtering_rules_id_seq', 1, false);


--
-- Name: feed_performance_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.feed_performance_metrics_id_seq', 1, false);


--
-- Name: generated_briefings_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.generated_briefings_id_seq', 1, false);


--
-- Name: global_filtering_config_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.global_filtering_config_id_seq', 4, true);


--
-- Name: ml_model_performance_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.ml_model_performance_id_seq', 10, true);


--
-- Name: ml_performance_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.ml_performance_metrics_id_seq', 1, false);


--
-- Name: ml_resource_usage_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.ml_resource_usage_id_seq', 1, false);


--
-- Name: ml_task_dependencies_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.ml_task_dependencies_id_seq', 1, false);


--
-- Name: ml_task_queue_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.ml_task_queue_id_seq', 1, false);


--
-- Name: performance_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.performance_metrics_id_seq', 1, false);


--
-- Name: performance_monitoring_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.performance_monitoring_id_seq', 1, false);


--
-- Name: priority_rules_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.priority_rules_id_seq', 4, true);


--
-- Name: rate_limiting_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.rate_limiting_id_seq', 1, false);


--
-- Name: rss_feeds_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.rss_feeds_id_seq', 10, true);


--
-- Name: search_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.search_logs_id_seq', 1, false);


--
-- Name: similarity_scores_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.similarity_scores_id_seq', 1, false);


--
-- Name: sources_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.sources_id_seq', 10, true);


--
-- Name: storage_cleanup_policies_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.storage_cleanup_policies_id_seq', 5, true);


--
-- Name: story_threads_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.story_threads_id_seq', 1, false);


--
-- Name: storyline_articles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.storyline_articles_id_seq', 1, false);


--
-- Name: system_alerts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.system_alerts_id_seq', 1, false);


--
-- Name: system_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.system_logs_id_seq', 1, false);


--
-- Name: system_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.system_metrics_id_seq', 1, false);


--
-- Name: system_scaling_metrics_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.system_scaling_metrics_id_seq', 1, false);


--
-- Name: timeline_analysis_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.timeline_analysis_id_seq', 1, false);


--
-- Name: timeline_events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.timeline_events_id_seq', 1, false);


--
-- Name: timeline_generation_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.timeline_generation_log_id_seq', 1, false);


--
-- Name: timeline_milestones_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.timeline_milestones_id_seq', 1, false);


--
-- Name: timeline_periods_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.timeline_periods_id_seq', 1, false);


--
-- Name: user_rules_id_seq; Type: SEQUENCE SET; Schema: public; Owner: newsapp
--

SELECT pg_catalog.setval('public.user_rules_id_seq', 1, false);


--
-- Name: api_cache api_cache_cache_key_service_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.api_cache
    ADD CONSTRAINT api_cache_cache_key_service_key UNIQUE (cache_key, service);


--
-- Name: api_cache api_cache_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.api_cache
    ADD CONSTRAINT api_cache_pkey PRIMARY KEY (id);


--
-- Name: api_usage_tracking api_usage_tracking_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.api_usage_tracking
    ADD CONSTRAINT api_usage_tracking_pkey PRIMARY KEY (id);


--
-- Name: application_metrics application_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.application_metrics
    ADD CONSTRAINT application_metrics_pkey PRIMARY KEY (id);


--
-- Name: article_clusters article_clusters_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.article_clusters
    ADD CONSTRAINT article_clusters_pkey PRIMARY KEY (id);


--
-- Name: article_processing_batches article_processing_batches_batch_id_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.article_processing_batches
    ADD CONSTRAINT article_processing_batches_batch_id_key UNIQUE (batch_id);


--
-- Name: article_processing_batches article_processing_batches_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.article_processing_batches
    ADD CONSTRAINT article_processing_batches_pkey PRIMARY KEY (id);


--
-- Name: article_volume_metrics article_volume_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.article_volume_metrics
    ADD CONSTRAINT article_volume_metrics_pkey PRIMARY KEY (id);


--
-- Name: articles articles_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_pkey PRIMARY KEY (id);


--
-- Name: automation_logs automation_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.automation_logs
    ADD CONSTRAINT automation_logs_pkey PRIMARY KEY (id);


--
-- Name: automation_tasks automation_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.automation_tasks
    ADD CONSTRAINT automation_tasks_pkey PRIMARY KEY (id);


--
-- Name: briefing_templates briefing_templates_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.briefing_templates
    ADD CONSTRAINT briefing_templates_pkey PRIMARY KEY (id);


--
-- Name: cluster_articles cluster_articles_cluster_id_article_id_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.cluster_articles
    ADD CONSTRAINT cluster_articles_cluster_id_article_id_key UNIQUE (cluster_id, article_id);


--
-- Name: cluster_articles cluster_articles_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.cluster_articles
    ADD CONSTRAINT cluster_articles_pkey PRIMARY KEY (id);


--
-- Name: collection_rules collection_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.collection_rules
    ADD CONSTRAINT collection_rules_pkey PRIMARY KEY (id);


--
-- Name: content_hashes content_hashes_content_hash_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_hashes
    ADD CONSTRAINT content_hashes_content_hash_key UNIQUE (content_hash);


--
-- Name: content_hashes content_hashes_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_hashes
    ADD CONSTRAINT content_hashes_pkey PRIMARY KEY (id);


--
-- Name: content_priority_assignments content_priority_assignments_article_id_thread_id_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_priority_assignments
    ADD CONSTRAINT content_priority_assignments_article_id_thread_id_key UNIQUE (article_id, thread_id);


--
-- Name: content_priority_assignments content_priority_assignments_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_priority_assignments
    ADD CONSTRAINT content_priority_assignments_pkey PRIMARY KEY (id);


--
-- Name: content_priority_levels content_priority_levels_name_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_priority_levels
    ADD CONSTRAINT content_priority_levels_name_key UNIQUE (name);


--
-- Name: content_priority_levels content_priority_levels_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_priority_levels
    ADD CONSTRAINT content_priority_levels_pkey PRIMARY KEY (id);


--
-- Name: database_metrics database_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.database_metrics
    ADD CONSTRAINT database_metrics_pkey PRIMARY KEY (id);


--
-- Name: deduplication_settings deduplication_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.deduplication_settings
    ADD CONSTRAINT deduplication_settings_pkey PRIMARY KEY (id);


--
-- Name: deduplication_stats deduplication_stats_date_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.deduplication_stats
    ADD CONSTRAINT deduplication_stats_date_key UNIQUE (date);


--
-- Name: deduplication_stats deduplication_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.deduplication_stats
    ADD CONSTRAINT deduplication_stats_pkey PRIMARY KEY (id);


--
-- Name: entities entities_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.entities
    ADD CONSTRAINT entities_pkey PRIMARY KEY (id);


--
-- Name: feed_categories feed_categories_name_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.feed_categories
    ADD CONSTRAINT feed_categories_name_key UNIQUE (name);


--
-- Name: feed_categories feed_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.feed_categories
    ADD CONSTRAINT feed_categories_pkey PRIMARY KEY (id);


--
-- Name: feed_filtering_rules feed_filtering_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.feed_filtering_rules
    ADD CONSTRAINT feed_filtering_rules_pkey PRIMARY KEY (id);


--
-- Name: feed_performance_metrics feed_performance_metrics_feed_id_date_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.feed_performance_metrics
    ADD CONSTRAINT feed_performance_metrics_feed_id_date_key UNIQUE (feed_id, date);


--
-- Name: feed_performance_metrics feed_performance_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.feed_performance_metrics
    ADD CONSTRAINT feed_performance_metrics_pkey PRIMARY KEY (id);


--
-- Name: generated_briefings generated_briefings_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.generated_briefings
    ADD CONSTRAINT generated_briefings_pkey PRIMARY KEY (id);


--
-- Name: global_filtering_config global_filtering_config_config_name_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.global_filtering_config
    ADD CONSTRAINT global_filtering_config_config_name_key UNIQUE (config_name);


--
-- Name: global_filtering_config global_filtering_config_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.global_filtering_config
    ADD CONSTRAINT global_filtering_config_pkey PRIMARY KEY (id);


--
-- Name: ml_model_performance ml_model_performance_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_model_performance
    ADD CONSTRAINT ml_model_performance_pkey PRIMARY KEY (id);


--
-- Name: ml_performance_metrics ml_performance_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_performance_metrics
    ADD CONSTRAINT ml_performance_metrics_pkey PRIMARY KEY (id);


--
-- Name: ml_resource_usage ml_resource_usage_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_resource_usage
    ADD CONSTRAINT ml_resource_usage_pkey PRIMARY KEY (id);


--
-- Name: ml_task_dependencies ml_task_dependencies_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_task_dependencies
    ADD CONSTRAINT ml_task_dependencies_pkey PRIMARY KEY (id);


--
-- Name: ml_task_queue ml_task_queue_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_task_queue
    ADD CONSTRAINT ml_task_queue_pkey PRIMARY KEY (id);


--
-- Name: ml_task_queue ml_task_queue_task_id_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_task_queue
    ADD CONSTRAINT ml_task_queue_task_id_key UNIQUE (task_id);


--
-- Name: performance_metrics performance_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.performance_metrics
    ADD CONSTRAINT performance_metrics_pkey PRIMARY KEY (id);


--
-- Name: performance_monitoring performance_monitoring_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.performance_monitoring
    ADD CONSTRAINT performance_monitoring_pkey PRIMARY KEY (id);


--
-- Name: priority_rules priority_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.priority_rules
    ADD CONSTRAINT priority_rules_pkey PRIMARY KEY (id);


--
-- Name: rate_limiting rate_limiting_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.rate_limiting
    ADD CONSTRAINT rate_limiting_pkey PRIMARY KEY (id);


--
-- Name: rate_limiting rate_limiting_resource_type_resource_key_window_start_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.rate_limiting
    ADD CONSTRAINT rate_limiting_resource_type_resource_key_window_start_key UNIQUE (resource_type, resource_key, window_start);


--
-- Name: rss_feeds rss_feeds_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.rss_feeds
    ADD CONSTRAINT rss_feeds_pkey PRIMARY KEY (id);


--
-- Name: rss_feeds rss_feeds_url_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.rss_feeds
    ADD CONSTRAINT rss_feeds_url_key UNIQUE (url);


--
-- Name: search_logs search_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.search_logs
    ADD CONSTRAINT search_logs_pkey PRIMARY KEY (id);


--
-- Name: similarity_scores similarity_scores_article_id_1_article_id_2_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.similarity_scores
    ADD CONSTRAINT similarity_scores_article_id_1_article_id_2_key UNIQUE (article_id_1, article_id_2);


--
-- Name: similarity_scores similarity_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.similarity_scores
    ADD CONSTRAINT similarity_scores_pkey PRIMARY KEY (id);


--
-- Name: sources sources_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (id);


--
-- Name: sources sources_url_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_url_key UNIQUE (url);


--
-- Name: storage_cleanup_policies storage_cleanup_policies_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.storage_cleanup_policies
    ADD CONSTRAINT storage_cleanup_policies_pkey PRIMARY KEY (id);


--
-- Name: storage_cleanup_policies storage_cleanup_policies_policy_name_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.storage_cleanup_policies
    ADD CONSTRAINT storage_cleanup_policies_policy_name_key UNIQUE (policy_name);


--
-- Name: story_threads story_threads_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.story_threads
    ADD CONSTRAINT story_threads_pkey PRIMARY KEY (id);


--
-- Name: storyline_articles storyline_articles_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.storyline_articles
    ADD CONSTRAINT storyline_articles_pkey PRIMARY KEY (id);


--
-- Name: storyline_articles storyline_articles_storyline_id_article_id_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.storyline_articles
    ADD CONSTRAINT storyline_articles_storyline_id_article_id_key UNIQUE (storyline_id, article_id);


--
-- Name: system_alerts system_alerts_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.system_alerts
    ADD CONSTRAINT system_alerts_pkey PRIMARY KEY (id);


--
-- Name: system_logs system_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.system_logs
    ADD CONSTRAINT system_logs_pkey PRIMARY KEY (id);


--
-- Name: system_metrics system_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.system_metrics
    ADD CONSTRAINT system_metrics_pkey PRIMARY KEY (id);


--
-- Name: system_scaling_metrics system_scaling_metrics_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.system_scaling_metrics
    ADD CONSTRAINT system_scaling_metrics_pkey PRIMARY KEY (id);


--
-- Name: timeline_analysis timeline_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_analysis
    ADD CONSTRAINT timeline_analysis_pkey PRIMARY KEY (id);


--
-- Name: timeline_analysis timeline_analysis_storyline_id_analysis_date_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_analysis
    ADD CONSTRAINT timeline_analysis_storyline_id_analysis_date_key UNIQUE (storyline_id, analysis_date);


--
-- Name: timeline_events timeline_events_event_id_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_events
    ADD CONSTRAINT timeline_events_event_id_key UNIQUE (event_id);


--
-- Name: timeline_events timeline_events_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_events
    ADD CONSTRAINT timeline_events_pkey PRIMARY KEY (id);


--
-- Name: timeline_generation_log timeline_generation_log_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_generation_log
    ADD CONSTRAINT timeline_generation_log_pkey PRIMARY KEY (id);


--
-- Name: timeline_milestones timeline_milestones_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_milestones
    ADD CONSTRAINT timeline_milestones_pkey PRIMARY KEY (id);


--
-- Name: timeline_periods timeline_periods_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_periods
    ADD CONSTRAINT timeline_periods_pkey PRIMARY KEY (id);


--
-- Name: timeline_periods timeline_periods_storyline_id_period_key; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_periods
    ADD CONSTRAINT timeline_periods_storyline_id_period_key UNIQUE (storyline_id, period);


--
-- Name: user_rules user_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.user_rules
    ADD CONSTRAINT user_rules_pkey PRIMARY KEY (id);


--
-- Name: idx_api_cache_created_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_api_cache_created_at ON public.api_cache USING btree (created_at DESC);


--
-- Name: idx_api_cache_service_created; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_api_cache_service_created ON public.api_cache USING btree (service, created_at DESC);


--
-- Name: idx_api_cache_service_key; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_api_cache_service_key ON public.api_cache USING btree (service, cache_key);


--
-- Name: idx_api_usage_tracking_created_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_api_usage_tracking_created_at ON public.api_usage_tracking USING btree (created_at DESC);


--
-- Name: idx_api_usage_tracking_service; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_api_usage_tracking_service ON public.api_usage_tracking USING btree (service);


--
-- Name: idx_api_usage_tracking_success; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_api_usage_tracking_success ON public.api_usage_tracking USING btree (success);


--
-- Name: idx_application_metrics_timestamp; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_application_metrics_timestamp ON public.application_metrics USING btree ("timestamp");


--
-- Name: idx_article_clusters_created_date; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_article_clusters_created_date ON public.article_clusters USING btree (created_date);


--
-- Name: idx_article_clusters_main_article; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_article_clusters_main_article ON public.article_clusters USING btree (main_article_id);


--
-- Name: idx_article_clusters_type; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_article_clusters_type ON public.article_clusters USING btree (cluster_type);


--
-- Name: idx_article_processing_batches_created_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_article_processing_batches_created_at ON public.article_processing_batches USING btree (created_at DESC);


--
-- Name: idx_article_processing_batches_status; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_article_processing_batches_status ON public.article_processing_batches USING btree (status);


--
-- Name: idx_article_volume_metrics_timestamp; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_article_volume_metrics_timestamp ON public.article_volume_metrics USING btree ("timestamp");


--
-- Name: idx_articles_category; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_articles_category ON public.articles USING btree (category);


--
-- Name: idx_articles_content_hash; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_articles_content_hash ON public.articles USING btree (content_hash);


--
-- Name: idx_articles_created_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_articles_created_at ON public.articles USING btree (created_at);


--
-- Name: idx_articles_processing_status; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_articles_processing_status ON public.articles USING btree (processing_status);


--
-- Name: idx_articles_published_date; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_articles_published_date ON public.articles USING btree (published_at);


--
-- Name: idx_articles_source; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_articles_source ON public.articles USING btree (source);


--
-- Name: idx_articles_title; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_articles_title ON public.articles USING btree (title);


--
-- Name: idx_automation_logs_operation; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_automation_logs_operation ON public.automation_logs USING btree (operation);


--
-- Name: idx_automation_logs_status; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_automation_logs_status ON public.automation_logs USING btree (status);


--
-- Name: idx_automation_logs_timestamp; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_automation_logs_timestamp ON public.automation_logs USING btree ("timestamp");


--
-- Name: idx_automation_tasks_enabled; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_automation_tasks_enabled ON public.automation_tasks USING btree (enabled);


--
-- Name: idx_automation_tasks_next_run; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_automation_tasks_next_run ON public.automation_tasks USING btree (next_run);


--
-- Name: idx_automation_tasks_status; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_automation_tasks_status ON public.automation_tasks USING btree (status);


--
-- Name: idx_briefing_templates_enabled; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_briefing_templates_enabled ON public.briefing_templates USING btree (enabled);


--
-- Name: idx_briefing_templates_schedule; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_briefing_templates_schedule ON public.briefing_templates USING btree (schedule);


--
-- Name: idx_content_priority_assignments_article; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_content_priority_assignments_article ON public.content_priority_assignments USING btree (article_id);


--
-- Name: idx_content_priority_assignments_thread; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_content_priority_assignments_thread ON public.content_priority_assignments USING btree (thread_id);


--
-- Name: idx_database_metrics_timestamp; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_database_metrics_timestamp ON public.database_metrics USING btree ("timestamp");


--
-- Name: idx_deduplication_stats_date; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_deduplication_stats_date ON public.deduplication_stats USING btree (date);


--
-- Name: idx_entities_frequency; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_entities_frequency ON public.entities USING btree (frequency);


--
-- Name: idx_entities_text; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_entities_text ON public.entities USING btree (text);


--
-- Name: idx_entities_type; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_entities_type ON public.entities USING btree (type);


--
-- Name: idx_feed_filtering_rules_active; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_feed_filtering_rules_active ON public.feed_filtering_rules USING btree (is_active);


--
-- Name: idx_feed_filtering_rules_feed_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_feed_filtering_rules_feed_id ON public.feed_filtering_rules USING btree (feed_id);


--
-- Name: idx_feed_filtering_rules_type; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_feed_filtering_rules_type ON public.feed_filtering_rules USING btree (rule_type);


--
-- Name: idx_feed_performance_metrics_date; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_feed_performance_metrics_date ON public.feed_performance_metrics USING btree (date);


--
-- Name: idx_feed_performance_metrics_feed_date; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_feed_performance_metrics_feed_date ON public.feed_performance_metrics USING btree (feed_id, date);


--
-- Name: idx_generated_briefings_generated_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_generated_briefings_generated_at ON public.generated_briefings USING btree (generated_at);


--
-- Name: idx_generated_briefings_status; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_generated_briefings_status ON public.generated_briefings USING btree (status);


--
-- Name: idx_generated_briefings_template_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_generated_briefings_template_id ON public.generated_briefings USING btree (template_id);


--
-- Name: idx_ml_performance_measured_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_performance_measured_at ON public.ml_model_performance USING btree (measured_at);


--
-- Name: idx_ml_performance_metric; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_performance_metric ON public.ml_model_performance USING btree (metric_name);


--
-- Name: idx_ml_performance_metrics_task_type; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_performance_metrics_task_type ON public.ml_performance_metrics USING btree (task_type);


--
-- Name: idx_ml_performance_model; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_performance_model ON public.ml_model_performance USING btree (model_name);


--
-- Name: idx_ml_resource_usage_timestamp; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_resource_usage_timestamp ON public.ml_resource_usage USING btree ("timestamp");


--
-- Name: idx_ml_task_dependencies_depends_on; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_task_dependencies_depends_on ON public.ml_task_dependencies USING btree (depends_on_task_id);


--
-- Name: idx_ml_task_dependencies_task_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_task_dependencies_task_id ON public.ml_task_dependencies USING btree (task_id);


--
-- Name: idx_ml_task_queue_article_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_task_queue_article_id ON public.ml_task_queue USING btree (article_id);


--
-- Name: idx_ml_task_queue_created_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_task_queue_created_at ON public.ml_task_queue USING btree (created_at);


--
-- Name: idx_ml_task_queue_priority; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_task_queue_priority ON public.ml_task_queue USING btree (priority DESC);


--
-- Name: idx_ml_task_queue_status; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_task_queue_status ON public.ml_task_queue USING btree (status);


--
-- Name: idx_ml_task_queue_storyline_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_task_queue_storyline_id ON public.ml_task_queue USING btree (storyline_id);


--
-- Name: idx_ml_task_queue_task_type; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_ml_task_queue_task_type ON public.ml_task_queue USING btree (task_type);


--
-- Name: idx_performance_metrics_name; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_performance_metrics_name ON public.performance_metrics USING btree (metric_name);


--
-- Name: idx_performance_metrics_timestamp; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_performance_metrics_timestamp ON public.performance_metrics USING btree ("timestamp");


--
-- Name: idx_performance_monitoring_operation; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_performance_monitoring_operation ON public.performance_monitoring USING btree (operation_type, "timestamp" DESC);


--
-- Name: idx_priority_rules_enabled; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_priority_rules_enabled ON public.priority_rules USING btree (enabled);


--
-- Name: idx_priority_rules_priority; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_priority_rules_priority ON public.priority_rules USING btree (priority);


--
-- Name: idx_rate_limiting_resource; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rate_limiting_resource ON public.rate_limiting USING btree (resource_type, resource_key, window_start);


--
-- Name: idx_rss_feeds_category; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rss_feeds_category ON public.rss_feeds USING btree (category);


--
-- Name: idx_rss_feeds_country; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rss_feeds_country ON public.rss_feeds USING btree (country);


--
-- Name: idx_rss_feeds_is_active; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rss_feeds_is_active ON public.rss_feeds USING btree (is_active);


--
-- Name: idx_rss_feeds_language; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rss_feeds_language ON public.rss_feeds USING btree (language);


--
-- Name: idx_rss_feeds_last_fetched; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rss_feeds_last_fetched ON public.rss_feeds USING btree (last_fetched);


--
-- Name: idx_rss_feeds_priority; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rss_feeds_priority ON public.rss_feeds USING btree (priority);


--
-- Name: idx_rss_feeds_reliability_score; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rss_feeds_reliability_score ON public.rss_feeds USING btree (reliability_score);


--
-- Name: idx_rss_feeds_status; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rss_feeds_status ON public.rss_feeds USING btree (status);


--
-- Name: idx_rss_feeds_tier; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rss_feeds_tier ON public.rss_feeds USING btree (tier);


--
-- Name: idx_rss_feeds_url; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_rss_feeds_url ON public.rss_feeds USING btree (url);


--
-- Name: idx_search_logs_query; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_search_logs_query ON public.search_logs USING btree (query);


--
-- Name: idx_search_logs_timestamp; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_search_logs_timestamp ON public.search_logs USING btree ("timestamp");


--
-- Name: idx_search_logs_user_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_search_logs_user_id ON public.search_logs USING btree (user_id);


--
-- Name: idx_sources_article_count; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_sources_article_count ON public.sources USING btree (article_count);


--
-- Name: idx_sources_category; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_sources_category ON public.sources USING btree (category);


--
-- Name: idx_sources_created_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_sources_created_at ON public.sources USING btree (created_at);


--
-- Name: idx_sources_is_active; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_sources_is_active ON public.sources USING btree (is_active);


--
-- Name: idx_sources_reliability_score; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_sources_reliability_score ON public.sources USING btree (reliability_score);


--
-- Name: idx_sources_status; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_sources_status ON public.sources USING btree (status);


--
-- Name: idx_sources_updated_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_sources_updated_at ON public.sources USING btree (updated_at);


--
-- Name: idx_story_threads_priority; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_story_threads_priority ON public.story_threads USING btree (priority_level_id);


--
-- Name: idx_story_threads_status; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_story_threads_status ON public.story_threads USING btree (status);


--
-- Name: idx_storyline_articles_article_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_storyline_articles_article_id ON public.storyline_articles USING btree (article_id);


--
-- Name: idx_storyline_articles_storyline_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_storyline_articles_storyline_id ON public.storyline_articles USING btree (storyline_id);


--
-- Name: idx_system_alerts_created_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_system_alerts_created_at ON public.system_alerts USING btree (created_at);


--
-- Name: idx_system_alerts_resolved; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_system_alerts_resolved ON public.system_alerts USING btree (resolved);


--
-- Name: idx_system_alerts_severity; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_system_alerts_severity ON public.system_alerts USING btree (severity);


--
-- Name: idx_system_logs_created_at; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_system_logs_created_at ON public.system_logs USING btree (created_at);


--
-- Name: idx_system_logs_level; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_system_logs_level ON public.system_logs USING btree (level);


--
-- Name: idx_system_metrics_timestamp; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_system_metrics_timestamp ON public.system_metrics USING btree ("timestamp");


--
-- Name: idx_system_scaling_metrics_timestamp; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_system_scaling_metrics_timestamp ON public.system_scaling_metrics USING btree ("timestamp" DESC);


--
-- Name: idx_timeline_analysis_date; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_analysis_date ON public.timeline_analysis USING btree (analysis_date);


--
-- Name: idx_timeline_analysis_storyline_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_analysis_storyline_id ON public.timeline_analysis USING btree (storyline_id);


--
-- Name: idx_timeline_events_event_date; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_events_event_date ON public.timeline_events USING btree (event_date);


--
-- Name: idx_timeline_events_event_type; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_events_event_type ON public.timeline_events USING btree (event_type);


--
-- Name: idx_timeline_events_importance_score; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_events_importance_score ON public.timeline_events USING btree (importance_score);


--
-- Name: idx_timeline_events_ml_generated; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_events_ml_generated ON public.timeline_events USING btree (ml_generated);


--
-- Name: idx_timeline_events_storyline_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_events_storyline_id ON public.timeline_events USING btree (storyline_id);


--
-- Name: idx_timeline_generation_log_date; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_generation_log_date ON public.timeline_generation_log USING btree (generation_date);


--
-- Name: idx_timeline_generation_log_storyline_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_generation_log_storyline_id ON public.timeline_generation_log USING btree (storyline_id);


--
-- Name: idx_timeline_milestones_milestone_type; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_milestones_milestone_type ON public.timeline_milestones USING btree (milestone_type);


--
-- Name: idx_timeline_milestones_storyline_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_milestones_storyline_id ON public.timeline_milestones USING btree (storyline_id);


--
-- Name: idx_timeline_periods_period; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_periods_period ON public.timeline_periods USING btree (period);


--
-- Name: idx_timeline_periods_storyline_id; Type: INDEX; Schema: public; Owner: newsapp
--

CREATE INDEX idx_timeline_periods_storyline_id ON public.timeline_periods USING btree (storyline_id);


--
-- Name: automation_tasks update_automation_tasks_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_automation_tasks_updated_at BEFORE UPDATE ON public.automation_tasks FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: briefing_templates update_briefing_templates_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_briefing_templates_updated_at BEFORE UPDATE ON public.briefing_templates FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: deduplication_settings update_deduplication_settings_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_deduplication_settings_updated_at BEFORE UPDATE ON public.deduplication_settings FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: feed_filtering_rules update_feed_filtering_rules_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_feed_filtering_rules_updated_at BEFORE UPDATE ON public.feed_filtering_rules FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: global_filtering_config update_global_filtering_config_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_global_filtering_config_updated_at BEFORE UPDATE ON public.global_filtering_config FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: ml_task_queue update_ml_task_queue_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_ml_task_queue_updated_at BEFORE UPDATE ON public.ml_task_queue FOR EACH ROW EXECUTE FUNCTION public.update_ml_task_queue_updated_at();


--
-- Name: priority_rules update_priority_rules_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_priority_rules_updated_at BEFORE UPDATE ON public.priority_rules FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: rss_feeds update_rss_feeds_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_rss_feeds_updated_at BEFORE UPDATE ON public.rss_feeds FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: sources update_sources_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON public.sources FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: timeline_events update_timeline_events_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_timeline_events_updated_at BEFORE UPDATE ON public.timeline_events FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: timeline_periods update_timeline_periods_updated_at; Type: TRIGGER; Schema: public; Owner: newsapp
--

CREATE TRIGGER update_timeline_periods_updated_at BEFORE UPDATE ON public.timeline_periods FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- Name: article_clusters article_clusters_main_article_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.article_clusters
    ADD CONSTRAINT article_clusters_main_article_id_fkey FOREIGN KEY (main_article_id) REFERENCES public.articles(id) ON DELETE CASCADE;


--
-- Name: articles articles_feed_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.articles
    ADD CONSTRAINT articles_feed_id_fkey FOREIGN KEY (feed_id) REFERENCES public.rss_feeds(id);


--
-- Name: cluster_articles cluster_articles_article_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.cluster_articles
    ADD CONSTRAINT cluster_articles_article_id_fkey FOREIGN KEY (article_id) REFERENCES public.articles(id) ON DELETE CASCADE;


--
-- Name: cluster_articles cluster_articles_cluster_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.cluster_articles
    ADD CONSTRAINT cluster_articles_cluster_id_fkey FOREIGN KEY (cluster_id) REFERENCES public.article_clusters(id) ON DELETE CASCADE;


--
-- Name: collection_rules collection_rules_feed_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.collection_rules
    ADD CONSTRAINT collection_rules_feed_id_fkey FOREIGN KEY (feed_id) REFERENCES public.rss_feeds(id) ON DELETE CASCADE;


--
-- Name: content_hashes content_hashes_article_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_hashes
    ADD CONSTRAINT content_hashes_article_id_fkey FOREIGN KEY (article_id) REFERENCES public.articles(id) ON DELETE CASCADE;


--
-- Name: content_priority_assignments content_priority_assignments_article_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_priority_assignments
    ADD CONSTRAINT content_priority_assignments_article_id_fkey FOREIGN KEY (article_id) REFERENCES public.articles(id) ON DELETE CASCADE;


--
-- Name: content_priority_assignments content_priority_assignments_priority_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_priority_assignments
    ADD CONSTRAINT content_priority_assignments_priority_level_id_fkey FOREIGN KEY (priority_level_id) REFERENCES public.content_priority_levels(id);


--
-- Name: content_priority_assignments content_priority_assignments_thread_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.content_priority_assignments
    ADD CONSTRAINT content_priority_assignments_thread_id_fkey FOREIGN KEY (thread_id) REFERENCES public.story_threads(id) ON DELETE CASCADE;


--
-- Name: feed_filtering_rules feed_filtering_rules_feed_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.feed_filtering_rules
    ADD CONSTRAINT feed_filtering_rules_feed_id_fkey FOREIGN KEY (feed_id) REFERENCES public.rss_feeds(id) ON DELETE CASCADE;


--
-- Name: feed_performance_metrics feed_performance_metrics_feed_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.feed_performance_metrics
    ADD CONSTRAINT feed_performance_metrics_feed_id_fkey FOREIGN KEY (feed_id) REFERENCES public.rss_feeds(id) ON DELETE CASCADE;


--
-- Name: generated_briefings generated_briefings_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.generated_briefings
    ADD CONSTRAINT generated_briefings_template_id_fkey FOREIGN KEY (template_id) REFERENCES public.briefing_templates(id) ON DELETE SET NULL;


--
-- Name: ml_task_dependencies ml_task_dependencies_depends_on_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_task_dependencies
    ADD CONSTRAINT ml_task_dependencies_depends_on_task_id_fkey FOREIGN KEY (depends_on_task_id) REFERENCES public.ml_task_queue(task_id) ON DELETE CASCADE;


--
-- Name: ml_task_dependencies ml_task_dependencies_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.ml_task_dependencies
    ADD CONSTRAINT ml_task_dependencies_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.ml_task_queue(task_id) ON DELETE CASCADE;


--
-- Name: similarity_scores similarity_scores_article_id_1_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.similarity_scores
    ADD CONSTRAINT similarity_scores_article_id_1_fkey FOREIGN KEY (article_id_1) REFERENCES public.articles(id) ON DELETE CASCADE;


--
-- Name: similarity_scores similarity_scores_article_id_2_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.similarity_scores
    ADD CONSTRAINT similarity_scores_article_id_2_fkey FOREIGN KEY (article_id_2) REFERENCES public.articles(id) ON DELETE CASCADE;


--
-- Name: story_threads story_threads_priority_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.story_threads
    ADD CONSTRAINT story_threads_priority_level_id_fkey FOREIGN KEY (priority_level_id) REFERENCES public.content_priority_levels(id);


--
-- Name: storyline_articles storyline_articles_article_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.storyline_articles
    ADD CONSTRAINT storyline_articles_article_id_fkey FOREIGN KEY (article_id) REFERENCES public.articles(id) ON DELETE CASCADE;


--
-- Name: storyline_articles storyline_articles_storyline_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.storyline_articles
    ADD CONSTRAINT storyline_articles_storyline_id_fkey FOREIGN KEY (storyline_id) REFERENCES public.story_threads(id) ON DELETE CASCADE;


--
-- Name: timeline_milestones timeline_milestones_event_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.timeline_milestones
    ADD CONSTRAINT timeline_milestones_event_id_fkey FOREIGN KEY (event_id) REFERENCES public.timeline_events(event_id) ON DELETE CASCADE;


--
-- Name: user_rules user_rules_priority_level_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: newsapp
--

ALTER TABLE ONLY public.user_rules
    ADD CONSTRAINT user_rules_priority_level_id_fkey FOREIGN KEY (priority_level_id) REFERENCES public.content_priority_levels(id);


--
-- PostgreSQL database dump complete
--

\unrestrict IwsbMNY9dvIczavK6ffQc4J45Wv1r6kNVQJKwVqjgZznHJV5b0eCD4CL1m9CW3j

