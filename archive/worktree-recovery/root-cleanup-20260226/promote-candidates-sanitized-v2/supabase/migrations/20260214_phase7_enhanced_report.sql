-- Phase 7: Enhanced Daily Report
-- Date: 2026-02-14
-- Purpose: FoodPanda integration, weather correlation, rolling averages, week-on-week comparison
-- Dependencies: store_daily_closing materialized view (20260214_store_daily_closing.sql)

-- ============================================================================
-- 1. FoodPanda Store Mapping
-- ============================================================================

CREATE TABLE IF NOT EXISTS fp_store_mapping (
    fp_restaurant_name TEXT PRIMARY KEY,
    fp_restaurant_code TEXT NOT NULL,
    website_slug TEXT,
    bei_store_code TEXT NOT NULL,
    bei_store_name TEXT NOT NULL,
    location_id INTEGER REFERENCES stores(location_id)
);

-- ============================================================================
-- 2. FoodPanda Orders
-- ============================================================================

CREATE TABLE IF NOT EXISTS foodpanda_orders (
    order_id TEXT PRIMARY KEY,
    fp_restaurant_code TEXT NOT NULL,
    location_id INTEGER REFERENCES stores(location_id),
    delivery_type TEXT,
    payment_type TEXT,
    payment_method TEXT,
    is_pro_order BOOLEAN DEFAULT FALSE,
    order_status TEXT NOT NULL,
    order_received_at TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT,
    cancellation_owner TEXT,
    has_complaint BOOLEAN DEFAULT FALSE,
    subtotal NUMERIC(12,2),
    packaging_charges NUMERIC(12,2),
    tax_charge NUMERIC(12,2),
    business_date DATE,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fp_orders_date ON foodpanda_orders(business_date);
CREATE INDEX IF NOT EXISTS idx_fp_orders_location ON foodpanda_orders(location_id, business_date);

-- ============================================================================
-- 3. Daily Weather
-- ============================================================================

CREATE TABLE IF NOT EXISTS daily_weather (
    location_id INTEGER REFERENCES stores(location_id),
    business_date DATE NOT NULL,
    avg_temperature NUMERIC(4,1),
    max_temperature NUMERIC(4,1),
    min_temperature NUMERIC(4,1),
    avg_humidity INTEGER,
    total_precipitation NUMERIC(6,1),
    weather_description TEXT,
    weather_code INTEGER,
    avg_wind_speed NUMERIC(5,1),
    is_rainy BOOLEAN DEFAULT FALSE,
    rain_hours INTEGER DEFAULT 0,
    business_impact TEXT,
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (location_id, business_date)
);

-- ============================================================================
-- 4. Enhanced Daily Report (Materialized View)
-- ============================================================================

CREATE MATERIALIZED VIEW IF NOT EXISTS store_daily_report AS
WITH
base AS (
    SELECT * FROM store_daily_closing
),
fp AS (
    SELECT
        location_id,
        business_date,
        COUNT(*) FILTER (WHERE order_status NOT IN ('Cancelled')) AS fp_orders,
        COALESCE(SUM(subtotal) FILTER (WHERE order_status NOT IN ('Cancelled')), 0) AS fp_gross,
        COUNT(*) FILTER (WHERE order_status = 'Cancelled') AS fp_cancelled_orders
    FROM foodpanda_orders
    GROUP BY location_id, business_date
),
fp_available AS (
    SELECT DISTINCT location_id, business_date, TRUE AS has_fp_data
    FROM foodpanda_orders
),
weather AS (
    SELECT * FROM daily_weather
),
rolling AS (
    SELECT
        location_id,
        business_date,
        AVG(total_gross_sales) OVER (
            PARTITION BY location_id ORDER BY business_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS avg_gross_7d,
        AVG(total_gross_sales) OVER (
            PARTITION BY location_id ORDER BY business_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS avg_gross_30d,
        AVG(total_orders) OVER (
            PARTITION BY location_id ORDER BY business_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS avg_orders_7d,
        AVG(total_orders) OVER (
            PARTITION BY location_id ORDER BY business_date
            ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
        ) AS avg_orders_30d
    FROM store_daily_closing
),
wow AS (
    SELECT
        a.location_id,
        a.business_date,
        b.total_gross_sales AS last_week_gross,
        b.total_orders AS last_week_orders,
        b.total_net_sales AS last_week_net,
        CASE WHEN b.total_gross_sales > 0
            THEN ROUND(((a.total_gross_sales - b.total_gross_sales) / b.total_gross_sales * 100)::NUMERIC, 1)
            ELSE NULL
        END AS wow_gross_pct,
        CASE WHEN b.total_orders > 0
            THEN ROUND(((a.total_orders - b.total_orders)::NUMERIC / b.total_orders * 100), 1)
            ELSE NULL
        END AS wow_orders_pct
    FROM store_daily_closing a
    LEFT JOIN store_daily_closing b
        ON a.location_id = b.location_id
        AND b.business_date = a.business_date - INTERVAL '7 days'
)
SELECT
    -- Identity
    b.location_id,
    b.store_name,
    b.business_date,

    -- Core sales (POS + Web)
    b.total_gross_sales,
    b.total_net_sales,
    b.total_orders,
    b.pos_original_gross AS pos_gross,
    b.pos_orders,
    b.web_gross,
    b.web_orders,
    b.discount_rate_pct,

    -- FoodPanda
    COALESCE(fp.fp_gross, 0) AS fp_gross,
    COALESCE(fp.fp_orders, 0) AS fp_orders,
    COALESCE(fp.fp_cancelled_orders, 0) AS fp_cancelled_orders,
    CASE
        WHEN fpa.has_fp_data IS TRUE THEN 'available'
        WHEN b.business_date >= CURRENT_DATE - INTERVAL '2 days' THEN 'pending'
        ELSE 'none'
    END AS fp_data_status,

    -- Grand total (POS + Web + FoodPanda)
    b.total_gross_sales + COALESCE(fp.fp_gross, 0) AS grand_total_gross,
    b.total_orders + COALESCE(fp.fp_orders, 0) AS grand_total_orders,

    -- Average ticket size
    CASE WHEN b.total_orders > 0
        THEN ROUND((b.total_net_sales / b.total_orders)::NUMERIC, 2)
        ELSE 0
    END AS avg_ticket_size,

    -- Channel mix (% of grand total)
    CASE WHEN (b.total_gross_sales + COALESCE(fp.fp_gross, 0)) > 0
        THEN ROUND((b.pos_original_gross / (b.total_gross_sales + COALESCE(fp.fp_gross, 0)) * 100)::NUMERIC, 1)
        ELSE 0
    END AS pos_pct,
    CASE WHEN (b.total_gross_sales + COALESCE(fp.fp_gross, 0)) > 0
        THEN ROUND((b.web_gross / (b.total_gross_sales + COALESCE(fp.fp_gross, 0)) * 100)::NUMERIC, 1)
        ELSE 0
    END AS web_pct,
    CASE WHEN (b.total_gross_sales + COALESCE(fp.fp_gross, 0)) > 0
        THEN ROUND((COALESCE(fp.fp_gross, 0) / (b.total_gross_sales + COALESCE(fp.fp_gross, 0)) * 100)::NUMERIC, 1)
        ELSE 0
    END AS fp_pct,

    -- Rolling averages
    ROUND(r.avg_gross_7d::NUMERIC, 2) AS avg_gross_7d,
    ROUND(r.avg_gross_30d::NUMERIC, 2) AS avg_gross_30d,
    ROUND(r.avg_orders_7d::NUMERIC, 1) AS avg_orders_7d,
    ROUND(r.avg_orders_30d::NUMERIC, 1) AS avg_orders_30d,

    -- Trend: today vs 7d average
    CASE WHEN r.avg_gross_7d > 0
        THEN ROUND(((b.total_gross_sales - r.avg_gross_7d) / r.avg_gross_7d * 100)::NUMERIC, 1)
        ELSE NULL
    END AS vs_7d_avg_pct,

    -- Trend: today vs 30d average
    CASE WHEN r.avg_gross_30d > 0
        THEN ROUND(((b.total_gross_sales - r.avg_gross_30d) / r.avg_gross_30d * 100)::NUMERIC, 1)
        ELSE NULL
    END AS vs_30d_avg_pct,

    -- Week-on-week
    wow.last_week_gross,
    wow.last_week_orders,
    wow.wow_gross_pct,
    wow.wow_orders_pct,

    -- Weather
    w.avg_temperature,
    w.max_temperature,
    w.total_precipitation,
    w.weather_description,
    w.is_rainy,
    w.rain_hours,
    w.business_impact AS weather_impact,

    -- Data completeness
    b.data_sources,
    CASE
        WHEN fpa.has_fp_data IS TRUE THEN b.data_sources || '+FP'
        ELSE b.data_sources
    END AS full_data_sources

FROM base b
LEFT JOIN fp ON b.location_id = fp.location_id AND b.business_date = fp.business_date
LEFT JOIN fp_available fpa ON b.location_id = fpa.location_id AND b.business_date = fpa.business_date
LEFT JOIN weather w ON b.location_id = w.location_id AND b.business_date = w.business_date
LEFT JOIN rolling r ON b.location_id = r.location_id AND b.business_date = r.business_date
LEFT JOIN wow ON b.location_id = wow.location_id AND b.business_date = wow.business_date;

CREATE UNIQUE INDEX IF NOT EXISTS idx_sdr_pk ON store_daily_report(location_id, business_date);
CREATE INDEX IF NOT EXISTS idx_sdr_date ON store_daily_report(business_date);
CREATE INDEX IF NOT EXISTS idx_sdr_store ON store_daily_report(store_name, business_date);

-- ============================================================================
-- 5. RPC Function: get_daily_report
-- ============================================================================

CREATE OR REPLACE FUNCTION get_daily_report(p_date DATE DEFAULT CURRENT_DATE - 1)
RETURNS JSON AS $$
    SELECT json_build_object(
        'report_date', p_date,
        'generated_at', NOW(),
        'system_totals', (
            SELECT json_build_object(
                'total_stores', COUNT(*),
                'grand_total_gross', SUM(grand_total_gross),
                'grand_total_orders', SUM(grand_total_orders),
                'avg_ticket_size', ROUND(AVG(avg_ticket_size)::NUMERIC, 2),
                'fp_pending_count', COUNT(*) FILTER (WHERE fp_data_status = 'pending'),
                'rainy_stores', COUNT(*) FILTER (WHERE is_rainy = TRUE)
            )
            FROM store_daily_report
            WHERE business_date = p_date
        ),
        'stores', (
            SELECT json_agg(row_to_json(s) ORDER BY s.grand_total_gross DESC)
            FROM store_daily_report s
            WHERE s.business_date = p_date
        )
    );
$$ LANGUAGE SQL STABLE;

-- ============================================================================
-- 6. pg_cron: Refresh store_daily_report at 16:15 UTC (00:15 PHT)
-- ============================================================================

SELECT cron.schedule(
    'refresh-store-daily-report',
    '15 16 * * *',
    'REFRESH MATERIALIZED VIEW CONCURRENTLY store_daily_report'
);
