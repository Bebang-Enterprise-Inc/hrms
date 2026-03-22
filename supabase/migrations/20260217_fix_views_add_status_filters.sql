-- ============================================================================
-- Migration: Fix web order status filters in all views
-- Date: 2026-02-17
-- Why: v_all_channel_daily and store_daily_closing include ALL web orders
--      (Cancelled, Pending, etc.) in sales totals. Dashboard only counts
--      Completed orders. Also: gross_sales now stores subtotal (not amount),
--      so views should use gross_sales directly.
-- Bugs fixed:
--   1. v_all_channel_daily web subquery: NO status filter → add Completed only
--   2. store_daily_closing web subquery: NO status filter → add Completed only
--   3. v_all_channel_daily date spine: included non-Completed web order dates
-- Reference: memory/supabase-schema.md
-- ============================================================================


-- ────────────────────────────────────────────────────────────────────────────
-- 1. Fix v_all_channel_daily — add status filter to web subquery
-- ────────────────────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS v_ops_weekly CASCADE;
DROP VIEW IF EXISTS v_all_channel_daily CASCADE;

CREATE VIEW v_all_channel_daily AS
SELECT
    business_date,

    -- POS
    COALESCE(pos.order_count, 0)     AS pos_orders,
    COALESCE(pos.gross_sales, 0)     AS pos_gross_sales,
    COALESCE(pos.net_sales, 0)       AS pos_net_sales,

    -- Web (bebang.ph) — FIXED: only Completed orders
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
    -- Generate date spine from all 3 tables (FIXED: web date spine also filtered)
    SELECT DISTINCT business_date FROM pos_orders WHERE payment_status = 'PAID'
    UNION
    SELECT DISTINCT business_date FROM web_orders WHERE order_status_raw = 'Completed'
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
    -- FIXED: Filter to Completed orders only (matches Superadmin dashboard)
    SELECT business_date,
           COUNT(*)           AS order_count,
           SUM(gross_sales)   AS gross_sales,
           SUM(net_sales)     AS net_sales
    FROM web_orders
    WHERE order_status_raw = 'Completed'
    GROUP BY business_date
) web USING (business_date)

LEFT JOIN (
    SELECT business_date,
           COUNT(*)           AS order_count,
           SUM(subtotal)      AS gross_sales
    FROM foodpanda_orders
    WHERE LOWER(order_status) = 'delivered'
    GROUP BY business_date
) fp USING (business_date)

ORDER BY business_date DESC;

GRANT SELECT ON v_all_channel_daily TO authenticated;


-- ────────────────────────────────────────────────────────────────────────────
-- 2. Recreate v_ops_weekly (depends on v_all_channel_daily)
-- ────────────────────────────────────────────────────────────────────────────

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


-- ────────────────────────────────────────────────────────────────────────────
-- 3. Fix store_daily_closing — add status filter to web subquery
-- ────────────────────────────────────────────────────────────────────────────

DROP VIEW IF EXISTS v_system_daily_totals CASCADE;
DROP MATERIALIZED VIEW IF EXISTS store_daily_closing CASCADE;

CREATE MATERIALIZED VIEW store_daily_closing AS
SELECT
    s.location_id,
    s.store_name,
    s.legal_entity,
    s.store_type,
    combined.business_date,

    -- Order counts
    combined.pos_orders,
    combined.web_orders,
    combined.pos_orders + combined.web_orders           AS total_orders,

    -- POS breakdown
    combined.pos_original_gross,
    combined.pos_after_discount,
    combined.pos_net_of_vat,
    combined.pos_discounts,
    combined.pos_vat,
    combined.pos_vat_exempt,

    -- Web/Delivery breakdown
    combined.web_gross,
    combined.web_delivery_fee,

    -- COMBINED METRICS
    combined.pos_original_gross + combined.web_gross     AS total_gross_sales,
    combined.pos_after_discount + combined.web_gross     AS total_net_sales,

    -- Discount rate
    CASE WHEN combined.pos_original_gross > 0
         THEN ROUND(combined.pos_discounts / combined.pos_original_gross * 100, 1)
         ELSE 0
    END                                                 AS discount_rate_pct,

    -- Data completeness flag
    CASE WHEN combined.web_orders > 0 THEN 'POS+Web' ELSE 'POS' END AS data_sources

FROM stores s
JOIN (
    SELECT
        location_id,
        business_date,
        SUM(CASE WHEN source = 'pos' THEN order_count ELSE 0 END) AS pos_orders,
        SUM(CASE WHEN source = 'web' THEN order_count ELSE 0 END) AS web_orders,
        SUM(CASE WHEN source = 'pos' THEN orig_gross ELSE 0 END)  AS pos_original_gross,
        SUM(CASE WHEN source = 'pos' THEN after_disc ELSE 0 END)  AS pos_after_discount,
        SUM(CASE WHEN source = 'pos' THEN net_vat ELSE 0 END)     AS pos_net_of_vat,
        SUM(CASE WHEN source = 'pos' THEN discounts ELSE 0 END)   AS pos_discounts,
        SUM(CASE WHEN source = 'pos' THEN vat ELSE 0 END)         AS pos_vat,
        SUM(CASE WHEN source = 'pos' THEN vat_exempt ELSE 0 END)  AS pos_vat_exempt,
        SUM(CASE WHEN source = 'web' THEN after_disc ELSE 0 END)  AS web_gross,
        SUM(CASE WHEN source = 'web' THEN del_fee ELSE 0 END)     AS web_delivery_fee
    FROM (
        -- POS orders
        SELECT
            location_id,
            business_date,
            'pos'                            AS source,
            COUNT(*)                         AS order_count,
            SUM(original_gross_sales)        AS orig_gross,
            SUM(gross_sales)                 AS after_disc,
            SUM(net_sales)                   AS net_vat,
            SUM(total_discounts)             AS discounts,
            SUM(vat_amount)                  AS vat,
            SUM(vat_exempt_sales)            AS vat_exempt,
            0::NUMERIC                       AS del_fee
        FROM pos_orders
        WHERE payment_status = 'PAID'
        GROUP BY location_id, business_date

        UNION ALL

        -- Web/delivery orders — FIXED: only Completed orders
        SELECT
            location_id,
            business_date,
            'web'                            AS source,
            COUNT(*),
            SUM(original_gross_sales),
            SUM(gross_sales),
            SUM(net_sales),
            SUM(total_discounts),
            SUM(vat_amount),
            SUM(vat_exempt_sales),
            SUM(COALESCE(delivery_fee, 0))
        FROM web_orders
        WHERE order_status_raw = 'Completed'
        GROUP BY location_id, business_date
    ) all_orders
    GROUP BY location_id, business_date
) combined ON s.location_id = combined.location_id;

CREATE UNIQUE INDEX idx_store_daily_closing_pk
    ON store_daily_closing (location_id, business_date);

CREATE INDEX idx_store_daily_closing_date
    ON store_daily_closing (business_date DESC);

CREATE INDEX idx_store_daily_closing_store_date
    ON store_daily_closing (store_name, business_date DESC);


-- ────────────────────────────────────────────────────────────────────────────
-- 4. Recreate v_system_daily_totals (depends on store_daily_closing)
-- ────────────────────────────────────────────────────────────────────────────

CREATE VIEW v_system_daily_totals AS
SELECT
    business_date,
    COUNT(*)                        AS store_count,
    SUM(total_orders)               AS total_orders,
    SUM(pos_orders)                 AS pos_order_count,
    SUM(web_orders)                 AS web_order_count,
    SUM(total_gross_sales)          AS total_gross_sales,
    SUM(total_net_sales)            AS total_net_sales,
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

GRANT SELECT ON store_daily_closing TO authenticated;
GRANT SELECT ON v_system_daily_totals TO authenticated;


-- ────────────────────────────────────────────────────────────────────────────
-- 5. Refresh materialized views
-- ────────────────────────────────────────────────────────────────────────────

REFRESH MATERIALIZED VIEW store_daily_closing;

-- store_daily_report also depends on store_daily_closing — refresh it too
REFRESH MATERIALIZED VIEW CONCURRENTLY store_daily_report;
