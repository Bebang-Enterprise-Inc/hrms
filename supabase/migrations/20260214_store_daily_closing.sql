-- ============================================================================
-- Migration: store_daily_closing materialized view
-- Date: 2026-02-14
-- Purpose: Single view that matches store closing report terminology
--          One row per store per day with POS + Web combined
-- ============================================================================

-- Drop if exists (for idempotent re-runs)
DROP MATERIALIZED VIEW IF EXISTS store_daily_closing CASCADE;

-- ============================================================================
-- MATERIALIZED VIEW: store_daily_closing
--
-- Terminology mapping (WHY these column names):
--   Store "Total Gross Sales"  = pos_original_gross + web_gross = total_gross_sales
--   Store "Total Net Sales"    = pos_after_discount + web_gross = total_net_sales
--   Store "Total Delivery"     = web_gross (Website only; FoodPanda/GrabFood TBD)
--
-- Column naming convention:
--   pos_*  = POS register data only
--   web_*  = Online/delivery data only
--   total_* = POS + Web combined (matches store closing reports)
-- ============================================================================

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

    -- POS breakdown (register sales only)
    combined.pos_original_gross,                         -- Menu price before any discount
    combined.pos_after_discount,                         -- After discount, VAT-inclusive
    combined.pos_net_of_vat,                             -- VAT-exclusive (for BIR)
    combined.pos_discounts,
    combined.pos_vat,
    combined.pos_vat_exempt,

    -- Web/Delivery breakdown (online orders)
    combined.web_gross,                                  -- Online order value
    combined.web_delivery_fee,

    -- ═══════════════════════════════════════════════════════════
    -- COMBINED METRICS — these match store closing reports
    -- ═══════════════════════════════════════════════════════════
    combined.pos_original_gross + combined.web_gross     AS total_gross_sales,
    combined.pos_after_discount + combined.web_gross     AS total_net_sales,

    -- Discount rate (POS only — web orders rarely have discounts)
    CASE WHEN combined.pos_original_gross > 0
         THEN ROUND(combined.pos_discounts / combined.pos_original_gross * 100, 1)
         ELSE 0
    END                                                 AS discount_rate_pct,

    -- Data completeness flag
    -- 'POS+Web' = both channels synced
    -- 'POS'     = no web orders (may be missing or store has no delivery)
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

        -- Web/delivery orders
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
        GROUP BY location_id, business_date
    ) all_orders
    GROUP BY location_id, business_date
) combined ON s.location_id = combined.location_id;

-- Required for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX idx_store_daily_closing_pk
    ON store_daily_closing (location_id, business_date);

-- Index for common query patterns
CREATE INDEX idx_store_daily_closing_date
    ON store_daily_closing (business_date DESC);

CREATE INDEX idx_store_daily_closing_store_date
    ON store_daily_closing (store_name, business_date DESC);


-- ============================================================================
-- REGULAR VIEW: v_system_daily_totals
-- System-wide daily summary (all stores combined)
-- ============================================================================

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
    SUM(pos_original_gross)         AS pos_gross_total,
    SUM(pos_after_discount)         AS pos_net_total,
    SUM(web_gross)                  AS web_total,
    SUM(pos_discounts)              AS total_discounts,
    SUM(pos_vat)                    AS total_vat,
    ROUND(AVG(discount_rate_pct), 1) AS avg_discount_rate,
    COUNT(*) FILTER (WHERE data_sources = 'POS+Web') AS stores_with_web,
    COUNT(*) FILTER (WHERE data_sources = 'POS')     AS stores_pos_only
FROM store_daily_closing
GROUP BY business_date
ORDER BY business_date DESC;


-- ============================================================================
-- GRANT access via PostgREST (Supabase REST API)
-- ============================================================================

GRANT SELECT ON store_daily_closing TO authenticated;
GRANT SELECT ON v_system_daily_totals TO authenticated;


-- ============================================================================
-- Initial refresh
-- ============================================================================

REFRESH MATERIALIZED VIEW store_daily_closing;
