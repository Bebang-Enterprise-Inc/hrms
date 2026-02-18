-- ============================================================================
-- Migration: Fix confusing view aliases + add FoodPanda to daily views
-- Date: 2026-02-15
-- Why: v_system_daily_totals used `pos_gross_total` / `pos_net_total` aliases
--      which don't exist in source tables (pos_orders has `gross_sales`).
--      This caused scripts to guess wrong column names.
--      Also: FoodPanda orders were missing from all views.
-- Reference: docs/data/SUPABASE_SCHEMA_REFERENCE.md
-- ============================================================================


-- ────────────────────────────────────────────────────────────────────────────
-- 1. Fix v_system_daily_totals — rename misleading aliases
-- ────────────────────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS v_system_daily_totals CASCADE;

CREATE VIEW v_system_daily_totals AS
SELECT
    business_date,
    COUNT(*)                        AS store_count,
    SUM(total_orders)               AS total_orders,
    SUM(pos_orders)                 AS pos_order_count,
    SUM(web_orders)                 AS web_order_count,
    SUM(total_gross_sales)          AS total_gross_sales,
    SUM(total_net_sales)            AS total_net_sales,
    -- FIXED: renamed from pos_gross_total/pos_net_total to match source table naming
    SUM(pos_original_gross)         AS pos_original_gross_sales,
    SUM(pos_after_discount)         AS pos_gross_sales,
    SUM(web_gross)                  AS web_gross_sales,
    SUM(pos_discounts)              AS total_discounts,
    SUM(pos_vat)                    AS total_vat,
    ROUND(AVG(discount_rate_pct), 1) AS avg_discount_rate,
    COUNT(*) FILTER (WHERE data_sources = 'POS+Web') AS stores_with_web,
    COUNT(*) FILTER (WHERE data_sources = 'POS')     AS stores_pos_only
FROM store_daily_closing
GROUP BY business_date
ORDER BY business_date DESC;

GRANT SELECT ON v_system_daily_totals TO authenticated;


-- ────────────────────────────────────────────────────────────────────────────
-- 2. Create FoodPanda store name → location_id mapping table
--    (FoodPanda uses store_name, not location_id)
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS foodpanda_store_mapping (
    fp_store_name   TEXT PRIMARY KEY,
    location_id     INTEGER NOT NULL REFERENCES stores(location_id),
    store_name      TEXT NOT NULL,
    mapped_on       TIMESTAMPTZ DEFAULT NOW(),
    notes           TEXT
);

-- Populate from existing data (best-effort fuzzy match via stores table)
INSERT INTO foodpanda_store_mapping (fp_store_name, location_id, store_name)
SELECT DISTINCT
    COALESCE(fo.fp_restaurant_code, 'loc_' || fo.location_id::TEXT) AS fp_store_name,
    fo.location_id,
    s.store_name
FROM foodpanda_orders fo
JOIN stores s ON fo.location_id = s.location_id
WHERE fo.location_id IS NOT NULL
ON CONFLICT (fp_store_name) DO NOTHING;

GRANT SELECT ON foodpanda_store_mapping TO authenticated;


-- ────────────────────────────────────────────────────────────────────────────
-- 3. Create v_all_channel_daily — unified view across ALL 3 channels
--    This is what scripts should use for total sales reporting
-- ────────────────────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS v_all_channel_daily CASCADE;

CREATE VIEW v_all_channel_daily AS
SELECT
    business_date,

    -- POS
    COALESCE(pos.order_count, 0)     AS pos_orders,
    COALESCE(pos.gross_sales, 0)     AS pos_gross_sales,
    COALESCE(pos.net_sales, 0)       AS pos_net_sales,

    -- Web (bebang.ph)
    COALESCE(web.order_count, 0)     AS web_orders,
    COALESCE(web.gross_sales, 0)     AS web_gross_sales,
    COALESCE(web.net_sales, 0)       AS web_net_sales,

    -- FoodPanda
    COALESCE(fp.order_count, 0)      AS fp_orders,
    COALESCE(fp.gross_sales, 0)      AS fp_gross_sales,

    -- COMBINED (all 3 channels)
    COALESCE(pos.order_count, 0)
        + COALESCE(web.order_count, 0)
        + COALESCE(fp.order_count, 0)   AS total_orders,

    COALESCE(pos.gross_sales, 0)
        + COALESCE(web.gross_sales, 0)
        + COALESCE(fp.gross_sales, 0)   AS total_gross_sales,

    -- Data completeness flags
    CASE WHEN pos.order_count > 0 THEN 1 ELSE 0 END
        + CASE WHEN web.order_count > 0 THEN 1 ELSE 0 END
        + CASE WHEN fp.order_count > 0 THEN 1 ELSE 0 END  AS channel_count,

    CONCAT_WS('+',
        CASE WHEN pos.order_count > 0 THEN 'POS' END,
        CASE WHEN web.order_count > 0 THEN 'Web' END,
        CASE WHEN fp.order_count > 0 THEN 'FP' END
    ) AS data_sources

FROM (
    -- Generate date spine from all 3 tables
    SELECT DISTINCT business_date FROM pos_orders WHERE payment_status = 'PAID'
    UNION
    SELECT DISTINCT business_date FROM web_orders
    UNION
    SELECT DISTINCT business_date FROM foodpanda_orders WHERE LOWER(order_status) = 'delivered'
) dates

LEFT JOIN (
    SELECT business_date,
           COUNT(*)           AS order_count,
           SUM(gross_sales)   AS gross_sales,
           SUM(net_sales)     AS net_sales
    FROM pos_orders
    WHERE payment_status = 'PAID'
    GROUP BY business_date
) pos USING (business_date)

LEFT JOIN (
    SELECT business_date,
           COUNT(*)           AS order_count,
           SUM(gross_sales)   AS gross_sales,
           SUM(net_sales)     AS net_sales
    FROM web_orders
    GROUP BY business_date
) web USING (business_date)

LEFT JOIN (
    SELECT business_date,
           COUNT(*)           AS order_count,
           SUM(subtotal)      AS gross_sales  -- NOTE: subtotal → gross_sales normalization
    FROM foodpanda_orders
    WHERE LOWER(order_status) = 'delivered'
    GROUP BY business_date
) fp USING (business_date)

ORDER BY business_date DESC;

GRANT SELECT ON v_all_channel_daily TO authenticated;


-- ────────────────────────────────────────────────────────────────────────────
-- 4. Create v_ops_weekly — Weekly aggregation using Mon-Sun ops weeks
-- ────────────────────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS v_ops_weekly CASCADE;

CREATE VIEW v_ops_weekly AS
SELECT
    DATE_TRUNC('week', business_date)::DATE  AS week_start,
    (DATE_TRUNC('week', business_date) + INTERVAL '6 days')::DATE AS week_end,

    SUM(pos_orders)          AS pos_orders,
    SUM(pos_gross_sales)     AS pos_gross_sales,
    SUM(web_orders)          AS web_orders,
    SUM(web_gross_sales)     AS web_gross_sales,
    SUM(fp_orders)           AS fp_orders,
    SUM(fp_gross_sales)      AS fp_gross_sales,

    SUM(total_orders)        AS total_orders,
    SUM(total_gross_sales)   AS total_gross_sales,

    COUNT(*)                 AS days_with_data,
    MAX(channel_count)       AS max_channels

FROM v_all_channel_daily
GROUP BY DATE_TRUNC('week', business_date)
ORDER BY week_start DESC;

GRANT SELECT ON v_ops_weekly TO authenticated;
