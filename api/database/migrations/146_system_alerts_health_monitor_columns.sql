-- Migration 146: Add columns required by health_monitor_orchestrator (and other alert writers).
-- system_alerts may have been created by migration 011 (title, message, severity, category, resolved, ...)
-- without alert_type, description, updated_at, is_active. This adds them when missing.

DO $$
BEGIN
    -- alert_type (required by health check alerts)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'system_alerts' AND column_name = 'alert_type') THEN
        ALTER TABLE system_alerts ADD COLUMN alert_type VARCHAR(50) DEFAULT 'system';
        RAISE NOTICE 'Added system_alerts.alert_type';
    END IF;

    -- description (health monitor uses it; 011 has "message" - add description for compatibility)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'system_alerts' AND column_name = 'description') THEN
        ALTER TABLE system_alerts ADD COLUMN description TEXT;
        UPDATE system_alerts SET description = message WHERE description IS NULL AND message IS NOT NULL;
        RAISE NOTICE 'Added system_alerts.description';
    END IF;

    -- updated_at
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'system_alerts' AND column_name = 'updated_at') THEN
        ALTER TABLE system_alerts ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP;
        RAISE NOTICE 'Added system_alerts.updated_at';
    END IF;

    -- is_active (health monitor inserts with is_active = true)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'system_alerts' AND column_name = 'is_active') THEN
        ALTER TABLE system_alerts ADD COLUMN is_active BOOLEAN DEFAULT true;
        UPDATE system_alerts SET is_active = NOT COALESCE(resolved, false) WHERE is_active IS NULL;
        RAISE NOTICE 'Added system_alerts.is_active';
    END IF;

    -- alert_data (used by health monitor; may already exist from 102)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'system_alerts' AND column_name = 'alert_data') THEN
        ALTER TABLE system_alerts ADD COLUMN alert_data JSONB DEFAULT '{}';
        RAISE NOTICE 'Added system_alerts.alert_data';
    END IF;
END $$;
