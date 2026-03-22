-- Migration: ADMS Attendance Punches Schema (Sprint S024)
-- Date: 2026-03-03
-- Purpose: Biometric attendance punch data from ADMS → Supabase sync pipeline
-- Fixes applied: FIX-1,4,12,18,20,21

-- ============================================================================
-- Table: attendance_punches (core fact table — one row per punch event)
-- ============================================================================

CREATE TABLE IF NOT EXISTS attendance_punches (
    id BIGSERIAL PRIMARY KEY,
    pin VARCHAR(10) NOT NULL,            -- Bio ID (e.g., '9000318')
    event_time TIMESTAMPTZ NOT NULL,     -- Punch timestamp (PHT)
    device_sn VARCHAR(20) NOT NULL,      -- Device serial number
    store_name VARCHAR(100) NOT NULL,    -- Resolved store name from device_mapping
    status_code INT DEFAULT 0,           -- ZKTeco status (0=IN, 1=OUT) — cast from source VARCHAR [FIX-1]
    verify_code INT DEFAULT 0,           -- Verification method (1=FP, 15=face) — cast from source VARCHAR [FIX-1]
    employee_name VARCHAR(150),          -- Matched from Employee Master (NULL if unknown Bio ID)
    employee_id VARCHAR(20),             -- Frappe Employee ID (NULL if unknown)
    designation VARCHAR(100),            -- From Employee Master
    department VARCHAR(50),              -- From Employee Master
    home_store VARCHAR(100),             -- Employee's assigned store (vs where they punched)
    is_known_employee BOOLEAN DEFAULT FALSE,  -- [FIX-4] FALSE = ghost puncher / unknown Bio ID
    is_roving BOOLEAN DEFAULT FALSE,     -- [FIX-4] TRUE = authorized multi-store employee
    synced_at TIMESTAMPTZ DEFAULT NOW(), -- When this row was synced to Supabase
    adms_id TEXT,                         -- Original UUID from ADMS for traceability

    -- [FIX-20] PostgREST upsert uses this constraint via ?on_conflict=pin,event_time,device_sn
    CONSTRAINT uq_punch UNIQUE (pin, event_time, device_sn)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_punches_pin_time ON attendance_punches (pin, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_punches_device_time ON attendance_punches (device_sn, event_time DESC);
CREATE INDEX IF NOT EXISTS idx_punches_store_time ON attendance_punches (store_name, event_time DESC);
-- Note: TIMESTAMPTZ::date is STABLE not IMMUTABLE, can't use as expression index.
-- A plain BTREE on event_time efficiently covers date-range queries via range scans.
CREATE INDEX IF NOT EXISTS idx_punches_event_time ON attendance_punches (event_time DESC);
CREATE INDEX IF NOT EXISTS idx_punches_unknown ON attendance_punches (is_known_employee) WHERE NOT is_known_employee;

-- ============================================================================
-- Table: adms_sync_progress (checkpoint table for resumable incremental sync)
-- ============================================================================

CREATE TABLE IF NOT EXISTS adms_sync_progress (
    id SERIAL PRIMARY KEY,
    sync_type VARCHAR(20) NOT NULL,        -- 'incremental' or 'backfill'
    device_sn VARCHAR(20),                 -- NULL for global, device SN for per-device
    last_received_at TIMESTAMPTZ,          -- High-water mark for incremental sync
    last_event_time TIMESTAMPTZ,           -- Latest event_time synced
    rows_synced INT DEFAULT 0,             -- Count of rows in this sync run
    status VARCHAR(20) NOT NULL,           -- 'in_progress', 'complete', 'error'
    error_message TEXT,                    -- Error details if status='error'
    started_at TIMESTAMPTZ DEFAULT NOW(),  -- When sync run started
    completed_at TIMESTAMPTZ,             -- When sync run finished

    -- [FIX-21] NULLS NOT DISTINCT prevents multiple NULL device_sn rows per sync_type
    CONSTRAINT uq_sync_device UNIQUE NULLS NOT DISTINCT (sync_type, device_sn)
);

-- ============================================================================
-- Table: employee_directory (employee master for attendance enrichment)
-- ============================================================================

CREATE TABLE IF NOT EXISTS employee_directory (
    id SERIAL PRIMARY KEY,
    bio_id VARCHAR(10) NOT NULL UNIQUE,
    employee_name VARCHAR(150) NOT NULL,
    employee_id VARCHAR(20),
    designation VARCHAR(100),
    department VARCHAR(50),
    store_location VARCHAR(100),
    status VARCHAR(20) DEFAULT 'Active',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emp_dir_bio_id ON employee_directory (bio_id);

-- ============================================================================
-- Row-Level Security
-- ============================================================================

ALTER TABLE attendance_punches ENABLE ROW LEVEL SECURITY;
ALTER TABLE adms_sync_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE employee_directory ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (sync script uses service key)
CREATE POLICY "Service role full access on punches"
    ON attendance_punches FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on sync_progress"
    ON adms_sync_progress FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access on employee_directory"
    ON employee_directory FOR ALL
    USING (auth.role() = 'service_role');

-- Authenticated can read (for dashboards)
CREATE POLICY "Authenticated read access on punches"
    ON attendance_punches FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated read access on sync_progress"
    ON adms_sync_progress FOR SELECT
    USING (auth.role() = 'authenticated');

CREATE POLICY "Authenticated read access on employee_directory"
    ON employee_directory FOR SELECT
    USING (auth.role() = 'authenticated');

-- ============================================================================
-- View: v_daily_time_record (one row per employee per day)
-- [FIX-13] Groups by (pin, date) only — not by store
-- [FIX-14] No late/undertime/OT — deferred to Phase 5
-- ============================================================================

CREATE OR REPLACE VIEW v_daily_time_record AS
WITH daily_punches AS (
    SELECT
        pin,
        MAX(employee_name) AS employee_name,
        MAX(employee_id) AS employee_id,
        MAX(designation) AS designation,
        MAX(department) AS department,
        MAX(home_store) AS home_store,
        -- Show where they first punched as primary location
        (ARRAY_AGG(store_name ORDER BY event_time ASC))[1] AS punch_store,
        -- If they punched at multiple stores, list them
        CASE WHEN COUNT(DISTINCT store_name) > 1
             THEN ARRAY_TO_STRING(ARRAY_AGG(DISTINCT store_name ORDER BY store_name), ', ')
             ELSE NULL
        END AS other_stores,
        event_time::date AS work_date,
        MIN(event_time) AS time_in,
        MAX(event_time) AS time_out,
        COUNT(*) AS punch_count,
        EXTRACT(DOW FROM event_time::date) AS day_of_week,
        BOOL_OR(is_roving) AS is_roving
    FROM attendance_punches
    WHERE is_known_employee = TRUE
    GROUP BY pin, event_time::date
)
SELECT
    pin,
    employee_name,
    employee_id,
    designation,
    department,
    home_store,
    punch_store,
    other_stores,
    work_date,
    TO_CHAR(work_date, 'Dy') AS day_name,
    time_in,
    time_out,
    CASE WHEN punch_count > 1
         THEN ROUND(EXTRACT(EPOCH FROM (time_out - time_in)) / 3600.0, 2)
         ELSE NULL
    END AS hours_worked,
    punch_count,
    is_roving,
    CASE
        WHEN punch_count = 1 THEN 'MISSING PUNCH'
        WHEN day_of_week IN (0, 6) THEN 'REST DAY'
        ELSE 'PRESENT'
    END AS status
FROM daily_punches;

-- ============================================================================
-- View: v_attendance_summary (one row per employee — all-time summary)
-- [FIX-18] punch_store removed from GROUP BY, aggregated instead
-- ============================================================================

CREATE OR REPLACE VIEW v_attendance_summary AS
SELECT
    pin,
    employee_name,
    employee_id,
    designation,
    department,
    home_store,
    MIN(work_date) AS period_start,
    MAX(work_date) AS period_end,
    COUNT(*) FILTER (WHERE status IN ('PRESENT', 'REST DAY')) AS days_present,
    COUNT(*) FILTER (WHERE status = 'MISSING PUNCH') AS missing_punches,
    COUNT(*) FILTER (WHERE status = 'REST DAY') AS rest_day_punches,
    COALESCE(SUM(hours_worked), 0) AS total_hours,
    COUNT(DISTINCT punch_store) AS stores_worked,
    ARRAY_TO_STRING(ARRAY_AGG(DISTINCT punch_store ORDER BY punch_store), ', ') AS stores_list,
    BOOL_OR(is_roving) AS is_roving
FROM v_daily_time_record
GROUP BY pin, employee_name, employee_id, designation, department, home_store;

-- ============================================================================
-- View: v_store_compliance (store-level daily compliance)
-- ============================================================================

CREATE OR REPLACE VIEW v_store_compliance AS
SELECT
    punch_store AS store,
    work_date,
    COUNT(DISTINCT pin) AS employees_punched,
    COUNT(*) AS total_dtr_rows,
    COUNT(*) FILTER (WHERE status = 'MISSING PUNCH') AS missing_punch_count,
    COUNT(*) FILTER (WHERE status = 'REST DAY') AS rest_day_count,
    ROUND(
        COUNT(*) FILTER (WHERE status = 'PRESENT')::numeric /
        NULLIF(COUNT(*)::numeric, 0) * 100, 1
    ) AS compliance_pct
FROM v_daily_time_record
GROUP BY punch_store, work_date;

-- ============================================================================
-- View: v_ghost_punchers (unknown Bio IDs for audit)
-- [FIX-4]
-- ============================================================================

CREATE OR REPLACE VIEW v_ghost_punchers AS
SELECT
    pin,
    COUNT(*) AS punch_count,
    COUNT(DISTINCT device_sn) AS devices_used,
    ARRAY_AGG(DISTINCT store_name ORDER BY store_name) AS stores,
    MIN(event_time) AS first_seen,
    MAX(event_time) AS last_seen
FROM attendance_punches
WHERE is_known_employee = FALSE
GROUP BY pin
ORDER BY last_seen DESC;
